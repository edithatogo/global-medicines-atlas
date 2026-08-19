"""Fail-closed publication planning without external transport side effects."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Protocol, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonBlank = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1024),
]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

PUBLICATION_ENVIRONMENT_VARIABLE = "GMA_PUBLICATION_ENVIRONMENT"
PUBLICATION_APPROVAL_VARIABLE = "GMA_MAINTAINER_PUBLICATION_APPROVED"
PRODUCTION_ENVIRONMENT = "production"
APPROVAL_VALUE = "yes-i-approve-publication"


class PublicationTransportModel(BaseModel):
    """Immutable model that rejects undocumented transport fields."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class PublicationDestination(StrEnum):
    """Supported destination classes; neither implies a transport."""

    HUGGING_FACE = "hugging_face"
    ARCHIVAL = "archival"


class PublicationTransportState(StrEnum):
    """Observable states in the external publication lifecycle."""

    PREPARED = "prepared"
    UPLOADED = "uploaded"
    PUBLIC = "public"
    VERIFICATION_FAILED = "verification_failed"


class ArtifactBinding(PublicationTransportModel):
    """Identity of one immutable local artifact."""

    relative_path: NonBlank
    sha256: Sha256
    size: int = Field(ge=0)

    @field_validator("relative_path")
    @classmethod
    def path_is_safe(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in value
            or value != path.as_posix()
        ):
            raise ValueError("artifact path must be normalized, relative POSIX")
        return value


class PublicationTarget(PublicationTransportModel):
    """A named remote target without credentials or write capability."""

    destination: PublicationDestination
    repository: Annotated[
        NonBlank, Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    ]
    revision: Annotated[
        NonBlank, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    ]
    public_base_url: Annotated[
        NonBlank,
        Field(
            pattern=r"^https://[A-Za-z0-9.-]+(?:/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*)?$"
        ),
    ]

    @model_validator(mode="after")
    def destination_matches_host(self) -> Self:
        expected_host = {
            PublicationDestination.HUGGING_FACE: "https://huggingface.co/",
            PublicationDestination.ARCHIVAL: "https://",
        }[self.destination]
        if not self.public_base_url.startswith(expected_host):
            raise ValueError("target URL does not match destination")
        return self


class PublicationPlan(PublicationTransportModel):
    """Deterministic dry-run plan bound to exact artifacts."""

    plan_version: NonBlank = "1"
    release_version: NonBlank
    target: PublicationTarget
    artifacts: tuple[ArtifactBinding, ...] = Field(min_length=1)
    dry_run: bool = True
    maintainer_approved: bool = False

    @model_validator(mode="after")
    def plan_is_safe_and_canonical(self) -> Self:
        if not self.dry_run:
            raise ValueError("plans are always prepared as dry runs")
        if self.maintainer_approved:
            raise ValueError("approval must not be embedded in a prepared plan")
        paths = tuple(item.relative_path for item in self.artifacts)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("artifacts must have unique paths in sorted order")
        digests = tuple(item.sha256 for item in self.artifacts)
        if len(digests) != len(set(digests)):
            raise ValueError("artifact digests must be unique")
        return self

    def canonical_bytes(self) -> bytes:
        payload = self.model_dump(mode="json")
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


class PublicationAuthorization(PublicationTransportModel):
    """Ephemeral dual gate evaluated immediately before a future write."""

    environment: NonBlank
    maintainer_approval: NonBlank

    @property
    def permits_external_write(self) -> bool:
        return (
            self.environment == PRODUCTION_ENVIRONMENT
            and self.maintainer_approval == APPROVAL_VALUE
        )


class PublicationTransportReceipt(PublicationTransportModel):
    """Durable, content-addressed state evidence for a prepared plan."""

    receipt_version: NonBlank = "1"
    plan_sha256: Sha256
    artifact_sha256: tuple[Sha256, ...] = Field(min_length=1)
    target: PublicationTarget
    state: PublicationTransportState
    recorded_at: AwareDatetime
    remote_revision: NonBlank | None = None
    verification_uri: NonBlank | None = None
    failure_reason: NonBlank | None = None

    @model_validator(mode="after")
    def state_has_required_evidence(self) -> Self:
        if len(self.artifact_sha256) != len(set(self.artifact_sha256)):
            raise ValueError("receipt artifact digests must be unique")
        has_remote = self.remote_revision is not None
        has_verification = self.verification_uri is not None
        has_failure = self.failure_reason is not None
        if self.state is PublicationTransportState.PREPARED:
            if has_remote or has_verification or has_failure:
                raise ValueError("prepared state cannot claim remote evidence")
        elif self.state is PublicationTransportState.UPLOADED:
            if not has_remote or has_verification or has_failure:
                raise ValueError(
                    "uploaded state requires only a remote revision"
                )
        elif self.state is PublicationTransportState.PUBLIC:
            if not has_remote or not has_verification or has_failure:
                raise ValueError(
                    "public state requires remote and verification evidence"
                )
            verification_uri = self.verification_uri
            if verification_uri is None or not verification_uri.startswith(
                "https://"
            ):
                raise ValueError("public verification URI must use HTTPS")
        elif not has_failure or has_verification:
            raise ValueError(
                "verification-failed state requires only a failure reason"
            )
        return self


def authorization_from_environment(
    environment: Mapping[str, str],
) -> PublicationAuthorization:
    """Read the two explicit external-write gates without accepting defaults."""

    return PublicationAuthorization(
        environment=environment.get(PUBLICATION_ENVIRONMENT_VARIABLE, "unset"),
        maintainer_approval=environment.get(
            PUBLICATION_APPROVAL_VARIABLE, "unset"
        ),
    )


def bind_artifacts(
    root: Path, relative_paths: tuple[str, ...]
) -> tuple[ArtifactBinding, ...]:
    """Hash root-contained regular files without following escaping links."""

    resolved_root = root.resolve(strict=True)
    if not relative_paths:
        raise ValueError("at least one artifact path is required")
    if tuple(sorted(relative_paths)) != relative_paths:
        raise ValueError("artifact paths must be sorted")
    bindings: list[ArtifactBinding] = []
    for relative_path in relative_paths:
        candidate = ArtifactBinding(
            relative_path=relative_path,
            sha256="0" * 64,
            size=0,
        )
        resolved = (resolved_root / candidate.relative_path).resolve(
            strict=True
        )
        try:
            resolved.relative_to(resolved_root)
        except ValueError as error:
            raise ValueError(
                "artifact resolves outside publication root"
            ) from error
        if not resolved.is_file():
            raise ValueError("publication artifact must be a regular file")
        payload = resolved.read_bytes()
        bindings.append(
            ArtifactBinding(
                relative_path=candidate.relative_path,
                sha256=hashlib.sha256(payload).hexdigest(),
                size=len(payload),
            )
        )
    return tuple(bindings)


def prepare_publication(
    *,
    root: Path,
    release_version: str,
    target: PublicationTarget,
    relative_paths: tuple[str, ...],
    recorded_at: datetime,
) -> tuple[PublicationPlan, PublicationTransportReceipt]:
    """Prepare deterministic upload metadata and a local-only receipt."""

    plan = PublicationPlan(
        release_version=release_version,
        target=target,
        artifacts=bind_artifacts(root, relative_paths),
    )
    receipt = PublicationTransportReceipt(
        plan_sha256=plan.sha256(),
        artifact_sha256=tuple(item.sha256 for item in plan.artifacts),
        target=target,
        state=PublicationTransportState.PREPARED,
        recorded_at=recorded_at,
    )
    return plan, receipt


def assert_external_write_authorized(
    authorization: PublicationAuthorization,
) -> None:
    """Fail unless both explicit gates authorize a future transport."""

    if not authorization.permits_external_write:
        raise PermissionError(
            "external publication requires production environment and "
            "explicit maintainer approval"
        )


class PublicationUploader(Protocol):
    """Execute a prepared upload without embedding credentials."""

    def upload_folder(
        self,
        *,
        repository: str,
        folder: Path,
        commit_message: str,
    ) -> str: ...


def execute_publication(
    *,
    plan: PublicationPlan,
    authorization: PublicationAuthorization,
    root: Path,
    uploader: PublicationUploader,
    recorded_at: datetime,
) -> PublicationTransportReceipt:
    """Upload prepared artifacts after the dual external-write gate."""

    assert_external_write_authorized(authorization)
    current = bind_artifacts(
        root, tuple(item.relative_path for item in plan.artifacts)
    )
    planned = tuple(item.sha256 for item in plan.artifacts)
    observed = tuple(item.sha256 for item in current)
    if planned != observed:
        return PublicationTransportReceipt(
            plan_sha256=plan.sha256(),
            artifact_sha256=planned,
            target=plan.target,
            state=PublicationTransportState.VERIFICATION_FAILED,
            recorded_at=recorded_at,
            failure_reason="local artifacts no longer match the prepared plan",
        )
    revision = uploader.upload_folder(
        repository=plan.target.repository,
        folder=root,
        commit_message=f"Archive {plan.release_version}",
    )
    verification_uri = (
        f"{plan.target.public_base_url.rstrip('/')}/tree/{revision}"
    )
    return PublicationTransportReceipt(
        plan_sha256=plan.sha256(),
        artifact_sha256=planned,
        target=plan.target,
        state=PublicationTransportState.PUBLIC,
        recorded_at=recorded_at,
        remote_revision=revision,
        verification_uri=verification_uri,
    )
