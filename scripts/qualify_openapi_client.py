"""Snapshot, diff, and generate the public read-only OpenAPI client."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.api import create_app
from global_medicines_atlas.openapi_client_generator import generate_client
from global_medicines_atlas.openapi_semantic import (
    assert_semantically_compatible,
    semantic_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "contracts/openapi-readonly-v1.json"
CLIENT = ROOT / "src/global_medicines_atlas/generated/openapi_client.py"


def _document() -> dict[str, Any]:
    return create_app(cast("Any", object())).openapi()


def _render_snapshot(document: dict[str, Any]) -> str:
    return (
        json.dumps(semantic_snapshot(document), indent=2, sort_keys=True) + "\n"
    )


def main() -> int:
    """Check committed artifacts or regenerate them deterministically."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    document = _document()
    rendered_snapshot = _render_snapshot(document)
    snapshot = json.loads(rendered_snapshot)
    rendered_client = generate_client(snapshot)
    if arguments.write:
        SNAPSHOT.write_text(rendered_snapshot, encoding="utf-8", newline="\n")
        CLIENT.parent.mkdir(parents=True, exist_ok=True)
        CLIENT.write_text(rendered_client, encoding="utf-8", newline="\n")
        return 0
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert_semantically_compatible(committed, document)
    if SNAPSHOT.read_text(encoding="utf-8") != rendered_snapshot:
        raise SystemExit("OpenAPI snapshot is stale; run with --write")
    if CLIENT.read_text(encoding="utf-8") != rendered_client:
        raise SystemExit("generated OpenAPI client is stale; run with --write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
