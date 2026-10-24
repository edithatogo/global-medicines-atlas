"""Exact PBS date identity crosswalk remains value-free."""

from test_au_pbs_v3 import (
    _production_xml,  # ruff: ignore[import-private-name] -- synthetic fixture
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic fixture
)

from global_medicines_atlas.pbs_date_occurrence_reconciliation import (
    build_pbs_date_occurrence_crosswalk,
    reconcile_pbs_date_occurrences,
)
from global_medicines_atlas.pbs_dates import iter_pbs_date_batches


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
