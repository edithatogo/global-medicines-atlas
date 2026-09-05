"""Actions-only execution of the preserving source metadata append contract."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from global_medicines_atlas.federation_metadata_append import (
    MetadataAppend,
    ObjectDigest,
    prepare_metadata_append,
    verify_metadata_append,
)
from global_medicines_atlas.federation_source_metadata import (
    validate_source_metadata,
)

REPOSITORY = "edithatogo/global-medicines-atlas"
MAX_RECEIPT_CHARS = 60000


@dataclass(frozen=True)
class PublicSnapshot:
    """Anonymous all-object observations at an immutable public revision."""

    revision: str
    private: bool
    gated: bool
    objects: tuple[ObjectDigest, ...]


class MetadataHub(Protocol):
    """Transport with explicit anonymous reads and server-enforced CAS."""

    def snapshot(self, dataset: str, revision: str) -> PublicSnapshot:
        """Read and hash all objects anonymously at the requested revision."""
        ...

    def head(self, dataset: str) -> str:
        """Read public default head anonymously."""
        ...

    def append(self, plan: MetadataAppend) -> str:
        """Add only plan.payload using parent_commit=plan.parent_revision."""
        ...

    def metadata(self, dataset: str, revision: str, path: str) -> bytes:
        """Restore metadata anonymously at the resulting immutable revision."""
        ...


def require_hosted_main(exact_commit: str) -> None:
    """Refuse local, pull-request, unpinned or other-repository execution."""
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
    ):
        raise ValueError(
            "metadata publication requires Actions dispatch on main"
        )
    if not re.fullmatch(r"[0-9a-f]{40}", exact_commit) or (
        os.environ.get("GITHUB_SHA") != exact_commit
    ):
        raise ValueError("metadata publication requires exact workflow commit")
    if not re.fullmatch(r"[0-9]+", os.environ.get("GITHUB_RUN_ID", "")):
        raise ValueError("metadata publication requires run identity")


def execute_metadata_append(
    document: dict[str, Any],
    *,
    exact_commit: str,
    hub: MetadataHub,
    persist: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    """Persist intent, CAS-add metadata and persist anonymous verification.

    ``persist`` must durably store/read back its exact public-safe document and
    return the receipt URL. Failures propagate; no rollback deletes source data.
    """
    require_hosted_main(exact_commit)
    # Validate before any network call or credential use.
    metadata = validate_source_metadata(document)
    before = hub.snapshot(metadata.dataset, metadata.revision)
    if (
        before.revision != metadata.revision
        or before.private is not False
        or before.gated is not False
    ):
        raise ValueError(
            "source baseline must be exact public non-gated revision"
        )
    plan = prepare_metadata_append(document, before.objects)
    if hub.head(plan.dataset) != plan.parent_revision:
        raise ValueError("default head drifted before metadata intent")
    intent: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.source-metadata-append",
        "schema_version": 1,
        "status": "intent",
        "dataset": plan.dataset,
        "parent_revision": plan.parent_revision,
        "code_commit": exact_commit,
        "run_url": f"https://github.com/{REPOSITORY}/actions/runs/"
        + os.environ["GITHUB_RUN_ID"],
        "authorization": "conductor/decisions/0009-australian-health-authority-and-public-data-plane.md",
        "addition": asdict(plan.addition),
        "baseline": [asdict(obj) for obj in plan.baseline],
    }
    projected_receipt = {
        **intent,
        "status": "anonymously_verified",
        "revision": "f" * 40,
        "intent_url": "x" * 256,
        "parent_basis": "server_enforced_parent_commit",
        "observed": [asdict(obj) for obj in (*plan.baseline, plan.addition)],
        "private": False,
        "gated": False,
    }
    if (
        len(
            json.dumps(projected_receipt, sort_keys=True, separators=(",", ":"))
        )
        > MAX_RECEIPT_CHARS
    ):
        raise ValueError("durable receipt exceeds supported issue size")
    intent_url = persist(intent)
    if not intent_url.startswith(
        f"https://github.com/{REPOSITORY}/issues/340#"
    ):
        raise ValueError("durable intent URL missing")
    # Server-side CAS remains mandatory even after this second head check.
    if hub.head(plan.dataset) != plan.parent_revision:
        raise ValueError("default head drifted after metadata intent")
    revision = hub.append(plan)
    after = hub.snapshot(plan.dataset, revision)
    if after.revision != revision:
        raise ValueError("anonymous readback revision differs")
    payload = hub.metadata(plan.dataset, revision, plan.addition.path)
    verify_metadata_append(
        plan,
        dataset=plan.dataset,
        parent_revision=plan.parent_revision,
        revision=revision,
        private=after.private,
        gated=after.gated,
        observed=after.objects,
        anonymous_payload=payload,
    )
    receipt = {
        **intent,
        "status": "anonymously_verified",
        "revision": revision,
        "intent_url": intent_url,
        "parent_basis": "server_enforced_parent_commit",
        "observed": [asdict(obj) for obj in after.objects],
        "private": False,
        "gated": False,
    }
    receipt_url = persist(receipt)
    if not receipt_url.startswith(
        f"https://github.com/{REPOSITORY}/issues/340#"
    ):
        raise ValueError("durable verification URL missing")
    return {**receipt, "receipt_url": receipt_url}
