"""Independent PBS builds need distinct hosted jobs and metadata-only output."""

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pbs-independent-pipeline-qualification.yml"


def test_independent_pbs_builds_are_separate_fresh_jobs() -> None:
    workflow = cast(
        "dict[str, Any]",
        yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader),
    )
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    jobs = workflow["jobs"]
    assert set(jobs) == {"independent-build"}
    job = jobs["independent-build"]
    assert job["strategy"]["matrix"]["build"] == ["1", "2"]
    assert job["strategy"]["max-parallel"] == "2"
    assert job["strategy"]["fail-fast"] == "false"
    assert job["runs-on"] == "ubuntu-24.04"
    assert "needs" not in job
    assert not any(
        "download-artifact@" in step.get("uses", "") for step in job["steps"]
    )


def test_independent_jobs_reuse_full_source_qualifier_with_exact_main_guard() -> (
    None
):
    text = WORKFLOW.read_text()
    assert 'test "$GITHUB_SHA" = "$REQUESTED_COMMIT"' in text
    assert "test \"$GITHUB_REF\" = 'refs/heads/main'" in text
    assert "test \"$GITHUB_EVENT_NAME\" = 'workflow_dispatch'" in text
    assert (
        "--python 3.15.1 python scripts/qualify_historical_pbs_public.py"
        in text
    )
    assert "--projection value-package" in text
    assert "persist-credentials: false" in text
    assert "secrets." not in text
    assert "--date-profile" not in text


def test_worker_artifacts_cannot_include_source_or_parquet_outputs() -> None:
    workflow = cast(
        "dict[str, Any]",
        yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader),
    )
    steps = workflow["jobs"]["independent-build"]["steps"]
    artifacts = [
        step for step in steps if "upload-artifact@" in step.get("uses", "")
    ]
    assert len(artifacts) == 1
    assert (
        artifacts[0]["with"]["path"]
        == "pbs-independent-build-${{ matrix.build }}.json"
    )
    assert "${{ github.run_attempt }}" in artifacts[0]["with"]["name"]
    assert "${{ matrix.build }}" in artifacts[0]["with"]["name"]
    assert not any("upload_folder" in step.get("run", "") for step in steps)
