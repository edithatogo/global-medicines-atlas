from __future__ import annotations

import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - local script
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.publication_transport import (
    APPROVAL_VALUE,
    PRODUCTION_ENVIRONMENT,
    ArtifactBinding,
    PublicationAuthorization,
    PublicationDestination,
    PublicationPlan,
    PublicationTarget,
    PublicationTransportReceipt,
    PublicationTransportState,
    assert_external_write_authorized,
    authorization_from_environment,
    bind_artifacts,
    prepare_publication,
)

NOW = datetime(2026, 7, 29, 12, tzinfo=UTC)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def target(
    destination: PublicationDestination = PublicationDestination.HUGGING_FACE,
) -> PublicationTarget:
    url = (
        "https://huggingface.co/datasets/edithatogo/global-medicines-atlas"
        if destination is PublicationDestination.HUGGING_FACE
        else "https://archive.example.org/global-medicines-atlas"
    )
    return PublicationTarget(
        destination=destination,
        repository="edithatogo/global-medicines-atlas",
        revision="v0.7.0",
        public_base_url=url,
    )


def artifact(
    path: str = "data/a.parquet", digest: str = DIGEST_A
) -> ArtifactBinding:
    return ArtifactBinding(relative_path=path, sha256=digest, size=3)


def plan() -> PublicationPlan:
    return PublicationPlan(
        release_version="0.7.0",
        target=target(),
        artifacts=(artifact(),),
    )


@pytest.mark.parametrize(
    "path",
    ["../secret", "/absolute", "data\\windows", "data/../secret"],
)
def test_artifact_paths_fail_closed(path: str) -> None:
    with pytest.raises(ValidationError):
        artifact(path)


def test_target_rejects_non_hugging_face_host() -> None:
    with pytest.raises(ValidationError):
        PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository="owner/repo",
            revision="main",
            public_base_url="https://example.org/owner/repo",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repository", "not-a-pair"),
        ("revision", "../main"),
        ("public_base_url", "http://huggingface.co/owner/repo"),
    ],
)
def test_target_rejects_unsafe_identity(field: str, value: str) -> None:
    payload = target().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        PublicationTarget.model_validate(payload)


def test_archival_target_is_supported_without_transport() -> None:
    assert target(PublicationDestination.ARCHIVAL).destination is (
        PublicationDestination.ARCHIVAL
    )


def test_plan_is_deterministic_and_dry_run() -> None:
    first = plan()
    second = PublicationPlan.model_validate(first.model_dump())
    assert first.dry_run is True
    assert first.maintainer_approved is False
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.sha256() == second.sha256()


@pytest.mark.parametrize(
    "changes",
    [
        {"dry_run": False},
        {"maintainer_approved": True},
        {"artifacts": (artifact("z", DIGEST_A), artifact("a", DIGEST_B))},
        {"artifacts": (artifact("a", DIGEST_A), artifact("a", DIGEST_B))},
        {"artifacts": (artifact("a", DIGEST_A), artifact("b", DIGEST_A))},
    ],
)
def test_plan_rejects_unsafe_or_noncanonical_content(
    changes: dict[str, object],
) -> None:
    payload = plan().model_dump()
    payload.update(changes)
    with pytest.raises(ValidationError):
        PublicationPlan.model_validate(payload)


@pytest.mark.parametrize(
    ("environment", "approval", "permitted"),
    [
        (PRODUCTION_ENVIRONMENT, APPROVAL_VALUE, True),
        (PRODUCTION_ENVIRONMENT, "yes", False),
        ("staging", APPROVAL_VALUE, False),
        ("production ", APPROVAL_VALUE, True),
        ("PRODUCTION", APPROVAL_VALUE, False),
    ],
)
def test_dual_authorization_gate(
    environment: str, approval: str, *, permitted: bool
) -> None:
    authorization = PublicationAuthorization(
        environment=environment,
        maintainer_approval=approval,
    )
    assert authorization.permits_external_write is permitted
    if permitted:
        assert_external_write_authorized(authorization)
    else:
        with pytest.raises(PermissionError):
            assert_external_write_authorized(authorization)


def test_environment_authorization_has_no_permissive_defaults() -> None:
    authorization = authorization_from_environment({})
    assert authorization.environment == "unset"
    assert authorization.maintainer_approval == "unset"
    assert not authorization.permits_external_write


def test_environment_authorization_requires_both_exact_values() -> None:
    authorization = authorization_from_environment({
        "GMA_PUBLICATION_ENVIRONMENT": PRODUCTION_ENVIRONMENT,
        "GMA_MAINTAINER_PUBLICATION_APPROVED": APPROVAL_VALUE,
    })
    assert authorization.permits_external_write


def receipt_payload(state: PublicationTransportState) -> dict[str, object]:
    return {
        "plan_sha256": plan().sha256(),
        "artifact_sha256": (DIGEST_A,),
        "target": target(),
        "state": state,
        "recorded_at": NOW,
    }


def test_prepared_receipt_has_no_remote_claims() -> None:
    receipt = PublicationTransportReceipt(
        **receipt_payload(PublicationTransportState.PREPARED)
    )
    assert receipt.state is PublicationTransportState.PREPARED


@pytest.mark.parametrize(
    ("state", "extra"),
    [
        (PublicationTransportState.PREPARED, {"remote_revision": "abc"}),
        (PublicationTransportState.PREPARED, {"failure_reason": "failed"}),
        (PublicationTransportState.UPLOADED, {}),
        (
            PublicationTransportState.UPLOADED,
            {"remote_revision": "abc", "verification_uri": "https://x.test"},
        ),
        (PublicationTransportState.PUBLIC, {"remote_revision": "abc"}),
        (
            PublicationTransportState.PUBLIC,
            {
                "remote_revision": "abc",
                "verification_uri": "http://x.test",
            },
        ),
        (PublicationTransportState.VERIFICATION_FAILED, {}),
        (
            PublicationTransportState.VERIFICATION_FAILED,
            {
                "failure_reason": "not observable",
                "verification_uri": "https://x.test",
            },
        ),
    ],
)
def test_receipt_states_fail_closed(
    state: PublicationTransportState, extra: dict[str, object]
) -> None:
    payload = receipt_payload(state)
    payload.update(extra)
    with pytest.raises(ValidationError):
        PublicationTransportReceipt(**payload)


def test_uploaded_public_and_failed_receipts_are_distinct() -> None:
    uploaded = PublicationTransportReceipt(
        **receipt_payload(PublicationTransportState.UPLOADED),
        remote_revision="commit-123",
    )
    public = PublicationTransportReceipt(
        **receipt_payload(PublicationTransportState.PUBLIC),
        remote_revision="commit-123",
        verification_uri="https://huggingface.co/datasets/owner/repo",
    )
    failed = PublicationTransportReceipt(
        **receipt_payload(PublicationTransportState.VERIFICATION_FAILED),
        failure_reason="remote revision was not publicly observable",
    )
    assert {uploaded.state, public.state, failed.state} == {
        PublicationTransportState.UPLOADED,
        PublicationTransportState.PUBLIC,
        PublicationTransportState.VERIFICATION_FAILED,
    }


def test_receipt_rejects_duplicate_artifact_digests() -> None:
    payload = receipt_payload(PublicationTransportState.PREPARED)
    payload["artifact_sha256"] = (DIGEST_A, DIGEST_A)
    with pytest.raises(ValidationError):
        PublicationTransportReceipt(**payload)


def test_bind_artifacts_records_exact_bytes(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    payload = b"abc"
    (tmp_path / "data" / "a.parquet").write_bytes(payload)
    bindings = bind_artifacts(tmp_path, ("data/a.parquet",))
    assert bindings == (
        ArtifactBinding(
            relative_path="data/a.parquet",
            sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            size=3,
        ),
    )


@pytest.mark.parametrize(
    "paths",
    [(), ("z", "a"), ("missing",)],
)
def test_bind_artifacts_rejects_missing_or_noncanonical_inputs(
    tmp_path: Path, paths: tuple[str, ...]
) -> None:
    with pytest.raises((ValueError, FileNotFoundError)):
        bind_artifacts(tmp_path, paths)


def test_bind_artifacts_rejects_directory(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    with pytest.raises(ValueError, match="regular file"):
        bind_artifacts(tmp_path, ("data",))


def test_bind_artifacts_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "escape"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is not available")
    with pytest.raises(ValueError, match="outside"):
        bind_artifacts(tmp_path, ("escape",))


def test_prepare_publication_binds_plan_and_receipt(tmp_path: Path) -> None:
    (tmp_path / "artifact.json").write_text("{}", encoding="utf-8")
    prepared_plan, receipt = prepare_publication(
        root=tmp_path,
        release_version="0.7.0",
        target=target(),
        relative_paths=("artifact.json",),
        recorded_at=NOW,
    )
    assert receipt.plan_sha256 == prepared_plan.sha256()
    assert receipt.artifact_sha256 == tuple(
        item.sha256 for item in prepared_plan.artifacts
    )
    assert receipt.state is PublicationTransportState.PREPARED


def test_preparation_script_emits_local_dry_run_only(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text('{"safe":true}', encoding="utf-8")
    script = Path("scripts/prepare_publication.py").resolve()
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [
            sys.executable,
            str(script),
            "--root",
            str(tmp_path),
            "--release-version",
            "0.7.0",
            "--destination",
            "hugging_face",
            "--repository",
            "edithatogo/global-medicines-atlas",
            "--revision",
            "v0.7.0",
            "--public-base-url",
            "https://huggingface.co/datasets/edithatogo/global-medicines-atlas",
            "--artifact",
            "artifact.json",
            "--recorded-at",
            NOW.isoformat(),
        ],
        check=True,
        capture_output=True,
        shell=False,
        text=True,
    )
    output = json.loads(result.stdout)
    assert output["plan"]["dry_run"] is True
    assert output["plan"]["maintainer_approved"] is False
    assert output["receipt"]["state"] == "prepared"
    assert "token" not in result.stdout.casefold()
