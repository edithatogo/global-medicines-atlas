"""Build and optionally upload the no-credential data-layer archive."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from global_medicines_atlas.data_layer_archive import (
    ARCHIVE_REVISION,
    CATALOGUE_PUBLIC_URL,
    CATALOGUE_REPOSITORY,
    HttpPayloadRetriever,
    HuggingFaceAuthError,
    HuggingFaceCliUploader,
    build_data_layer_archive,
    huggingface_external_gate_stdout,
    parse_authority_groups,
    write_huggingface_external_gate,
)
from global_medicines_atlas.publication_transport import (
    PublicationDestination,
    PublicationTarget,
    authorization_from_environment,
    execute_publication,
    prepare_publication,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Package FDA, EMA, TGA, and Medsafe public artefacts plus "
            "catalogue metadata for Hugging Face."
        )
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/data-layer-archive"),
    )
    parser.add_argument(
        "--retrieve",
        action="store_true",
        help="Fetch public/no-credential FDA, EMA, TGA, and Medsafe artefacts.",
    )
    parser.add_argument(
        "--authorities",
        default="fda,ema,tga,medsafe",
        help="Comma-separated archival authorities.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Upload an already packaged output directory.",
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


def _existing_relative_paths(directory: Path) -> tuple[str, ...]:
    paths = [
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    ]
    return tuple(sorted(paths))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.upload and os.environ.get("GITHUB_ACTIONS") != "true":
        raise PermissionError(
            "dataset archive uploads must run in GitHub Actions"
        )
    recorded_at = args.recorded_at or datetime.now(UTC)
    target = PublicationTarget(
        destination=PublicationDestination.HUGGING_FACE,
        repository=CATALOGUE_REPOSITORY,
        revision=ARCHIVE_REVISION,
        public_base_url=CATALOGUE_PUBLIC_URL,
    )
    skipped: list[str] = []
    if args.skip_build:
        relative_paths = _existing_relative_paths(args.output_dir)
        manifest_path = args.output_dir / "inventory" / "archival-manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            skipped = list(manifest.get("skipped_source_ids", []))
    else:
        retriever = HttpPayloadRetriever() if args.retrieve else None
        package = build_data_layer_archive(
            args.root,
            args.output_dir,
            retriever=retriever,
            authority_groups=parse_authority_groups(args.authorities),
        )
        relative_paths = tuple(item.relative_path for item in package.files)
        target = package.target
        skipped = [
            row.source_id
            for row in package.inventory.sources
            if row.skip_reason
        ]
    plan, receipt = prepare_publication(
        root=args.output_dir,
        release_version=ARCHIVE_REVISION,
        target=target,
        relative_paths=relative_paths,
        recorded_at=recorded_at,
    )
    payload: dict[str, object] = {
        "plan": plan.model_dump(mode="json"),
        "receipt": receipt.model_dump(mode="json"),
        "skipped_source_ids": skipped,
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
