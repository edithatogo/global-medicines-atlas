"""Build or verify the deterministic stable-v1 monitoring receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Protocol, cast

from jsonschema import Draft202012Validator

from global_medicines_atlas.stable_v1_monitoring import (
    StableV1MonitoringReceipt,
    build_monitoring_receipt,
    verify_monitoring_receipt,
    write_monitoring_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "quality/qualifications/stable-v1-evidence-monitoring.json"
)
SCHEMA = ROOT / "schemas/stable-v1-monitoring-receipt-v1.json"


class _SchemaValidator(Protocol):
    def validate(self, instance: object) -> None: ...


def _validate_schema(receipt: StableV1MonitoringReceipt) -> None:
    schema: dict[str, Any] = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = cast("_SchemaValidator", Draft202012Validator(schema))
    validator.validate(receipt.model_dump(mode="json"))


def main() -> int:
    """Build the receipt or check a committed receipt without side effects."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()

    expected = build_monitoring_receipt(ROOT)
    _validate_schema(expected)
    output = arguments.output.resolve()
    if arguments.check:
        if not output.is_file():
            raise FileNotFoundError(f"monitoring receipt is missing: {output}")
        observed = StableV1MonitoringReceipt.model_validate_json(
            output.read_bytes()
        )
        _validate_schema(observed)
        verify_monitoring_receipt(observed, ROOT)
        if observed.canonical_json() != output.read_bytes():
            raise ValueError("monitoring receipt is not canonical JSON")
        return 0

    write_monitoring_receipt(output, expected)
    verify_monitoring_receipt(expected, ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
