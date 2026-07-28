from hashlib import sha256

import pytest
from pydantic import ValidationError

from global_medicines_atlas.matching_indexes import (
    MatchingIndexLineage,
    MatchingIndexRow,
    build_manifest,
)
from global_medicines_atlas.receipts import RightsState


def _lineage() -> MatchingIndexLineage:
    return MatchingIndexLineage(
        index_version="matching-v1",
        embedding_provider="external-test",
        embedding_model="fixture-vector",
        embedding_version="1",
        generation_command="generate_matching_indexes.py rows lineage output",
        source_snapshot_sha256=sha256(b"snapshot").hexdigest(),
        rights_state=RightsState.RESTRICTED,
        redistributable=False,
    )


def _rows() -> tuple[MatchingIndexRow, ...]:
    return (
        MatchingIndexRow(
            concept_id="nz:1",
            mapping_level="ingredient",
            source_snapshot_id="snapshot-1",
            schema_version="1",
            text_selection_version="names-v1",
            embedding=(0.1, 0.2),
        ),
        MatchingIndexRow(
            concept_id="au:2",
            mapping_level="product",
            source_snapshot_id="snapshot-1",
            schema_version="1",
            text_selection_version="names-v1",
            embedding=(0.3, 0.4),
        ),
    )


def test_manifest_is_order_independent_and_content_addressed() -> None:
    first = build_manifest(_rows(), _lineage())
    second = build_manifest(reversed(_rows()), _lineage())

    assert first == second
    assert first.row_count == 2
    assert first.dimensions == 2


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ((), "at least one"),
        ((_rows()[0], _rows()[0]), "identifiers"),
        (
            (
                _rows()[0],
                _rows()[1].model_copy(update={"embedding": (0.3,)}),
            ),
            "equal dimensions",
        ),
    ],
)
def test_manifest_rejects_non_regenerable_rows(rows, message) -> None:
    with pytest.raises(ValueError, match=message):
        build_manifest(rows, _lineage())


def test_redistribution_requires_permitted_reviewed_rights() -> None:
    with pytest.raises(ValidationError):
        _lineage().model_copy(
            update={"redistributable": True},
        ).model_validate({
            **_lineage().model_dump(),
            "redistributable": True,
        })
