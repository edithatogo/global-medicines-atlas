"""Policy checks for release-only provenance attestations."""

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "release-provenance.yml"
)


def test_provenance_attestation_is_release_only_and_sha_pinned() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "release:" in workflow
    assert "types: [published]" in workflow
    assert "workflow_dispatch:" not in workflow
    assert "push:" not in workflow
    assert "pull_request:" not in workflow
    assert "github.event.release.draft == false" in workflow
    assert (
        "actions/attest-build-provenance@"
        "977bb373ede98d70efdf65b84cb5f73e068dcc2a" in workflow
    )


def test_provenance_job_has_minimal_required_permissions() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "contents: read" in workflow
    assert "id-token: write" in workflow
    assert "attestations: write" in workflow
    assert "contents: write" in workflow
    assert "persist-credentials: false" in workflow
    assert (
        "actions/upload-artifact@"
        "b7c566a772e6b6bfb58ed0dc250532a479d7789f" in workflow
    )
    assert "\n          path: dist/*" in workflow
    assert 'gh release upload "$RELEASE_TAG" dist/* --clobber' in workflow
    assert "subject-path: dist/*" in workflow
