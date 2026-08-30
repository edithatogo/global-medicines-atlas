"""Offline semantic checks for schema-validated federation v4 records.

These checks establish internal consistency, not truth or publication authority.
Consumers must first validate against the pinned JSON Schema with format checks,
then independently resolve receipts and verify remote bytes before using data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def validate_federation_semantics(document: dict[str, Any]) -> None:
    """Reject contradictory identities and lifecycle claims after schema validation.

    Raises:
        ValueError: Evidence identities or lifecycle constraints disagree.
    """
    location = document["location"]
    verification = document["verification"]
    rights = document["rights"]
    for field in ("dataset", "revision", "path", "sha256", "bytes"):
        if location[field] != verification[field]:
            raise ValueError(f"verification identity mismatch: {field}")
    if (
        rights["subject_sha256"] != location["sha256"]
        or rights["dataset"] != location["dataset"]
        or rights["path"] != location["path"]
    ):
        raise ValueError("authorization identity mismatch")
    _validate_layers(document)
    _validate_lifecycle(document)
    _validate_recovery(document["recovery"])


def _validate_layers(document: dict[str, Any]) -> None:
    source = document["source"]
    is_bronze = source["layer"] == "bronze"
    if source["bronze_stratum"] == "B0" and source["representation"] != "index":
        raise ValueError("B0 requires index representation")
    if is_bronze != (source["bronze_stratum"] is not None):
        raise ValueError("Bronze stratum must exist only for Bronze")
    if source["representation"] == "raw" and (
        not is_bronze or source["bronze_stratum"] != "B2"
    ):
        raise ValueError("raw evidence requires Bronze stratum B2")
    if (
        source["representation"] == "projection"
        and not document["lineage"]["inputs"]
    ):
        raise ValueError("projection lineage cannot be empty")
    if not is_bronze and document["lineage"]["promotion_receipt"] is None:
        raise ValueError("derived layer requires promotion receipt")
    if source["representation"] in {"index", "metadata"} and (
        not is_bronze
        or source["bronze_stratum"]
        != {"index": "B0", "metadata": "B1"}[source["representation"]]
    ):
        raise ValueError("index/metadata Bronze stratum mismatch")
    if (document["evidence_kind"] == "synthetic") != (
        source["comparison_cohort"] == "synthetic"
    ):
        raise ValueError("synthetic evidence cannot claim live cohort")


def _validate_lifecycle(document: dict[str, Any]) -> None:
    source = document["source"]
    verification = document["verification"]
    cache = document["cache"]
    producer = document["authority"]["producer_repository"]
    if not document["publication"]["run"].startswith(
        f"https://github.com/{producer}/actions/runs/"
    ):
        raise ValueError("publication run must belong to producer")
    retrieved = datetime.fromisoformat(source["retrieved_at"])
    verified = datetime.fromisoformat(verification["verified_at"])
    if retrieved > verified:
        raise ValueError("retrieval/verification time order")
    if datetime.fromisoformat(cache["created_at"]) >= datetime.fromisoformat(
        cache["expires_at"]
    ):
        raise ValueError("cache expiry must follow creation")
    if cache["state"] == "removed" and cache["cleanup_receipt"] is None:
        raise ValueError("removed cache requires cleanup receipt")
    if cache["state"] != "removed" and cache["cleanup_receipt"] is not None:
        raise ValueError("unremoved cache cannot claim cleanup receipt")


def _validate_recovery(recovery: dict[str, Any]) -> None:
    incomplete = (
        recovery["administrative_domain"].strip().casefold()
        == recovery["primary_administrative_domain"].strip().casefold()
        or recovery["region"].strip().casefold()
        == recovery["primary_region"].strip().casefold()
        or recovery["restore_receipt"] is None
        or recovery["authorization_receipt"] is None
        or "unverified"
        in {
            recovery["region"].strip().casefold(),
            recovery["primary_region"].strip().casefold(),
        }
    )
    missing_targets = (
        recovery["rpo_seconds"] is None or recovery["rto_seconds"] is None
    )
    if recovery["role"] == "independent_replica" and (
        incomplete or missing_targets
    ):
        raise ValueError(
            "independent replica requires distinct domains and restore evidence"
        )
    if recovery["role"] == "compatibility_replica" and recovery["independent"]:
        raise ValueError("compatibility replica is not independent")
    if recovery["independent"] != (recovery["role"] == "independent_replica"):
        raise ValueError("independent role mismatch")
