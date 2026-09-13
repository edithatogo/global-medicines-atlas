"""Bounded file loading for the history CLI."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from global_medicines_atlas.historical_change import (
    compare_historical_snapshots,
)
from global_medicines_atlas.historical_change_configuration import (
    MAX_HISTORY_EVIDENCE_BYTES,
    load_historical_change_service,
)
from global_medicines_atlas.historical_comparison import (
    NativeField,
    NativeRow,
    NativeSnapshot,
)


def _snapshot(value: str) -> NativeSnapshot:
    return NativeSnapshot(
        source_id="au-mbs",
        table="benefits",
        dimension="service_benefit",
        schema_era="2026-09",
        identity_profile="mbs-item",
        source_revision="2026-09",
        source_path="benefits.parquet",
        b1_sha256="a" * 64,
        b2_sha256="b" * 64,
        observed_at=datetime(2026, 9, 14, tzinfo=UTC),
        cohort="historical",
        declared_rows=1,
        complete=True,
        rows=(
            NativeRow(
                native_id="1001",
                occurrence_id="1001",
                fields=(
                    NativeField(name="benefit", state="value", value=value),
                ),
            ),
        ),
    )


def test_loader_revalidates_bounded_history_document(tmp_path: Path) -> None:
    change = compare_historical_snapshots(_snapshot("100"), _snapshot("110"))
    path = tmp_path / "history.json"
    path.write_text(
        json.dumps({
            "version": "1.0",
            "changes": [change.model_dump(mode="json")],
        })
    )

    page = load_historical_change_service(path).page(limit=1)

    assert page.total == 1
    assert page.items == (change,)


@pytest.mark.parametrize("path_kind", ["directory", "oversized"])
def test_loader_rejects_nonregular_or_oversized_input(
    tmp_path: Path, path_kind: str
) -> None:
    path = tmp_path / "history.json"
    if path_kind == "directory":
        path.mkdir()
        message = "regular file"
    else:
        path.write_bytes(b" " * (MAX_HISTORY_EVIDENCE_BYTES + 1))
        message = "byte bound"

    with pytest.raises(ValueError, match=message):
        load_historical_change_service(path)


@pytest.mark.parametrize(
    ("document", "message"),
    [({}, "Field required"), ({"version": "2.0", "changes": []}, "1.0")],
)
def test_loader_rejects_invalid_document(
    tmp_path: Path, document: dict[str, object], message: str
) -> None:
    path = tmp_path / "history.json"
    path.write_text(json.dumps(document))

    with pytest.raises(ValueError, match=message):
        load_historical_change_service(path)
