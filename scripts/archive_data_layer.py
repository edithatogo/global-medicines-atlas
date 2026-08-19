"""Build and optionally upload the no-credential data-layer archive."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from global_medicines_atlas.data_layer_archive import (
    ARCHIVE_REVISION,
    HuggingFaceAuthError,
    HuggingFaceCliUploader,
    build_data_layer_archive,
    huggingface_external_gate_stdout,
    write_huggingface_external_gate,
)
from global_medicines_atlas.publication_transport import (
    authorization_from_environment,
    execute_publication,
    prepare_publication,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Package catalogue metadata and governed fixtures for Hugging Face."
        )
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/data-layer-archive"),
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Execute the dual-gated Hugging Face upload.",
    )
    parser.add_argument(
        "--recorded-at",
        type=datetime.fromisoformat,
        default=None,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    recorded_at = args.recorded_at or datetime.now(UTC)
    package = build_data_layer_archive(args.root, args.output_dir)
    relative_paths = tuple(item.relative_path for item in package.files)
    plan, receipt = prepare_publication(
        root=args.output_dir,
        release_version=ARCHIVE_REVISION,
        target=package.target,
        relative_paths=relative_paths,
        recorded_at=recorded_at,
    )
    payload: dict[str, object] = {
        "plan": plan.model_dump(mode="json"),
        "receipt": receipt.model_dump(mode="json"),
        "skipped_source_ids": [
            row.source_id
            for row in package.inventory.sources
            if row.skip_reason
        ],
    }
    if args.upload:
        try:
            uploaded = execute_publication(
                plan=plan,
                authorization=authorization_from_environment(os.environ),
                root=args.output_dir,
                uploader=HuggingFaceCliUploader(),
                recorded_at=recorded_at,
            )
        except HuggingFaceAuthError:
            record_path = write_huggingface_external_gate(args.output_dir)
            payload["external_gate"] = huggingface_external_gate_stdout(
                record_path.name
            )
        else:
            payload["receipt"] = uploaded.model_dump(mode="json")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
