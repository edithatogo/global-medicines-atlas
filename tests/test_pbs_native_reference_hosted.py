"""Native reference screening stays behind exact-main source and output gates."""

import json
from pathlib import Path

import httpx
import pytest
import yaml
from scripts import screen_historical_pbs_references as cli
from test_pbs_hosted_qualification import SHA, synthetic

from global_medicines_atlas import pbs_hosted_qualification as module

__all__ = ["synthetic"]


def test_local_route_stops_before_transport(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def refuse(_):
        raise AssertionError("local transport must not run")

    with pytest.raises(module.QualificationError, match="context"):
        module.run_hosted_native_reference_screen(
            SHA, transport=httpx.MockTransport(refuse)
        )


def test_verified_route_returns_only_aggregate(synthetic, monkeypatch):
    def qualify(archive, member, parent, binding, *, progress):
        assert archive
        assert member
        assert binding.member_payload.sha256 == module.MEMBER.sha256
        assert binding.parent_receipt_sha256 == parent.digest()
        progress("native-reference-match", 1, 8)
        return {
            "native_fields": 8,
            "reference_fields": 2,
            "reference_status_counts": {"no_exact_literal": 2},
            "semantic_relationships_qualified": False,
            "native_values_emitted": False,
        }

    monkeypatch.setattr(module, "screen_native_references", qualify)
    checkpoints = []
    report = module.run_hosted_native_reference_screen(
        SHA, transport=synthetic[2], progress=checkpoints.append
    )
    assert report["status"] == "passed"
    assert len(synthetic[1]) == 5
    assert checkpoints[-1]["progress"]["phase"] == "native-reference-match"
    assert report["qualification"]["semantic_relationships_qualified"] is False
    assert report["publication_performed"] is False


def test_cli_withholds_source_exception_and_preserves_existing_receipt(
    tmp_path, monkeypatch
):
    output = tmp_path / "receipt.json"

    def fail(*_, **__):
        raise ValueError("SYNTHETIC SOURCE TEXT WITHHELD")

    monkeypatch.setattr(cli, "run_hosted_native_reference_screen", fail)
    assert cli.main(["--exact-commit", SHA, "--output", str(output)]) == 1
    report = json.loads(output.read_bytes())
    assert report["report"]["status"] == "failed"
    assert "SYNTHETIC SOURCE TEXT" not in output.read_text()
    with pytest.raises(SystemExit):
        cli.main(["--exact-commit", SHA, "--output", str(output)])


def test_workflow_exact_main_read_only_and_exclusive():
    workflow = yaml.safe_load(
        (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/pbs-historical-qualification.yml"
        ).read_text()
    )
    job = workflow["jobs"]["native-reference-screen"]
    assert job["permissions"] == {"contents": "read"}
    assert job["timeout-minutes"] == 65
    step = next(step for step in job["steps"] if "run" in step)
    assert step["timeout-minutes"] == 55
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in step["run"]
    assert "scripts/screen_historical_pbs_references.py" in step["run"]
    for name, other in workflow["jobs"].items():
        if name == "native-reference-screen":
            continue
        if "inputs.qualification_scope ==" in other["if"]:
            assert (
                "inputs.qualification_scope == 'native-reference-screen'"
                not in other["if"]
            )
            continue
        assert (
            "inputs.qualification_scope != 'native-reference-screen'"
            in other["if"]
        )
