"""Fail-closed contracts for resumable PBS preparation nodes."""

import hashlib
import json
from pathlib import Path

import pytest
from scripts import assemble_historical_pbs_reference_manifest as assemble
from scripts import prepare_historical_pbs_reference_node as node_cli


def _receipt(
    path: Path,
    *,
    attempt: int,
    index: int,
    digest: str,
    status: str = "prepared",
) -> None:
    node = {
        "purpose": "transient-reference-entity-partition",
        "partition": {"index": index, "sha256": digest},
    }
    report = {
        "status": status,
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


def _material_receipt(
    path: Path, *, attempt: int, digest: str, status: str = "prepared"
) -> None:
    report = {
        "status": status,
        "run_attempt": str(attempt),
        "node": {"contract_sha256": digest},
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
        digest="same",
    )
    _receipt(
        tmp_path / "attempt-2" / "reference-00-receipt.json",
        attempt=2,
        index=0,
        digest="same",
    )

    selected = assemble._latest_nodes(tmp_path)  # pyright: ignore[reportPrivateUsage]

    assert selected["partition:0"][1]["run_attempt"] == "2"
    assert selected["partition:0"][2]["partition"]["sha256"] == "same"


def test_divergent_successful_attempts_are_rejected(tmp_path: Path) -> None:
    _receipt(
        tmp_path / "copy-a" / "reference-00-receipt.json",
        attempt=1,
        index=0,
        digest="a",
    )
    _receipt(
        tmp_path / "copy-b" / "reference-00-receipt.json",
        attempt=2,
        index=0,
        digest="b",
    )

    with pytest.raises(ValueError, match="successful attempts conflict"):
        assemble._latest_nodes(tmp_path)  # pyright: ignore[reportPrivateUsage]


def test_failed_attempt_is_ignored_before_later_success(tmp_path: Path) -> None:
    _receipt(
        tmp_path / "attempt-1" / "reference-00-receipt.json",
        attempt=1,
        index=0,
        digest="failed",
        status="failed",
    )
    _receipt(
        tmp_path / "attempt-2" / "reference-00-receipt.json",
        attempt=2,
        index=0,
        digest="success",
    )
    selected = assemble._latest_nodes(tmp_path)  # pyright: ignore[reportPrivateUsage]
    assert selected["partition:0"][1]["run_attempt"] == "2"


def test_entity_attempt_selection_rejects_divergent_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        node_cli, "load_reference_entity_material", lambda *_: None
    )
    _material_receipt(
        tmp_path / "attempt-1" / "reference-entities-receipt.json",
        attempt=1,
        digest="a",
    )
    _material_receipt(
        tmp_path / "attempt-2" / "reference-entities-receipt.json",
        attempt=2,
        digest="b",
    )
    with pytest.raises(ValueError, match="successful attempts conflict"):
        node_cli._material_report(tmp_path, None)  # pyright: ignore[reportPrivateUsage]


def test_entity_attempt_selection_ignores_failed_and_uses_latest_identical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        node_cli, "load_reference_entity_material", lambda *_: None
    )
    _material_receipt(
        tmp_path / "failed" / "reference-entities-receipt.json",
        attempt=1,
        digest="failed",
        status="failed",
    )
    for attempt in (2, 3):
        _material_receipt(
            tmp_path / str(attempt) / "reference-entities-receipt.json",
            attempt=attempt,
            digest="same",
        )
    directory, report = node_cli._material_report(  # pyright: ignore[reportPrivateUsage]
        tmp_path, None
    )
    assert directory.name == "3"
    assert report["run_attempt"] == "3"


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
    assert workflow.count("--entity-material") == 1
    assert workflow.count("name: pbs-reference-entity-partition-") == 16
    assert "pattern: pbs-reference-index-input-" in workflow
    assert (
        "pattern: pbs-reference-entity-partition-${{ matrix.key }}-" in workflow
    )
    assert "--input material --output node" in workflow
    assert "max-parallel: 3" in workflow
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
    entity = workflow.split("  prepare-reference-entities:\n", 1)[1].split(
        "  prepare-reference-index:\n", 1
    )[0]
    assert "needs: qualify" in entity
    assert "if: always()" in entity
