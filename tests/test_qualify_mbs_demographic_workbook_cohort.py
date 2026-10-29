"""Protected workbook qualification reads one exact object and no CSV denominator."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from scripts import qualify_mbs_demographic_workbook_cohort as module


def hosted(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)


def test_local_execution_stops_before_network(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify(1, "a" * 40)


@pytest.mark.parametrize("quarter", [0, 4, True, "2"])
def test_invalid_frozen_selection_is_rejected(monkeypatch, quarter):
    hosted(monkeypatch)
    with pytest.raises(ValueError, match="frozen workbook cohort"):
        module.qualify(quarter, "a" * 40)


@pytest.mark.parametrize("quarter", [1, 2, 3])
def test_hosted_orchestration_binds_selected_workbook_and_independent_rows(
    monkeypatch, quarter
):
    hosted(monkeypatch)
    candidate = module.load_workbook_candidates(module.ROOT)[quarter - 1]
    directories = []

    def fetch(_client, item):
        assert item == {
            "path": candidate.source.source_path,
            "sha256": candidate.source.source_sha256,
            "bytes": candidate.byte_count,
        }
        return b"synthetic workbook"

    def rows(payload):
        assert payload == b"synthetic workbook"
        return [(None,) * 8] * 3

    def qualify(payload, source, output, **kwargs):
        assert payload == b"synthetic workbook"
        assert source == candidate.source
        assert kwargs["expected_rows"] == 3
        directories.append(output)
        return {"synthetic_row_count": 3}

    monkeypatch.setattr(
        module.qualifier.source_reader, "fetch_exact_source_bytes", fetch
    )
    monkeypatch.setattr(module.qualifier.source_reader, "workbook_rows", rows)
    monkeypatch.setattr(module.qualifier, "qualify_object", qualify)
    report = module.qualify(quarter, "a" * 40)
    assert report["selected_quarter"] == quarter
    assert report["source_path"] == candidate.source.source_path
    assert report["boundaries"]["new_sources"] == 0
    assert report["boundaries"]["new_admissions"] == 0
    assert report["boundaries"]["benefit_equivalence_established"] is False
    assert all(not path.exists() for path in directories)


def test_wrong_transport_identity_is_rejected(monkeypatch):
    hosted(monkeypatch)
    monkeypatch.setattr(
        module,
        "load_workbook_candidates",
        lambda _: [SimpleNamespace(source=SimpleNamespace(dataset="wrong"))],
    )
    with pytest.raises(ValueError, match="transport identity"):
        module.qualify(1, "a" * 40)


def test_cli_withholds_source_bearing_errors(tmp_path, monkeypatch):
    def fail(*_args):
        raise ValueError("SYNTHETIC_SOURCE_DETAIL")

    monkeypatch.setattr(module, "qualify", fail)
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify",
            "--quarter",
            "1",
            "--exact-commit",
            "a" * 40,
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit, match="source details withheld"):
        module.main()
    assert not output.exists()


def test_cli_writes_only_aggregate_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "qualify", lambda *_: {"candidate_only": True})
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify",
            "--quarter",
            "1",
            "--exact-commit",
            "a" * 40,
            "--output",
            str(output),
        ],
    )
    module.main()
    assert json.loads(output.read_text()) == {"candidate_only": True}


def test_registered_workbook_job_is_bounded_read_only_and_aggregate_only():
    path = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/mbs-q1-source-meaning-diagnostics.yml"
    )
    document = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    job = document["jobs"]["quarterly-workbooks"]
    assert job["if"] == "inputs.qualification_scope == 'quarterly-workbooks'"
    assert job["permissions"] == {"contents": "read"}
    assert job["strategy"]["max-parallel"] == "1"
    assert job["strategy"]["matrix"]["quarter"] == ["1", "2", "3"]
    run = next(step["run"] for step in job["steps"] if "run" in step)
    assert "qualify_mbs_demographic_workbook_cohort.py" in run
    assert "refs/heads/main" in run
    assert (
        job["steps"][-1]["with"]["path"]
        == "demographic-workbook-candidate.json"
    )


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("GITHUB_REF", "refs/heads/other"),
        ("GITHUB_REPOSITORY", "other/repo"),
        ("GITHUB_SHA", "b" * 40),
    ],
)
def test_wrong_hosted_identity_stops_before_network(
    monkeypatch, variable, value
):
    hosted(monkeypatch)
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify(1, "a" * 40)


def test_empty_independent_primary_denominator_is_not_qualified(monkeypatch):
    hosted(monkeypatch)
    monkeypatch.setattr(
        module.qualifier.source_reader,
        "fetch_exact_source_bytes",
        lambda *_: b"synthetic",
    )
    monkeypatch.setattr(
        module.qualifier.source_reader, "workbook_rows", lambda _: []
    )
    monkeypatch.setattr(
        module.qualifier,
        "qualify_object",
        lambda *_args, **_kwargs: {"invalid_empty": True},
    )
    with pytest.raises(ValueError, match="primary row denominator"):
        module.qualify(1, "a" * 40)
