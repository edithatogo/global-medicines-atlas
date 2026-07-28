"""Run bounded source-health probes and emit metadata-only JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Final, cast

from global_medicines_atlas.source_catalog import load_source_catalog
from global_medicines_atlas.source_health import (
    assess_schema_drift,
    drift_report_json,
    probe_sources,
)

SHA256_HEX_LENGTH: Final = 64


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/source-health.json"),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Previous metadata-only source-health report.",
    )
    parser.add_argument("--max-bytes", type=int, default=65_536)
    return parser.parse_args()


def load_baseline(path: Path | None) -> dict[str, str]:
    """Load fingerprints from a prior report, or start without a baseline."""

    if path is None or not path.exists():
        return {}
    document = cast("object", json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(document, dict):
        raise TypeError("baseline report must be a JSON object")
    typed_document = cast("dict[str, object]", document)
    baseline = typed_document.get("baseline")
    if not isinstance(baseline, dict):
        raise TypeError("baseline report has no fingerprint baseline")
    typed_baseline = cast("dict[object, object]", baseline)
    fingerprints: dict[str, str] = {}
    for source_id, fingerprint in typed_baseline.items():
        if (
            not isinstance(source_id, str)
            or not isinstance(fingerprint, str)
            or len(fingerprint) != SHA256_HEX_LENGTH
            or any(
                character not in "0123456789abcdef" for character in fingerprint
            )
        ):
            raise ValueError("baseline contains an invalid fingerprint")
        fingerprints[source_id] = fingerprint
    return fingerprints


def main() -> int:
    args = parse_args()
    previous = load_baseline(args.baseline)
    observations = probe_sources(
        load_source_catalog(),
        max_bytes=args.max_bytes,
    )
    assessments = assess_schema_drift(observations, previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        drift_report_json(observations, assessments),
        encoding="utf-8",
        newline="\n",
    )
    return int(any(item.state.value == "changed" for item in assessments))


if __name__ == "__main__":
    raise SystemExit(main())
