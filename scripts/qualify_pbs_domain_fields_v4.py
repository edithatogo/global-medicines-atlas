"""Write the PBS v4 semantics successor bound to exact schema metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from global_medicines_atlas.pbs_domain_field_semantics import (
    qualify_pbs_domain_fields_v4,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "quality/qualifications/pbs-domain-field-semantics-20261025-v4.json"
        ),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    report = qualify_pbs_domain_fields_v4(root)
    canonical = json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    envelope = {
        "report": report,
        "report_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(
            envelope, stream, sort_keys=True, indent=2, ensure_ascii=False
        )
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
