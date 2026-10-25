"""Protected PBS schema inventory binds its complete artifact without values."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml
from scripts import profile_historical_pbs_schema as cli
from scripts import profile_pbs_root_version_metadata as root_version_cli
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


@pytest.mark.parametrize(
    ("literal", "expected"),
    [("3", ("3", (3,))), ("3.1.9", ("3.1.9", (3, 1, 9)))],
)
def test_root_version_reader_stops_at_metadata_and_emits_no_descendant_values(
    literal, expected
):
    xml = (
        f'<pbs:root xmlns:pbs="{module.PBS_V3_NAMESPACE}" '
        f'version="{literal}"><pbs:private>SECRET_SOURCE_VALUE</pbs:private>'
        "</pbs:root>"
    ).encode()
    assert module._pbs_root_schema_version(xml) == expected


@pytest.mark.parametrize(
    "xml",
    [
        b'<pbs:schedule xmlns:pbs="http://schema.pbs.gov.au/" version="3"/>',
        b'<pbs:root xmlns:pbs="http://schema.pbs.gov.au/"/>',
        b'<pbs:root xmlns:pbs="http://schema.pbs.gov.au/" version="4"/>',
        b'<!DOCTYPE root [<!ENTITY e "x">]><root version="3"/>',
        b'<pbs:root xmlns:pbs="http://schema.pbs.gov.au/" version="3.x"/>',
    ],
)
def test_root_version_reader_rejects_unbound_or_unsafe_metadata(xml):
    with pytest.raises(ValueError, match="PBS"):
        module._pbs_root_schema_version(xml)


def test_root_version_reader_rejects_metadata_beyond_prefix_bound(monkeypatch):
    xml = (
        b" " * 80
        + f'<pbs:root xmlns:pbs="{module.PBS_V3_NAMESPACE}" version="3"/>'.encode()
    )
    monkeypatch.setattr(module, "_ROOT_METADATA_PREFIX_BYTES", 64)
    monkeypatch.setattr(module, "_ROOT_METADATA_CHUNK_BYTES", 16)
    with pytest.raises(ValueError, match="within prefix bound"):
        module._pbs_root_schema_version(xml)


def test_hosted_root_version_receipt_binds_only_pinned_identity_and_version(
    tmp_path, monkeypatch
):
    xml = (
        f'<pbs:root xmlns:pbs="{module.PBS_V3_NAMESPACE}" version="3">'
        "<pbs:private>SECRET_SOURCE_VALUE</pbs:private></pbs:root>"
    ).encode()
    binding = SimpleNamespace(
        archive_payload=SimpleNamespace(sha256="a" * 64, byte_count=123),
        member_payload=SimpleNamespace(sha256="b" * 64, byte_count=len(xml)),
        member_path="sch-2026-04-01-r1.xml",
        digest=lambda: "c" * 64,
    )
    inputs = SimpleNamespace(
        context={
            "workflow_commit": SHA,
            "run_id": "123",
            "run_attempt": "1",
        },
        xml=xml,
        binding=binding,
        parent=SimpleNamespace(digest=lambda: "d" * 64),
    )

    def use_synthetic_inputs(*_args, **_kwargs):
        return inputs

    monkeypatch.setattr(module, "_verified_inputs", use_synthetic_inputs)
    report = module.run_hosted_root_schema_version_metadata(
        SHA, tmp_path / "receipt.json"
    )
    assert report["status"] == "passed"
    assert report["archive_sha256"] == "a" * 64
    assert report["member_sha256"] == "b" * 64
    assert report["member_binding_sha256"] == "c" * 64
    assert report["declared_schema_version"] == "3"
    assert report["schema_major"] == 3
    assert report["schema_minor"] is None
    assert report["schema_minor_bound"] is False
    assert report["source_field_values_emitted"] is False
    assert "SECRET_SOURCE_VALUE" not in json.dumps(report)


def test_existing_root_version_receipt_is_preserved(tmp_path, monkeypatch):
    output = tmp_path / "receipt.json"
    output.write_text("existing evidence", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "_verified_inputs",
        lambda *_args, **_kwargs: pytest.fail("must not load pinned inputs"),
    )
    with pytest.raises(ValueError, match="output already exists"):
        module.run_hosted_root_schema_version_metadata(SHA, output)
    assert output.read_text(encoding="utf-8") == "existing evidence"


def test_root_version_cli_failure_receipt_never_serializes_source_text(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        root_version_cli,
        "run_hosted_root_schema_version_metadata",
        lambda *_args: (_ for _ in ()).throw(ValueError("SECRET_SOURCE_VALUE")),
    )
    receipt = tmp_path / "receipt.json"
    assert (
        root_version_cli.main([
            "--exact-commit",
            SHA,
            "--output",
            str(receipt),
        ])
        == 1
    )
    assert "SECRET_SOURCE_VALUE" not in receipt.read_text()


def test_root_version_cli_success_writes_bounded_receipt(tmp_path, monkeypatch):
    report = {
        "status": "passed",
        "operation": "pbs-root-schema-version-metadata",
        "declared_schema_version": "3",
        "schema_minor_bound": False,
        "source_field_values_emitted": False,
    }
    monkeypatch.setattr(
        root_version_cli,
        "run_hosted_root_schema_version_metadata",
        lambda *_args: report,
    )
    receipt = tmp_path / "receipt.json"
    assert (
        root_version_cli.main([
            "--exact-commit",
            SHA,
            "--output",
            str(receipt),
        ])
        == 0
    )
    envelope = json.loads(receipt.read_bytes())
    assert envelope["report"] == report
    assert len(envelope["report_sha256"]) == 64


def test_local_root_version_profile_stops_before_source_transport(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def refuse(_request):
        raise AssertionError("local context must stop before transport")

    output = tmp_path / "receipt.json"
    with pytest.raises(module.QualificationError, match="context"):
        module.run_hosted_root_schema_version_metadata(
            SHA, output, transport=httpx.MockTransport(refuse)
        )
    assert not output.exists()


def test_root_version_workflow_is_exact_main_and_uploads_only_receipt():
    path = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/pbs-root-schema-version-metadata.yml"
    )
    document = yaml.load(
        path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    job = document["jobs"]["inspect-root-metadata"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    run = next(step["run"] for step in job["steps"] if "run" in step)
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in run
    assert "scripts/profile_pbs_root_version_metadata.py" in run
    artifact = job["steps"][-1]["with"]["path"]
    assert artifact == "pbs-root-schema-version-metadata.json"
