from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from scripts.prepare_m112_imported_b2_manifest import (
    OUTPUT_PATH,
    QUALIFICATION_PATH,
    build_reconciliation,
    resolve_repo_file,
)

from global_medicines_atlas.bronze_raw_evidence import RawEvidenceState

RIGHTS_DECISION_PATH = (
    "quality/qualifications/"
    "australian-mbs-utilisation-exact-scope-rights-decision-20261004.json"
)


def _assert_m112_cohort_member_bound(
    *,
    root: Path,
    approved: dict[str, Any],
    approved_rights_paths: set[str],
    rights_decision_sha256: str,
    acquisitions_by_path: dict[str, dict[str, Any]],
    bindings_by_acquisition: dict[str, dict[str, Any]],
    b2_by_acquisition: dict[str, dict[str, Any]],
) -> None:
    imported = acquisitions_by_path[approved["path"]]
    acquisition_id = imported["acquisition_id"]
    binding = bindings_by_acquisition[acquisition_id]
    b2 = b2_by_acquisition[acquisition_id]
    event = json.loads(
        (root / imported["event_path"]).read_text(encoding="utf-8")
    )
    digest = approved["identity"]["sha256"]
    byte_count = approved["identity"]["byte_count"]

    assert binding["content_id"] == digest
    assert binding["expected_payload_sha256"] == digest
    assert binding["expected_byte_count"] == byte_count
    assert b2["content_id"] == digest
    assert b2["source_id"] == event["source_id"]
    assert b2["external_reference"] == binding["external_reference"]
    assert b2["state"] == RawEvidenceState.EXTERNAL_REFERENCE_ONLY
    assert b2["payload_sha256"] is None
    assert b2["byte_count"] is None

    assert approved["path"] in approved_rights_paths
    assert approved["rights"]["state"].startswith("approved_exact_scope_")
    assert approved["rights"]["decision_evidence"] == {
        "path": RIGHTS_DECISION_PATH,
        "sha256": rights_decision_sha256,
    }
    assert approved["v4_admission"] is False
    assert approved["consumer_canary"] is False
    assert approved["disposition"] == "deferred_not_admitted"


@pytest.mark.unit
def test_m112_historical_events_bind_to_explicit_b2_external_references() -> (
    None
):
    manifest, qualification = build_reconciliation()

    assert manifest.row_count == 14
    assert len({row.acquisition_id for row in manifest.rows}) == 14
    by_acquisition = {
        item["acquisition_id"]: item["content_id"]
        for item in qualification["records"]
    }
    assert all(
        row.state is RawEvidenceState.EXTERNAL_REFERENCE_ONLY
        and by_acquisition[row.acquisition_id] == row.content_id
        and row.raw_object_locator is None
        and row.payload_sha256 is None
        and row.byte_count is None
        and row.external_reference is not None
        and row.external_reference.startswith(
            "https://huggingface.co/datasets/"
        )
        for row in manifest.rows
    )
    assert qualification["counts"] == {
        "b1_b2_reference_bindings": 14,
        "native_source_receipts": 0,
        "native_payload_storage_receipts": 0,
        "admission_histories": 0,
    }
    assert qualification["boundaries"]["source_payload_bytes_read"] is False
    assert qualification["boundaries"]["m112_federation_accepted"] is False
    assert qualification["scope"] == {
        "approved_m112_denominator": 1759,
        "selected_historical_mbs_utilisation_objects": 14,
        "selection_is_full_denominator": False,
    }
    assert qualification["output"]["path"] == str(OUTPUT_PATH)
    assert qualification["input"]["path"].endswith(
        "australian-mbs-utilisation-raw-reference-import-20261004.json"
    )
    event_source_counts: Counter[str] = Counter()
    for record in qualification["records"]:
        event_path = resolve_repo_file(
            Path(__file__).resolve().parents[1], record["event_path"]
        )
        event_bytes = event_path.read_bytes()
        assert sha256(event_bytes).hexdigest() == record["event_sha256"]
        event_source_counts[json.loads(event_bytes)["source_id"]] += 1
    assert event_source_counts == {
        "au-data-gov-mbs-demographics": 10,
        "au-data-gov-mbs-group": 4,
    }
    catalog = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "src/global_medicines_atlas/data/medicine_source_catalog.json"
        ).read_text(encoding="utf-8")
    )
    catalog_source_ids = {source["source_id"] for source in catalog["sources"]}
    assert set(event_source_counts).issubset(catalog_source_ids)


@pytest.mark.unit
def test_m112_b2_reference_manifest_and_qualification_are_reproducible() -> (
    None
):
    manifest, qualification = build_reconciliation()
    root = Path(__file__).resolve().parents[1]
    manifest_bytes = manifest.canonical_json()
    qualification_bytes = (
        json.dumps(qualification, indent=2, sort_keys=True) + "\n"
    ).encode()

    assert (root / OUTPUT_PATH).read_bytes() == manifest_bytes
    assert (root / QUALIFICATION_PATH).read_bytes() == qualification_bytes


@pytest.mark.unit
def test_m112_b2_reference_rows_bind_to_the_exact_approved_14_object_cohort() -> (
    None
):
    root = Path(__file__).resolve().parents[1]
    m112 = json.loads(
        (
            root / "quality/qualifications/"
            "australian-m112-per-object-gate-reconciliation-20261005.json"
        ).read_text(encoding="utf-8")
    )
    rights_decision_file = root / RIGHTS_DECISION_PATH
    rights_decision = json.loads(
        rights_decision_file.read_text(encoding="utf-8")
    )
    receipt_join_audit = json.loads(
        (
            root / "quality/qualifications/"
            "australian-m112-receipt-sidecar-join-audit-20260930.json"
        ).read_text(encoding="utf-8")
    )
    acquisition_import = json.loads(
        (
            root / "quality/qualifications/"
            "australian-mbs-utilisation-acquisition-import-20261004.json"
        ).read_text(encoding="utf-8")
    )
    manifest = json.loads((root / OUTPUT_PATH).read_text(encoding="utf-8"))
    qualification = json.loads(
        (root / QUALIFICATION_PATH).read_text(encoding="utf-8")
    )

    cohort = [
        row
        for row in m112["objects"]
        if row["dataset"] == "edithatogo/australian-mbs-utilisation-archive"
    ]
    assert len(cohort) == 14
    assert all(row["approved_denominator_member"] for row in cohort)
    assert m112["scope"]["approved_denominator"] == 1759
    approved_rights_paths = {
        row["path"]
        for dataset in receipt_join_audit["datasets"]
        if dataset["dataset"] == "edithatogo/australian-mbs-utilisation-archive"
        for row in dataset["joined_objects"]
        if row["authorization_scope_match"]
    }
    assert len(approved_rights_paths) == 14
    assert rights_decision["scope"]["candidate_paths"] == len(
        approved_rights_paths
    )
    rights_decision_sha256 = sha256(
        rights_decision_file.read_bytes()
    ).hexdigest()
    acquisitions_by_path = {
        row["path"]: row for row in acquisition_import["records"]
    }
    bindings_by_acquisition = {
        row["acquisition_id"]: row for row in qualification["records"]
    }
    b2_by_acquisition = {row["acquisition_id"]: row for row in manifest["rows"]}
    assert len(bindings_by_acquisition) == len(b2_by_acquisition) == 14

    for approved in cohort:
        _assert_m112_cohort_member_bound(
            root=root,
            approved=approved,
            approved_rights_paths=approved_rights_paths,
            rights_decision_sha256=rights_decision_sha256,
            acquisitions_by_path=acquisitions_by_path,
            bindings_by_acquisition=bindings_by_acquisition,
            b2_by_acquisition=b2_by_acquisition,
        )


@pytest.mark.unit
def test_m112_reconciliation_rejects_paths_outside_its_repository_root(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="stay within repository"):
        resolve_repo_file(tmp_path, "../outside.json")
    with pytest.raises(ValueError, match="stay within repository"):
        resolve_repo_file(tmp_path, str(outside))
