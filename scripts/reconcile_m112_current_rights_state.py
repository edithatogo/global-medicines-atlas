"""Reconcile effective rights over the frozen M-112 objects and CMS reference."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from operator import itemgetter
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
FROZEN_OVERLAY = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "reimbursement-medallion-projection-lineage.json"
)
CMS_REVIEW = QUAL / "cms-hcpcs-rights-review-20261019.json"
MBS_RIGHTS_ATTESTATION = QUAL / (
    "australian-mbs-v4-public-release-rights-attestation-20261019.json"
)
MBS_SILVER_PUBLIC_TREE_READBACK = QUAL / (
    "australian-mbs-v4-current-public-tree-readback-20261020.json"
)
AUGUST_MBS_RIGHTS_ATTESTATION = QUAL / (
    "australian-mbs-august-bronze-rights-attestation-20261020.json"
)
PBS_UTILISATION_AUTHORIZATION = (
    QUAL / "australian-pbs-utilisation-publication-authorization.json"
)
PBS_UTILISATION_LINEAGE = (
    QUAL / "australian-pbs-utilisation-landed-lineage-20261019.json"
)
PBS_SOURCE_ARCHIVE_AUDIT = (
    QUAL / "australian-m112-source-archive-receipt-join-audit-20260930.json"
)
PBS_SOURCE_ARCHIVE_ACQUISITION = Path(
    "quality/bronze/imported-acquisitions/au-pbs/"
    "712fd306658de6db5ae0aaa2be39d554e5a18c306987cc614152efbed53f30f4.json"
)
PBS_RAW_PERMISSION = (
    QUAL / "reimbursement-atlas-pbs-raw-permission-20260831.json"
)
PBS_PROJECTED_LINEAGE = (
    QUAL / "australian-m112-pbs-projected-b1-b2-lineage-20261019.json"
)
PBS_ARCHIVE_LINEAGE = (
    QUAL / "australian-m112-pbs-pdf-archive-lineage-20261019.json"
)
PBS_RAW_PERMISSION_SHA256 = (
    "0817123492cfe20858f86b3ec14c92539081a647b17dd6933d2d2ff8c266d098"
)
PBS_RAW_PERMISSION_REVISION = "a93516ed416118bc51c1db2b71ab540fa4d0fe52"
PBS_RAW_PERMISSION_OBJECT_COUNT = 1708
M112_CURRENT_ADMITTED_CANARIED_COUNT = 2
PBS_DECISION_0009 = Path(
    "conductor/decisions/0009-australian-health-authority-and-public-data-plane.md"
)
MBS_JULY2016_CANARY_RECEIPTS = (
    QUAL
    / "australian-m112-v4-july2016-consumer-canary-20261020-39300224557.json",
    QUAL
    / "australian-m112-v4-july2016-consumer-canary-20261020-39306554319.json",
)
M112_ROLE_QUALIFICATION = QUAL / (
    "australian-m112-v4-contract-role-evidence-qualification-20261020.json"
)
M108_ASSESSMENT = QUAL / "australian-m108-derived-products-20261017.json"
OUTPUT = QUAL / "australian-m112-current-rights-reconciliation-20261019.json"

MBS_SILVER_PREFIX = "silver/mbs/v4/2025-07-v3/"
AUGUST_BRONZE_PREFIX = "bronze/mbs/releases/2026-08-01/"
PBS_UTILISATION_DATASET = "edithatogo/australian-pbs-utilisation-archive"
PBS_SOURCE_ARCHIVE_DATASET = "edithatogo/australian-pbs-source-archive"
PBS_SOURCE_ARCHIVE_PATH = "raw/2026-04-01/2026-04-01-XML-V3.zip"
PBS_SOURCE_ARCHIVE_SHA256 = (
    "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
)
PBS_SOURCE_ARCHIVE_BYTES = 11156706
PBS_SOURCE_PROJECTION_PATH = "bronze/2026-04-01/pbs-v3-source.parquet"
PBS_SOURCE_PROJECTION_SHA256 = (
    "9e9facc336b47c5a9d514388a95c9797ba3e03474806fba00b6f03c0e601e97d"
)
PBS_SOURCE_PROJECTION_BYTES = 158134
MBS_JULY2016_CANARY_DATASET = "edithatogo/australian-mbs-utilisation-archive"
MBS_JULY2016_CANARY_PATH = (
    "raw/mbs/utilisation/group/mbs-group-2016hr-july.xlsx"
)
MBS_JULY2016_CANARY_SHA256 = (
    "9f2f28b69f58a0aa05a0b56b09515651b1e0b50a634234ce7f6f6c8426373285"
)
MBS_JULY2016_CANARY_BYTES = 6857437
MBS_JULY2016_CONTRACT_SHA256 = (
    "b95056d6ab657f5b280870dc2ac7dcb1578019224e843d423a99e2880f451d7e"
)
PBS_UTILISATION_RIGHTS_STATE = "maintainer_attested_dataset_publication_permission_with_vocabulary_exclusion"
PBS_RAW_RIGHTS_STATE = "owner_attested_pbs_raw_redistribution_permission"
PBS_UTILISATION_OBJECT_COUNT = 6
CMS_SOURCE_ID = "us_cms_hcpcs_level_ii"
CMS_SOURCE_VERSION = "us_cms_hcpcs_level_ii_2026_07"
CMS_SHA256 = "5591fed257e4d2307c1d2dc9c66abc8e346b1f4c076e9e48559799e2de14b70a"
FROZEN_OBJECT_COUNT = 1759
MBS_SILVER_OBJECT_COUNT = 6
AUGUST_PROJECTION_COUNT = 4
MBS_AUGUST_RIGHTS_STATE = (
    "maintainer_attested_exact_public_release_permission_for_bronze_projection"
)
RIGHTS_RESOLVED_STATES = {
    "authorized_exact_source_release_permitted",
    "approved_exact_scope_CC_BY_3_0_AU_publicly_readback_verified",
    "maintainer_attested_exact_public_release_permission_for_silver_object",
    MBS_AUGUST_RIGHTS_STATE,
    PBS_UTILISATION_RIGHTS_STATE,
    PBS_RAW_RIGHTS_STATE,
}


def _read(root: Path, relative: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((root / relative).read_text()))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reconcile_cms(
    root: Path, review: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    decision_path = Path(review["rights_review"]["decision_path"])
    decision = _read(root, decision_path)
    scope = review["scope"]["exact_external_file"]
    if (
        review["scope"]["source_id"] != CMS_SOURCE_ID
        or review["scope"]["source_version"] != CMS_SOURCE_VERSION
        or scope["sha256"] != CMS_SHA256
        or decision["effective_state"]["rights_state"] != "permitted"
        or decision["effective_state"]["reviewer_status"] != "approved"
    ):
        raise ValueError(
            "the exact CMS HCPCS effective rights decision did not reconcile"
        )

    acquisition_path = Path(scope["acquisition_path"])
    admission_path = Path(review["rights_review"]["superseding_admission_path"])
    acquisition = _read(root, acquisition_path)
    admission = _read(root, admission_path)
    hashes = {
        str(CMS_REVIEW): _sha256(root / CMS_REVIEW),
        str(decision_path): _sha256(root / decision_path),
        str(acquisition_path): _sha256(root / acquisition_path),
        str(admission_path): _sha256(root / admission_path),
    }
    effective = decision["effective_state"]
    return (
        {
            "inside_m112_frozen_inventory": False,
            "source_id": CMS_SOURCE_ID,
            "source_version": CMS_SOURCE_VERSION,
            "sha256": CMS_SHA256,
            "byte_count": scope["byte_count"],
            "rights_decision_path": str(decision_path),
            "rights_decision_sha256": hashes[str(decision_path)],
            "rights_state": effective["rights_state"],
            "reviewer_status": effective["reviewer_status"],
            "acquisition_time_rights_state_preserved": acquisition[
                "rights_state"
            ],
            "latest_admission_state": admission["state"],
            "b2_state": decision["scope"]["b2_state"],
            "processing_or_v4_admission_authorized": effective[
                "processing_or_v4_admission_authorized"
            ],
            "consumer_canaries_authorized": effective[
                "consumer_canaries_authorized"
            ],
            "derived_table_rights_concluded": effective[
                "derived_table_rights_concluded"
            ],
            "external_publication_authorized": effective[
                "external_publication_authorized"
            ],
        },
        hashes,
    )


def _reconcile_pbs_source_archive_publication(
    root: Path, objects: list[dict[str, Any]]
) -> dict[str, Any]:
    """Bind exact PBS source publication authorization without inferring a licence."""

    audit = _read(root, PBS_SOURCE_ARCHIVE_AUDIT)["pbs"]
    acquisition = _read(root, PBS_SOURCE_ARCHIVE_ACQUISITION)
    decision_sha256 = _sha256(root / PBS_DECISION_0009)
    frozen = {
        obj["path"]: obj
        for obj in objects
        if obj["dataset"] == PBS_SOURCE_ARCHIVE_DATASET
    }
    raw = frozen.get(PBS_SOURCE_ARCHIVE_PATH)
    projection = frozen.get(PBS_SOURCE_PROJECTION_PATH)
    raw_evidence = audit["raw_object"]
    publication = audit["maintainer_publication_authority"]
    checks = [audit["dataset"] != PBS_SOURCE_ARCHIVE_DATASET]
    if raw is None or projection is None:
        raise ValueError(
            "exact PBS source publication evidence did not reconcile"
        )
    checks.extend([
        raw["candidate_class"] != "raw_source_payload",
        raw["identity"]["sha256"] != PBS_SOURCE_ARCHIVE_SHA256,
        raw["identity"]["byte_count"] != PBS_SOURCE_ARCHIVE_BYTES,
        raw_evidence["path"] != PBS_SOURCE_ARCHIVE_PATH,
        raw_evidence["manifest_sha256"] != PBS_SOURCE_ARCHIVE_SHA256,
        raw_evidence["receipt_sha256"] != PBS_SOURCE_ARCHIVE_SHA256,
        raw_evidence["manifest_bytes"] != PBS_SOURCE_ARCHIVE_BYTES,
        raw_evidence["receipt_bytes"] != PBS_SOURCE_ARCHIVE_BYTES,
        raw_evidence["receipt_rights_state"] != "permitted",
        not raw_evidence["manifest_receipt_exact_match"],
        publication["exact_object_publication_authorized"] is not True,
        publication["hosted_anonymous_digest_verification"] != "passed",
        not publication["current_pinned_digest_equals_hosted_verified_digest"],
        publication["decision"] != str(PBS_DECISION_0009),
        publication["decision_sha256"] != decision_sha256,
        publication["hosted_verification_source_archive_sha256"]
        != PBS_SOURCE_ARCHIVE_SHA256,
        acquisition["payload_sha256"] != PBS_SOURCE_ARCHIVE_SHA256,
        acquisition["rights_state"] != "unknown",
        raw["v4_admission"] is not False,
        raw["disposition"] != "deferred_not_admitted",
        projection["identity"]["sha256"] != PBS_SOURCE_PROJECTION_SHA256,
        projection["identity"]["byte_count"] != PBS_SOURCE_PROJECTION_BYTES,
        projection["v4_admission"] is not False,
        projection["disposition"] != "deferred_not_admitted",
    ])
    if any(checks):
        raise ValueError(
            "exact PBS source publication evidence did not reconcile"
        )

    hashes = {
        str(PBS_SOURCE_ARCHIVE_AUDIT): _sha256(root / PBS_SOURCE_ARCHIVE_AUDIT),
        str(PBS_SOURCE_ARCHIVE_ACQUISITION): _sha256(
            root / PBS_SOURCE_ARCHIVE_ACQUISITION
        ),
        str(PBS_DECISION_0009): decision_sha256,
    }
    return {
        "record": {
            "dataset": PBS_SOURCE_ARCHIVE_DATASET,
            "revision": audit["revision"],
            "path": PBS_SOURCE_ARCHIVE_PATH,
            "sha256": PBS_SOURCE_ARCHIVE_SHA256,
            "byte_count": PBS_SOURCE_ARCHIVE_BYTES,
            "exact_object_publication_authorized": True,
            "rights_state": PBS_RAW_RIGHTS_STATE,
            "authorization_id": "decision-0009",
            "publication_intent": publication["publication_intent_comment"],
            "publication_intent_workflow_run": publication[
                "publication_intent_workflow_run"
            ],
            "hosted_anonymous_digest_verification": "passed",
            "hosted_verification_receipt": publication[
                "hosted_anonymous_verification_comment"
            ],
            "hosted_verification_revision": publication[
                "hosted_verification_revision"
            ],
            "current_digest_matches_hosted_verification": True,
            "upstream_redistribution_terms": "owner-attested raw redistribution permission; publisher document not verified",
            "historical_acquisition_rights_state": acquisition["rights_state"],
            "v4_admission": False,
            "release_performed_by_this_reconciliation": False,
            "source_projection": {
                "path": PBS_SOURCE_PROJECTION_PATH,
                "sha256": PBS_SOURCE_PROJECTION_SHA256,
                "byte_count": PBS_SOURCE_PROJECTION_BYTES,
                "rights_state": projection["rights"]["state"],
                "v4_admission": projection["v4_admission"],
                "derived_rights_inferred_from_source_permission": False,
            },
            "rights_conclusion_made": True,
            "rights_scope": "exact raw PBS source archive object only",
            "derived_projection_rights_inferred": False,
        },
        "evidence_inputs": hashes,
    }


def _reconcile_pbs_raw_permission(
    root: Path,
    objects: list[dict[str, Any]],
    permission: dict[str, Any],
    projected: dict[str, Any],
    archived: dict[str, Any],
) -> dict[str, Any]:
    """Apply the owner-attested permission to exact, lineaged PBS raw objects."""
    permission_hash = _sha256(root / PBS_RAW_PERMISSION)
    invalid_permission = [
        permission_hash != PBS_RAW_PERMISSION_SHA256
        or permission.get("permission_status") != "active"
        or permission.get("revoked_at") is not None
        or permission.get("source_id") != "au_pbs"
        or permission.get("decision") != "allow_raw_redistribution"
        or permission.get("permission_basis") != "owner_attestation"
        or permission.get("per_file_owner_approval_required") is not False
        or permission.get("publisher_permission_document_verified") is not False
        or permission.get("licence_identifier") is not None
        or permission.get("publication_state") != "not_asserted"
        or "Raw PBS schedule PDFs and machine-readable schedule packages"
        not in permission.get("scope", "")
    ]
    if any(invalid_permission):
        raise ValueError("PBS raw redistribution permission did not reconcile")

    frozen = {
        (obj["dataset"], obj["path"]): obj
        for obj in objects
        if obj["candidate_class"] == "raw_source_payload"
        and obj["dataset"]
        in {"edithatogo/reimbursement-atlas", PBS_SOURCE_ARCHIVE_DATASET}
    }
    items: list[dict[str, Any]] = []
    for item in projected["objects"]:
        source_id = item.get("producer_b1", {}).get("source_id")
        source_url = cast(
            "str", item.get("producer_b1", {}).get("source_locator", "")
        )
        local = item.get("local_records", {})
        projected_checks: list[bool] = [
            item.get("dataset")
            not in {
                "edithatogo/reimbursement-atlas",
                PBS_SOURCE_ARCHIVE_DATASET,
            },
            item.get("lineage_complete") is not True,
            item.get("v4_admission") is not False,
            item.get("consumer_canary") is not False,
            source_id != "au_pbs",
            urlsplit(source_url).hostname != "www.pbs.gov.au",
            not urlsplit(source_url).path.startswith("/publication/schedule/"),
            item.get("content_sha256")
            != item
            .get("producer_b2", {})
            .get("evidence_id", "")
            .removeprefix("evidence:sha256:"),
            item.get("content_sha256")
            != item
            .get("producer_b2", {})
            .get("immutable_locator", "")
            .removeprefix("sha256:"),
            not all(
                local.get(key)
                for key in (
                    "acquisition_event_path",
                    "b2_manifest_path",
                    "landed_admission_path",
                )
            ),
        ]
        obj = frozen.get((item.get("dataset"), item.get("path")))
        if (
            obj is None
            or obj["identity"]["sha256"] != item.get("content_sha256")
            or obj["identity"]["byte_count"] != item.get("byte_count")
        ):
            projected_checks.append(True)
        if any(projected_checks):
            raise ValueError(
                f"PBS raw redistribution permission lineage mismatch: {item.get('path')}"
            )
        items.append({
            "dataset": item["dataset"],
            "path": item["path"],
            "sha256": item["content_sha256"],
            "byte_count": item["byte_count"],
            "source_locator": source_url,
            "lineage_complete": True,
            "v4_admission": False,
            "consumer_canary": False,
            "format": Path(item["path"]).suffix.removeprefix(".").lower(),
        })

    for item in archived["objects"]:
        receipt = item["producer_archive_variant_receipt"]
        source_url = cast("str", receipt["official_source_url"])
        obj = frozen.get((item["dataset"], item["path"]))
        archived_checks: list[bool] = [
            item.get("lineage_complete", True) is not True,
            item.get("v4_admission") is not False,
            item.get("consumer_canary") is not False,
            receipt.get("raw_redistribution_status")
            != "blocked_pending_explicit_permission",
            urlsplit(source_url).hostname != "www.pbs.gov.au",
            not urlsplit(source_url).path.startswith("/publication/schedule/"),
            not urlsplit(source_url).path.endswith(".pdf"),
            obj is None
            or obj["identity"]["sha256"] != item["content_sha256"]
            or obj["identity"]["byte_count"] != item["byte_count"],
        ]
        if any(archived_checks):
            raise ValueError(
                f"PBS archived raw permission lineage mismatch: {item.get('path')}"
            )
        items.append({
            "dataset": item["dataset"],
            "path": item["path"],
            "sha256": item["content_sha256"],
            "byte_count": item["byte_count"],
            "source_locator": source_url,
            "lineage_complete": True,
            "v4_admission": False,
            "consumer_canary": False,
            "format": "pdf",
        })

    expected = {(dataset, path) for dataset, path in frozen}
    observed = {(item["dataset"], item["path"]) for item in items}
    if (
        len(items) != PBS_RAW_PERMISSION_OBJECT_COUNT
        or observed != expected
        or len(observed) != len(items)
    ):
        raise ValueError(
            "PBS raw redistribution permission did not bind exact frozen membership"
        )
    hashes = {
        str(path): _sha256(root / path)
        for path in (
            PBS_RAW_PERMISSION,
            PBS_PROJECTED_LINEAGE,
            PBS_ARCHIVE_LINEAGE,
        )
    }
    return {
        "source_owner_permission": {
            key: permission.get(key)
            for key in (
                "permission_status",
                "source_id",
                "decision",
                "permission_basis",
                "scope",
                "per_file_owner_approval_required",
                "publisher_permission_document_verified",
                "licence_identifier",
                "publication_state",
            )
        },
        "permission_repository": "edithatogo/reimbursement-atlas",
        "permission_revision": PBS_RAW_PERMISSION_REVISION,
        "permission_path": "data/licence_review/pbs_raw_permission.json",
        "permission_sha256": PBS_RAW_PERMISSION_SHA256,
        "permission_snapshot_sha256": permission_hash,
        "rights_state": PBS_RAW_RIGHTS_STATE,
        "object_count": len(items),
        "dataset_counts": dict(
            sorted(Counter(item["dataset"] for item in items).items())
        ),
        "format_counts": dict(
            sorted(Counter(item["format"] for item in items).items())
        ),
        "b1_b2_lineage_complete": True,
        "all_objects_remain_deferred": True,
        "v4_admissions": 0,
        "consumer_canaries": 0,
        "external_publication_performed": False,
        "project_publication_authorized_by_this_record": False,
        "objects": sorted(items, key=itemgetter("dataset", "path")),
        "evidence_inputs": hashes,
    }


def _reconcile_m112_canary_readback(
    root: Path, objects: list[dict[str, Any]]
) -> dict[str, Any]:
    """Overlay successful exact-main receipts on stale per-object gate flags."""

    frozen = [
        obj
        for obj in objects
        if obj["dataset"] == MBS_JULY2016_CANARY_DATASET
        and obj["path"] == MBS_JULY2016_CANARY_PATH
    ]
    if len(frozen) != 1:
        raise ValueError("July 2016 MBS canary object is not uniquely frozen")
    obj = frozen[0]
    if (
        obj["identity"]["sha256"] != MBS_JULY2016_CANARY_SHA256
        or obj["identity"]["byte_count"] != MBS_JULY2016_CANARY_BYTES
        or obj["rights"]["state"]
        != "approved_exact_scope_CC_BY_3_0_AU_publicly_readback_verified"
    ):
        raise ValueError(
            "July 2016 MBS canary identity or rights did not reconcile"
        )

    runs: list[dict[str, Any]] = []
    input_hashes: dict[str, str] = {}
    for path in MBS_JULY2016_CANARY_RECEIPTS:
        receipt = _read(root, path)
        admission = receipt["admission"]
        canary = receipt["consumer_canary"]
        canary_object = canary["object"]
        workflow = canary["hosted_workflow"]
        checks = [
            receipt["approved_denominator"] != FROZEN_OBJECT_COUNT,
            receipt["admissions"] != 1,
            receipt["consumer_canaries"] != 1,
            canary["status"] != "passed",
            admission["dataset"] != MBS_JULY2016_CANARY_DATASET,
            admission["path"] != MBS_JULY2016_CANARY_PATH,
            admission["sha256"] != MBS_JULY2016_CANARY_SHA256,
            admission["byte_count"] != MBS_JULY2016_CANARY_BYTES,
            admission["contract_sha256"] != MBS_JULY2016_CONTRACT_SHA256,
            canary_object["dataset"] != MBS_JULY2016_CANARY_DATASET,
            canary_object["path"] != MBS_JULY2016_CANARY_PATH,
            canary_object["sha256"] != MBS_JULY2016_CANARY_SHA256,
            canary_object["bytes"] != MBS_JULY2016_CANARY_BYTES,
            canary["contract_sha256"] != MBS_JULY2016_CONTRACT_SHA256,
            workflow["repository"] != "edithatogo/global-medicines-atlas",
            workflow["run_id"] <= 0,
            canary["verification"]["remote_digest_match"] is not True,
            canary["verification"]["consumer_stream_digest_match"] is not True,
            canary["boundaries"]["admission_used"] is not True,
            canary["boundaries"]["admission_performed"] is not False,
            canary["boundaries"]["public_dataset_mutated"] is not False,
            canary["boundaries"]["source_payload_bytes_retained"] is not False,
            canary["boundaries"]["source_values_or_rows_included"] is not False,
            receipt["native_workbook_layout_qualified"] is not False,
            receipt["source_values_or_payload_bytes_retained"] is not False,
            obj["disposition"] != "deferred_not_admitted",
            obj["v4_admission"] is not False,
            obj["consumer_canary"] is not False,
        ]
        if any(checks):
            raise ValueError(
                f"July 2016 MBS canary receipt did not reconcile: {path}"
            )
        if admission["sha256"] != obj["identity"]["sha256"]:
            raise ValueError(
                f"July 2016 MBS canary differs from frozen object: {path}"
            )
        input_hashes[str(path)] = _sha256(root / path)
        runs.append({
            "receipt_path": str(path),
            "receipt_sha256": input_hashes[str(path)],
            "run_id": workflow["run_id"],
            "run_url": workflow["run_url"],
            "workflow_commit": workflow["commit"],
        })

    role_qualification = _read(root, M112_ROLE_QUALIFICATION)
    cohort = role_qualification["cohort"]
    current_admissions = role_qualification["current_admission_evidence"]
    if (
        cohort["v4_admissions"] != M112_CURRENT_ADMITTED_CANARIED_COUNT
        or cohort["consumer_canaries"] != M112_CURRENT_ADMITTED_CANARIED_COUNT
        or len(current_admissions) != M112_CURRENT_ADMITTED_CANARIED_COUNT
        or len({item["path"] for item in current_admissions})
        != M112_CURRENT_ADMITTED_CANARIED_COUNT
    ):
        raise ValueError(
            "current M-112 role qualification counts did not reconcile"
        )
    input_hashes[str(M112_ROLE_QUALIFICATION)] = _sha256(
        root / M112_ROLE_QUALIFICATION
    )

    return {
        "record": {
            "admitted_object_count": cohort["v4_admissions"],
            "canaried_object_count": cohort["consumer_canaries"],
            "deferred_object_count": FROZEN_OBJECT_COUNT
            - cohort["v4_admissions"],
            "current_role_qualification": {
                "path": str(M112_ROLE_QUALIFICATION),
                "sha256": _sha256(root / M112_ROLE_QUALIFICATION),
                "admitted_objects": current_admissions,
            },
            "object": {
                "dataset": MBS_JULY2016_CANARY_DATASET,
                "path": MBS_JULY2016_CANARY_PATH,
                "sha256": MBS_JULY2016_CANARY_SHA256,
                "byte_count": MBS_JULY2016_CANARY_BYTES,
                "rights_state": obj["rights"]["state"],
            },
            "contract_sha256": MBS_JULY2016_CONTRACT_SHA256,
            "successful_workflow_runs": runs,
            "unique_object_counts_are_deduplicated_across_runs": True,
            "source_values_or_rows_interpreted": False,
            "native_workbook_layout_qualified": False,
            "public_dataset_mutated_by_reconciliation": False,
            "overlay_object_flags_pre_readback": {
                "disposition": obj["disposition"],
                "v4_admission": obj["v4_admission"],
                "consumer_canary": obj["consumer_canary"],
            },
        },
        "evidence_inputs": input_hashes,
    }


def _reconcile_object_rights(
    objects: list[dict[str, Any]], rights_overrides: dict[str, str]
) -> dict[str, Any]:
    paths = [obj["path"] for obj in objects]
    if len(objects) != FROZEN_OBJECT_COUNT or len(set(paths)) != len(paths):
        raise ValueError(
            "frozen M-112 membership is not the approved 1,759 paths"
        )
    groups = Counter(
        (
            obj["dataset"],
            obj["candidate_class"],
            rights_overrides.get(obj["path"], obj["rights"]["state"]),
        )
        for obj in objects
    )
    return {
        "counts": [
            {
                "dataset": dataset,
                "candidate_class": candidate_class,
                "state": state,
                "object_count": count,
            }
            for (dataset, candidate_class, state), count in sorted(
                groups.items()
            )
        ],
        "resolved_count": sum(
            rights_overrides.get(obj["path"], obj["rights"]["state"])
            in RIGHTS_RESOLVED_STATES
            and (
                obj["rights"]["decision_evidence"] is not None
                or obj["path"] in rights_overrides
            )
            for obj in objects
        ),
    }


def _reconcile_mbs_silver_attestation(
    objects: list[dict[str, Any]],
    attestation: dict[str, Any],
    public_tree_readback: dict[str, Any],
) -> dict[str, Any]:
    silver_objects = [
        obj for obj in objects if obj["path"].startswith(MBS_SILVER_PREFIX)
    ]
    if len(silver_objects) != MBS_SILVER_OBJECT_COUNT or any(
        obj["rights"]["state"]
        not in {
            "underlying source authorization exists; no projection rights conclusion added",
            "maintainer_attested_exact_public_release_permission_for_silver_object",
        }
        for obj in silver_objects
    ):
        raise ValueError(
            "the exact six-object MBS Silver attestation did not reconcile"
        )
    authorised = {
        item["path"]: (item["sha256"], item["byte_count"])
        for item in attestation["authorized_objects"]
    }
    if (
        not attestation["public_release_authorized"]
        or len(authorised) != MBS_SILVER_OBJECT_COUNT
    ):
        raise ValueError(
            "the exact six-object MBS rights attestation is incomplete"
        )
    paths: list[dict[str, Any]] = []
    for obj in silver_objects:
        path = obj["path"]
        identity = (obj["identity"]["sha256"], obj["identity"]["byte_count"])
        if authorised.get(path) != identity:
            raise ValueError(
                f"MBS Silver attestation identity mismatch: {path}"
            )
        paths.append({
            "path": path,
            "sha256": identity[0],
            "byte_count": identity[1],
        })
    expected_dataset = attestation["dataset_identity"]["dataset"]
    observed_objects = {
        item["path"]: (item["sha256"], item["byte_count"])
        for item in public_tree_readback["objects"]
    }
    expected_objects = {
        item["path"]: (item["sha256"], item["byte_count"]) for item in paths
    }
    invalid_readback = [
        public_tree_readback["dataset"] != expected_dataset,
        public_tree_readback["access"]["anonymous"] is not True,
        public_tree_readback["access"]["private"] is not False,
        public_tree_readback["access"]["gated"] is not False,
        public_tree_readback["scope"]["objects_present_and_digest_size_matched"]
        != MBS_SILVER_OBJECT_COUNT,
        observed_objects != expected_objects,
        public_tree_readback["boundaries"][
            "current_revision_payload_bytes_downloaded_or_reverified"
        ]
        is not False,
        public_tree_readback["boundaries"]["rights_conclusion_added"]
        is not False,
        public_tree_readback["boundaries"]["external_publication_performed"]
        is not False,
        public_tree_readback["boundaries"]["dataset_mutated"] is not False,
    ]
    if any(invalid_readback):
        raise ValueError(
            "the current MBS Silver public tree readback did not reconcile"
        )
    return {
        "object_count": len(silver_objects),
        "paths": sorted(paths, key=itemgetter("path")),
        "public_release_authorized": attestation["public_release_authorized"],
        "public_release_performed": attestation["public_release_performed"],
        "current_public_tree_readback": {
            "path": str(MBS_SILVER_PUBLIC_TREE_READBACK),
            "dataset": public_tree_readback["dataset"],
            "revision": public_tree_readback["current_revision"],
            "observed_at": public_tree_readback["observed_at"],
            "anonymous_metadata_identity_verified": True,
            "exact_object_count": MBS_SILVER_OBJECT_COUNT,
            "current_revision_payload_bytes_reverified": False,
            "public_release_observed": True,
        },
    }


def reconcile_august_mbs_attestation(
    objects: list[dict[str, Any]], attestation: dict[str, Any]
) -> list[dict[str, Any]]:
    frozen = {
        obj["path"]: obj
        for obj in objects
        if obj["path"].startswith(AUGUST_BRONZE_PREFIX)
        and obj["candidate_class"] == "existing_data_projection"
    }
    authorized = {
        item["path"]: (item["sha256"], item["byte_count"])
        for item in attestation["authorized_objects"]
    }
    if (
        attestation.get("public_release_rights_attested") is not True
        or attestation.get("permission_instrument_existence_and_applicability")
        != "maintainer_attested_not_independently_reviewed_or_located_at_maintainer_direction"
        or len(frozen) != AUGUST_PROJECTION_COUNT
        or len(authorized) != AUGUST_PROJECTION_COUNT
        or set(authorized) != set(frozen)
    ):
        raise ValueError(
            "the exact four-object August MBS attestation is incomplete"
        )
    result: list[dict[str, Any]] = []
    for path, obj in frozen.items():
        identity = (obj["identity"]["sha256"], obj["identity"]["byte_count"])
        if authorized[path] != identity:
            raise ValueError(
                f"August MBS attestation identity mismatch: {path}"
            )
        result.append({
            "path": path,
            "sha256": identity[0],
            "byte_count": identity[1],
            "rights_state": MBS_AUGUST_RIGHTS_STATE,
            "lineage_complete": obj["b1_b2_lineage"]["complete"],
        })
    return sorted(result, key=itemgetter("path"))


def _reconcile_pbs_utilisation_authorization(
    root: Path,
    objects: list[dict[str, Any]],
    authorization: dict[str, Any],
    lineage: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if (
        authorization["dataset"] != PBS_UTILISATION_DATASET
        or authorization["external_publication_authorized"] is not True
        or authorization["maintainer_asserted_redistribution_permission"]
        is not True
    ):
        raise ValueError(
            "PBS utilisation publication authority is not approved"
        )

    frozen_by_path = {obj["path"]: obj for obj in objects}
    expected_paths = {
        obj["path"]
        for obj in objects
        if obj["dataset"] == PBS_UTILISATION_DATASET
        and obj["candidate_class"] == "raw_source_payload"
    }
    if len(expected_paths) != PBS_UTILISATION_OBJECT_COUNT:
        raise ValueError("frozen PBS utilisation membership changed")
    authorised: list[dict[str, Any]] = []
    lineage_objects = cast("list[dict[str, Any]]", lineage["objects"])
    for item in lineage_objects:
        path = item["path"]
        source_url = cast("str", item["source_url"])
        host: str | None = urlsplit(source_url).hostname
        frozen = frozen_by_path.get(path)
        if not _pbs_lineage_item_is_authorized(
            item, frozen, host, authorization
        ):
            raise ValueError(f"PBS utilisation rights scope mismatch: {path}")
        authorised.append({
            "path": path,
            "sha256": item["content_sha256"],
            "byte_count": item["byte_count"],
            "source_id": item["source_id"],
            "category": item["category"],
            "source_url": item["source_url"],
            "historical_acquisition_rights_state": item["rights_state"],
        })

    if (
        len(authorised) != PBS_UTILISATION_OBJECT_COUNT
        or len({item["path"] for item in authorised})
        != PBS_UTILISATION_OBJECT_COUNT
        or {item["path"] for item in authorised} != expected_paths
    ):
        raise ValueError(
            "PBS utilisation authorization did not bind six objects"
        )

    hashes = {
        str(PBS_UTILISATION_AUTHORIZATION): _sha256(
            root / PBS_UTILISATION_AUTHORIZATION
        ),
        str(PBS_UTILISATION_LINEAGE): _sha256(root / PBS_UTILISATION_LINEAGE),
    }
    return sorted(authorised, key=itemgetter("path")), hashes


def _pbs_lineage_item_is_authorized(
    item: dict[str, Any],
    frozen: dict[str, Any] | None,
    host: str | None,
    authorization: dict[str, Any],
) -> bool:
    if frozen is None:
        return False
    return all((
        item["dataset"] == PBS_UTILISATION_DATASET,
        item["lineage_complete"] is True,
        frozen["dataset"] == PBS_UTILISATION_DATASET,
        item["source_id"] in authorization["allowed_sources"],
        item["category"] in authorization["categories"],
        host in authorization["allowed_domains"],
        item["content_sha256"] == frozen["identity"]["sha256"],
        item["byte_count"] == frozen["identity"]["byte_count"],
    ))


def build_report(root: Path, *, observed_at: str) -> dict[str, Any]:
    overlay = _read(root, FROZEN_OVERLAY)
    pbs_authorization = _read(root, PBS_UTILISATION_AUTHORIZATION)
    m108 = _read(root, M108_ASSESSMENT)
    objects = overlay["objects"]
    mbs_summary = _reconcile_mbs_silver_attestation(
        objects,
        _read(root, MBS_RIGHTS_ATTESTATION),
        _read(root, MBS_SILVER_PUBLIC_TREE_READBACK),
    )
    august_mbs_objects = reconcile_august_mbs_attestation(
        objects, _read(root, AUGUST_MBS_RIGHTS_ATTESTATION)
    )

    rights_overrides = {
        item[
            "path"
        ]: "maintainer_attested_exact_public_release_permission_for_silver_object"
        for item in mbs_summary["paths"]
    }
    pbs_utilisation_objects, pbs_rights_evidence_inputs = (
        _reconcile_pbs_utilisation_authorization(
            root,
            objects,
            pbs_authorization,
            _read(root, PBS_UTILISATION_LINEAGE),
        )
    )
    rights_overrides.update({
        item["path"]: PBS_UTILISATION_RIGHTS_STATE
        for item in pbs_utilisation_objects
    })
    rights_overrides.update({
        item["path"]: MBS_AUGUST_RIGHTS_STATE for item in august_mbs_objects
    })
    pbs_raw_rights = _reconcile_pbs_raw_permission(
        root,
        objects,
        _read(root, PBS_RAW_PERMISSION),
        _read(root, PBS_PROJECTED_LINEAGE),
        _read(root, PBS_ARCHIVE_LINEAGE),
    )
    rights_overrides.update({
        item["path"]: PBS_RAW_RIGHTS_STATE for item in pbs_raw_rights["objects"]
    })
    rights_summary = _reconcile_object_rights(objects, rights_overrides)

    if len(august_mbs_objects) != AUGUST_PROJECTION_COUNT:
        raise ValueError(
            "the four frozen August Bronze projections did not reconcile"
        )

    cms_reference, cms_evidence_inputs = _reconcile_cms(
        root, _read(root, CMS_REVIEW)
    )
    supplemental_readbacks = {
        "pbs_source_archive": _reconcile_pbs_source_archive_publication(
            root, objects
        ),
        "m112_gate": _reconcile_m112_canary_readback(root, objects),
    }

    evidence_inputs = {
        str(FROZEN_OVERLAY): _sha256(root / FROZEN_OVERLAY),
        **cms_evidence_inputs,
        str(MBS_RIGHTS_ATTESTATION): _sha256(root / MBS_RIGHTS_ATTESTATION),
        str(MBS_SILVER_PUBLIC_TREE_READBACK): _sha256(
            root / MBS_SILVER_PUBLIC_TREE_READBACK
        ),
        str(AUGUST_MBS_RIGHTS_ATTESTATION): _sha256(
            root / AUGUST_MBS_RIGHTS_ATTESTATION
        ),
        **pbs_rights_evidence_inputs,
        **pbs_raw_rights["evidence_inputs"],
        **supplemental_readbacks["pbs_source_archive"]["evidence_inputs"],
        **supplemental_readbacks["m112_gate"]["evidence_inputs"],
        str(M108_ASSESSMENT): _sha256(root / M108_ASSESSMENT),
    }

    return {
        "schema_id": "global-medicines-atlas.australian-m112-current-rights-reconciliation",
        "schema_version": 1,
        "observed_at": observed_at,
        "purpose": "Reconcile effective rights evidence after the exact MBS Silver attestation, PBS utilisation publication authorization, and CMS HCPCS rights decision without changing object membership or release state.",
        "frozen_inventory": {
            "path": str(FROZEN_OVERLAY),
            "sha256": evidence_inputs[str(FROZEN_OVERLAY)],
            "membership_sha256": overlay["approved_path_membership_sha256"],
            "object_count": len(objects),
            "raw_paths": overlay["scope"]["approved_raw_paths"],
            "projection_paths": overlay["scope"]["approved_projection_paths"],
            "membership_changed": False,
            "all_b1_b2_lineages_complete": overlay["updated_gate_totals"][
                "complete_b1_b2_lineage_objects"
            ]
            == FROZEN_OBJECT_COUNT,
        },
        "effective_m112_rights": {
            "resolved_object_count": rights_summary["resolved_count"],
            "unresolved_object_count": FROZEN_OBJECT_COUNT
            - rights_summary["resolved_count"],
            "state_counts": rights_summary["counts"],
            "rights_evidence_does_not_imply_admission": True,
        },
        "exact_july_2025_mbs_silver": {
            "object_count": mbs_summary["object_count"],
            "attestation_path": str(MBS_RIGHTS_ATTESTATION),
            "attestation_sha256": evidence_inputs[str(MBS_RIGHTS_ATTESTATION)],
            "rights_state": "maintainer_attested_exact_public_release_permission_for_silver_object",
            "public_release_authorized": mbs_summary[
                "public_release_authorized"
            ],
            "public_release_performed": mbs_summary["public_release_performed"],
            "current_public_tree_readback": mbs_summary[
                "current_public_tree_readback"
            ],
            "paths": mbs_summary["paths"],
        },
        "pbs_utilisation_raw_objects": {
            "object_count": len(pbs_utilisation_objects),
            "authorization_path": str(PBS_UTILISATION_AUTHORIZATION),
            "authorization_sha256": evidence_inputs[
                str(PBS_UTILISATION_AUTHORIZATION)
            ],
            "lineage_path": str(PBS_UTILISATION_LINEAGE),
            "lineage_sha256": evidence_inputs[str(PBS_UTILISATION_LINEAGE)],
            "rights_state": PBS_UTILISATION_RIGHTS_STATE,
            "public_release_authorized_within_scope": pbs_authorization[
                "external_publication_authorized"
            ],
            "maintainer_asserted_redistribution_permission": pbs_authorization[
                "maintainer_asserted_redistribution_permission"
            ],
            "scope": {
                "dataset": pbs_authorization["dataset"],
                "allowed_sources": pbs_authorization["allowed_sources"],
                "allowed_domains": pbs_authorization["allowed_domains"],
                "categories": pbs_authorization["categories"],
            },
            "publication_exclusions": pbs_authorization[
                "publication_does_not_authorize"
            ],
            "unlicensed_vocabulary_presence_reviewed": False,
            "full_object_release_requires_exclusion_review": True,
            "objects": pbs_utilisation_objects,
        },
        "pbs_raw_redistribution_permission": {
            key: value
            for key, value in pbs_raw_rights.items()
            if key != "evidence_inputs"
        },
        "pbs_source_archive_exact_publication": supplemental_readbacks[
            "pbs_source_archive"
        ]["record"],
        "m112_admission_canary_readback": supplemental_readbacks["m112_gate"][
            "record"
        ],
        "august_2026_mbs_bronze_projections": {
            "object_count": len(august_mbs_objects),
            "rights_state": MBS_AUGUST_RIGHTS_STATE,
            "attestation_path": str(AUGUST_MBS_RIGHTS_ATTESTATION),
            "attestation_sha256": evidence_inputs[
                str(AUGUST_MBS_RIGHTS_ATTESTATION)
            ],
            "public_release_rights_attested": True,
            "permission_instrument_existence_and_applicability": (
                "maintainer_attested_not_independently_reviewed_or_located_at_maintainer_direction"
            ),
            "public_release_performed_by_this_action": False,
            "m108_assessment_derived_output_authority": m108[
                "august_2026_six_table_operation_assessment"
            ]["authorization"]["derived_output_authority"],
            "objects": august_mbs_objects,
        },
        "cms_hcpcs_external_reference": cms_reference,
        "boundaries": {
            "m112_denominator_changed": False,
            "all_remaining_deferrals_preserved": True,
            "deferred_objects": supplemental_readbacks["m112_gate"]["record"][
                "deferred_object_count"
            ],
            "v4_admissions": supplemental_readbacks["m112_gate"]["record"][
                "admitted_object_count"
            ],
            "consumer_canaries": supplemental_readbacks["m112_gate"]["record"][
                "canaried_object_count"
            ],
            "new_sources_or_datasets_added": False,
            "source_payload_bytes_read": False,
            "source_payload_values_inspected": False,
            "external_publication_performed": mbs_summary[
                "public_release_performed"
            ],
        },
        "evidence_inputs": evidence_inputs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--observed-at",
        default=datetime
        .now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    )
    arguments = parser.parse_args()
    report = build_report(arguments.root, observed_at=arguments.observed_at)
    destination = arguments.root / arguments.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps({
            "path": str(arguments.output),
            "object_count": FROZEN_OBJECT_COUNT,
        })
    )


if __name__ == "__main__":
    main()
