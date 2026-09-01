"""Assemble digest-bound transient PBS reference nodes fail closed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.pbs_hosted_qualification import (
    QualificationError,
    failure_report,
)
from global_medicines_atlas.pbs_member_identity import PbsXmlMemberBinding
from global_medicines_atlas.pbs_reference_shards import (
    assemble_reference_manifest,
)


def _node(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    raw: object = json.loads(path.read_bytes())
    if not isinstance(raw, dict):
        raise TypeError("PBS reference node receipt is invalid")
    raw = cast("dict[str, Any]", raw)
    if not isinstance(raw.get("report"), dict):
        raise TypeError("PBS reference node receipt is invalid")
    report = cast("dict[str, Any]", raw["report"])
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    if raw.get("report_sha256") != hashlib.sha256(encoded).hexdigest():
        raise ValueError("PBS reference node receipt digest changed")
    if report.get("status") != "prepared":
        return report, None
    if not isinstance(report.get("node"), dict):
        raise TypeError("PBS reference node receipt is invalid")
    return report, cast("dict[str, Any]", report["node"])


def _latest_nodes(
    directory: Path,
) -> dict[str, tuple[Path, dict[str, Any], dict[str, Any]]]:
    selected: dict[str, tuple[Path, dict[str, Any], dict[str, Any]]] = {}
    canonical: dict[str, dict[str, Any]] = {}
    for path in directory.glob("**/*-receipt.json"):
        report, node = _node(path)
        if node is None:
            continue
        kind = node.get("node_kind", report.get("node_kind"))
        if (
            kind == "index"
            or node.get("purpose") == "transient-reference-global-index"
        ):
            key = "index"
        else:
            partition = node.get("partition")
            if not isinstance(partition, dict):
                raise TypeError("PBS reference partition receipt is invalid")
            partition = cast("dict[str, Any]", partition)
            if type(partition.get("index")) is not int:
                raise TypeError("PBS reference partition receipt is invalid")
            key = f"partition:{cast('int', partition['index'])}"
        attempt = report.get("run_attempt")
        if not isinstance(attempt, str) or not attempt.isdigit():
            raise ValueError("PBS reference node attempt is invalid")
        previous = selected.get(key)
        if key in canonical and node != canonical[key]:
            raise ValueError("PBS reference node successful attempts conflict")
        canonical[key] = node
        if previous is None or int(attempt) > int(previous[1]["run_attempt"]):
            selected[key] = path, report, node
    return selected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reference-shards", required=True, type=int)
    return parser


def _run(args: argparse.Namespace) -> dict[str, Any]:
    selected = _latest_nodes(args.input)
    if set(selected) != {
        "index",
        *(f"partition:{i}" for i in range(args.reference_shards)),
    }:
        raise ValueError("PBS reference node coverage is incomplete")
    index_path, index_report, index_receipt = selected["index"]
    binding = PbsXmlMemberBinding.model_validate(index_receipt.get("binding"))
    denominator = cast("dict[str, Any]", index_receipt["denominator"])
    partition_receipts = [
        selected[f"partition:{index}"][2]
        for index in range(args.reference_shards)
    ]
    args.output.mkdir(parents=True, exist_ok=False)
    index_record = cast("dict[str, Any]", index_receipt["index"])
    index_source = index_path.parent / str(index_record["path"])
    (args.output / index_source.name).write_bytes(index_source.read_bytes())
    for index, receipt in enumerate(partition_receipts):
        record = cast("dict[str, Any]", receipt["partition"])
        source = selected[f"partition:{index}"][0].parent / str(record["path"])
        (args.output / source.name).write_bytes(source.read_bytes())
    manifest = assemble_reference_manifest(
        args.output,
        binding,
        denominator,
        index_receipt,
        partition_receipts,
    )
    manifest.update({
        "workflow_commit": index_receipt.get("workflow_commit"),
        "preparation_run_id": index_report.get("run_id"),
        "preparation_run_attempt": index_report.get("run_attempt"),
    })
    path = args.output / "reference-manifest.json"
    path.write_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    )
    return {
        "schema_version": 1,
        "status": "prepared",
        "operation": "pbs-reference-manifest-assembly",
        "workflow_commit": index_report["workflow_commit"],
        "run_id": index_report["run_id"],
        "run_attempt": index_report["run_attempt"],
        "reference_manifest_sha256": hashlib.sha256(
            path.read_bytes()
        ).hexdigest(),
        "publication_performed": False,
    }


def _write_receipt(output: Path, report: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    (output / "preparation-receipt.json").write_text(
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = _run(args)
    except Exception as error:  # Never serialize node/source-bearing text.
        category = (
            "structure"
            if isinstance(error, TypeError)
            else "validation"
            if isinstance(error, ValueError)
            else "unexpected"
        )
        report = failure_report(
            QualificationError("manifest-verification", category)
        )
        report["operation"] = "pbs-reference-manifest-assembly"
    _write_receipt(args.output, report)
    return 0 if report["status"] == "prepared" else 1


if __name__ == "__main__":
    raise SystemExit(main())
