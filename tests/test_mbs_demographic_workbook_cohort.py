"""Frozen workbook qualification must retain independent B1/B2 identities."""

import json
from pathlib import Path

import pytest

from global_medicines_atlas import mbs_demographic_workbook_cohort as module
from global_medicines_atlas.mbs_demographic_workbook_cohort import (
    load_workbook_candidates,
)

ROOT = Path(__file__).resolve().parents[1]


def test_three_frozen_workbooks_bind_latest_structural_evidence():
    candidates = load_workbook_candidates(ROOT)
    assert len(candidates) == 3
    assert [candidate.byte_count for candidate in candidates] == [
        21966140,
        23765087,
        7316301,
    ]
    assert all(
        candidate.source.source_format == "workbook" for candidate in candidates
    )
    assert len({candidate.source.object_id for candidate in candidates}) == 3
    assert all(
        candidate.source.benefit_semantics.state == "native_unresolved"
        for candidate in candidates
    )
    assert candidates[0].structural_receipt_path.endswith(
        "streaming-receipt-20261017.json"
    )
    assert candidates[1].structural_receipt_path.endswith(
        "streaming-receipt-20261017.json"
    )
    assert candidates[2].structural_receipt_path.endswith(
        "payload-validation-receipt-20261004.json"
    )


def test_metadata_digest_is_checked_before_any_source_context(tmp_path):
    path = tmp_path / module.STRUCTURE
    path.parent.mkdir(parents=True)
    path.write_text('{"changed":true}')
    with pytest.raises(ValueError, match="metadata digest"):
        load_workbook_candidates(tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        "identity",
        "status",
        "anonymous",
        "acquisition",
        "membership",
        "duplicate",
        "missing_streaming",
        "b1_digest",
        "b2_bytes",
        "boolean_bytes",
    ],
)
def test_inconsistent_latest_evidence_fails_closed(monkeypatch, change):
    original = module._bound

    def altered(root, path, digest):
        report = original(root, path, digest)
        if path == module.STREAMING:
            document = next(
                row["document"]
                for row in report["per_object_receipts"]
                if row["document"]["raw_reference"]["path"]
                == module.SOURCE_PATHS[0]
            )
            if change == "identity":
                document["raw_reference"]["sha256"] = "0" * 64
            elif change == "status":
                document["result"]["status"] = "structure_failed"
            elif change == "anonymous":
                document["result"]["anonymous_digest_verified"] = False
            elif change == "acquisition":
                document["acquisition_id"] = "0" * 64
            elif change == "missing_streaming":
                report["per_object_receipts"] = report["per_object_receipts"][
                    1:
                ]
            elif change == "duplicate":
                report["per_object_receipts"].append(
                    report["per_object_receipts"][0]
                )
        if path in {module.STRUCTURE, module.STREAMING} and change in {
            "b1_digest",
            "b2_bytes",
            "boolean_bytes",
        }:
            document = next(
                row["document"]
                for row in report["per_object_receipts"]
                if row["document"]["raw_reference"]["path"]
                == module.SOURCE_PATHS[0]
            )
            if change == "b1_digest":
                document["raw_reference"]["sha256"] = "0" * 64
            else:
                document["raw_reference"]["byte_count"] = (
                    True if change == "boolean_bytes" else 1
                )
        if path == module.FROZEN and change == "membership":
            report["members"] = [
                row
                for row in report["members"]
                if row["path"] != module.SOURCE_PATHS[0]
            ]
        return report

    monkeypatch.setattr(module, "_bound", altered)
    with pytest.raises(ValueError, match=r"workbook|demographic"):
        load_workbook_candidates(ROOT)


def test_retained_q2_workbook_qualification_keeps_native_denominator_and_uncertainty():
    report = json.loads(
        (
            ROOT
            / "quality/qualifications/mbs-demographic-workbook-q2-native-qualification-20261022-39648296077.json"
        ).read_bytes()
    )
    source = load_workbook_candidates(ROOT)[1].source
    assert report["selected_quarter"] == 2
    assert report["source_path"] == source.source_path
    assert report["source_path"].endswith("qtr2-junehr.xlsx")
    result = report["result"]
    assert result["source_sha256"] == source.source_sha256
    assert result["coverage"]["native_rows"] == 567339
    assert result["coverage"]["native_fields"] == 567339 * 8
    assert result["coverage"]["literal_unknown_age_rows"] == 55
    assert result["coverage"]["benefit_unrepresentable"] == 78882
    assert result["patient_rate_state"] == "unavailable"
    assert result["rebuild_equal"]
    assert result["independent_parquet_restore"]
    assert result["duckdb_consumer_counts_equal"]
    assert result["unqualified_pooling_blocked"]
    assert report["boundaries"]["new_admissions"] == 0
    assert report["boundaries"]["benefit_equivalence_established"] is False
