"""Existing quarterly CSV candidates retain exact provenance and denominators."""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from global_medicines_atlas import mbs_demographic_csv_cohort as module
from global_medicines_atlas.mbs_demographic_csv_cohort import (
    load_csv_candidates,
)

ROOT = Path(__file__).resolve().parents[1]


def test_three_frozen_csv_candidates_are_bound_without_source_reads():
    candidates = load_csv_candidates(ROOT)
    assert [candidate.expected_rows for candidate in candidates] == [
        545070,
        567335,
        186082,
    ]
    assert len({candidate.source.object_id for candidate in candidates}) == 3
    assert all(
        candidate.source.source_format == "csv" for candidate in candidates
    )
    assert all(
        candidate.source.benefit_semantics.state == "native_unresolved"
        for candidate in candidates
    )


def test_mutated_prior_receipt_fails_before_source_context(tmp_path: Path):
    path = (
        tmp_path
        / "quality/qualifications/australian-mbs-utilisation-payload-validation-receipt-20261004.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text('{"modified":true}')
    with pytest.raises(ValueError, match="retained metadata digest"):
        load_csv_candidates(tmp_path)


@pytest.mark.parametrize(
    ("kind", "field", "value"),
    [
        ("checks", "column_count", 7),
        ("checks", "row_count", 0),
        ("checks", "row_count", True),
        ("reference", "byte_count", 0),
        ("reference", "byte_count", "23934884"),
        ("header", "header_sha256", "wrong"),
        ("header", "source_sha256", "0" * 64),
        ("header", "source_revision", "0" * 40),
        ("header", "acquisition_id", "0" * 64),
        ("header", "byte_count", 1),
        ("header", "anonymous_digest_verified", False),
        ("result", "status", "structure_failed"),
        ("result", "anonymous_digest_verified", False),
    ],
)
def test_candidate_join_rejects_inconsistent_metadata(
    monkeypatch, kind, field, value
):
    original = module._bound

    def modified(root, path, digest):
        data = original(root, path, digest)
        if path == module.STRUCTURE and kind != "header":
            document = data["per_object_receipts"][0]["document"]
            target = (
                document["raw_reference"]
                if kind == "reference"
                else document["result"]["checks"]
                if kind == "checks"
                else document["result"]
            )
            target[field] = value
        elif path == module.HEADERS and kind == "header":
            data["records"][0][field] = value
        return data

    monkeypatch.setattr(module, "_bound", modified)
    with pytest.raises(ValueError, match="structural/header evidence"):
        load_csv_candidates(ROOT)


@pytest.mark.parametrize(
    "change", ["duplicate", "missing", "unfrozen", "b1_digest"]
)
def test_membership_denominator_and_b1_binding_fail_closed(monkeypatch, change):
    original = module._bound

    def modified(root, path, digest):
        data = original(root, path, digest)
        if path == module.STRUCTURE:
            if change == "duplicate":
                data["per_object_receipts"].append(
                    data["per_object_receipts"][0]
                )
            elif change == "missing":
                data["per_object_receipts"] = []
            elif change == "b1_digest":
                data["per_object_receipts"][0]["document"]["raw_reference"][
                    "sha256"
                ] = "0" * 64
        elif path == module.FROZEN and change == "unfrozen":
            data["members"] = []
        elif path == module.HEADERS and change == "b1_digest":
            data["records"][0]["source_sha256"] = "0" * 64
        return data

    monkeypatch.setattr(module, "_bound", modified)
    with pytest.raises(
        ValueError, match=r"membership|denominator|B1/B2 digest"
    ):
        load_csv_candidates(ROOT)


@pytest.mark.parametrize(
    ("quarter", "digest"),
    [
        (1, "69e6882678ec67157b69738531a3847ef6a3b16c42a75d3a0fdcd32ee98f16f5"),
        (2, "1805a45bd998bb07b863b839e15b73552007c064f38b92b07043413f8fb34708"),
        (3, "e0dc024bae88b40c7a62d881c64038b3d77f981ad4a35af28c9906c54c009c8d"),
    ],
)
def test_retained_quarterly_qualification_binds_complete_candidate(
    quarter, digest
):
    path = (
        ROOT
        / f"quality/qualifications/mbs-demographic-q{quarter}-native-qualification-20261022-39627746801.json"
    )
    assert sha256(path.read_bytes()).hexdigest() == digest
    report = json.loads(path.read_text())
    candidate = load_csv_candidates(ROOT)[quarter - 1]
    result = report["result"]
    assert (
        report["workflow_commit"] == "ebd4e300f4aafc809fedfe4b1214fdbe44b381ca"
    )
    assert report["selected_quarter"] == quarter
    assert report["source_path"] == candidate.source.source_path
    assert result["source_object_id"] == candidate.source.object_id
    assert result["source_sha256"] == candidate.source.source_sha256
    assert result["coverage"]["native_rows"] == candidate.expected_rows
    assert (
        result["source_native_primary_fields_equal"]
        == candidate.expected_rows * 8
    )
    assert result["independent_parquet_restore"] is True
    assert result["rebuild_equal"] is True
    assert result["duckdb_consumer_counts_equal"] is True
    assert result["unqualified_pooling_blocked"] is True
    assert result["patient_rate_state"] == "unavailable"
    assert report["boundaries"]["new_admissions"] == 0
    assert report["boundaries"]["new_sources"] == 0
    if quarter == 2:
        assert result["coverage"]["services_invalid"] == 4728
