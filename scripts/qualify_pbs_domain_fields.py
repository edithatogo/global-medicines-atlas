"""Write value-free semantics qualification from retained PBS receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from global_medicines_atlas.pbs_domain_field_semantics import (
    qualify_pbs_domain_fields,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "quality/qualifications/pbs-domain-field-semantics-20261025-v3.json"
        ),
    )
    args = parser.parse_args()
    report = qualify_pbs_domain_fields(args.root)
    report_bytes = json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    envelope = {
        "report": report,
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
    }
    destination = args.root / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(envelope, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
