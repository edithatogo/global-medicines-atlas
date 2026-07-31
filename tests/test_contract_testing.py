"""Consumer/provider contracts for the versioned read-only API."""

import json
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.api import create_app
from global_medicines_atlas.openapi_semantic import (
    assert_semantically_compatible,
    semantic_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


def test_provider_satisfies_published_read_only_consumer_contract() -> None:
    """The live provider may extend but must not break the v1 contract."""

    baseline = cast(
        "dict[str, Any]",
        json.loads(
            (ROOT / "contracts/openapi-readonly-v1.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    provider = cast(
        "dict[str, Any]", create_app(cast("Any", object())).openapi()
    )

    assert_semantically_compatible(baseline, provider)


def test_provider_contract_is_read_only_and_deterministic() -> None:
    """Repeated provider snapshots must be byte-equivalent semantic objects."""

    first = cast("dict[str, Any]", create_app(cast("Any", object())).openapi())
    second = cast("dict[str, Any]", create_app(cast("Any", object())).openapi())

    assert semantic_snapshot(first) == semantic_snapshot(second)
