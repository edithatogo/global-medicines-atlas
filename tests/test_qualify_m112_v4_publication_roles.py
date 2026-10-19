"""Tests for unbound M-112 publication and anonymous-restore receipt evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from scripts.qualify_m112_v4_publication_roles import (
    CONTRACT_COMMIT,
    CONTRACT_REPOSITORY,
    CONTRACT_SCHEMA_PATH,
    CONTRACT_SCHEMA_SHA256,
    DIGEST_REPORT,
    DISCOVERY_REPORT,
    PRODUCER_WORKFLOW,
    ROLE_REPORT,
    SOURCE_SEMANTICS_PATH,
    SOURCE_SEMANTICS_REPORT,
    qualify,
)


def test_exact_mbs_candidates_receive_unbound_publication_and_restore_evidence() -> (
    None
):
    report = qualify()
    candidates = [
        item
        for item in report["objects"]
        if item["dataset"] == "edithatogo/australian-mbs-utilisation-archive"
    ]

    assert len(candidates) == 14
    assert report["cohort"]["publication_candidate_receipts"] == 14
    assert report["cohort"]["verification_candidate_receipts"] == 14
    for candidate in candidates:
        assert candidate["contract_role_states"]["publication"] == (
            "candidate_receipt_available_unbound"
        )
        assert candidate["contract_role_states"]["verification"] == (
            "candidate_receipt_available_unbound"
        )
        assert (
            candidate["publication_candidate_receipt"]["manifest"][
                "exact_object_match"
            ]
            is True
        )
        verification = candidate["verification_candidate_receipt"]
        assert verification["anonymous"] is True
        assert verification["token_free"] is True
        assert verification["clean_room"] is True
        assert verification["temporary_source_bytes_removed"] is True


def test_refresh_preserves_the_denominator_and_zero_admissions_and_canaries() -> (
    None
):
    report = qualify()

    assert report["cohort"]["approved_denominator"] == 1759
    assert report["cohort"]["approved_denominator_changed"] is False
    assert report["cohort"]["v4_admissions"] == 0
    assert report["cohort"]["consumer_canaries"] == 0
    assert report["boundaries"]["v4_admission_performed"] is False
    assert report["boundaries"]["consumer_canary_performed"] is False


def test_exact_contract_authority_identity_binds_all_candidates_unbound() -> (
    None
):
    report = qualify()

    assert report["authority_identity"]["candidate_objects"] == 16
    assert report["authority_identity"]["state"] == (
        "candidate_identity_available_unbound_for_16_of_16"
    )
    for candidate in report["objects"]:
        authority = candidate["authority_candidate"]
        assert authority["producer_repository"] == CONTRACT_REPOSITORY
        assert authority["contract_repository"] == CONTRACT_REPOSITORY
        assert authority["contract_commit"] == CONTRACT_COMMIT
        assert authority["schema_path"] == CONTRACT_SCHEMA_PATH
        assert authority["schema_sha256"] == CONTRACT_SCHEMA_SHA256
        assert authority["producer_workflow"] == PRODUCER_WORKFLOW
        assert authority["contract_role_state"] == (
            "candidate_identity_available_unbound"
        )
        assert candidate["contract_role_states"]["authority"] == (
            "candidate_identity_available_unbound"
        )


def test_current_discovery_receipts_bind_all_candidates_without_rights_promotion() -> (
    None
):
    report = qualify()

    assert report["discovery_candidate_evidence"]["objects"] == 16
    assert report["discovery_candidate_evidence"]["state"] == (
        "candidate_receipt_available_unbound_for_16_of_16"
    )
    assert report["cohort"]["v4_admissions"] == 0
    for candidate in report["objects"]:
        discovery = candidate["discovery_candidate_receipt"]
        assert discovery["contract_role_state"] == (
            "candidate_receipt_available_unbound"
        )
        assert discovery["collection"].startswith(
            "https://huggingface.co/collections/"
        )
        assert discovery["estate_entry"]["status"] == "not_assessed"
        assert discovery["estate_entry"]["rights_status"] == (
            "source_specific_review_required"
        )
        assert candidate["contract_role_states"]["discovery"] == (
            "candidate_receipt_available_unbound"
        )


def test_location_receipts_bind_exact_identity_and_anonymous_digest_evidence() -> (
    None
):
    report = qualify()

    assert report["location_candidate_evidence"]["objects"] == 16
    assert report["location_candidate_evidence"]["state"] == (
        "candidate_receipt_available_unbound_for_16_of_16"
    )
    for candidate in report["objects"]:
        location = candidate["location_candidate_receipt"]
        assert location["dataset"] == candidate["dataset"]
        assert location["revision"] == candidate["revision"]
        assert location["path"] == candidate["path"]
        assert location["bytes"] == candidate["bytes"]
        assert location["sha256"] == candidate["sha256"]
        assert location["private"] is False
        assert location["gated"] is False
        assert location["anonymous_digest_readback"] is True
        assert location["contract_role_state"] == (
            "candidate_receipt_available_unbound"
        )
        assert candidate["contract_role_states"]["location"] == (
            "candidate_receipt_available_unbound"
        )


def test_recovery_receipts_bind_only_the_restored_utilisation_cohort() -> None:
    report = qualify()

    assert report["recovery_candidate_evidence"]["objects"] == 14
    assert report["recovery_candidate_evidence"]["state"] == (
        "candidate_receipts_available_unbound_for_14_of_16"
    )
    for candidate in report["objects"]:
        recovery = candidate.get("recovery_candidate_receipt")
        if (
            candidate["dataset"]
            == "edithatogo/australian-mbs-utilisation-archive"
        ):
            assert isinstance(recovery, dict)
            assert recovery["role"] == "primary"
            assert recovery["independent"] is False
            assert recovery["rpo_seconds"] is None
            assert recovery["rto_seconds"] is None
            assert recovery["verified_manifest_object_count"] == 28
            assert recovery["temporary_source_bytes_removed"] is True
            assert recovery["contract_role_state"] == (
                "candidate_receipt_available_unbound"
            )
            assert candidate["contract_role_states"]["recovery"] == (
                "candidate_receipt_available_unbound"
            )
        else:
            assert recovery is None
            assert candidate["contract_role_states"]["recovery"] == "missing"


def test_source_temporal_semantics_bind_only_exact_metadata_matches() -> None:
    report = qualify()
    source_candidates = [
        item for item in report["objects"] if "source_candidate_receipt" in item
    ]
    candidate = next(
        item
        for item in source_candidates
        if item["path"] == SOURCE_SEMANTICS_PATH
    )
    source = candidate["source_candidate_receipt"]

    assert source["effective_date"] == "2016-07-31"
    assert source["retrieved_at"] == "2026-09-27T16:43:13Z"
    assert source["comparison_cohort"] == "legacy"
    assert source["bronze_stratum"] == "B2"
    assert source["representation"] == "raw"
    assert source["native_schema_layout_qualified"] is False
    assert source["temporal_semantics"]["service_month_basis"] == (
        "claim_processing_date_not_service_provision_date"
    )
    assert (
        source["contract_role_state"] == "candidate_receipt_available_unbound"
    )
    assert candidate["contract_role_states"]["source"] == (
        "candidate_receipt_available_unbound"
    )
    assert len(source_candidates) == 13
    assert len({item["path"] for item in source_candidates}) == 13
    assert all(
        item["contract_role_states"]["source"]
        == "candidate_receipt_available_unbound"
        for item in source_candidates
    )
    assert not any(
        item["path"].endswith("mbs-demographics-historical-2013-2015.zip")
        for item in source_candidates
    )
    assert report["source_semantics_candidate_evidence"]["objects"] == 13
    assert report["cohort"]["v4_admissions"] == 0
    assert report["cohort"]["consumer_canaries"] == 0


def test_missing_exact_manifest_match_fails_closed(tmp_path: Path) -> None:
    (tmp_path / ROLE_REPORT).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / DIGEST_REPORT).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / DISCOVERY_REPORT).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / SOURCE_SEMANTICS_REPORT).parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / CONTRACT_SCHEMA_PATH).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / ROLE_REPORT, tmp_path / ROLE_REPORT)
    digest_path = tmp_path / DIGEST_REPORT
    shutil.copy(ROOT / DIGEST_REPORT, digest_path)
    shutil.copy(ROOT / DISCOVERY_REPORT, tmp_path / DISCOVERY_REPORT)
    shutil.copy(
        ROOT / SOURCE_SEMANTICS_REPORT, tmp_path / SOURCE_SEMANTICS_REPORT
    )
    shutil.copy(ROOT / CONTRACT_SCHEMA_PATH, tmp_path / CONTRACT_SCHEMA_PATH)
    role_report = json.loads(
        (tmp_path / ROLE_REPORT).read_text(encoding="utf-8")
    )
    for candidate in role_report["objects"]:
        reference = candidate["digest_evidence"]
        evidence_path = tmp_path / reference["path"]
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / reference["path"], evidence_path)
    digest_report = json.loads(digest_path.read_text(encoding="utf-8"))
    mbs = next(
        item
        for item in digest_report["verified_objects"]
        if item["dataset"] == "edithatogo/australian-mbs-utilisation-archive"
    )
    mbs["sha256"] = "0" * 64
    digest_path.write_text(json.dumps(digest_report), encoding="utf-8")
    digest_sha256 = hashlib.sha256(digest_path.read_bytes()).hexdigest()
    for candidate in role_report["objects"]:
        if (
            candidate["dataset"]
            == "edithatogo/australian-mbs-utilisation-archive"
        ):
            candidate["digest_evidence"]["sha256"] = digest_sha256
    (tmp_path / ROLE_REPORT).write_text(
        json.dumps(role_report), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="unique hosted manifest match"):
        qualify(tmp_path)


def test_schema_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    (tmp_path / ROLE_REPORT).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / DIGEST_REPORT).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / DISCOVERY_REPORT).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / SOURCE_SEMANTICS_REPORT).parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / CONTRACT_SCHEMA_PATH).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / ROLE_REPORT, tmp_path / ROLE_REPORT)
    shutil.copy(ROOT / DIGEST_REPORT, tmp_path / DIGEST_REPORT)
    shutil.copy(ROOT / DISCOVERY_REPORT, tmp_path / DISCOVERY_REPORT)
    shutil.copy(
        ROOT / SOURCE_SEMANTICS_REPORT, tmp_path / SOURCE_SEMANTICS_REPORT
    )
    (tmp_path / CONTRACT_SCHEMA_PATH).write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="schema digest differs"):
        qualify(tmp_path)


ROOT = Path(__file__).resolve().parents[1]
