"""Rights append execution is hosted-only, preserving and fail-closed."""

# Fake transport signatures implement the production protocol.
# ruff: file-ignore[unused-method-argument]

import json
from dataclasses import replace
from pathlib import Path

import pytest

from global_medicines_atlas.federation_metadata_append import ObjectDigest
from global_medicines_atlas.federation_metadata_hosted import PublicSnapshot
from global_medicines_atlas.mbs_utilisation_lifecycle_append import (
    execute_lifecycle_append,
    validate_lifecycle_append,
)
from global_medicines_atlas.mbs_utilisation_rights_append import (
    validate_rights_append,
)
from global_medicines_atlas.mbs_utilisation_rights_hosted import (
    execute_rights_append,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "quality/qualifications"
COMMIT = "a" * 40
URL = "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-1"


class FakeHub:
    def __init__(self, validated):
        self.objects = tuple(
            ObjectDigest(path, 1, sha)
            for path, sha in validated.required_objects
        )
        self.parent = validated.parent_revision
        self.plan = None
        self.calls = []
        self.tamper = False
        self.wrong_payload = False
        self.private = False
        self.drift = False

    def snapshot(self, dataset, revision):
        self.calls.append("snapshot")
        objects = self.objects
        if self.plan:
            objects += (self.plan.addition,)
            if self.tamper:
                objects = objects[1:]
        return PublicSnapshot(
            revision=revision,
            private=self.private,
            gated=False,
            objects=objects,
        )

    def head(self, dataset):
        self.calls.append("head")
        return "b" * 40 if self.drift else self.parent

    def append(self, plan):
        self.calls.append("append")
        self.plan = plan
        return "f" * 40

    def metadata(self, dataset, revision, path):
        self.calls.append("metadata")
        return b"altered" if self.wrong_payload else self.plan.payload


@pytest.fixture
def inputs(monkeypatch):
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": COMMIT,
        "GITHUB_RUN_ID": "123",
    }.items():
        monkeypatch.setenv(key, value)
    contract = json.loads(
        (
            BASE
            / "australian-mbs-utilisation-rights-append-contract-20261004.json"
        ).read_bytes()
    )
    payload = (ROOT / contract["addition"]["local_path"]).read_bytes()
    decision = (ROOT / contract["rights_decision"]["path"]).read_bytes()
    metadata = json.loads(payload)
    joins = (ROOT / metadata["receipt_join_audit"]["path"]).read_bytes()
    hub = FakeHub(validate_rights_append(contract, payload, decision, joins))
    return contract, payload, decision, joins, hub


def run(inputs, persist=None, main=None):
    contract, payload, decision, joins, hub = inputs
    records = []

    def save(document):
        hub.calls.append(document["status"])
        records.append(document)
        return URL

    result = execute_rights_append(
        contract,
        payload,
        decision,
        joins,
        exact_commit=COMMIT,
        current_main=main or (lambda: COMMIT),
        hub=hub,
        persist=persist or save,
    )
    return result, records


def test_ordered_preserving_append(inputs):
    result, records = run(inputs)
    hub = inputs[-1]
    assert hub.calls == [
        "snapshot",
        "head",
        "intent",
        "head",
        "append",
        "cas_acknowledged",
        "snapshot",
        "metadata",
        "anonymously_verified",
    ]
    assert [row["status"] for row in records] == [
        "intent",
        "cas_acknowledged",
        "anonymously_verified",
    ]
    assert result["revision"] == "f" * 40
    assert len(result["observed"]) == 30
    assert result["receipt_url"] == URL
    assert hub.plan.baseline == tuple(
        sorted(hub.objects, key=lambda row: row.path)
    )


def test_local_execution_has_no_side_effects(inputs, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS")
    with pytest.raises(ValueError, match="Actions"):
        run(inputs)
    assert inputs[-1].calls == []


@pytest.mark.parametrize(
    "fault",
    [
        "drift",
        "private",
        "missing",
        "duplicate",
        "existing",
        "wrong_revision",
        "big_receipt",
        "main",
    ],
)
def test_prewrite_failures_never_append(inputs, fault, monkeypatch):
    hub = inputs[-1]
    if fault == "drift":
        hub.drift = True
    elif fault == "private":
        hub.private = True
    elif fault == "missing":
        hub.objects = hub.objects[1:]
    elif fault == "duplicate":
        hub.objects += (hub.objects[0],)
    elif fault == "existing":
        contract, payload, decision, joins, _ = inputs
        hub.objects += (
            validate_rights_append(contract, payload, decision, joins).addition,
        )
    elif fault == "wrong_revision":
        snapshot = hub.snapshot
        monkeypatch.setattr(
            hub,
            "snapshot",
            lambda dataset, revision: replace(
                snapshot(dataset, revision), revision="c" * 40
            ),
        )
    elif fault == "big_receipt":
        hub.objects += tuple(
            ObjectDigest(f"metadata/{'x' * 3000}{index}.json", 1, "0" * 64)
            for index in range(12)
        )
    with pytest.raises(
        ValueError, match=r"head|snapshot|baseline|already|receipt|main"
    ):
        run(inputs, main=(lambda: "b" * 40) if fault == "main" else None)
    assert "append" not in hub.calls


@pytest.mark.parametrize(
    "fault",
    [
        "tamper",
        "wrong_payload",
        "private_after",
        "bad_revision",
        "same_revision",
    ],
)
def test_postwrite_failures_do_not_report_success(inputs, fault, monkeypatch):
    hub = inputs[-1]
    if fault == "tamper":
        hub.tamper = True
    elif fault == "wrong_payload":
        hub.wrong_payload = True
    elif fault == "private_after":
        snapshot = hub.snapshot
        monkeypatch.setattr(
            hub,
            "snapshot",
            lambda dataset, revision: replace(
                snapshot(dataset, revision), private=hub.plan is not None
            ),
        )
    else:
        append = hub.append

        def invalid(plan):
            append(plan)
            return "invalid" if fault == "bad_revision" else hub.parent

        monkeypatch.setattr(hub, "append", invalid)
    with pytest.raises(
        ValueError, match=r"inventory|metadata|snapshot|revision"
    ):
        run(inputs)
    assert hub.calls.count("append") == 1
    assert "anonymously_verified" not in hub.calls


@pytest.mark.parametrize(
    "stage", ["intent", "cas_acknowledged", "anonymously_verified"]
)
def test_durable_receipt_failure_stops_transaction(inputs, stage):
    seen = []

    def persist(document):
        seen.append(document["status"])
        if document["status"] == stage:
            raise RuntimeError("durable store unavailable")
        return URL

    with pytest.raises(RuntimeError, match="durable store"):
        run(inputs, persist=persist)
    assert seen[-1] == stage
    assert inputs[-1].calls.count("append") == (stage != "intent")


def test_drift_after_durable_intent_never_appends(inputs):
    def persist(_document):
        inputs[-1].drift = True
        return URL

    with pytest.raises(ValueError, match="after intent"):
        run(inputs, persist=persist)
    assert "append" not in inputs[-1].calls


def test_invalid_receipt_url_never_appends(inputs):
    with pytest.raises(ValueError, match="receipt URL"):
        run(inputs, persist=lambda _document: "https://example.org/untrusted")
    assert "append" not in inputs[-1].calls


def test_invalid_contract_is_rejected_before_transport_use(inputs):
    inputs[0]["dataset"] = "unapproved/dataset"
    with pytest.raises(ValueError, match="approved scope"):
        run(inputs)
    assert inputs[-1].calls == []


@pytest.fixture
def lifecycle_inputs(inputs):
    del inputs  # Reuse the hosted environment fixture without transport calls.
    contract = json.loads(
        (
            BASE
            / "australian-mbs-utilisation-lifecycle-append-contract-20261004.json"
        ).read_bytes()
    )
    payload = (ROOT / contract["addition"]["local_path"]).read_bytes()
    baseline = (
        ROOT / contract["baseline_verification_receipt"]["path"]
    ).read_bytes()
    validated = validate_lifecycle_append(contract, payload, baseline)
    hub = FakeHub(validated)
    hub.objects = validated.expected_baseline
    return contract, payload, baseline, hub


def test_lifecycle_publication_uses_preserving_receipt_protocol(
    lifecycle_inputs,
):
    contract, payload, baseline, hub = lifecycle_inputs
    receipts = []

    def save(document):
        receipts.append(document)
        return URL

    result = execute_lifecycle_append(
        contract,
        payload,
        baseline,
        exact_commit=COMMIT,
        current_main=lambda: COMMIT,
        hub=hub,
        persist=save,
    )
    assert (
        result["schema_id"]
        == "global-medicines-atlas.mbs-utilisation-lifecycle-append"
    )
    assert len(result["observed"]) == 32
    assert result["receipt_url"] == URL
    assert [r["status"] for r in receipts] == [
        "intent",
        "cas_acknowledged",
        "anonymously_verified",
    ]
    assert hub.plan.payload == payload


@pytest.mark.parametrize("changed", ["contract", "payload", "baseline"])
def test_lifecycle_tampering_fails_before_transport(lifecycle_inputs, changed):
    contract, payload, baseline, hub = lifecycle_inputs
    if changed == "contract":
        contract["execution_controls"]["historical_overwrite_allowed"] = True
    elif changed == "payload":
        payload += b" "
    else:
        baseline += b" "
    with pytest.raises(ValueError, match="reviewed"):
        execute_lifecycle_append(
            contract,
            payload,
            baseline,
            exact_commit=COMMIT,
            current_main=lambda: COMMIT,
            hub=hub,
            persist=lambda _: URL,
        )
    assert hub.calls == []


def test_lifecycle_local_execution_has_no_side_effects(
    lifecycle_inputs, monkeypatch
):
    monkeypatch.delenv("GITHUB_ACTIONS")
    contract, payload, baseline, hub = lifecycle_inputs
    with pytest.raises(ValueError, match="Actions"):
        execute_lifecycle_append(
            contract,
            payload,
            baseline,
            exact_commit=COMMIT,
            current_main=lambda: COMMIT,
            hub=hub,
            persist=lambda _: URL,
        )
    assert hub.calls == []


@pytest.mark.parametrize(
    "failure", ["size", "extra", "private", "drift", "tamper", "wrong_payload"]
)
def test_lifecycle_transport_failures_do_not_verify(lifecycle_inputs, failure):
    contract, payload, baseline, hub = lifecycle_inputs
    receipts = []
    if failure == "size":
        hub.objects = (replace(hub.objects[0], byte_count=2), *hub.objects[1:])
    elif failure == "extra":
        hub.objects += (ObjectDigest("metadata/extra.json", 1, "0" * 64),)
    else:
        setattr(hub, failure, True)

    def save(document):
        receipts.append(document)
        return URL

    with pytest.raises(
        ValueError, match=r"baseline|snapshot|head|inventory|metadata"
    ):
        execute_lifecycle_append(
            contract,
            payload,
            baseline,
            exact_commit=COMMIT,
            current_main=lambda: COMMIT,
            hub=hub,
            persist=save,
        )
    assert "anonymously_verified" not in [r["status"] for r in receipts]
    if failure in {"size", "extra", "private", "drift"}:
        assert hub.plan is None
