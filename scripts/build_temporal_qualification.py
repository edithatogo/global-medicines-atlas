"""Build or verify a deterministic fixture-only temporal qualification manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.snapshots import (
    build_fixture_snapshot_manifest,
    verify_snapshot_manifest,
    write_snapshot_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--input", action="append", type=Path, default=[])
    parser.add_argument("--output", action="append", type=Path, default=[])
    parser.add_argument("--source-catalog", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset-schema-id")
    parser.add_argument("--dataset-schema-version")
    parser.add_argument("--package-commit")
    parser.add_argument("--command", action="append", default=[])
    parser.add_argument("--verify", action="store_true")
    return parser


def main() -> None:
    """Run fixture-only manifest generation or verification."""
    arguments = _parser().parse_args()
    if arguments.verify:
        verify_snapshot_manifest(
            arguments.manifest,
            fixture_root=arguments.fixture_root,
            source_catalog_path=arguments.source_catalog,
        )
        print(f"verified fixture-only manifest: {arguments.manifest}")
        return

    required = {
        "--dataset-schema-id": arguments.dataset_schema_id,
        "--dataset-schema-version": arguments.dataset_schema_version,
        "--package-commit": arguments.package_commit,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        _parser().error(f"generation requires: {', '.join(missing)}")
    manifest = build_fixture_snapshot_manifest(
        fixture_root=arguments.fixture_root,
        input_paths=arguments.input,
        output_paths=arguments.output,
        source_catalog_path=arguments.source_catalog,
        dataset_schema_id=arguments.dataset_schema_id,
        dataset_schema_version=arguments.dataset_schema_version,
        transformation_command=arguments.command,
        package_commit=arguments.package_commit,
    )
    write_snapshot_manifest(manifest, arguments.manifest)
    print(f"wrote fixture-only manifest: {arguments.manifest}")


if __name__ == "__main__":
    main()
