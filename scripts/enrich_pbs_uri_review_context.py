"""Enrich the pinned PBS URI packet from its retained value-free context receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.pbs_uri_context_enrichment import (
    enrich_uri_review_packet,
)
from global_medicines_atlas.pbs_uri_review_packet_reconciler import (
    PACKET_FILENAME,
    ReconciliationError,
    write_new_envelope,
)

SCREEN_FILENAME = "pbs-native-reference-screen-20261025-40103169910.json"
URI_RECONCILIATION_FILENAME = (
    "pbs-native-reference-uri-review-reconciliation-20261025-40120162365.json"
)


def _read(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("evidence envelope is invalid")
    return cast("dict[str, Any]", value), hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve() / "quality/qualifications"
    try:  # ruff: ignore[too-many-statements-in-try-clause] -- exact receipt joins stay together for review
        packet, packet_sha = _read(root / PACKET_FILENAME)
        screen, screen_sha = _read(root / SCREEN_FILENAME)
        reconciliation, _ = _read(root / URI_RECONCILIATION_FILENAME)
        envelope = enrich_uri_review_packet(
            packet,
            screen,
            reconciliation,
            packet_file_sha256=packet_sha,
            screen_file_sha256=screen_sha,
        )
        output = args.output if args.output.is_absolute() else args.root / args.output
        write_new_envelope(envelope, output.resolve())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, ReconciliationError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
