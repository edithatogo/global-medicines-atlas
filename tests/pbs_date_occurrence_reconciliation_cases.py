"""Exact PBS date identity crosswalk remains value-free."""

from types import SimpleNamespace

import pyarrow as pa
import pytest
from test_au_pbs_v3 import (
    _production_xml,  # ruff: ignore[import-private-name] -- synthetic fixture
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic fixture
)

import global_medicines_atlas.pbs_date_occurrence_reconciliation as hosted_dates
from global_medicines_atlas.pbs_date_occurrence_reconciliation import (
    build_pbs_date_occurrence_crosswalk,
    reconcile_pbs_date_occurrences,
)
from global_medicines_atlas.pbs_dates import iter_pbs_date_batches


def test_hosted_date_crosswalk_rejects_nonmatching_denominators(monkeypatch):
    inputs = SimpleNamespace(
        xml=b"synthetic",
        archive=b"synthetic",
        parent=object(),
        binding=object(),
        context={},
    )
    empty_crosswalk = {
        "status": "unresolved_incomplete_or_nonmatching_denominators",
        "occurrence_sets": {
            "restriction_effective_date_path": {"fields": 0},
            "item_effective_date_profile": {"fields": 0},
        },
        "join": {"overlap_fields": 0, "unmatched_total": 0},
    }
    monkeypatch.setattr(
        hosted_dates, "_verified_inputs", lambda _commit, **_kwargs: inputs
    )
    monkeypatch.setattr(hosted_dates, "_denominator", lambda _xml: {})
    monkeypatch.setattr(
        hosted_dates,
        "iter_pbs_historical_entity_batches",
        lambda _archive, _xml, _parent, _binding: (),
    )
    monkeypatch.setattr(
        hosted_dates, "_date_batches", lambda _entities, _profile, _size: ()
    )
    monkeypatch.setattr(
        hosted_dates,
        "reconcile_pbs_date_occurrences",
        lambda _batches: empty_crosswalk,
    )
    with pytest.raises(ValueError, match="date occurrence denominators"):
        hosted_dates.run_hosted_date_occurrence_reconciliation(
            "0" * 40, transport=None
        )


def test_distinct_date_paths_reconcile_by_exact_field_identity() -> None:
    payload = (
        _production_xml()
        .replace(
            b"<pbs:block-container>",
            b"""<pbs:effective><pbs:date>2019-03-20</pbs:date></pbs:effective>
<pbs:block-container>""",
        )
        .replace(
            b"</pbs:root>",
            b"<pbs:prescribing-texts-list><pbs:restriction><pbs:effective>"
            b"<pbs:date>2026-05-01</pbs:date></pbs:effective></pbs:restriction>"
            b"</pbs:prescribing-texts-list></pbs:root>",
        )
    )
    report = build_pbs_date_occurrence_crosswalk(
        payload, _receipt(payload, "au-pbs")
    )
    sets = report["occurrence_sets"]
    join = report["join"]
    assert sets["restriction_effective_date_path"]["fields"] == 1
    assert sets["item_effective_date_profile"]["fields"] == 1
    assert join["overlap_fields"] == 0
    assert join["restriction_only_fields"] == 1
    assert join["item_profile_only_fields"] == 1
    assert join["unmatched_total"] == 2
    assert report["status"] == (
        "unresolved_incomplete_or_nonmatching_denominators"
    )
    assert report["source_values_emitted"] is False
    assert "2026-05-01" not in str(report)
    assert "2019-03-20" not in str(report)


def test_exact_identity_set_digests_are_stable_and_roles_are_closed() -> None:
    payload = _production_xml()
    batches = list(iter_pbs_date_batches(payload, _receipt(payload, "au-pbs")))
    first = reconcile_pbs_date_occurrences(batches)
    second = reconcile_pbs_date_occurrences(batches)
    assert first == second
    assert set(first["occurrence_sets"]) == {
        "restriction_effective_date_path",
        "item_effective_date_profile",
    }
    assert all(
        len(value["identity_set_sha256"]) == 64
        for value in first["occurrence_sets"].values()
    )


def test_empty_crosswalk_remains_unresolved() -> None:
    report = reconcile_pbs_date_occurrences(())
    assert report["status"] == (
        "unresolved_incomplete_or_nonmatching_denominators"
    )
    assert (
        report["occurrence_sets"]["restriction_effective_date_path"]["fields"]
        == 0
    )
    assert (
        report["occurrence_sets"]["item_effective_date_profile"]["fields"] == 0
    )


def test_counts_effective_date_slots_without_source_identity() -> None:
    payload = _production_xml()
    receipt = _receipt(payload, "au-pbs")
    batch = next(iter_pbs_date_batches(payload, receipt))
    rows = batch.to_pylist()
    rows[0]["date_role"] = "pbs_effective_date"
    rows[0]["date_source_field_id"] = None
    result = reconcile_pbs_date_occurrences([
        pa.RecordBatch.from_pylist(rows, schema=batch.schema)
    ])
    assert result["date_role_slots_without_source_field"] == 1


def test_duplicate_restriction_occurrences_count_once() -> None:
    payload = _production_xml().replace(
        b"</pbs:root>",
        b"<pbs:prescribing-texts-list><pbs:restriction><pbs:effective>"
        b"<pbs:date>2026-05-01</pbs:date></pbs:effective></pbs:restriction>"
        b"</pbs:prescribing-texts-list></pbs:root>",
    )
    receipt = _receipt(payload, "au-pbs")
    batch = next(iter_pbs_date_batches(payload, receipt))
    rows = batch.to_pylist()
    repeated_row = next(
        row
        for row in rows
        if any(
            field["schema_path"] == hosted_dates._RESTRICTION_DATE_PATH
            for field in row["native_fields"]
        )
    )
    rows.append(repeated_row)
    result = reconcile_pbs_date_occurrences([
        pa.RecordBatch.from_pylist(rows, schema=batch.schema)
    ])
    assert (
        result["occurrence_sets"]["restriction_effective_date_path"]["fields"]
        == 1
    )


def test_rejects_occurrence_identity_limit(monkeypatch) -> None:
    payload = _production_xml().replace(
        b"</pbs:root>",
        b"<pbs:prescribing-texts-list><pbs:restriction><pbs:effective>"
        b"<pbs:date>2026-05-01</pbs:date></pbs:effective></pbs:restriction>"
        b"</pbs:prescribing-texts-list></pbs:root>",
    )
    receipt = _receipt(payload, "au-pbs")
    monkeypatch.setattr(hosted_dates, "_MAX_IDENTITIES", 0)
    with pytest.raises(ValueError, match="identity limit exceeded"):
        reconcile_pbs_date_occurrences(iter_pbs_date_batches(payload, receipt))


def _hosted_inputs() -> SimpleNamespace:
    binding = SimpleNamespace(
        member_path="sch-2026-04-01-r1.xml",
        member_payload=SimpleNamespace(sha256="a" * 64),
        archive_payload=SimpleNamespace(sha256="b" * 64),
        digest=lambda: "c" * 64,
        parent_receipt_sha256="d" * 64,
    )
    return SimpleNamespace(
        xml=b"synthetic xml",
        archive=b"synthetic archive",
        parent=object(),
        binding=binding,
        context={"workflow_run_id": "40199999999"},
    )


def _qualifying_crosswalk() -> dict[str, object]:
    return {
        "status": "reconciled_by_exact_occurrence_identity",
        "occurrence_sets": {
            "restriction_effective_date_path": {"fields": 1},
            "item_effective_date_profile": {"fields": 1},
        },
        "join": {"overlap_fields": 0, "unmatched_total": 2},
    }


def _mock_hosted_reconciliation(monkeypatch, *, max_report_bytes: int) -> None:
    inputs = _hosted_inputs()
    monkeypatch.setattr(
        hosted_dates, "_verified_inputs", lambda _commit, **_kwargs: inputs
    )
    monkeypatch.setattr(
        hosted_dates,
        "_denominator",
        lambda _xml: {"native_digest": "e" * 64, "native_fields": 3},
    )
    monkeypatch.setattr(
        hosted_dates,
        "iter_pbs_historical_entity_batches",
        lambda _archive, _xml, _parent, _binding: (),
    )
    monkeypatch.setattr(
        hosted_dates, "_date_batches", lambda _entities, _profile, _size: ()
    )
    monkeypatch.setattr(
        hosted_dates,
        "reconcile_pbs_date_occurrences",
        lambda _batches: _qualifying_crosswalk(),
    )
    monkeypatch.setattr(hosted_dates, "_EXPECTED_RESTRICTION_FIELDS", 1)
    monkeypatch.setattr(hosted_dates, "_EXPECTED_ITEM_DATE_FIELDS", 1)
    monkeypatch.setattr(hosted_dates, "_EXPECTED_UNMATCHED_DATE_FIELDS", 2)
    monkeypatch.setattr(hosted_dates, "MAX_REPORT_BYTES", max_report_bytes)


def test_hosted_reconciliation_builds_bounded_report(monkeypatch) -> None:
    _mock_hosted_reconciliation(monkeypatch, max_report_bytes=100_000)
    result = hosted_dates.run_hosted_date_occurrence_reconciliation("a" * 40)
    assert result["status"] == "passed"
    assert result["crosswalk"] == _qualifying_crosswalk()
    assert result["source_values_emitted"] is False


def test_hosted_reconciliation_rejects_oversized_report(monkeypatch) -> None:
    _mock_hosted_reconciliation(monkeypatch, max_report_bytes=1)
    with pytest.raises(ValueError, match="report exceeds byte limit"):
        hosted_dates.run_hosted_date_occurrence_reconciliation("a" * 40)
