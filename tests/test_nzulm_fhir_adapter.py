"""Contract tests for the preserved nzmedicines FHIR fixture adapter."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from sources.nz.nzulm_fhir import (
    iter_fhir_resources,
    load_upstream_fixture_records,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_upstream_snapshot_has_expected_unique_fhir_resources() -> None:
    records = load_upstream_fixture_records(PROJECT_ROOT)

    assert len(records) == 51
    assert (
        len({(record.resource_type, record.resource_id) for record in records})
        == 51
    )
    assert Counter(record.resource_type for record in records) == {
        "Medication": 42,
        "Bundle": 3,
        "DocumentReference": 4,
        "Substance": 2,
    }
    assert all(
        record.source_commit == "6a8ecfae67f15d635750d11d5f446b93d76c1865"
        for record in records
    )
    assert all(len(record.source_sha256) == 64 for record in records)


def test_adapter_rejects_duplicate_fhir_identity(tmp_path: Path) -> None:
    fixture = (
        '{"resourceType":"Bundle","id":"bundle-1","entry":['
        '{"resource":{"resourceType":"Medication","id":"duplicate"}},'
        '{"resource":{"resourceType":"Medication","id":"duplicate"}}]}'
    )
    path = tmp_path / "duplicate.json"
    path.write_text(fixture, encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate FHIR identity"):
        tuple(iter_fhir_resources([path], source_root=tmp_path))


def test_adapter_rejects_resource_without_id(tmp_path: Path) -> None:
    path = tmp_path / "missing-id.json"
    path.write_text('{"resourceType":"Medication"}', encoding="utf-8")

    with pytest.raises(ValueError, match="FHIR id is required"):
        tuple(iter_fhir_resources([path], source_root=tmp_path))


def test_adapter_rejects_resource_without_type(tmp_path: Path) -> None:
    path = tmp_path / "missing-type.json"
    path.write_text(
        '{"resourceType":"Bundle","id":"bundle-1",'
        '"entry":[{"resource":{"id":"medicine-1"}}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="FHIR resourceType is required"):
        tuple(iter_fhir_resources([path], source_root=tmp_path))
