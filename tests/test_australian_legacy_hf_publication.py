"""Fail-closed contract for hosted Australian legacy raw publication."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/australian-health-legacy-publication-authorization.json"
)
WORKFLOW = ROOT / ".github/workflows/australian-legacy-hf-publication.yml"


def test_authorization_binds_every_nonempty_donor_payload() -> None:
    authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    assert authorization["external_publication_authorized"] is True
    assert (
        authorization["maintainer_asserted_redistribution_permission"] is True
    )
    assert (
        authorization["dataset"] == "edithatogo/australian-mbs-source-archive"
    )
    assert authorization["visibility"] == "public"
    assert authorization["gated"] is False
    donors = {item["repository"]: item for item in authorization["donors"]}
    assert set(donors) == {
        "edithatogo/aus_mbs_pbs_graph",
        "edithatogo/aus-health-data-scraper",
    }
    payloads = donors["edithatogo/aus_mbs_pbs_graph"]["payloads"]
    assert {item["git_path"] for item in payloads} == {
        "scripts/parsing/MBS-XML-20250701 Version 3.XML",
        "data/source/MBS - 2024.07 - Group P7 (Genetics).xlsx",
    }
    assert {(item["bytes"], item["sha256"]) for item in payloads} == {
        (
            8_194_522,
            "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556",
        ),
        (
            87_727,
            "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8",
        ),
    }
    assert donors["edithatogo/aus-health-data-scraper"]["payloads"] == []


def test_workflow_uploads_only_from_actions_and_verifies_anonymously() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in workflow
    assert workflow.index("gh issue comment 340") < workflow.index(
        "api.create_repo("
    )
    assert "private=True, exist_ok=False" in workflow
    assert "git', 'bundle', 'create'" in workflow
    assert "git', 'bundle', 'verify'" in workflow
    assert "api.upload_folder(" in workflow
    assert "repo_type='dataset', private=False" in workflow
    assert "HfApi(token=False).dataset_info" in workflow
    assert "snapshot_download(" in workflow
    assert "token=False" in workflow
    assert "anonymous restore digest mismatch" in workflow
    assert "needs.publish.result != 'success'" in workflow
    assert "failed transaction was not restored to private" in workflow
    assert "publication_performed_by_github_actions': True" in workflow
    assert "HF_TOKEN: ${{ secrets.HF_TOKEN }}" in workflow


def test_project_dependencies_are_not_expanded_for_hosted_transport() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "huggingface-hub" not in pyproject
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "huggingface-hub==1.14.0" in workflow
