"""Keep exact digest/path matches separate from complete B1/B2 lineage."""

from __future__ import annotations

from typing import cast

from scripts.reconcile_m112_projected_b1_b2_path_joins import (
    EXPECTED_COMPLETE_LINEAGES_WITHIN_EXISTING_PATH_JOINS,
    OVERLAY,
    SOURCE_ARCHIVE,
    UTILISATION,
    count_complete_lineages_for_keys,
    read_json,
)


def test_exact_digest_path_matches_do_not_equal_complete_lineages() -> None:
    overlay = read_json(OVERLAY)
    utilisation = read_json(UTILISATION)
    source_archive = read_json(SOURCE_ARCHIVE)
    raw_objects = [
        row
        for row in overlay["objects"]
        if row["candidate_class"] == "raw_source_payload"
    ]
    digest_path_rows = [
        *utilisation["verified_objects"],
        *source_archive["verified_objects"],
        *overlay["retained_evidence_join_increment"]["new_joins"],
    ]
    exact_keys = cast(
        "set[tuple[str, str, str]]",
        {
            (
                row["dataset"],
                row.get("revision", row.get("dataset_revision")),
                row["path"],
            )
            for row in digest_path_rows
        },
    )

    assert len(exact_keys) == 26
    assert (
        count_complete_lineages_for_keys(raw_objects, exact_keys)
        == EXPECTED_COMPLETE_LINEAGES_WITHIN_EXISTING_PATH_JOINS
    )
    assert sum(row["b1_b2_lineage"]["complete"] for row in raw_objects) == 6
