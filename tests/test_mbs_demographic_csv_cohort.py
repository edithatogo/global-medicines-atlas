"""Existing quarterly CSV candidates retain exact provenance and denominators."""

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
