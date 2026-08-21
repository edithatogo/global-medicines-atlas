"""Rebuild portable B1 acquisition-metadata projections from native evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.bronze_acquisition_metadata import (
    B1AcquisitionMetadataManifest,
    acquisition_metadata_json_bytes,
    acquisition_metadata_parquet_bytes,
    reconstruct_b1_acquisition_metadata,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas/b1-acquisition-metadata-manifest-v1.json"


def _schema_bytes() -> bytes:
    return (
        json.dumps(
            B1AcquisitionMetadataManifest.model_json_schema(),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def main(argv: list[str] | None = None) -> int:
    """Rebuild JSON and Parquet without reading source payload contents."""

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--bronze-root", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--parquet-output", type=Path, required=True)
    parser.add_argument("--schema-output", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args(argv)

    manifest = reconstruct_b1_acquisition_metadata(args.bronze_root)
    outputs = (
        (args.json_output, acquisition_metadata_json_bytes(manifest)),
        (args.parquet_output, acquisition_metadata_parquet_bytes(manifest)),
        (args.schema_output, _schema_bytes()),
    )
    for path, content in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print(
        f"rebuilt {manifest.event_count} B1 acquisition events as "
        f"{manifest.manifest_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
