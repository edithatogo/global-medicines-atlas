"""Reconcile independently observed donor deltas without reading payloads.

The caller must obtain a complete, authenticated Git comparison independently.
This offline checker does not fetch GitHub, authenticate observations, preserve
history, establish behavioral parity, grant rights, or authorize archival.
Only added/modified deltas are supported; other changes need a new profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

BASELINES = {
    "edithatogo/aus_mbs_pbs_graph": "64e764cebeb3826f98ce672cbb4affc65d06a92f",
    "edithatogo/aus-health-data-scraper": "931da0b9b6ae3e3cec0743568abb71a50d62b7cf",
}


class _Metadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _path(value: str) -> str:
    path = PurePosixPath(value)
    if not value.isprintable() or "\\" in value:
        raise ValueError("invalid donor path")
    if (
        not path.parts
        or value != value.strip()
        or path.is_absolute()
        or str(path) != value
        or ".." in path.parts
    ):
        raise ValueError("invalid donor path")
    return value


class ChangedFile(_Metadata):
    """Exact path and Git blob identity from an added/modified comparison."""

    path: str
    blob: str = Field(pattern=r"^[0-9a-f]{40}$", min_length=40, max_length=40)
    status: Literal["added", "modified"]

    _valid_path = field_validator("path")(_path)


class DeltaObservation(_Metadata):
    """Caller-observed complete delta for one frozen donor baseline."""

    repository: str
    baseline: str = Field(
        pattern=r"^[0-9a-f]{40}$", min_length=40, max_length=40
    )
    head: str = Field(pattern=r"^[0-9a-f]{40}$", min_length=40, max_length=40)
    ancestry: Literal["ahead"]
    files: tuple[ChangedFile, ...] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def exact_identity(self) -> Self:
        """Reject unrelated baselines, unchanged heads and duplicate paths."""
        if BASELINES.get(self.repository) != self.baseline:
            raise ValueError("unknown donor baseline")
        if self.head == self.baseline:
            raise ValueError("ahead comparison requires a changed head")
        if len({item.path for item in self.files}) != len(self.files):
            raise ValueError("duplicate changed path")
        return self


class FileDisposition(_Metadata):
    """A review decision, not proof the chosen behavior has been executed."""

    path: str
    disposition: Literal[
        "documentation-only", "supersede", "retain-legacy", "adapt", "pending"
    ]
    reason: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(min_length=1, max_length=2000)

    _valid_path = field_validator("path")(_path)

    @field_validator("reason", "evidence")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        """Reject blank or padded review evidence."""
        if value != value.strip() or not value:
            raise ValueError("review text must be nonblank and unpadded")
        return value


class DeltaReview(_Metadata):
    """Disposition inventory supplied separately from trusted observations."""

    observation: DeltaObservation
    dispositions: tuple[FileDisposition, ...] = Field(max_length=10000)


@dataclass(frozen=True)
class DeltaResult:
    """Independent outcomes; disposition is not preservation or authority.

    ``no_data_delta`` classifies known path roles only. It does not prove code
    or documentation contains no embedded payloads, or authenticate complete
    remote tree coverage. Unknown path roles are conservatively possible data.
    """

    no_data_delta: bool
    functionality_disposition_complete: bool
    current_head_history_preserved: Literal[False] = False
    archive_authorized: Literal[False] = False


def _non_data(path: str) -> bool:
    # Unknown formats/locations are conservatively possible data, not excluded.
    pure = PurePosixPath(path)
    return (
        _documentation(path)
        or (pure.parts[0] in {"src", "tests"} and pure.suffix == ".py")
        or (
            pure.parts[:2] == (".github", "workflows")
            and pure.suffix in {".yml", ".yaml"}
        )
    )


def _documentation(path: str) -> bool:
    pure = PurePosixPath(path)
    return path in {"README.md", "SUCCESSOR.md"} or (
        pure.parts[0] == "docs" and pure.suffix == ".md"
    )


def reconcile_delta(
    review: DeltaReview, observed: DeltaObservation
) -> DeltaResult:
    """Check exact identities/denominators against caller-admitted metadata.

    Args:
        review: Proposed complete review inventory.
        observed: Independently verified complete comparison, never inferred
            from the review itself by this function.

    Returns:
        Conservative data/disposition flags; preservation/authority stay false.

    Raises:
        ValueError: Identity, file denominator or classification mismatches.
    """
    review = DeltaReview.model_validate(review.model_dump())
    observed = DeltaObservation.model_validate(observed.model_dump())
    if review.observation != observed:
        raise ValueError("review differs from independently observed delta")
    dispositions = {item.path: item for item in review.dispositions}
    if len(dispositions) != len(review.dispositions) or set(dispositions) != {
        item.path for item in observed.files
    }:
        raise ValueError("disposition denominator mismatch")
    for item in observed.files:
        if dispositions[
            item.path
        ].disposition == "documentation-only" and not _documentation(item.path):
            raise ValueError("non-documentation change needs functional review")
    return DeltaResult(
        no_data_delta=all(_non_data(item.path) for item in observed.files),
        functionality_disposition_complete=all(
            item.disposition != "pending" for item in review.dispositions
        ),
    )
