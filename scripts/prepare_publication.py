"""Prepare a local publication plan and receipt; never perform an upload."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from global_medicines_atlas.publication_transport import (
    PublicationDestination,
    PublicationTarget,
    prepare_publication,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare local, content-addressed publication metadata."
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--release-version", required=True)
    parser.add_argument(
        "--destination",
        choices=tuple(item.value for item in PublicationDestination),
        required=True,
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--public-base-url", required=True)
    parser.add_argument(
        "--artifact",
        action="append",
        required=True,
        help="Root-relative POSIX path; repeat for each sorted artifact.",
    )
    parser.add_argument(
        "--recorded-at",
        type=datetime.fromisoformat,
        default=None,
        help="Aware ISO timestamp; defaults to current UTC time.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    recorded_at = args.recorded_at or datetime.now(UTC)
    target = PublicationTarget(
        destination=PublicationDestination(args.destination),
        repository=args.repository,
        revision=args.revision,
        public_base_url=args.public_base_url,
    )
    plan, receipt = prepare_publication(
        root=args.root,
        release_version=args.release_version,
        target=target,
        relative_paths=tuple(args.artifact),
        recorded_at=recorded_at,
    )
    print(
        json.dumps(
            {
                "plan": plan.model_dump(mode="json"),
                "receipt": receipt.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
