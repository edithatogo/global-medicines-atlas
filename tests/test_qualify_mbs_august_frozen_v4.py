"""August raw profile declarations remain scoped to two exact paths."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_mbs_august_frozen_v4 as august

from global_medicines_atlas.federation_consumer import bind_consumer_contract
from global_medicines_atlas.federation_identity import AdmissionRecord
from global_medicines_atlas.federation_reader import FederatedReader


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
