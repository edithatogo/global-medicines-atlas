"""Generate deterministic B0 Source Index projections and metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from global_medicines_atlas.bronze_source_index import (
    B0SourceIndex,
    build_b0_source_index,
    build_b0_source_index_dataset_metadata,
    render_b0_source_index_markdown,
    source_index_parquet_bytes,
)
from global_medicines_atlas.source_catalog import load_catalog
from global_medicines_atlas.source_landing_factory import (
    LandingOverrides,
    build_source_landing_queue,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "quality/qualifications/bronze-source-index-v1.json"
DEFAULT_PARQUET = ROOT / "quality/qualifications/bronze-source-index-v1.parquet"
DEFAULT_SCHEMA = ROOT / "schemas/bronze-source-index-v1.json"
DEFAULT_MARKDOWN = ROOT / "docs/data-sources/bronze-source-index.md"
DEFAULT_METADATA = (
    ROOT / "quality/qualifications/bronze-source-index-dataset-metadata.json"
)


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode()


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main(argv: list[str] | None = None) -> int:
    """Write JSON, Parquet, schema, documentation, and citation metadata."""

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--parquet-output", type=Path, default=DEFAULT_PARQUET)
    parser.add_argument("--schema-output", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--markdown-output", type=Path, default=DEFAULT_MARKDOWN
    )
    parser.add_argument(
        "--metadata-output", type=Path, default=DEFAULT_METADATA
    )
    args = parser.parse_args(argv)

    catalog = load_catalog()
    queue = build_source_landing_queue(catalog, LandingOverrides.load())
    index = build_b0_source_index(catalog, queue)
    json_content = _json_bytes(index.model_dump(mode="json"))
    parquet_content = source_index_parquet_bytes(index)
    metadata = build_b0_source_index_dataset_metadata(
        index,
        json_sha256=hashlib.sha256(json_content).hexdigest(),
        parquet_sha256=hashlib.sha256(parquet_content).hexdigest(),
    )

    _write(args.json_output, json_content)
    _write(args.parquet_output, parquet_content)
    _write(args.schema_output, _json_bytes(B0SourceIndex.model_json_schema()))
    _write(
        args.markdown_output, render_b0_source_index_markdown(index).encode()
    )
    _write(args.metadata_output, _json_bytes(metadata))
    print(f"generated {index.snapshot_id} with {index.source_count} B0 sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
