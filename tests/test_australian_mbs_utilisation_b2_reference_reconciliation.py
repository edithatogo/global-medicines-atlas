from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest
from scripts.prepare_m112_imported_b2_manifest import (
    OUTPUT_PATH,
    QUALIFICATION_PATH,
    build_reconciliation,
    resolve_repo_file,
)

from global_medicines_atlas.bronze_raw_evidence import RawEvidenceState


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
def test_m112_reconciliation_rejects_paths_outside_its_repository_root(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="stay within repository"):
        resolve_repo_file(tmp_path, "../outside.json")
    with pytest.raises(ValueError, match="stay within repository"):
        resolve_repo_file(tmp_path, str(outside))
