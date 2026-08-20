"""Generate the exhaustive Bronze source-family landing work queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.source_catalog import load_catalog
from global_medicines_atlas.source_landing_factory import (
    LandingOverrides,
    SourceLandingQueue,
    build_source_landing_queue,
    render_conductor_queue,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = (
    ROOT / "quality" / "qualifications" / "bronze-source-landing-queue.json"
)
DEFAULT_SCHEMA = ROOT / "schemas" / "bronze-source-landing-queue-v1.json"
DEFAULT_MARKDOWN = (
    ROOT / "conductor" / "generated" / "bronze-source-landing-queue.md"
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: list[str] | None = None) -> int:
    """Write JSON, JSON Schema, and Conductor Markdown projections."""

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--schema-output", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--markdown-output", type=Path, default=DEFAULT_MARKDOWN
    )
    args = parser.parse_args(argv)

    queue = build_source_landing_queue(
        load_catalog(),
        LandingOverrides.load(),
    )
    _write_json(args.json_output, queue.model_dump(mode="json"))
    _write_json(args.schema_output, SourceLandingQueue.model_json_schema())
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(
        render_conductor_queue(queue),
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"generated {queue.source_count} source work items across "
        f"{len(queue.family_counts)} adapter families"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
