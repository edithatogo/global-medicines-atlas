"""Validate publication identities and optionally enforce release readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.publication_contracts import (
    PublicationIdentityRegistry,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "quality/qualifications/publication-identities.json"


def load_registry(path: Path = DEFAULT_REGISTRY) -> PublicationIdentityRegistry:
    return PublicationIdentityRegistry.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--require-publishable", action="store_true")
    args = parser.parse_args()
    registry = load_registry(args.registry)
    if args.require_publishable:
        registry.assert_publishable()
    print(
        json.dumps(
            {
                "blocking_reasons": registry.blocking_reasons(),
                "publishable": not registry.blocking_reasons(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
