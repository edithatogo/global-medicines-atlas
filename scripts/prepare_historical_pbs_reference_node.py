"""Prepare one bounded transient PBS reference DAG node on main Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.pbs_hosted_qualification import (
    failure_report,
    run_hosted_entity_material,
    run_prepared_reference_node,
)
from global_medicines_atlas.pbs_reference_shards import (
    load_reference_entity_material,
    load_reference_entity_partition,
)


def _write(path: Path, report: dict[str, Any]) -> None:
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "report": report,
                "report_sha256": hashlib.sha256(payload).hexdigest(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _material_report(
    directory: Path, shard_index: int | None
) -> tuple[Path, dict[str, Any]]:
    successes: list[tuple[Path, dict[str, Any]]] = []
    for path in directory.glob("**/reference-entities-receipt.json"):
        wrapper: object = json.loads(path.read_bytes())
        if not isinstance(wrapper, dict):
            raise TypeError("PBS entity material receipt is invalid")
        wrapper = cast("dict[str, Any]", wrapper)
        if not isinstance(wrapper.get("report"), dict):
            raise TypeError("PBS entity material receipt is invalid")
        report = cast("dict[str, Any]", wrapper["report"])
        encoded = json.dumps(
            report, sort_keys=True, separators=(",", ":")
        ).encode()
        if wrapper.get("report_sha256") != hashlib.sha256(encoded).hexdigest():
            raise ValueError("PBS entity material receipt digest changed")
        if report.get("status") != "prepared":
            continue
        if (
            not isinstance(report.get("node"), dict)
            or not isinstance(report.get("run_attempt"), str)
            or not report["run_attempt"].isdigit()
        ):
            raise TypeError("PBS entity material receipt is invalid")
        material_directory = (
            path.parent if shard_index is None else path.parent / "node"
        )
        try:
            if shard_index is None:
                load_reference_entity_material(
                    material_directory, cast("dict[str, Any]", report["node"])
                )
            else:
                load_reference_entity_partition(
                    material_directory,
                    cast("dict[str, Any]", report["node"]),
                    shard_index,
                )
        except OSError, TypeError, ValueError:
            continue
        successes.append((material_directory, report))
    if not successes:
        raise ValueError("PBS entity material did not prepare")
    expected = successes[0][1]["node"]
    if any(report["node"] != expected for _, report in successes[1:]):
        raise ValueError("PBS entity material successful attempts conflict")
    return max(successes, key=lambda item: int(item[1]["run_attempt"]))


def _run(
    args: argparse.Namespace,
    checkpoint: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    if args.entity_material:
        if args.input is not None or args.shard_index is not None:
            raise ValueError("invalid PBS entity material node arguments")
        return run_hosted_entity_material(
            args.exact_commit,
            args.output,
            shard_count=args.reference_shards,
            progress=checkpoint,
        )
    if args.input is None:
        raise ValueError("PBS entity material input is required")
    material_directory, material = _material_report(
        args.input, args.shard_index
    )
    return run_prepared_reference_node(
        args.exact_commit,
        material_directory,
        cast("dict[str, Any]", material["node"]),
        args.output,
        shard_count=args.reference_shards,
        shard_index=args.shard_index,
        preparation_run_id=str(material.get("run_id")),
        preparation_run_attempt=str(material.get("run_attempt")),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--reference-shards", required=True, type=int)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--entity-material", action="store_true")
    parser.add_argument("--input", type=Path)
    args = parser.parse_args(argv)
    checkpoints: list[dict[str, Any]] = []

    def checkpoint(report: dict[str, Any]) -> None:
        checkpoints.append(report)
        bounded = dict(report)
        bounded.update({
            "operation": "pbs-reference-node-preparation",
            "publication_performed": False,
        })
        _write(args.receipt, bounded)

    try:
        report = _run(args, checkpoint)
    except Exception as error:  # Never serialize source-bearing exception text.
        report = failure_report(error)
        report.update({
            "operation": "pbs-reference-node-preparation",
            "publication_performed": False,
        })
        if checkpoints and isinstance(
            progress := checkpoints[-1].get("progress"), dict
        ):
            progress = cast("dict[str, Any]", progress)
            report["progress"] = progress
            stage = progress.get("stage")
            if isinstance(stage, str):
                report["failure_stage"] = stage
    _write(args.receipt, report)
    return 0 if report["status"] == "prepared" else 1


if __name__ == "__main__":
    raise SystemExit(main())
