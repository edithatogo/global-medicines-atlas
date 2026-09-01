"""Fail-closed contracts for resumable PBS preparation nodes."""

import hashlib
import json
from pathlib import Path

import pytest
from scripts import assemble_historical_pbs_reference_manifest as assemble


def _receipt(path: Path, *, attempt: int, index: int, digest: str) -> None:
    node = {
        "purpose": "transient-reference-entity-partition",
        "partition": {"index": index, "sha256": digest},
    }
    report = {
        "status": "prepared",
        "run_attempt": str(attempt),
        "node_kind": "partition",
        "node": node,
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "report": report,
            "report_sha256": hashlib.sha256(encoded).hexdigest(),
        }),
        encoding="utf-8",
    )


def test_latest_successful_node_is_selected_across_attempts(
    tmp_path: Path,
) -> None:
    _receipt(
        tmp_path / "attempt-1" / "reference-00-receipt.json",
        attempt=1,
        index=0,
        digest="old",
    )
    _receipt(
        tmp_path / "attempt-2" / "reference-00-receipt.json",
        attempt=2,
        index=0,
        digest="new",
    )

    selected = assemble._latest_nodes(tmp_path)  # pyright: ignore[reportPrivateUsage]

    assert selected["partition:0"][1]["run_attempt"] == "2"
    assert selected["partition:0"][2]["partition"]["sha256"] == "new"


def test_same_attempt_conflicting_node_is_rejected(tmp_path: Path) -> None:
    _receipt(
        tmp_path / "copy-a" / "reference-00-receipt.json",
        attempt=2,
        index=0,
        digest="a",
    )
    _receipt(
        tmp_path / "copy-b" / "reference-00-receipt.json",
        attempt=2,
        index=0,
        digest="b",
    )

    with pytest.raises(ValueError, match="duplicate conflicts"):
        assemble._latest_nodes(tmp_path)  # pyright: ignore[reportPrivateUsage]


def test_manifest_assembly_failure_writes_bounded_receipt(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    assert (
        assemble.main([
            "--input",
            str(tmp_path / "missing"),
            "--output",
            str(output),
            "--reference-shards",
            "16",
        ])
        == 1
    )
    raw = (output / "preparation-receipt.json").read_text(encoding="utf-8")
    report = json.loads(raw)["report"]
    assert report["failure_stage"] == "manifest-verification"
    assert report["failure_category"] == "validation"
    assert report["publication_performed"] is False


def test_workflow_disaggregates_preparation_without_raw_artifacts() -> None:
    workflow = Path(
        ".github/workflows/pbs-historical-qualification.yml"
    ).read_text(encoding="utf-8")
    assert "prepare-reference-index:" in workflow
    assert "prepare-reference-partitions:" in workflow
    assert "max-parallel: 4" in workflow
    assert "prepare_historical_pbs_reference_node.py" in workflow
    assert "assemble_historical_pbs_reference_manifest.py" in workflow
    assert "pattern: pbs-reference-node-*-${{ github.run_id }}-*" in workflow
    assert "archive.zip" not in workflow
    assert "member.xml" not in workflow
    phase = workflow.split("  qualify:\n", 1)[1].split(
        "  qualify-references:\n", 1
    )[0]
    assert "needs:" not in phase
