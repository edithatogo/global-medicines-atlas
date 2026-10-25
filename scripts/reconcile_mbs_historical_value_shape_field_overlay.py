"""Bind the 91-workbook value-shape receipt to unchanged field states."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from global_medicines_atlas.mbs_historical_value_shape_field_overlay import (  # ruff: ignore[module-import-not-at-top-of-file]
    FIELD_STATE_SHA256,
    bind_value_shape_overlay,
)

FIELD_STATE_PATH = ROOT / (
    "quality/qualifications/mbs-workbook-field-state-reconciliation-20261025.json"
)


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path.name} must contain a JSON object")
    return cast("dict[str, Any]", value)


def reconcile(value_shape_path: Path, workflow_run_id: int) -> dict[str, Any]:
    field_state_bytes = FIELD_STATE_PATH.read_bytes()
    field_state_sha256 = hashlib.sha256(field_state_bytes).hexdigest()
    if field_state_sha256 != FIELD_STATE_SHA256:
        raise ValueError("bound MBS field-state report digest differs")
    value_shape_bytes = value_shape_path.read_bytes()
    value_shape_sha256 = hashlib.sha256(value_shape_bytes).hexdigest()
    return bind_value_shape_overlay(
        json.loads(field_state_bytes),
        _read_object(value_shape_path),
        field_state_sha256=field_state_sha256,
        value_shape_sha256=value_shape_sha256,
        workflow_run_id=workflow_run_id,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--value-shape-cohort", required=True, type=Path)
    parser.add_argument("--workflow-run-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = reconcile(args.value_shape_cohort, args.workflow_run_id)
    payload = (
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError("existing value-shape overlay must be preserved")
    args.output.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
