"""Group qualification reads only its frozen object and emits bounded receipts."""

import sys
from pathlib import Path

import pytest
import yaml
from scripts import qualify_mbs_group_native_silver as module
from test_mbs_group_silver import context, csv_payload


def test_existing_group_context_is_bound_without_payload_reads():
    source, reference = module.load_group_source(
        Path(__file__).resolve().parents[1]
    )
    assert (
        source.source_sha256
        == "62ad118d94cd565a051164aa645eff1fef84a5beb74d501e3dc64344fcf16d3b"
    )
    assert reference["byte_count"] == 12291303
    assert source.source_format == "csv"


def test_local_execution_fails_before_network(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify("a" * 40)


def test_group_object_qualification_is_deterministic_and_bounded(
    tmp_path: Path,
):
    payload = csv_payload()
    report = module.qualify_object(
        payload, context(payload), tmp_path, expected_rows=1
    )
    assert report["coverage"]["data_records"] == 1
    assert report["coverage"]["native_field_slots"] == 16
    assert report["rebuild_equal"] is True
    assert report["duckdb_counts_verified"] is True
    assert report["candidate_only"] is True


def test_exact_prior_row_denominator_is_enforced(tmp_path: Path):
    payload = csv_payload()
    with pytest.raises(ValueError, match="row denominator"):
        module.qualify_object(
            payload, context(payload), tmp_path, expected_rows=2
        )


def test_registered_group_job_only_uploads_aggregate_receipt():
    path = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/mbs-q1-source-meaning-diagnostics.yml"
    )
    document = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    job = document["jobs"]["group-csv"]
    assert job["if"] == "inputs.qualification_scope == 'group-csv'"
    assert job["permissions"] == {"contents": "read"}
    run = next(step["run"] for step in job["steps"] if "run" in step)
    assert "scripts/qualify_mbs_group_native_silver.py" in run
    assert "refs/heads/main" in run
    assert '"${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in run
    assert (
        job["steps"][-1]["with"]["path"] == "group-native-silver-candidate.json"
    )


def hosted_environment(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)


def test_hosted_group_orchestration_reads_one_exact_object(monkeypatch):
    hosted_environment(monkeypatch)
    source, reference = module.load_group_source(module.ROOT)
    directories = []

    def fetch(_client, item):
        assert item == {
            "path": module.SOURCE_PATH,
            "sha256": module.SOURCE_SHA256,
            "bytes": reference["byte_count"],
        }
        return b"synthetic"

    def check(_payload, context, directory, **kwargs):
        assert context == source
        assert kwargs["expected_rows"] == 164543
        directories.append(directory)
        return {"candidate_only": True}

    monkeypatch.setattr(module.transport, "fetch_exact_source_bytes", fetch)
    monkeypatch.setattr(module, "qualify_object", check)
    report = module.qualify("a" * 40)
    assert report["boundaries"]["new_sources"] == 0
    assert report["boundaries"]["new_admissions"] == 0
    assert all(not path.exists() for path in directories)


def test_cli_withholds_source_bearing_errors(tmp_path: Path, monkeypatch):
    def fail(_):
        raise ValueError("SYNTHETIC_SOURCE_DETAIL")

    monkeypatch.setattr(module, "qualify", fail)
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["qualify", "--exact-commit", "a" * 40, "--output", str(output)],
    )
    with pytest.raises(SystemExit, match="source details withheld"):
        module.main()
    assert not output.exists()
