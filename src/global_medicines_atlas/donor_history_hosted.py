"""Guarded orchestration for exact donor history publication and recovery."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Any, Protocol

from .donor_delta import DeltaObservation
from .donor_history_publication import (
    DonorHistoryPublicationContract,
    HistoryAppendPlan,
    HistoryVerification,
    require_donor_history_hosted_authority,
    validate_append_plan,
    verification_digest,
)
from .federation_metadata_hosted import REPOSITORY, require_hosted_main


class HistoryTransport(Protocol):
    """The hosted implementation authenticates Git, Hub and receipt reads."""

    def observations(self) -> tuple[DeltaObservation, ...]:
        """Independently obtain complete current donor deltas."""
        ...

    def prepare(self) -> HistoryAppendPlan:
        """Build incremental bundles over an anonymously verified baseline."""
        ...

    def head(self) -> str:
        """Read the public archive head anonymously."""
        ...

    def append(self, plan: HistoryAppendPlan) -> str:
        """Append absent objects only with server-enforced parent CAS."""
        ...

    def verify(
        self, plan: HistoryAppendPlan, revision: str
    ) -> HistoryVerification:
        """Hash all siblings and restore both histories anonymously."""
        ...


def execute_history_append(
    contract: DonorHistoryPublicationContract,
    *,
    exact_commit: str,
    transport: HistoryTransport,
    persist: Callable[[dict[str, Any]], str],
    acknowledgement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist intent and CAS acknowledgement before verified restoration.

    Recovery requires an authenticated acknowledgement and prior intent from
    the caller. A missing receipt after an uncertain write fails closed; this
    function never fabricates an empty commit or removes prior archive data.
    """
    require_hosted_main(exact_commit)
    require_donor_history_hosted_authority(contract)
    contract = DonorHistoryPublicationContract.model_validate(
        contract.model_dump()
    )
    observations = transport.observations()
    plan = validate_append_plan(
        HistoryAppendPlan.model_validate(acknowledgement["plan"])
        if acknowledgement is not None
        else transport.prepare(),
        observations,
    )
    intent = {
        "schema_id": "global-medicines-atlas.donor-history-append",
        "schema_version": 1,
        "status": "intent",
        "contract": contract.model_dump(mode="json"),
        "code_commit": exact_commit,
        "run_url": f"https://github.com/{REPOSITORY}/actions/runs/"
        + os.environ["GITHUB_RUN_ID"],
        "plan": plan.model_dump(mode="json"),
    }
    if acknowledgement is None:
        if transport.head() != plan.before.revision:
            raise ValueError("archive head drifted before intent")
        # Existing complete additions need an authenticated recovery receipt,
        # never an empty commit to manufacture a new preservation event.
        existing = {item.path for item in plan.before.objects}
        if all(
            item.path in existing
            for ext in plan.extensions
            for item in (ext.bundle, ext.manifest)
        ):
            raise ValueError("existing history requires authenticated recovery")
        intent_url = persist(intent)
        if not intent_url.startswith(
            f"https://github.com/{REPOSITORY}/issues/340#issuecomment-"
        ):
            raise ValueError("durable intent URL missing")
        if transport.head() != plan.before.revision:
            raise ValueError("archive head drifted after intent")
        revision = transport.append(plan)
        acknowledgement = {
            **intent,
            "status": "cas_acknowledged",
            "revision": revision,
            "intent_url": intent_url,
            "parent_basis": "server_enforced_parent_commit",
        }
        acknowledgement_url = persist(acknowledgement)
        if not acknowledgement_url.startswith(
            f"https://github.com/{REPOSITORY}/issues/340#issuecomment-"
        ):
            raise ValueError("durable acknowledgement URL missing")
    else:
        expected = {
            key: value
            for key, value in intent.items()
            if key not in {"run_url", "code_commit"}
        }
        observed = {key: acknowledgement.get(key) for key in expected}
        observed["status"] = "intent"
        if (
            observed != expected
            or acknowledgement.get("status") != "cas_acknowledged"
        ):
            raise ValueError(
                "recovery acknowledgement differs from exact intent"
            )
        if (
            acknowledgement.get("parent_basis")
            != "server_enforced_parent_commit"
        ):
            raise ValueError("recovery CAS evidence missing")
        revision = acknowledgement["revision"]
    # Later writers may advance main; restore this immutable CAS revision.
    # Current-head preservation is a separate final archival preflight.
    if (
        not isinstance(revision, str)
        or re.fullmatch(r"[0-9a-f]{40}", revision) is None
    ):
        raise ValueError("acknowledgement requires an immutable revision")
    verification = HistoryVerification.model_validate(
        transport.verify(plan, revision).model_dump()
    )
    if verification.plan != plan or verification.after.revision != revision:
        raise ValueError("verification differs from acknowledged append")
    result = {
        **acknowledgement,
        "status": "anonymously_verified",
        "verification": verification.model_dump(mode="json"),
        "verification_sha256": verification_digest(verification),
        "archive_authorized": False,
        "verification_code_commit": exact_commit,
        "verification_run_url": intent["run_url"],
    }
    url = persist(result)
    if not url.startswith(
        f"https://github.com/{REPOSITORY}/issues/340#issuecomment-"
    ):
        raise ValueError("durable verification URL missing")
    return {**result, "receipt_url": url}
