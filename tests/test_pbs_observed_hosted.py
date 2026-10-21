"""Observed PBS route retains exact-main and anonymous pinned transport gates."""

import json
from pathlib import Path

import httpx
import pytest
import yaml
from scripts import qualify_observed_pbs_values as cli
from test_pbs_hosted_qualification import SHA, synthetic

from global_medicines_atlas import pbs_hosted_qualification as module

__all__ = ["synthetic"]


def test_local_observed_route_stops_before_transport(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def refuse(_):
        raise AssertionError("local transport must not run")

    with pytest.raises(module.QualificationError, match="context"):
        module.run_hosted_observed_values(
            SHA, Path(), transport=httpx.MockTransport(refuse)
        )


def test_observed_route_uses_verified_source_and_safe_aggregate(
    synthetic, monkeypatch
):
    sentinel = object()
    monkeypatch.setattr(module, "load_observed_profile", lambda _: sentinel)

    def qualify(archive, member, parent, binding, profile, *, progress):
        assert profile is sentinel
        assert binding.member_payload.sha256 == module.MEMBER.sha256
        assert binding.archive_payload.sha256 == module.ARCHIVE.sha256
        assert binding.parent_receipt_sha256 == parent.digest()
        assert archive
        assert member
        progress("values", 1, 2)
        return {
            "qualification": "observed_structural_value_candidates_only",
            "domain_semantics_qualified": False,
            "new_admissions": 0,
        }

    monkeypatch.setattr(module, "qualify_observed_values", qualify)
    checkpoints = []
    report = module.run_hosted_observed_values(
        SHA, Path(), transport=synthetic[2], progress=checkpoints.append
    )
    assert report["status"] == "passed"
    assert report["publication_performed"] is False
    assert report["qualification"]["domain_semantics_qualified"] is False
    assert len(synthetic[1]) == 5
    assert checkpoints[-1]["progress"]["phase"] == "values"


def test_cli_withholds_source_exception_text(tmp_path, monkeypatch):
    def fail(*_, **__):
        raise ValueError("SYNTHETIC SOURCE TEXT WITHHELD")

    monkeypatch.setattr(cli, "run_hosted_observed_values", fail)
    output = tmp_path / "receipt.json"
    assert cli.main(["--exact-commit", SHA, "--output", str(output)]) == 1
    report = json.loads(output.read_bytes())
    assert report["report"]["status"] == "failed"
    assert "SYNTHETIC SOURCE TEXT" not in output.read_text()


def test_cli_preserves_existing_evidence_before_transport(tmp_path):
    output = tmp_path / "receipt.json"
    output.write_text("human evidence")
    with pytest.raises(SystemExit) as caught:
        cli.main(["--exact-commit", SHA, "--output", str(output)])
    assert caught.value.code == 2
    assert output.read_text() == "human evidence"


def test_observed_workflow_is_read_only_and_excludes_other_routes():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load(
        (
            root / ".github/workflows/pbs-historical-qualification.yml"
        ).read_text()
    )
    job = workflow["jobs"]["observed-domain-values"]
    assert job["permissions"] == {"contents": "read"}
    assert job["timeout-minutes"] == 65
    step = next(step for step in job["steps"] if "run" in step)
    assert step["timeout-minutes"] == 55
    assert "scripts/qualify_observed_pbs_values.py" in step["run"]
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in step["run"]
    for name, other in workflow["jobs"].items():
        if name in {
            "native-values",
            "native-value-package",
            "native-schema-inventory",
            "observed-domain-values",
        }:
            continue
        assert (
            "inputs.qualification_scope != 'observed-domain-values'"
            in other["if"]
        )
