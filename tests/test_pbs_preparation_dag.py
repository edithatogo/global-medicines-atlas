"""Fail-closed contracts for resumable PBS preparation nodes."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

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


def test_group_receipt_expands_to_exact_partition_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    partition = {
        "index": 0,
        "count": 4,
        "path": "reference-00.arrow",
    }
    node = {
        "purpose": "transient-reference-partition-group",
        "group": {"index": 0},
        "binding_sha256": "binding",
        "denominator": {"elements": 4},
    }
    report = {
        "status": "prepared",
        "run_attempt": "2",
        "node_kind": "partition-group",
        "node": node,
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    path = tmp_path / "reference-group-0-receipt.json"
    path.write_text(
        json.dumps({
            "report": report,
            "report_sha256": hashlib.sha256(encoded).hexdigest(),
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        assemble,
        "validate_reference_partition_group",
        lambda *_: (object(), {"elements": 4}, [partition]),
    )

    selected = assemble._latest_nodes(tmp_path)  # pyright: ignore[reportPrivateUsage]

    assert selected["partition:0"][2]["purpose"] == (
        "transient-reference-entity-partition"
    )
    assert selected["partition:0"][2]["partition"] == partition


def test_eight_pair_receipts_expand_to_exact_sixteen_partition_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for group_index in range(8):
        node = {
            "purpose": "transient-reference-partition-group",
            "group": {"index": group_index},
            "binding_sha256": "binding",
            "denominator": {"elements": 16},
        }
        report = {
            "status": "prepared",
            "run_attempt": "1",
            "node_kind": "partition-group",
            "node": node,
        }
        encoded = json.dumps(
            report, sort_keys=True, separators=(",", ":")
        ).encode()
        path = (
            tmp_path
            / f"group-{group_index}"
            / (f"reference-group-{group_index}-receipt.json")
        )
        path.parent.mkdir()
        path.write_text(
            json.dumps({
                "report": report,
                "report_sha256": hashlib.sha256(encoded).hexdigest(),
            }),
            encoding="utf-8",
        )

    def validate(_material: Path, node: dict) -> tuple[object, dict, list]:
        start = node["group"]["index"] * 2
        partitions = [
            {
                "index": index,
                "count": 1,
                "path": f"reference-{index:02}.arrow",
            }
            for index in range(start, start + 2)
        ]
        return object(), {"elements": 16}, partitions

    monkeypatch.setattr(
        assemble, "validate_reference_partition_group", validate
    )

    selected = assemble._latest_nodes(tmp_path)  # pyright: ignore[reportPrivateUsage]

    assert set(selected) == {f"partition:{index}" for index in range(16)}


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


def test_node_run_routes_streaming_index_and_partition_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_args = SimpleNamespace(
        global_index=True,
        group_index=None,
        group_count=4,
        exact_commit="a" * 40,
        output=tmp_path / "index",
        reference_shards=16,
    )
    monkeypatch.setattr(
        node_cli,
        "run_hosted_reference_node",
        lambda *_, **__: {"kind": "index"},
    )
    assert node_cli._run(index_args, lambda _: None) == {  # pyright: ignore[reportPrivateUsage]
        "kind": "index"
    }
    group_args = SimpleNamespace(
        global_index=False,
        group_index=2,
        group_count=4,
        exact_commit="b" * 40,
        output=tmp_path / "group",
        reference_shards=16,
    )
    monkeypatch.setattr(
        node_cli,
        "run_hosted_reference_group",
        lambda *_, **__: {"kind": "group"},
    )
    assert node_cli._run(group_args, lambda _: None) == {  # pyright: ignore[reportPrivateUsage]
        "kind": "group"
    }


def test_node_main_preserves_bounded_checkpoint_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = tmp_path / "receipt.json"

    def fail(_args: object, checkpoint: object) -> dict[str, object]:
        checkpoint({"status": "running", "progress": {"stage": "global-index"}})
        raise MemoryError

    monkeypatch.setattr(node_cli, "_run", fail)
    result = node_cli.main([
        "--exact-commit",
        "c" * 40,
        "--output",
        str(tmp_path / "output"),
        "--receipt",
        str(receipt),
        "--reference-shards",
        "2",
        "--global-index",
    ])
    report = json.loads(receipt.read_text(encoding="utf-8"))["report"]
    assert result == 1
    assert report["failure_stage"] == "global-index"
    assert report["progress"] == {"stage": "global-index"}


@pytest.mark.parametrize("payload", [[], {"report": []}])
def test_manifest_node_rejects_invalid_wrapper(
    tmp_path: Path, payload: object
) -> None:
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TypeError, match="receipt is invalid"):
        assemble._node(path)  # pyright: ignore[reportPrivateUsage]


def test_manifest_node_rejects_digest_and_missing_prepared_node(
    tmp_path: Path,
) -> None:
    path = tmp_path / "receipt.json"
    report = {"status": "prepared"}
    path.write_text(
        json.dumps({"report": report, "report_sha256": "bad"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="digest changed"):
        assemble._node(path)  # pyright: ignore[reportPrivateUsage]
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    path.write_text(
        json.dumps({
            "report": report,
            "report_sha256": hashlib.sha256(encoded).hexdigest(),
        }),
        encoding="utf-8",
    )
    with pytest.raises(TypeError, match="receipt is invalid"):
        assemble._node(path)  # pyright: ignore[reportPrivateUsage]


def test_manifest_run_copies_selected_nodes_and_binds_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.arrow").write_bytes(b"index")
    (source / "reference-00.arrow").write_bytes(b"partition")
    index_node = {
        "node_kind": "index",
        "binding": {"synthetic": True},
        "denominator": {"row_count": 1},
        "index": {"path": "index.arrow"},
        "workflow_commit": "a" * 40,
    }
    partition_node = {
        "node_kind": "partition",
        "partition": {"index": 0, "path": "reference-00.arrow"},
    }
    report = {
        "workflow_commit": "a" * 40,
        "dataset": "example/dataset",
        "revision": "revision",
        "run_id": "10",
        "run_attempt": "2",
    }
    monkeypatch.setattr(
        assemble,
        "_latest_nodes",
        lambda _: {
            "index": (source / "index-receipt.json", report, index_node),
            "partition:0": (
                source / "partition-receipt.json",
                report,
                partition_node,
            ),
        },
    )
    monkeypatch.setattr(
        assemble.PbsXmlMemberBinding,
        "model_validate",
        lambda value: value,
    )
    monkeypatch.setattr(
        assemble,
        "assemble_reference_manifest",
        lambda *_: {"schema_version": 1, "status": "prepared"},
    )
    output = tmp_path / "output"
    result = assemble._run(  # pyright: ignore[reportPrivateUsage]
        SimpleNamespace(input=tmp_path, output=output, reference_shards=1)
    )
    assert result["status"] == "prepared"
    assert result["run_id"] == "10"
    manifest = json.loads(
        (output / "reference-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["preparation_run_attempt"] == "2"
    assert manifest["workflow_commit"] == "a" * 40
    assert manifest["dataset"] == "example/dataset"
    assert (output / "index.arrow").read_bytes() == b"index"
    assert (output / "reference-00.arrow").read_bytes() == b"partition"


def test_manifest_run_rejects_unbound_inner_index_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = {
        "workflow_commit": "a" * 40,
        "dataset": "example/dataset",
        "revision": "revision",
        "run_id": "10",
        "run_attempt": "2",
    }
    monkeypatch.setattr(
        assemble,
        "_latest_nodes",
        lambda _: {
            "index": (
                tmp_path / "index-receipt.json",
                report,
                {"node_kind": "index", "workflow_commit": None},
            ),
            "partition:0": (
                tmp_path / "partition-receipt.json",
                report,
                {"node_kind": "partition", "partition": {"index": 0}},
            ),
        },
    )
    with pytest.raises(ValueError, match="hosted identity changed"):
        assemble._run(  # pyright: ignore[reportPrivateUsage]
            SimpleNamespace(
                input=tmp_path,
                output=tmp_path / "output",
                reference_shards=1,
            )
        )


def test_manifest_latest_nodes_rejects_invalid_partition_and_attempt(
    tmp_path: Path,
) -> None:
    _receipt(
        tmp_path / "bad-partition" / "reference-00-receipt.json",
        attempt=1,
        index=0,
        digest="same",
    )
    wrapper_path = tmp_path / "bad-partition" / "reference-00-receipt.json"
    wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
    wrapper["report"]["node"]["partition"] = []
    encoded = json.dumps(
        wrapper["report"], sort_keys=True, separators=(",", ":")
    ).encode()
    wrapper["report_sha256"] = hashlib.sha256(encoded).hexdigest()
    wrapper_path.write_text(json.dumps(wrapper), encoding="utf-8")
    with pytest.raises(TypeError, match="partition receipt is invalid"):
        assemble._latest_nodes(tmp_path)  # pyright: ignore[reportPrivateUsage]

    wrapper["report"]["node"]["partition"] = {"index": 0}
    wrapper["report"]["run_attempt"] = "latest"
    encoded = json.dumps(
        wrapper["report"], sort_keys=True, separators=(",", ":")
    ).encode()
    wrapper["report_sha256"] = hashlib.sha256(encoded).hexdigest()
    wrapper_path.write_text(json.dumps(wrapper), encoding="utf-8")
    with pytest.raises(ValueError, match="attempt is invalid"):
        assemble._latest_nodes(tmp_path)  # pyright: ignore[reportPrivateUsage]


def test_workflow_disaggregates_preparation_without_raw_artifacts() -> None:
    workflow = Path(
        ".github/workflows/pbs-historical-qualification.yml"
    ).read_text(encoding="utf-8")
    assert "prepare-reference-index:" in workflow
    assert "prepare-reference-pairs:" in workflow
    assert "--entity-material" not in workflow
    assert "--global-index" in workflow
    assert '--group-index "$GROUP" --group-count 8' in workflow
    assert "max-parallel: 8" in workflow
    assert "prepare_historical_pbs_reference_node.py" in workflow
    assert "assemble_historical_pbs_reference_manifest.py" in workflow
    assert "pattern: pbs-reference-node-*-${{ github.run_id }}-*" in workflow
    assert "archive.zip" not in workflow
    assert "member.xml" not in workflow
    phase = workflow.split("  qualify:\n", 1)[1].split(
        "  qualify-references:\n", 1
    )[0]
    assert "needs:" not in phase
    assert "needs: qualify" not in workflow
    assert "needs.qualify.result" not in workflow
    assert (
        "pbs-reference-complete-${{ needs.prepare.outputs.artifact_suffix }}"
        in workflow
    )
