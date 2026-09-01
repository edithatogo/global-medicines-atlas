"""Pure append-plan checks for two exact donor history extensions.

These models validate caller-supplied metadata, not Git, HTTP, receipts or
credentials. They perform no I/O and grant no publication, cleanup or archival
authority. A future hosted publisher must independently authenticate every
observation, bind an exact authorization and record durable verification.
"""

from __future__ import annotations

import hashlib
import os
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .donor_delta import ChangedFile, DeltaObservation

GitId = Annotated[
    str, Field(pattern=r"^[0-9a-f]{40}$", min_length=40, max_length=40)
]
Digest = Annotated[
    str, Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
]
ApprovalReference = Annotated[
    str,
    Field(
        pattern=(
            r"^https://github\.com/edithatogo/global-medicines-atlas/"
            r"issues/339#issuecomment-[1-9][0-9]*$"
        ),
        max_length=200,
    ),
]
EXACT_HEADS = (
    (
        "edithatogo/aus_mbs_pbs_graph",
        "3993e5e331eb2d3d9e9d354d80e52c684ad26a1e",
    ),
    (
        "edithatogo/aus-health-data-scraper",
        "009e80544588a956c8922aaab052ee08947e2b30",
    ),
)
MAX_DELTA_PATHS = 256
MAX_METADATA_PATH_LENGTH = 1024


class _Metadata(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("evidence flag must be an exact boolean")
    return value


class HistoryObject(_Metadata):
    """An exact nonempty object; metadata is not proof of its remote bytes."""

    path: str = Field(max_length=1024)
    sha256: Digest
    byte_count: int = Field(strict=True, gt=0, le=1024 * 1024 * 1024)

    @model_validator(mode="after")
    def safe_path(self) -> Self:
        """Reuse canonical donor path validation without reading a blob."""
        ChangedFile(path=self.path, blob="0" * 40, status="added")
        return self


class HistoryArchiveState(_Metadata):
    """A caller-observed public existing archive inventory at one revision."""

    dataset: Literal["edithatogo/australian-mbs-source-archive"]
    revision: GitId
    private: Literal[False]
    gated: Literal[False]
    objects: tuple[HistoryObject, ...] = Field(min_length=1, max_length=10000)

    _strict_flags = field_validator("private", "gated", mode="before")(_boolean)

    @model_validator(mode="after")
    def unique_paths(self) -> Self:
        """Require an unambiguous complete supplied object denominator."""
        _objects(self.objects)
        return self


def _objects(objects: tuple[HistoryObject, ...]) -> dict[str, HistoryObject]:
    result = {item.path: item for item in objects}
    if len(result) != len(objects):
        raise ValueError("duplicate history object path")
    return result


def observation_digest(observation: DeltaObservation) -> str:
    """Hash revalidated canonical model JSON, retaining observed file order."""
    checked = DeltaObservation.model_validate(observation.model_dump())
    return hashlib.sha256(checked.model_dump_json().encode()).hexdigest()


def _bundle_path(repository: str, commit: str) -> str:
    return f"history/{repository.split('/', 1)[1]}-{commit}.bundle"


class HistoryExtension(_Metadata):
    """Incremental bundle and sidecar bound to one exact observed delta."""

    observation: DeltaObservation
    delta_sha256: Digest
    bundle: HistoryObject
    manifest: HistoryObject

    @field_validator("observation", mode="before")
    @classmethod
    def normalize_observation(cls, value: object) -> object:
        """Reconstruct imported models rather than retaining mutable copies."""
        if isinstance(value, DeltaObservation):
            return value.model_dump(warnings=False)
        return value

    @model_validator(mode="after")
    def exact_paths(self) -> Self:
        """Reject relabelled heads, observations and non-head-addressed paths."""
        observed = self.observation
        if len(observed.files) > MAX_DELTA_PATHS or any(
            len(item.path) > MAX_METADATA_PATH_LENGTH for item in observed.files
        ):
            raise ValueError("history delta metadata exceeds bounded profile")
        if dict(EXACT_HEADS).get(observed.repository) != observed.head:
            raise ValueError("history extension head is outside exact scope")
        if self.delta_sha256 != observation_digest(observed):
            raise ValueError("delta digest mismatch")
        name = observed.repository.split("/", 1)[1]
        if self.bundle.path != _bundle_path(observed.repository, observed.head):
            raise ValueError("bundle path does not bind exact head")
        if self.manifest.path != (
            f"provenance/donor-deltas/{name}-{observed.head}.json"
        ):
            raise ValueError("manifest path does not bind exact head")
        return self


class HistoryAppendPlan(_Metadata):
    """Two incremental histories; no source bytes or authorization embedded."""

    before: HistoryArchiveState
    extensions: tuple[HistoryExtension, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def append_only(self) -> Self:
        """Require both donors, existing baseline bundles and no overwrites."""
        repositories = {item.observation.repository for item in self.extensions}
        if repositories != {item[0] for item in EXACT_HEADS}:
            raise ValueError("history plan requires both exact donors")
        existing = _objects(self.before.objects)
        for extension in self.extensions:
            observation = extension.observation
            if (
                _bundle_path(observation.repository, observation.baseline)
                not in existing
            ):
                raise ValueError("baseline history prerequisite is absent")
            for item in (extension.bundle, extension.manifest):
                if item.path in existing and existing[item.path] != item:
                    raise ValueError("append would overwrite existing history")
        return self


class RestoredHistory(_Metadata):
    """Observed clean Git reconstruction, not a claim authenticated here."""

    repository: str
    head: GitId
    baseline: GitId
    baseline_bundle_sha256: Digest
    bundle_sha256: Digest
    delta_sha256: Digest
    prerequisites: tuple[GitId, ...] = Field(min_length=1, max_length=1)
    baseline_is_ancestor: Literal[True]
    clean_restore: Literal[True]

    _strict_flags = field_validator(
        "baseline_is_ancestor", "clean_restore", mode="before"
    )(_boolean)


def validate_append_plan(
    plan: HistoryAppendPlan,
    observations: tuple[DeltaObservation, ...],
) -> HistoryAppendPlan:
    """Revalidate plan against independently obtained exact delta metadata.

    This is consistency validation, not authentication or permission. The
    hosted caller remains responsible for a complete trusted Git comparison.
    """
    checked = HistoryAppendPlan.model_validate(plan.model_dump())
    if len(observations) != len(EXACT_HEADS):
        raise ValueError("independent observation denominator differs")
    independent = tuple(
        DeltaObservation.model_validate(item.model_dump())
        for item in observations
    )
    expected = {
        item.observation.repository: item.observation
        for item in checked.extensions
    }
    if (
        len({item.repository for item in independent}) != len(independent)
        or {item.repository: item for item in independent} != expected
    ):
        raise ValueError("independent observation differs from history plan")
    return checked


class HistoryVerification(_Metadata):
    """Full supplied evidence retained so copied models can be revalidated."""

    plan: HistoryAppendPlan
    parent_revision: GitId
    after: HistoryArchiveState
    anonymous_objects: tuple[HistoryObject, ...] = Field(
        min_length=6, max_length=6
    )
    restored: tuple[RestoredHistory, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def exact_restore(self) -> Self:
        """Check CAS, unchanged prior objects and exact anonymous/Git evidence."""
        if self.parent_revision != self.plan.before.revision:
            raise ValueError("publication parent differs from planned CAS")
        if self.after.revision == self.parent_revision:
            raise ValueError("verification requires a new publication revision")
        expected = _objects(self.plan.before.objects)
        required: dict[str, HistoryObject] = {}
        restores = {item.repository: item for item in self.restored}
        if len(restores) != len(self.restored):
            raise ValueError("duplicate restored donor")
        for extension in self.plan.extensions:
            observed = extension.observation
            baseline = expected[
                _bundle_path(observed.repository, observed.baseline)
            ]
            for item in (baseline, extension.bundle, extension.manifest):
                required[item.path] = item
            expected.update(_objects((extension.bundle, extension.manifest)))
            restore = restores.get(observed.repository)
            if restore != RestoredHistory(
                repository=observed.repository,
                head=observed.head,
                baseline=observed.baseline,
                baseline_bundle_sha256=baseline.sha256,
                bundle_sha256=extension.bundle.sha256,
                delta_sha256=extension.delta_sha256,
                prerequisites=(observed.baseline,),
                baseline_is_ancestor=True,
                clean_restore=True,
            ):
                raise ValueError("restored Git history differs from exact plan")
        if _objects(self.after.objects) != expected:
            raise ValueError(
                "publication changed previous objects or sibling set"
            )
        if _objects(self.anonymous_objects) != required:
            raise ValueError("anonymous object verification differs from plan")
        return self


class DurableHistoryReceipt(_Metadata):
    """An observed issue receipt identity; URL format is not authentication."""

    issue_comment: str = Field(
        pattern=(
            r"^https://github\.com/edithatogo/global-medicines-atlas/"
            r"issues/340#issuecomment-[1-9][0-9]*$"
        ),
        max_length=200,
    )
    verification_sha256: Digest


class DonorHistoryPublicationContract(_Metadata):
    """Exact hosted authority envelope; false remains deliberately inert."""

    dataset: Literal["edithatogo/australian-mbs-source-archive"]
    heads: tuple[tuple[str, GitId], ...] = Field(min_length=2, max_length=2)
    publication_authorized: bool = False
    authorization_reference: ApprovalReference | None = None

    _strict_authority_flag = field_validator(
        "publication_authorized", mode="before"
    )(_boolean)

    @model_validator(mode="after")
    def exact_scope(self) -> Self:
        if self.heads != EXACT_HEADS:
            raise ValueError("history publication contract heads differ")
        if self.publication_authorized != (
            self.authorization_reference is not None
        ):
            raise ValueError("authorization flag and exact receipt must agree")
        return self


def require_donor_history_hosted_authority(
    contract: DonorHistoryPublicationContract,
) -> None:
    """Reject every run until an explicitly approved contract replaces this one."""
    checked = DonorHistoryPublicationContract.model_validate(
        contract.model_dump()
    )
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY")
        != "edithatogo/global-medicines-atlas"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
    ):
        raise ValueError(
            "donor history publication requires GitHub Actions on main"
        )
    if not checked.publication_authorized:
        raise ValueError("exact donor history publication is not authorized")


def verification_digest(verification: HistoryVerification) -> str:
    """Revalidate complete nested evidence and compute its receipt binding."""
    checked = HistoryVerification.model_validate(verification.model_dump())
    return hashlib.sha256(checked.model_dump_json().encode()).hexdigest()


def cleanup_preconditions_match(
    verification: HistoryVerification, receipt: DurableHistoryReceipt
) -> bool:
    """Check receipt binding only; do not authenticate, authorize or delete.

    A future hosted caller must independently retrieve the durable issue
    receipt and verify Git/anonymous evidence before using this consistency
    result. Passing a fabricated matching receipt cannot establish authority.
    """
    checked = DurableHistoryReceipt.model_validate(receipt.model_dump())
    return verification_digest(verification) == checked.verification_sha256
