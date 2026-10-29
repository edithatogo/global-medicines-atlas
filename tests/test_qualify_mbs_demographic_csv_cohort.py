"""Quarterly native candidate jobs enforce exact main and separate measures."""

import json
import sys
from pathlib import Path

import pytest
from scripts import qualify_mbs_demographic_csv_cohort as module


def hosted_environment(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)


def test_local_qualification_stops_before_network(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify(2, "a" * 40)


@pytest.mark.parametrize("quarter", [0, 4, True, "2"])
def test_quarter_selection_cannot_expand_inventory(monkeypatch, quarter):
    hosted_environment(monkeypatch)
    with pytest.raises(ValueError, match="frozen CSV cohort"):
        module.qualify(quarter, "a" * 40)


@pytest.mark.parametrize("quarter", [1, 2, 3])
def test_each_exact_candidate_is_selected_and_temporary_outputs_removed(
    monkeypatch, quarter
):
    hosted_environment(monkeypatch)
    candidate = module.load_csv_candidates(module.ROOT)[quarter - 1]
    directories = []

    def fetch(_client, item):
        assert item == {
            "path": candidate.source.source_path,
            "sha256": candidate.source.source_sha256,
            "bytes": candidate.byte_count,
        }
        return b"synthetic"

    def check(payload, context, directory, **kwargs):
        assert payload == b"synthetic"
        assert context == candidate.source
        assert kwargs["expected_rows"] == candidate.expected_rows
        directories.append(directory)
        return {
            "source_measure_id": context.source_measure_id,
            "candidate_only": True,
        }

    monkeypatch.setattr(
        module.qualifier.source_reader, "fetch_exact_source_bytes", fetch
    )
    monkeypatch.setattr(module.qualifier, "qualify_object", check)
    report = module.qualify(quarter, "a" * 40)
    assert report["selected_quarter"] == quarter
    assert report["frozen_candidate_count"] == 3
    assert report["boundaries"]["new_sources"] == 0
    assert report["boundaries"]["new_admissions"] == 0
    assert report["boundaries"]["benefit_equivalence_established"] is False
    assert all(not path.exists() for path in directories)


def test_workflow_retains_only_aggregate_artifacts():
    text = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/mbs-demographic-csv-candidates.yml"
    ).read_text()
    assert "quarter: [1, 2, 3]" in text
    assert "path: demographic-csv-candidate.json" in text
    assert "refs/heads/main" in text
    assert "contents: read" in text
    assert "issues: write" not in text


def test_cli_only_writes_aggregate(tmp_path: Path, monkeypatch):
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(module, "qualify", lambda *_: {"candidate_only": True})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify",
            "--quarter",
            "2",
            "--exact-commit",
            "a" * 40,
            "--output",
            str(output),
        ],
    )
    module.main()
    assert json.loads(output.read_text()) == {"candidate_only": True}


def test_cli_hides_source_bearing_failures(tmp_path: Path, monkeypatch, capsys):
    def fail(*_):
        raise ValueError("SYNTHETIC_SOURCE_DETAIL")

    output = tmp_path / "receipt.json"
    monkeypatch.setattr(module, "qualify", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify",
            "--quarter",
            "2",
            "--exact-commit",
            "a" * 40,
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit, match="source details withheld"):
        module.main()
    assert not output.exists()
    assert "SYNTHETIC_SOURCE_DETAIL" not in str(capsys.readouterr())
