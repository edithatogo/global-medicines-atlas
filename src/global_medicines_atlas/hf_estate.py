"""Public-safe, denominator-bound observations of the visible Hub estate.

Enumeration is not a rights conclusion, payload acquisition or publication
receipt. Private identities are pseudonymized, not claimed anonymous.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Literal, Self, cast

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from .models import FrozenModel

Kind = Literal["model", "dataset", "space", "collection"]
KINDS: tuple[Kind, ...] = ("model", "dataset", "space", "collection")
COLLECTION_LIMIT = 100
REPOSITORY_LIMIT = 1001
_IDENTITY = re.compile(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+")
_REVISION = re.compile(r"[0-9a-f]{40}")
VISIBILITY_MAX_AGE_SECONDS = 3600


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class EstateEntry(FrozenModel):
    """Allowlisted metadata; unknown rights stay explicitly unassessed."""

    kind: Kind
    identity: str
    identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    private: StrictBool
    gated: StrictBool | Literal["auto", "manual"] | None
    revision: str | None = Field(pattern=r"^[0-9a-f]{40}$")
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    collection_item_count: int | None = Field(ge=0)
    scope: Literal["australian_source_archive", "gma_related", "unassessed"]
    rights_state: Literal["not_assessed"] = "not_assessed"
    publication_state: Literal["not_assessed"] = "not_assessed"
    disposition: Literal["retain_private", "review_required"]

    @model_validator(mode="after")
    def validate_private_boundary(self) -> Self:
        if self.private and (
            self.identity != f"private:{self.identity_sha256}"
            or self.disposition != "retain_private"
            or self.scope != "unassessed"
        ):
            raise ValueError(
                "private metadata must remain pseudonymized and unassessed"
            )
        if not self.private and (
            _IDENTITY.fullmatch(self.identity) is None
            or self.identity_sha256 != _digest([self.kind, self.identity])
        ):
            raise ValueError("public identity digest mismatch")
        return self


class EnumerationReceipt(FrozenModel):
    """Both stable scans must exhaust below the explicit result cap."""

    kind: Kind
    count: int = Field(ge=0)
    limit: int = Field(ge=1, le=REPOSITORY_LIMIT)
    entries_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    repeated_scan_equal: Literal[True] = True

    @model_validator(mode="after")
    def validate_exhaustion(self) -> Self:
        if self.count >= self.limit:
            raise ValueError("listing reached limit; exhaustion is unproven")
        if self.kind == "collection" and self.limit > COLLECTION_LIMIT:
            raise ValueError("collection endpoint limit exceeded")
        return self


class OwnerVisibilityEvidence(FrozenModel):
    """Minimal observed read grants; no token identity or value is permitted."""

    owner: str
    scope_owner: str
    scope_kind: Literal["user"]
    endpoint: Literal["https://huggingface.co/api/whoami-v2"]
    observed_at: AwareDatetime
    permissions: tuple[
        Literal["repo.content.read", "repo.access.read", "collection.read"], ...
    ]

    @model_validator(mode="after")
    def validate_read_grants(self) -> Self:
        required = {"repo.content.read", "repo.access.read", "collection.read"}
        if self.owner != self.scope_owner or set(self.permissions) != required:
            raise ValueError(
                "owner-wide repository and collection read grants required"
            )
        return self


class EstateSnapshot(FrozenModel):
    """A stable inventory with separately recorded credential-scope evidence."""

    schema_version: Literal["hf-estate-v1"] = "hf-estate-v1"
    owner: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    observed_at: AwareDatetime
    enumeration_scope: Literal["authenticated_visible_owner_metadata"] = (
        "authenticated_visible_owner_metadata"
    )
    credential_visibility_attested: StrictBool = False
    visibility_evidence: OwnerVisibilityEvidence | None = None
    entries: tuple[EstateEntry, ...]
    enumerations: tuple[EnumerationReceipt, ...]

    @model_validator(mode="after")
    def validate_denominator(self) -> Self:
        if self.credential_visibility_attested != (
            self.visibility_evidence is not None
        ):
            raise ValueError(
                "visibility claim requires explicit permission observation"
            )
        if self.visibility_evidence is not None:
            age = (
                self.observed_at - self.visibility_evidence.observed_at
            ).total_seconds()
            if (
                self.visibility_evidence.owner != self.owner
                or not 0 <= age <= VISIBILITY_MAX_AGE_SECONDS
            ):
                raise ValueError(
                    "visibility evidence owner or observation window mismatch"
                )
        if len(self.enumerations) != len(KINDS) or {
            item.kind for item in self.enumerations
        } != set(KINDS):
            raise ValueError("denominator requires all four kinds")
        identities = [
            (item.kind, item.identity_sha256) for item in self.entries
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate estate identity")
        for item in self.entries:
            if not item.private and not item.identity.startswith(
                f"{self.owner}/"
            ):
                raise ValueError("estate owner mismatch")
        for receipt in self.enumerations:
            entries = [
                item for item in self.entries if item.kind == receipt.kind
            ]
            if (
                len(entries) != receipt.count
                or _entries_digest(entries) != receipt.entries_sha256
            ):
                raise ValueError("observed denominator mismatch")
        return self


def _entries_digest(entries: list[EstateEntry]) -> str:
    return _digest([
        item.model_dump(mode="json")
        for item in sorted(entries, key=lambda item: item.identity_sha256)
    ])


def _scope(identity: str, *, private: bool) -> str:
    if private:
        return "unassessed"
    if identity in {
        "edithatogo/australian-mbs-source-archive",
        "edithatogo/australian-pbs-source-archive",
    }:
        return "australian_source_archive"
    if identity in {
        "edithatogo/global-medicines-atlas-international-open",
        "edithatogo/dataset-estate-registry",
        "edithatogo/reimbursement-atlas",
    }:
        return "gma_related"
    return "unassessed"


def _entry(owner: str, kind: Kind, raw: dict[str, Any]) -> EstateEntry:
    identity = raw.get("slug" if kind == "collection" else "id")
    if not isinstance(identity, str) or _IDENTITY.fullmatch(identity) is None:
        raise ValueError("invalid Hub identity")
    if not identity.startswith(f"{owner}/"):
        raise ValueError("listing contains another owner")
    private = raw.get("private")
    if not isinstance(private, bool):
        raise TypeError("visibility missing or malformed")
    revision = None
    gated = None
    count = None
    if kind == "collection":
        if not isinstance(raw.get("items"), list):
            raise ValueError("collection membership missing")
        if not all(
            isinstance(item, dict)
            and isinstance(cast("dict[str, object]", item).get("item_id"), str)
            and isinstance(
                cast("dict[str, object]", item).get("item_type"), str
            )
            for item in raw["items"]
        ):
            raise ValueError("collection membership malformed")
        count = len(raw["items"])
    else:
        if "sha" not in raw:
            raise ValueError("revision field missing")
        revision = raw["sha"]
        if revision is not None and (
            not isinstance(revision, str)
            or _REVISION.fullmatch(revision) is None
        ):
            raise ValueError(
                "revision must be immutable or explicitly unreported"
            )
        if kind != "space":
            gated = raw.get("gated")
            if not isinstance(gated, bool) and not (
                isinstance(gated, str) and gated in {"auto", "manual"}
            ):
                raise ValueError("gated state missing or malformed")
    identity_hash = _digest([kind, identity])
    return EstateEntry.model_validate({
        "kind": kind,
        "identity": f"private:{identity_hash}" if private else identity,
        "identity_sha256": identity_hash,
        "private": private,
        "gated": gated,
        "revision": revision,
        "metadata_sha256": _digest({
            "identity": identity_hash,
            "revision": revision,
            "private": private,
            "gated": gated,
            "collection_items": count,
            "collection_members_sha256": _digest([
                [item.get("item_type"), item.get("item_id")]
                for item in raw["items"]
            ])
            if kind == "collection"
            else None,
            "last_updated": raw.get("last_updated")
            if kind == "collection"
            else None,
        }),
        "collection_item_count": count,
        "scope": _scope(identity, private=private),
        "disposition": "retain_private" if private else "review_required",
    })


def build_estate_snapshot(
    owner: str,
    first: dict[str, list[dict[str, Any]]],
    second: dict[str, list[dict[str, Any]]],
    *,
    observed_at: datetime,
    authenticated_owner: str | None,
    limit: int = REPOSITORY_LIMIT,
    visibility_evidence: OwnerVisibilityEvidence | None = None,
) -> EstateSnapshot:
    """Require two complete consistent metadata scans and a matching identity.

    Authentication identifies the account, not the token's visibility scope.
    No credential is accepted, inspected, persisted or returned by this function.
    """
    if owner != authenticated_owner:
        raise ValueError("matching authenticated owner required")
    if set(first) != set(KINDS) or set(second) != set(KINDS):
        raise ValueError("enumeration requires all four kinds")
    entries: list[EstateEntry] = []
    receipts: list[EnumerationReceipt] = []
    for kind in KINDS:
        cap = min(limit, COLLECTION_LIMIT) if kind == "collection" else limit
        if len(first[kind]) >= cap or len(second[kind]) >= cap:
            raise ValueError("listing reached limit; exhaustion is unproven")
        a = sorted(
            (_entry(owner, kind, raw) for raw in first[kind]),
            key=lambda row: row.identity_sha256,
        )
        b = sorted(
            (_entry(owner, kind, raw) for raw in second[kind]),
            key=lambda row: row.identity_sha256,
        )
        if a != b:
            raise ValueError(
                "estate changed between scans; retry a fresh observation"
            )
        receipts.append(
            EnumerationReceipt(
                kind=kind,
                count=len(a),
                limit=cap,
                entries_sha256=_entries_digest(a),
            )
        )
        entries.extend(a)
    return EstateSnapshot(
        owner=owner,
        observed_at=observed_at,
        entries=tuple(entries),
        enumerations=tuple(receipts),
        visibility_evidence=visibility_evidence,
        credential_visibility_attested=visibility_evidence is not None,
    )
