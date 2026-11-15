"""Exact July raw v4 qualification remains bounded and fail closed."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_mbs_august_frozen_v4 as august
import scripts.qualify_mbs_july_frozen_v4 as qualification

from global_medicines_atlas.federation_consumer import bind_consumer_contract
from global_medicines_atlas.federation_identity import AdmissionRecord
from global_medicines_atlas.federation_reader import FederatedReader


def _hosted(monkeypatch: pytest.MonkeyPatch, commit: str) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", qualification.REPO)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_SHA", commit)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")


def test_candidate_uses_existing_exact_source_and_preserves_recovery_limits() -> (
    None
):
    raw, trusted = qualification.candidate()
    document = json.loads(raw)
    assert raw == (qualification.ROOT / qualification.OUTPUT).read_bytes()
    assert trusted.path == qualification.lineage.JULY
    assert trusted.sha256 == document["location"]["sha256"]
    assert trusted.schema_era == "2025-07-version-3"
    assert trusted.comparison_cohort == "legacy"
    assert (
        document["rights"]["basis"]
        == "maintainer_attested_exact_scope_permission_not_independently_reviewed"
    )
    assert document["recovery"]["role"] == "primary"
    assert document["recovery"]["independent"] is False
    assert document["recovery"]["rpo_seconds"] is None
    assert document["consumers"] == []


@pytest.mark.parametrize(
    ("field", "value"),
    [("comparison_cohort", "current"), ("acquisition_id", "wrong")],
)
def test_candidate_rejects_changed_source_profile(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    original = qualification.bounded.read_bound_metadata

    def read(root: Path, path: str, digest: str) -> dict[str, Any]:
        result = original(root, path, digest)
        if path == qualification.SILVER_PROFILE:
            result = copy.deepcopy(result)
            result["source"][field] = value
        return result

    monkeypatch.setattr(qualification.bounded, "read_bound_metadata", read)
    with pytest.raises(ValueError, match="source profile differs"):
        qualification.candidate()


def test_candidate_rejects_changed_privacy_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = qualification.bounded.read_bound_metadata
    path_to_change = qualification.lineage.INPUTS["july_receipt"][0]

    def read(root: Path, path: str, digest: str) -> dict[str, Any]:
        result = original(root, path, digest)
        if path == path_to_change:
            result = copy.deepcopy(result)
            result["sensitivity"]["data_sensitivity"] = "restricted"
        return result

    monkeypatch.setattr(qualification.bounded, "read_bound_metadata", read)
    with pytest.raises(
        ValueError, match="historical MBS B1/B2 lifecycle differs"
    ):
        qualification.candidate()


def test_local_verify_fails_before_loading_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(
        qualification,
        "candidate",
        lambda *_args: pytest.fail("unexpected candidate read"),
    )
    with pytest.raises(ValueError, match="Actions dispatch on main"):
        qualification.qualify(workflow_commit="a" * 40)


def test_invalid_hosted_run_fails_before_loading_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    _hosted(monkeypatch, commit)
    monkeypatch.setenv("GITHUB_RUN_ID", "0")
    monkeypatch.setattr(
        qualification,
        "candidate",
        lambda *_args: pytest.fail("unexpected candidate read"),
    )
    with pytest.raises(ValueError, match="run identity missing"):
        qualification.qualify(workflow_commit=commit)


def test_stale_contract_fails_before_receipt_or_source_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commit = "a" * 40
    _hosted(monkeypatch, commit)
    raw, trust = qualification.candidate()
    monkeypatch.setattr(qualification, "candidate", lambda _root: (raw, trust))
    monkeypatch.setattr(
        qualification.shared,
        "receipt_closure",
        lambda *_args, **_kwargs: pytest.fail("unexpected receipt fetch"),
    )
    path = tmp_path / qualification.OUTPUT
    path.parent.mkdir(parents=True)
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="contract is stale"):
        qualification.qualify(workflow_commit=commit, root=tmp_path)


def test_hosted_orchestration_uses_admission_for_bounded_canary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    _hosted(monkeypatch, commit)
    raw, trust = qualification.candidate()
    monkeypatch.setattr(qualification, "candidate", lambda _root: (raw, trust))

    class Result:
        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"status": "synthetic"}

    closure = Result()
    monkeypatch.setattr(
        qualification.shared, "receipt_closure", lambda _raw, **_kwargs: closure
    )
    monkeypatch.setattr(
        qualification,
        "admit_closed_contract",
        lambda _raw, _closure, **_kwargs: Result(),
    )
    seen: list[dict[str, str]] = []

    def canary(
        _raw: bytes, admission: dict[str, str], **_kwargs: Any
    ) -> dict[str, str]:
        seen.append(admission)
        return {"status": "synthetic"}

    monkeypatch.setattr(qualification, "run_reader_canary", canary)
    result = qualification.qualify(workflow_commit=commit)
    assert seen == [{"status": "synthetic"}]
    assert result["status"] == "passed"
    assert result["boundaries"]["dataset_added_or_published"] is False
    assert result["boundaries"]["independent_recovery_established"] is False


def test_cli_writes_and_checks_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw, trust = qualification.candidate()
    monkeypatch.setattr(qualification, "candidate", lambda: (raw, trust))
    monkeypatch.setattr(qualification, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["qualification", "--write"])
    assert qualification.main() == 0
    monkeypatch.setattr(sys, "argv", ["qualification", "--check"])
    assert qualification.main() == 0
    (tmp_path / qualification.OUTPUT).write_text("{}")
    with pytest.raises(ValueError, match="contract is stale"):
        qualification.main()


@pytest.mark.parametrize("path", tuple(august.OUTPUTS))
def test_candidate_binds_each_path_without_claiming_semantic_acceptance(
    path: str,
) -> None:
    raw, trust = august.shared.candidate(path=path)
    document = json.loads(raw)
    assert raw == (august.ROOT / august.OUTPUTS[path]).read_bytes()
    assert trust.path == document["location"]["path"] == path
    assert trust.revision == august.shared.lineage.REVISION
    assert trust.schema_era == "2026-08-01"
    assert trust.comparison_cohort == "current"
    assert document["recovery"]["independent"] is False
    assert document["consumers"] == []
    assert any(
        ref["sha256"] == august.shared.AUGUST_COMPARISON_SHA
        for ref in document["lineage"]["inputs"]
    )


def test_alias_is_a_distinct_contract_with_the_same_source_digest() -> None:
    first, _ = august.shared.candidate(path=august.shared.lineage.AUGUST)
    second, _ = august.shared.candidate(path=august.shared.lineage.ALIAS)
    first_doc, second_doc = json.loads(first), json.loads(second)
    assert first != second
    assert first_doc["location"]["path"] != second_doc["location"]["path"]
    assert first_doc["location"]["sha256"] == second_doc["location"]["sha256"]
    assert first_doc["location"]["bytes"] == second_doc["location"]["bytes"]


@pytest.mark.parametrize("path", tuple(august.OUTPUTS))
def test_consumer_binding_preserves_the_exact_pin(path: str) -> None:
    raw, trust = august.shared.candidate(path=path)
    binding = bind_consumer_contract(
        raw,
        consumer_repository=august.shared.REPO,
        consumer_commit=august.shared.EVIDENCE_COMMIT,
    )
    assert binding.path == trust.path == path
    assert binding.revision == trust.revision
    assert binding.object_sha256 == trust.sha256
    assert binding.contract_sha256 == hashlib.sha256(raw).hexdigest()


def test_live_reader_refuses_local_source_read_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    raw, trust = august.shared.candidate(path=august.shared.lineage.AUGUST)
    record = AdmissionRecord(
        producer_repository=trust.producer_repository,
        contract_repository=trust.contract_repository,
        contract_commit=trust.contract_commit,
        schema_sha256=trust.schema_sha256,
        evidence_kind="live",
        dataset=trust.dataset,
        revision=trust.revision,
        path=trust.path,
        byte_count=trust.byte_count,
        sha256=trust.sha256,
        layer=trust.layer,
        bronze_stratum=trust.bronze_stratum,
        representation=trust.representation,
        source_id=trust.source_id,
        acquisition_id=trust.acquisition_id,
        schema_era=trust.schema_era,
        comparison_cohort=trust.comparison_cohort,
        effective_date=trust.effective_date,
        retrieved_at=trust.retrieved_at,
        contract_sha256=hashlib.sha256(raw).hexdigest(),
    )
    monkeypatch.setattr(
        FederatedReader,
        "_remote",
        lambda *_a: pytest.fail("unexpected network"),
    )
    with (
        FederatedReader(
            schema=(august.ROOT / august.shared.SCHEMA).read_bytes(),
            admission_records=(record,),
        ) as reader,
        pytest.raises(
            ValueError, match="live raw source reads require GitHub Actions"
        ),
        reader.open(raw),
    ):
        pytest.fail("unexpected source read")


@pytest.mark.parametrize("change", ["semantics", "source_digest", "alias"])
def test_candidate_rejects_changed_comparison_evidence(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    original = august.shared.bounded.read_bound_metadata

    def read(root: Path, path: str, digest: str) -> dict[str, Any]:
        value = original(root, path, digest)
        if path == august.shared.AUGUST_COMPARISON:
            value = copy.deepcopy(value)
            if change == "semantics":
                value["semantics_accepted"] = True
            elif change == "source_digest":
                value["releases"][1]["sha256"] = "a" * 64
            else:
                value["releases"][1]["harvest_receipt_archive_path"] = "other"
        return value

    monkeypatch.setattr(august.shared.bounded, "read_bound_metadata", read)
    with pytest.raises(
        ValueError, match="August comparison source profile differs"
    ):
        august.shared.candidate(path=august.shared.lineage.AUGUST)


def test_unapproved_path_is_rejected_before_metadata_reads() -> None:
    with pytest.raises(ValueError, match="unsupported MBS path"):
        august.shared.candidate(path="other")


def test_local_verify_fails_before_candidate_or_source_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(
        august.shared,
        "candidate",
        lambda *_args, **_kwargs: pytest.fail("read"),
    )
    with pytest.raises(ValueError, match="Actions dispatch on main"):
        august.qualify(workflow_commit="a" * 40)


def test_qualification_uses_both_independent_trusted_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": august.shared.REPO,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": commit,
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
    }.items():
        monkeypatch.setenv(key, value)

    class Result:
        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"status": "synthetic"}

    seen: list[str] = []
    monkeypatch.setattr(
        august.receipts, "receipt_closure", lambda *_a, **_k: Result()
    )

    def admit(
        raw: bytes, _closure: Any, *, trusted: Any, **_kwargs: Any
    ) -> Result:
        path = json.loads(raw)["location"]["path"]
        assert trusted.path == path
        seen.append(path)
        return Result()

    monkeypatch.setattr(august, "admit_closed_contract", admit)
    monkeypatch.setattr(
        august, "run_reader_canary", lambda *_a, **_k: {"status": "synthetic"}
    )
    report = august.qualify(workflow_commit=commit)
    assert seen == list(august.OUTPUTS)
    assert [row["path"] for row in report["objects"]] == seen
    assert report["source_profile"]["field_semantics_accepted"] is False
    assert report["source_profile"]["latest_schedule_claimed"] is False
    assert report["boundaries"]["participant_or_cohort_data_accessed"] is False
    assert report["boundaries"]["dataset_added_or_published"] is False
