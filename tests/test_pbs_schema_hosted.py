"""Protected PBS schema inventory binds its complete artifact without values."""

import hashlib
import json
from pathlib import Path

import httpx
import pytest
import yaml
from scripts import profile_historical_pbs_schema as cli
from test_pbs_hosted_qualification import (
    SHA,
    synthetic,
)

from global_medicines_atlas import pbs_hosted_qualification as module

__all__ = ["synthetic"]


def test_local_profile_stops_before_source_transport(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def refuse(_request):
        raise AssertionError("local context must stop before transport")

    with pytest.raises(module.QualificationError, match="context"):
        module.run_hosted_schema_inventory(
            SHA,
            tmp_path / "inventory.json",
            transport=httpx.MockTransport(refuse),
        )
    assert list(tmp_path.iterdir()) == []


def test_hosted_inventory_is_complete_digest_bound_and_metadata_only(
    synthetic, tmp_path
):
    _, calls, transport = synthetic
    output = tmp_path / "inventory.json"
    checkpoints = []
    report = module.run_hosted_schema_inventory(
        SHA, output, transport=transport, progress=checkpoints.append
    )
    payload = output.read_bytes()
    inventory = json.loads(payload)
    assert report["status"] == "passed"
    assert report["inventory_sha256"] == hashlib.sha256(payload).hexdigest()
    assert report["inventory_bytes"] == len(payload)
    assert report["native_fields"] == inventory["native_fields"]
    assert report["native_values_emitted"] is False
    assert report["publication_performed"] is False
    assert len(calls) == 5
    assert checkpoints[-1]["progress"]["phase"] == "schema-inventory"


def test_existing_inventory_is_preserved(synthetic, tmp_path):
    output = tmp_path / "inventory.json"
    output.write_text("existing human evidence")
    with pytest.raises(module.QualificationError, match="context"):
        module.run_hosted_schema_inventory(SHA, output, transport=synthetic[2])
    assert synthetic[1] == []
    assert output.read_text() == "existing human evidence"


def test_schema_cli_writes_summary_and_does_not_expose_exception_text(
    tmp_path, monkeypatch
):

    def fail(*_args, **_kwargs):
        raise ValueError("SYNTHETIC SOURCE VALUE WITHHELD")

    monkeypatch.setattr(cli, "run_hosted_schema_inventory", fail)
    receipt = tmp_path / "receipt.json"
    inventory = tmp_path / "inventory.json"
    assert (
        cli.main([
            "--exact-commit",
            SHA,
            "--output",
            str(receipt),
            "--inventory-output",
            str(inventory),
        ])
        == 1
    )
    assert "SYNTHETIC SOURCE VALUE" not in receipt.read_text()
    assert not inventory.exists()


def test_schema_cli_success_binds_both_output_arguments(tmp_path, monkeypatch):

    receipt = tmp_path / "receipt.json"
    inventory = tmp_path / "inventory.json"

    def passed(commit, output, *, progress):
        assert commit == SHA
        assert output == inventory
        progress({
            "status": "incomplete",
            "progress": {"phase": "schema-inventory", "rows": 2},
        })
        output.write_text("{}")
        return {"status": "passed", "native_values_emitted": False}

    monkeypatch.setattr(cli, "run_hosted_schema_inventory", passed)
    assert (
        cli.main([
            "--exact-commit",
            SHA,
            "--output",
            str(receipt),
            "--inventory-output",
            str(inventory),
        ])
        == 0
    )
    assert json.loads(receipt.read_bytes())["report"]["status"] == "passed"


def test_schema_cli_rejects_colliding_evidence_paths_before_execution(tmp_path):

    path = str(tmp_path / "same.json")
    with pytest.raises(SystemExit):
        cli.main([
            "--exact-commit",
            SHA,
            "--output",
            path,
            "--inventory-output",
            path,
        ])


def test_schema_mode_keeps_legacy_concurrency_and_uploads_only_path_metadata():

    document = yaml.load(
        module_path().read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    group = document["concurrency"]["group"]
    assert (
        "'native-schema-inventory' && 'schema-inventory' || 'qualification'"
        in group
    )
    job = document["jobs"]["native-schema-inventory"]
    assert job["permissions"] == {"contents": "read"}
    assert job["timeout-minutes"] == "65"
    step = next(step for step in job["steps"] if "run" in step)
    assert step["timeout-minutes"] == "55"
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in step["run"]
    assert "scripts/profile_historical_pbs_schema.py" in step["run"]
    paths = job["steps"][-1]["with"]["path"].split()
    assert paths == [
        "pbs-native-schema-inventory-receipt.json",
        "pbs-native-schema-path-inventory.json",
    ]


def module_path():

    return (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/pbs-historical-qualification.yml"
    )
