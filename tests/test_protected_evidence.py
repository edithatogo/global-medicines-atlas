"""Fail-closed protected evidence qualification tests."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from global_medicines_atlas.protected_evidence import (
    EvidenceVerification,
    HostedEvidenceSnapshot,
    LocalTruth,
    ProtectedEvidencePolicy,
    ProtectedEvidenceReceipt,
    PublicationEvidence,
    PublicationReceipt,
    PublicationState,
    ReleaseEligibility,
    RequiredCheckVerification,
    inspect_local_truth,
    verify_protected_evidence,
    write_protected_evidence_receipt,
)

FIXTURES = Path("tests/fixtures/protected-evidence")
COMMIT = "a" * 40


def _policy() -> ProtectedEvidencePolicy:
    return ProtectedEvidencePolicy.model_validate_json(
        (FIXTURES / "policy.json").read_bytes()
    )


def _snapshot() -> HostedEvidenceSnapshot:
    return HostedEvidenceSnapshot.model_validate_json(
        (FIXTURES / "hosted-success.json").read_bytes()
    )


def _local(**changes: object) -> LocalTruth:
    return LocalTruth(commit_sha=COMMIT, dirty=False).model_copy(update=changes)


def test_exact_hosted_checks_are_verified_without_claiming_publication() -> (
    None
):
    first = verify_protected_evidence(
        policy=_policy(), local=_local(), hosted=_snapshot()
    )
    second = verify_protected_evidence(
        policy=_policy(), local=_local(), hosted=_snapshot()
    )

    assert first == second
    assert first.canonical_json() == second.canonical_json()
    assert first.evidence_verification is EvidenceVerification.VERIFIED
    assert first.hosted_truth_verified
    assert first.publication.state is PublicationState.NOT_ATTEMPTED
    assert first.release_eligibility is ReleaseEligibility.BLOCKED
    assert first.release_blockers == ("publication:not_attempted",)
    assert [check.name for check in first.required_checks] == [
        "Test-Goblin / routine",
        "CodeQL / Analyze (python)",
    ]
    assert all(check.verified for check in first.required_checks)
    assert len(first.input_sha256) == 64
    assert len(first.digest()) == 64


@pytest.mark.parametrize(
    ("field", "value", "blocker"),
    [
        ("status", "in_progress", "status:in_progress"),
        ("conclusion", "failure", "conclusion:failure"),
        ("head_sha", "b" * 40, "commit-mismatch"),
    ],
)
def test_pending_failing_and_mismatched_checks_are_rejected(
    field: str, value: str, blocker: str
) -> None:
    hosted = _snapshot()
    changed = hosted.check_runs[0].model_copy(update={field: value})
    hosted = hosted.model_copy(
        update={"check_runs": (changed, *hosted.check_runs[1:])}
    )

    receipt = verify_protected_evidence(
        policy=_policy(), local=_local(), hosted=hosted
    )

    assert receipt.evidence_verification is EvidenceVerification.REJECTED
    assert not receipt.hosted_truth_verified
    assert any(blocker in item for item in receipt.blockers)


@pytest.mark.parametrize(
    ("scope", "replacement", "blocker"),
    [
        ("local", "b" * 40, "local:commit-mismatch"),
        ("snapshot", "b" * 40, "hosted:snapshot-commit-mismatch"),
        ("pull_request", "b" * 40, "hosted:pr-head-mismatch"),
        ("workflow", "b" * 40, "workflow-commit-mismatch"),
    ],
)
def test_commit_identity_mismatches_fail_closed(
    scope: str, replacement: str, blocker: str
) -> None:
    local = _local()
    hosted = _snapshot()
    if scope == "local":
        local = _local(commit_sha=replacement)
    elif scope == "snapshot":
        hosted = hosted.model_copy(update={"commit_sha": replacement})
    elif scope == "pull_request":
        hosted = hosted.model_copy(
            update={
                "pull_request": hosted.pull_request.model_copy(
                    update={"head_sha": replacement}
                )
            }
        )
    else:
        changed = hosted.workflow_runs[0].model_copy(
            update={"head_sha": replacement}
        )
        hosted = hosted.model_copy(
            update={"workflow_runs": (changed, *hosted.workflow_runs[1:])}
        )

    receipt = verify_protected_evidence(
        policy=_policy(), local=local, hosted=hosted
    )

    assert receipt.evidence_verification is EvidenceVerification.REJECTED
    assert blocker in receipt.blockers or any(
        blocker in item for item in receipt.blockers
    )


def test_missing_or_duplicate_required_check_is_rejected() -> None:
    hosted = _snapshot()
    missing = hosted.model_copy(update={"check_runs": hosted.check_runs[1:]})
    duplicate = hosted.model_copy(
        update={"check_runs": (*hosted.check_runs, hosted.check_runs[0])}
    )

    missing_receipt = verify_protected_evidence(
        policy=_policy(), local=_local(), hosted=missing
    )
    duplicate_receipt = verify_protected_evidence(
        policy=_policy(), local=_local(), hosted=duplicate
    )

    assert "hosted:check:Test-Goblin / routine:missing" in (
        missing_receipt.blockers
    )
    assert "hosted:check:Test-Goblin / routine:duplicate" in (
        duplicate_receipt.blockers
    )


def test_policy_rejects_duplicate_or_incomplete_check_enumeration() -> None:
    payload = _policy().model_dump(mode="json")
    with pytest.raises(ValidationError, match="unique"):
        ProtectedEvidencePolicy.model_validate({
            **payload,
            "required_checks": [
                payload["required_checks"][0],
                payload["required_checks"][0],
            ],
        })
    with pytest.raises(ValidationError, match="enumerate CI and security"):
        ProtectedEvidencePolicy.model_validate({
            **payload,
            "required_checks": [payload["required_checks"][0]],
        })


def test_workflow_run_must_match_exact_identity_and_success() -> None:
    hosted = _snapshot()
    failed = hosted.workflow_runs[0].model_copy(
        update={"conclusion": "failure"}
    )
    hosted = hosted.model_copy(
        update={"workflow_runs": (failed, *hosted.workflow_runs[1:])}
    )

    receipt = verify_protected_evidence(
        policy=_policy(), local=_local(), hosted=hosted
    )

    assert receipt.evidence_verification is EvidenceVerification.REJECTED
    assert any(
        "workflow-conclusion:failure" in item for item in receipt.blockers
    )


def test_durable_publication_receipt_can_make_evidence_release_eligible() -> (
    None
):
    publication = PublicationEvidence(
        state=PublicationState.VERIFIED,
        receipts=(
            PublicationReceipt(
                surface="github_release",
                object_identity="global-medicines-atlas-v0.9.0",
                durable_url=(
                    "https://github.com/edithatogo/global-medicines-atlas/"
                    "releases/tag/v0.9.0"
                ),
                commit_sha=COMMIT,
                artifact_sha256="c" * 64,
            ),
        ),
    )
    hosted = _snapshot().model_copy(update={"publication": publication})

    receipt = verify_protected_evidence(
        policy=_policy(), local=_local(), hosted=hosted
    )

    assert receipt.evidence_verification is EvidenceVerification.VERIFIED
    assert receipt.release_eligibility is ReleaseEligibility.ELIGIBLE
    assert not receipt.release_blockers


def test_publication_cannot_be_claimed_without_durable_receipt() -> None:
    with pytest.raises(ValidationError, match="durable receipt"):
        PublicationEvidence(state=PublicationState.VERIFIED)

    with pytest.raises(ValidationError, match="cannot carry receipts"):
        PublicationEvidence(
            state=PublicationState.NOT_ATTEMPTED,
            receipts=(
                PublicationReceipt(
                    surface="zenodo",
                    object_identity="record-1",
                    durable_url="https://zenodo.org/records/1",
                    commit_sha=COMMIT,
                    artifact_sha256="c" * 64,
                ),
            ),
        )

    with pytest.raises(ValidationError, match="requires a blocker"):
        PublicationEvidence(state=PublicationState.BLOCKED)
    with pytest.raises(ValidationError, match="require blocked state"):
        PublicationEvidence(
            state=PublicationState.NOT_ATTEMPTED,
            blockers=("licence-decision",),
        )


def test_required_check_result_cannot_be_forged() -> None:
    with pytest.raises(ValidationError, match="exact identity"):
        RequiredCheckVerification(
            name="check",
            category="ci",
            app_slug="github-actions",
            verified=True,
        )
    with pytest.raises(ValidationError, match="requires a blocker"):
        RequiredCheckVerification(
            name="check",
            category="security",
            app_slug="github-actions",
            verified=False,
        )


def test_repository_pr_and_publication_commit_mismatches_are_rejected() -> None:
    hosted = _snapshot().model_copy(
        update={
            "repository": "other/project",
            "pull_request": _snapshot().pull_request.model_copy(
                update={"number": 102}
            ),
            "publication": PublicationEvidence(
                state=PublicationState.VERIFIED,
                receipts=(
                    PublicationReceipt(
                        surface="zenodo",
                        object_identity="record-1",
                        durable_url="https://zenodo.org/records/1",
                        commit_sha="b" * 40,
                        artifact_sha256="c" * 64,
                    ),
                ),
            ),
        }
    )

    receipt = verify_protected_evidence(
        policy=_policy(), local=_local(), hosted=hosted
    )

    assert "hosted:repository-mismatch" in receipt.blockers
    assert "hosted:pull-request-mismatch" in receipt.blockers
    assert "publication:receipt:zenodo:commit-mismatch" in receipt.blockers


def test_receipt_rejects_forged_verified_state() -> None:
    rejected = verify_protected_evidence(
        policy=_policy(),
        local=_local(dirty=True),
        hosted=_snapshot(),
    )

    with pytest.raises(ValidationError, match="verified evidence"):
        ProtectedEvidenceReceipt.model_validate({
            **rejected.model_dump(mode="json"),
            "evidence_verification": "verified",
        })

    with pytest.raises(ValidationError, match="requires blockers"):
        ProtectedEvidenceReceipt.model_validate({
            **rejected.model_dump(mode="json"),
            "blockers": [],
        })
    with pytest.raises(ValidationError, match="verified durable evidence"):
        ProtectedEvidenceReceipt.model_validate({
            **rejected.model_dump(mode="json"),
            "release_eligibility": "eligible",
            "release_blockers": [],
        })
    with pytest.raises(ValidationError, match="requires release blockers"):
        ProtectedEvidenceReceipt.model_validate({
            **rejected.model_dump(mode="json"),
            "release_blockers": [],
        })


def test_local_git_inspection_is_explicitly_local_truth() -> None:
    observed = inspect_local_truth(Path.cwd())

    assert len(observed.commit_sha) == 40
    assert isinstance(observed.dirty, bool)


def test_receipt_writer_emits_content_digest_and_schema_validates(
    tmp_path: Path,
) -> None:
    receipt = verify_protected_evidence(
        policy=_policy(), local=_local(), hosted=_snapshot()
    )
    output = tmp_path / "receipt.json"

    digest_path = write_protected_evidence_receipt(output, receipt)

    assert output.read_bytes() == receipt.canonical_json()
    assert digest_path.read_text(encoding="ascii") == f"{receipt.digest()}\n"
    schema = json.loads(
        Path("schemas/protected-evidence-receipt-v1.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(
        receipt.model_dump(mode="json")
    )
