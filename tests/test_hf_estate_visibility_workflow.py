"""Static fail-closed contract for the exact HF legacy visibility workflow."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hf-legacy-composite-visibility.yml"
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/hf-legacy-composite-authorization-20260829.json"
)


def test_authorization_is_exact_and_excludes_other_private_surfaces() -> None:
    authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    candidate = authorization["candidate"]

    assert authorization["external_publication_authorized"] is True
    assert (
        authorization["maintainer_asserted_redistribution_permission"] is True
    )
    assert authorization["operation"] == (
        "make-existing-exact-revision-public-no-upload"
    )
    assert candidate == {
        "dataset": "edithatogo/global-medicines-atlas-international-open",
        "revision": "654f71c84cdb17b4032396bcbc961bef8757fb19",
        "manifest_sha256": (
            "d058b78789cd8c2d0a19467063890d32c0757add10998d307422c3ec1550df86"
        ),
        "payload_file_count": 42,
        "source_count": 11,
    }
    assert {
        "default-head-equals-exact-authorized-revision",
        "durable-public-issue-intent-before-visibility-mutation",
        "durable-public-issue-success-or-rollback-receipt",
        "out-of-process-failure-cleanup",
        "scheduled-orphaned-public-visibility-watchdog",
    }.issubset(set(authorization["required_controls"]))
    assert (
        "edithatogo/hpo-licensed-ontology-archive"
        in authorization["excluded_private_surfaces"]
    )
    assert (
        "edithatogo/rareburden-commons-source-archive"
        in authorization["excluded_private_surfaces"]
    )


def test_workflow_changes_only_visibility_and_verifies_every_payload() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" in workflow
    assert "permissions: {}" in workflow
    assert "issues: write" in workflow
    assert "REQUESTED_REVISION" in workflow
    assert "requested revision differs from exact authorization" in workflow
    assert "candidate and public manifests differ" in workflow
    assert "candidate and public dataset cards differ" in workflow
    assert "candidate repository sibling set drifted" in workflow
    assert "candidate default head differs from authorization" in workflow
    assert "update_repo_settings(" in workflow
    assert "repo_type='dataset', private=False" in workflow
    assert "HfApi(token=False).dataset_info" in workflow
    assert "snapshot_download(" in workflow
    assert "token=False" in workflow
    assert "anonymous restore mismatch" in workflow
    assert "repo_type='dataset', private=True" in workflow
    assert "rollback_intent = bool(private_info.private)" in workflow
    assert workflow.index("rollback_intent = bool(private_info.private)") < (
        workflow.index("repo_type='dataset', private=False")
    )
    assert "needs.publicize-and-verify.result != 'success'" in workflow
    assert "failed transaction was not restored to private" in workflow
    assert "orphaned public visibility was not contained" in workflow
    assert "content_uploaded_or_mutated': False" in workflow
    assert "publication_performed_by_github_actions': True" in workflow
    assert "anonymous_digest_match_count': len(files)" in workflow
    assert "hf-legacy-composite-visibility-receipt.json" in workflow
    assert "durable_receipt_issue" in workflow
    assert "gh issue comment 340" in workflow
    assert "github-actions[bot]" in workflow
    assert "durable_success_receipt_found" in workflow
    assert "head_matches_authorization" in workflow

    prohibited_uploads = ("upload_file(", "upload_folder(", "create_commit(")
    assert all(operation not in workflow for operation in prohibited_uploads)
