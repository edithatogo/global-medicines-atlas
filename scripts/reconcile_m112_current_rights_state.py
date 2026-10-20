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
MBS_RAW_RIGHTS_ATTESTATION = QUAL / (
    "australian-mbs-six-raw-object-rights-attestation-20261020.json"
)
REIMBURSEMENT_MEDALLION_RIGHTS_ATTESTATION = QUAL / (
    "australian-reimbursement-atlas-medallion-rights-attestation-20261020.json"
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
M112_CURRENT_ADMISSION_COUNT = 6
M112_CURRENT_CANARY_COUNT = 6
M112_Q3_CANARY_RUN_ID = 39356792827
M112_Q3_CANARY_BYTES = 7_680_041
M112_HISTORICAL_CANARY_RUN_ID = 39330593204
M112_HISTORICAL_CANARY_BYTES = 205885063
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
M112_HISTORICAL_CANARY = QUAL / (
    "australian-m112-v4-historical-1993-2015-consumer-canary-"
    "20261020-39330593204.json"
)
M112_Q3_ADMISSION_CANARY = QUAL / (
    "australian-m112-v4-demographics-q3-july-admission-qualification-"
    "20261020-39356792827.json"
)
M112_Q2_ADMISSION_CANARY = QUAL / (
    "australian-m112-v4-demographics-q2-may-"
    "admission-qualification-20261020.json"
)
M112_Q2_CANARY_RUN_ID = 39419974066
M112_Q2_CANARY_COMMIT = "516d56e8fd5274b37d65a2192257a41e7cb8cb94"
M112_Q2_CANARY_CONTRACT_SHA256 = (
    "cd7ccdce266d1d42fa658abe4b097c207627d80943b01c198f7d844c16241152"
)
M112_Q2_CANARY_PATH = (
    "raw/mbs/utilisation/demographics/mbs-demographics-2016-qtr-2-may.csv"
)
M112_Q2_CANARY_SHA256 = (
    "495db013c1cb10d26455ffbcd6acbb229d1064fe6f48d3a62b92387866de4958"
)
M112_Q2_CANARY_BYTES = 23_436_706
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
PBS_SOURCE_PROJECTION_RIGHTS_ATTESTATION = QUAL / (
    "australian-pbs-bronze-projection-rights-attestation-20261020.json"
)
PBS_SOURCE_PROJECTION_RIGHTS_STATE = (
    "maintainer_attested_exact_public_release_permission_for_bronze_projection"
)
MBS_RAW_RIGHTS_STATE = (
    "maintainer_attested_exact_public_release_permission_for_mbs_raw_object"
)
MBS_RAW_RIGHTS_OBJECT_COUNT = 6
PBS_UTILISATION_LIMITED_SCREEN = QUAL / (
    "australian-pbs-utilisation-limited-vocabulary-screen-20261020.json"
)
PBS_UTILISATION_EXACT_RIGHTS_ATTESTATION = QUAL / (
    "australian-pbs-utilisation-six-object-rights-attestation-20261020.json"
)
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
PBS_UTILISATION_RIGHTS_STATE = "maintainer_attested_exact_public_release_permission_for_pbs_utilisation_raw_object"
PBS_RAW_RIGHTS_STATE = "owner_attested_pbs_raw_redistribution_permission"
PBS_UTILISATION_OBJECT_COUNT = 6
CMS_SOURCE_ID = "us_cms_hcpcs_level_ii"
CMS_SOURCE_VERSION = "us_cms_hcpcs_level_ii_2026_07"
CMS_SHA256 = "5591fed257e4d2307c1d2dc9c66abc8e346b1f4c076e9e48559799e2de14b70a"
FROZEN_OBJECT_COUNT = 1759
MBS_SILVER_OBJECT_COUNT = 6
AUGUST_PROJECTION_COUNT = 4
REIMBURSEMENT_MEDALLION_OBJECT_COUNT = 12
MBS_AUGUST_RIGHTS_STATE = (
    "maintainer_attested_exact_public_release_permission_for_bronze_projection"
)
REIMBURSEMENT_MEDALLION_RIGHTS_STATE = (
    "maintainer_attested_exact_public_release_permission_for_derived_projection"
)
RIGHTS_RESOLVED_STATES = {
    "authorized_exact_source_release_permitted",
    "approved_exact_scope_CC_BY_3_0_AU_publicly_readback_verified",
    MBS_RAW_RIGHTS_STATE,
    "maintainer_attested_exact_public_release_permission_for_silver_object",
    MBS_AUGUST_RIGHTS_STATE,
    REIMBURSEMENT_MEDALLION_RIGHTS_STATE,
    PBS_SOURCE_PROJECTION_RIGHTS_STATE,
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
    original_admission_path = Path(scope["admission_path"])
    admission_path = Path(review["rights_review"]["superseding_admission_path"])
    acquisition = _read(root, acquisition_path)
    original_admission = _read(root, original_admission_path)
    admission = _read(root, admission_path)
    invalid_admission = [
        admission.get("acquisition_id") != acquisition.get("acquisition_id"),
        admission.get("content_id") != CMS_SHA256,
        admission.get("state") != "landed",
        admission.get("reviewer_status") != "approved",
        "public_use_rights_reviewed" not in admission.get("reason_codes", []),
        "not_admitted_to_processing" not in admission.get("reason_codes", []),
        admission.get("supersedes_decision_id")
        != original_admission.get("decision_id"),
    ]
    if any(invalid_admission):
        raise ValueError("CMS HCPCS admission rights review did not reconcile")

    hashes = {
        str(CMS_REVIEW): _sha256(root / CMS_REVIEW),
        str(decision_path): _sha256(root / decision_path),
        str(acquisition_path): _sha256(root / acquisition_path),
        str(original_admission_path): _sha256(root / original_admission_path),
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
            "superseded_admission_path": str(original_admission_path),
            "superseded_admission_sha256": hashes[str(original_admission_path)],
            "superseded_admission_reviewer_status": original_admission[
                "reviewer_status"
            ],
            "latest_admission_path": str(admission_path),
            "latest_admission_sha256": hashes[str(admission_path)],
            "latest_admission_state": admission["state"],
            "latest_admission_reviewer_status": admission["reviewer_status"],
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
    projection_attestation = _read(
        root, PBS_SOURCE_PROJECTION_RIGHTS_ATTESTATION
    )
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
        projection_attestation["schema_id"]
        != "global-medicines-atlas.australian-pbs-bronze-projection-rights-attestation",
        projection_attestation["public_release_rights_attested"] is not True,
        projection_attestation[
            "permission_instrument_existence_and_applicability"
        ]
        != "maintainer_attested_not_independently_reviewed_or_located",
        projection_attestation["scope"]["dataset"]
        != PBS_SOURCE_ARCHIVE_DATASET,
        projection["revision"] != projection_attestation["scope"]["revision"],
        projection_attestation["scope"]["revision"] != audit["revision"],
        projection_attestation["scope"]["path"] != PBS_SOURCE_PROJECTION_PATH,
        projection_attestation["scope"]["sha256"]
        != PBS_SOURCE_PROJECTION_SHA256,
        projection_attestation["scope"]["byte_count"]
        != PBS_SOURCE_PROJECTION_BYTES,
        projection_attestation["boundaries"]["new_publication_performed"]
        is not False,
        projection_attestation["boundaries"]["v4_admission_performed"]
        is not False,
        projection_attestation["boundaries"]["consumer_canary_performed"]
        is not False,
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
        str(PBS_SOURCE_PROJECTION_RIGHTS_ATTESTATION): _sha256(
            root / PBS_SOURCE_PROJECTION_RIGHTS_ATTESTATION
        ),
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
                "rights_state": PBS_SOURCE_PROJECTION_RIGHTS_STATE,
                "rights_attestation_path": str(
                    PBS_SOURCE_PROJECTION_RIGHTS_ATTESTATION
                ),
                "rights_attestation_sha256": hashes[
                    str(PBS_SOURCE_PROJECTION_RIGHTS_ATTESTATION)
                ],
                "public_release_rights_attested": True,
                "permission_instrument_independently_reviewed": False,
                "v4_admission": projection["v4_admission"],
                "consumer_canary": False,
                "release_performed_by_this_reconciliation": False,
                "derived_rights_inferred_from_source_permission": False,
            },
            "rights_conclusion_made": True,
            "rights_scope": (
                "exact raw PBS source archive and separately attested exact "
                "Bronze projection; raw permission does not extend to projection"
            ),
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


def _verify_q3_m112_canary_receipt(root: Path) -> dict[str, Any]:
    """Verify the exact Q3 admission receipt and return its indexed run record."""
    receipt = _read(root, M112_Q3_ADMISSION_CANARY)
    admission = receipt["admission"]
    canary = receipt["consumer_canary"]
    object_identity = canary["object"]
    workflow = canary["hosted_workflow"]
    checks = [
        receipt["approved_denominator"] != FROZEN_OBJECT_COUNT,
        receipt["admissions"] != 1,
        receipt["consumer_canaries"] != 1,
        canary["status"] != "passed",
        admission["dataset"] != "edithatogo/australian-mbs-utilisation-archive",
        admission["path"]
        != "raw/mbs/utilisation/demographics/mbs-demographics-2016-qtr-3-july.csv",
        admission["sha256"]
        != "bc6ad85e41bd2394f4dc0b3550c0657eb7389f444c9300d72105a41530e08e1c",
        admission["byte_count"] != M112_Q3_CANARY_BYTES,
        admission["contract_sha256"]
        != "fdb1164ba5d03e7946c3146ee7ecde71a6b8d40f71af483fae356a0142baef7b",
        object_identity["dataset"] != admission["dataset"],
        object_identity["path"] != admission["path"],
        object_identity["sha256"] != admission["sha256"],
        object_identity["bytes"] != admission["byte_count"],
        canary["contract_sha256"] != admission["contract_sha256"],
        workflow["repository"] != "edithatogo/global-medicines-atlas",
        workflow["run_id"] != M112_Q3_CANARY_RUN_ID,
        canary["verification"]["remote_digest_match"] is not True,
        canary["verification"]["consumer_stream_digest_match"] is not True,
        canary["verification"]["reader_cache_bytes_after_close"] != 0,
        canary["boundaries"]["admission_used"] is not True,
        canary["boundaries"]["admission_performed"] is not False,
        canary["boundaries"]["public_dataset_mutated"] is not False,
        canary["boundaries"]["source_payload_bytes_retained"] is not False,
        canary["boundaries"]["source_values_or_rows_included"] is not False,
        receipt["native_source_layout_qualified"] is not False,
        receipt["source_values_or_payload_bytes_retained"] is not False,
    ]
    if any(checks):
        raise ValueError("Q3 M-112 admission/canary receipt did not reconcile")
    path = str(M112_Q3_ADMISSION_CANARY)
    return {
        "receipt_path": path,
        "receipt_sha256": _sha256(root / M112_Q3_ADMISSION_CANARY),
        "run_id": workflow["run_id"],
        "run_url": workflow["run_url"],
        "workflow_commit": workflow["commit"],
    }


def _verify_q2_m112_canary_receipt(root: Path) -> dict[str, Any]:
    """Verify the exact Q2 admission and hosted consumer-canary receipt."""
    receipt = _read(root, M112_Q2_ADMISSION_CANARY)
    if not isinstance(receipt.get("consumer_canary"), dict):
        raise TypeError("Q2 M-112 consumer-canary receipt is malformed")
    admission = receipt["admission"]
    canary = receipt["consumer_canary"]
    object_identity = canary["object"]
    workflow = canary["hosted_workflow"]
    verification = canary["verification"]
    boundaries = canary["boundaries"]
    checks = [
        receipt["schema_id"]
        != "global-medicines-atlas.m112-v4-admission-qualification",
        receipt["status"] != "admitted_with_consumer_canary",
        receipt["approved_denominator"] != FROZEN_OBJECT_COUNT,
        receipt["admissions"] != 1,
        receipt["consumer_canaries"] != 1,
        receipt["contract_path"]
        != "quality/qualifications/australian-m112-v4-demographics-q2-may-raw-b2-contract.json",
        receipt["contract_sha256"] != M112_Q2_CANARY_CONTRACT_SHA256,
        receipt["native_source_layout_qualified"] is not False,
        receipt["source_values_or_payload_bytes_retained"] is not False,
        admission["dataset"] != "edithatogo/australian-mbs-utilisation-archive",
        admission["revision"] != "dee9a5b0580dfe394474dc26b372559462e157e7",
        admission["path"] != M112_Q2_CANARY_PATH,
        admission["sha256"] != M112_Q2_CANARY_SHA256,
        admission["byte_count"] != M112_Q2_CANARY_BYTES,
        admission["contract_sha256"] != M112_Q2_CANARY_CONTRACT_SHA256,
        canary["status"] != "passed",
        canary["contract_sha256"] != M112_Q2_CANARY_CONTRACT_SHA256,
        object_identity["dataset"] != admission["dataset"],
        object_identity["revision"] != admission["revision"],
        object_identity["path"] != M112_Q2_CANARY_PATH,
        object_identity["sha256"] != M112_Q2_CANARY_SHA256,
        object_identity["bytes"] != M112_Q2_CANARY_BYTES,
        workflow["repository"] != "edithatogo/global-medicines-atlas",
        workflow["commit"] != M112_Q2_CANARY_COMMIT,
        workflow["run_id"] != M112_Q2_CANARY_RUN_ID,
        workflow["run_url"]
        != "https://github.com/edithatogo/global-medicines-atlas/actions/runs/39419974066",
        canary["consumer"]["module"]
        != "global_medicines_atlas.federation_reader.FederatedReader",
        verification["origin"] != "remote",
        verification["remote_digest_match"] is not True,
        verification["consumer_stream_digest_match"] is not True,
        verification["source_values_or_rows_interpreted"] is not False,
        verification["reader_cache_bytes_after_read"] != 0,
        verification["reader_cache_bytes_after_close"] != 0,
        boundaries["admission_used"] is not True,
        boundaries["admission_performed"] is not False,
        boundaries["public_dataset_mutated"] is not False,
        boundaries["source_payload_bytes_retained"] is not False,
        boundaries["source_values_or_rows_included"] is not False,
    ]
    if any(checks):
        raise ValueError("Q2 M-112 admission/canary receipt did not reconcile")
    path = str(M112_Q2_ADMISSION_CANARY)
    return {
        "receipt_path": path,
        "receipt_sha256": _sha256(root / M112_Q2_ADMISSION_CANARY),
        "run_id": workflow["run_id"],
        "run_url": workflow["run_url"],
        "workflow_commit": workflow["commit"],
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
    if (
        role_qualification["cohort"]["v4_admissions"]
        != M112_CURRENT_ADMISSION_COUNT
        or role_qualification["cohort"]["consumer_canaries"]
        != M112_CURRENT_CANARY_COUNT
        or len(role_qualification["current_admission_evidence"])
        != M112_CURRENT_ADMISSION_COUNT
        or len({
            item["path"]
            for item in role_qualification["current_admission_evidence"]
        })
        != M112_CURRENT_ADMISSION_COUNT
    ):
        raise ValueError(
            "current M-112 role qualification counts did not reconcile"
        )
    input_hashes[str(M112_ROLE_QUALIFICATION)] = _sha256(
        root / M112_ROLE_QUALIFICATION
    )
    historical_canary = _read(root, M112_HISTORICAL_CANARY)
    admission = historical_canary["admission"]
    canary = historical_canary["consumer_canary"]
    workflow = canary["hosted_workflow"]
    canary_checks: list[bool] = [
        historical_canary["approved_denominator"] != FROZEN_OBJECT_COUNT,
        historical_canary["admissions"] != 1,
        historical_canary["consumer_canaries"] != 1,
        canary["status"] != "passed",
        canary["boundaries"]["admission_used"] is not True,
        canary["boundaries"]["admission_performed"] is not False,
        canary["boundaries"]["public_dataset_mutated"] is not False,
        canary["boundaries"]["source_payload_bytes_retained"] is not False,
        canary["boundaries"]["source_values_or_rows_included"] is not False,
        workflow["repository"] != "edithatogo/global-medicines-atlas",
        workflow["run_id"] != M112_HISTORICAL_CANARY_RUN_ID,
        workflow["commit"] != "3149a5533ecb1b721d9deda66311d4abc94ee3d1",
        admission["dataset"] != "edithatogo/australian-mbs-utilisation-archive",
        admission["path"]
        != "raw/mbs/utilisation/group/mbs-demographics-historical-1993-2015.zip",
        admission["sha256"]
        != "e00bd214e7f9e2428000a8e67c8d46a78fb4b12f381373d813849287cbc9cc33",
        admission["byte_count"] != M112_HISTORICAL_CANARY_BYTES,
    ]
    if any(canary_checks):
        raise ValueError("historical M-112 canary receipt did not reconcile")
    input_hashes[str(M112_HISTORICAL_CANARY)] = _sha256(
        root / M112_HISTORICAL_CANARY
    )
    runs.append({
        "receipt_path": str(M112_HISTORICAL_CANARY),
        "receipt_sha256": input_hashes[str(M112_HISTORICAL_CANARY)],
        "run_id": workflow["run_id"],
        "run_url": workflow["run_url"],
        "workflow_commit": workflow["commit"],
    })

    q3_run = _verify_q3_m112_canary_receipt(root)
    input_hashes[str(M112_Q3_ADMISSION_CANARY)] = q3_run["receipt_sha256"]
    runs.append(q3_run)

    q2_run = _verify_q2_m112_canary_receipt(root)
    input_hashes[str(M112_Q2_ADMISSION_CANARY)] = q2_run["receipt_sha256"]
    runs.append(q2_run)

    return {
        "record": {
            "admitted_object_count": role_qualification["cohort"][
                "v4_admissions"
            ],
            "canaried_object_count": role_qualification["cohort"][
                "consumer_canaries"
            ],
            "deferred_object_count": FROZEN_OBJECT_COUNT
            - role_qualification["cohort"]["v4_admissions"],
            "current_role_qualification": {
                "path": str(M112_ROLE_QUALIFICATION),
                "sha256": _sha256(root / M112_ROLE_QUALIFICATION),
                "admitted_objects": role_qualification[
                    "current_admission_evidence"
                ],
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


def _reconcile_mbs_raw_attestation(
    objects: list[dict[str, Any]], attestation: dict[str, Any]
) -> dict[str, Any]:
    decision = attestation.get("decision", {})
    attested = {
        item["path"]: (item["sha256"], item["byte_count"])
        for item in attestation.get("authorized_objects", [])
    }
    frozen = {
        obj["path"]: (obj["identity"]["sha256"], obj["identity"]["byte_count"])
        for obj in objects
        if obj["path"] in attested
    }
    if (
        attestation.get("dataset_identity", {}).get("dataset")
        != "edithatogo/australian-mbs-source-archive"
        or decision.get("public_release_rights_attested") is not True
        or decision.get("public_release_performed") is not False
        or len(attested) != MBS_RAW_RIGHTS_OBJECT_COUNT
        or frozen != attested
    ):
        raise ValueError(
            "exact six-object MBS raw rights attestation did not reconcile"
        )
    return {
        "object_count": len(attested),
        "rights_state": MBS_RAW_RIGHTS_STATE,
        "permission_instrument_existence_and_applicability": (
            "maintainer_attested_not_independently_reviewed"
        ),
        "public_release_rights_attested": True,
        "public_release_performed": False,
        "v4_admission": False,
        "consumer_canary": False,
        "objects": [
            {
                "path": path,
                "sha256": identity[0],
                "byte_count": identity[1],
                "rights_state": MBS_RAW_RIGHTS_STATE,
                "pre_attestation_rights_review_state": next(
                    obj["rights"]["state"]
                    for obj in objects
                    if obj["path"] == path
                ),
            }
            for path, identity in sorted(attested.items())
        ],
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


def reconcile_reimbursement_medallion_attestation(
    objects: list[dict[str, Any]], attestation: dict[str, Any]
) -> list[dict[str, Any]]:
    """Bind the maintainer's scoped redistribution attestation to exact objects."""
    frozen = {
        (obj["dataset"], obj["path"]): obj
        for obj in objects
        if obj["dataset"] == "edithatogo/reimbursement-atlas"
        and obj["candidate_class"] == "existing_data_projection"
    }
    authorized = {
        (item["dataset"], item["path"]): item
        for item in attestation["authorized_objects"]
    }
    boundaries = attestation.get("boundaries", {})
    invalid_scope = [
        len(frozen) != REIMBURSEMENT_MEDALLION_OBJECT_COUNT,
        len(authorized) != REIMBURSEMENT_MEDALLION_OBJECT_COUNT,
        set(authorized) != set(frozen),
        attestation.get("dataset") != "edithatogo/reimbursement-atlas",
        {obj["revision"] for obj in frozen.values()}
        != {attestation.get("revision")},
        attestation.get("public_redistribution_rights_attested") is not True,
        attestation.get("permission_instrument_existence_and_applicability")
        != "maintainer_attested_not_independently_reviewed_or_located_at_maintainer_direction",
    ]
    invalid_boundaries = [
        boundaries.get("frozen_inventory_membership_changed") is not False,
        boundaries.get("public_release_performed") is not False,
        boundaries.get("v4_admission_or_promotion_authorized") is not False,
        boundaries.get("consumer_canaries_authorized") is not False,
    ]
    if any(invalid_scope) or any(invalid_boundaries):
        raise ValueError(
            "Reimbursement Atlas rights attestation scope mismatch"
        )
    result: list[dict[str, Any]] = []
    for key, item in authorized.items():
        obj = frozen[key]
        identity = obj["identity"]
        if (
            item.get("sha256") != identity.get("sha256")
            or item.get("byte_count") != identity.get("byte_count")
            or obj.get("b1_b2_lineage", {}).get("complete") is not True
        ):
            raise ValueError(
                f"Reimbursement Atlas rights attestation identity mismatch: {key[1]}"
            )
        result.append({
            "dataset": key[0],
            "revision": obj["revision"],
            "path": key[1],
            "sha256": item["sha256"],
            "byte_count": item["byte_count"],
            "rights_state": REIMBURSEMENT_MEDALLION_RIGHTS_STATE,
            "lineage_complete": True,
            "v4_admission": False,
            "consumer_canary": False,
        })
    return sorted(result, key=itemgetter("dataset", "path"))


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


def _reconcile_pbs_limited_vocabulary_screen(root: Path) -> dict[str, Any]:
    screen = _read(root, PBS_UTILISATION_LIMITED_SCREEN)
    lineage = _read(root, PBS_UTILISATION_LINEAGE)
    results = screen.get("results", {})
    lineage_objects = cast("list[dict[str, Any]]", lineage["objects"])
    expected_objects = {
        item["path"]: (item["content_sha256"], item["byte_count"])
        for item in lineage_objects
    }
    screened_objects = cast("list[dict[str, Any]]", screen.get("objects", []))
    observed_objects = {
        item["path"]: (item["sha256"], item["byte_count"])
        for item in screened_objects
    }
    checks = (
        screen.get("schema_id")
        == "global-medicines-atlas.australian-pbs-utilisation-limited-vocabulary-screen",
        screen.get("dataset") == PBS_UTILISATION_DATASET,
        screen.get("revision") == "9f1d53cd50eea251b326da42a96f3ac72ebce97a",
        screen.get("scope", {}).get("object_count")
        == PBS_UTILISATION_OBJECT_COUNT,
        len(expected_objects) == PBS_UTILISATION_OBJECT_COUNT,
        len(screened_objects) == PBS_UTILISATION_OBJECT_COUNT,
        len(observed_objects) == len(screened_objects),
        observed_objects == expected_objects,
        all(
            item["dataset"] == screen.get("dataset")
            and item["revision"] == screen.get("revision")
            for item in lineage_objects
        ),
        results.get("all_object_digests_and_byte_counts_match_pinned_lineage")
        is True,
        results.get("full_vocabulary_exclusion_review_complete") is False,
        results.get("rights_exclusion_fully_resolved") is False,
    )
    if not all(checks):
        raise ValueError("PBS limited vocabulary screen did not reconcile")
    return screen


def _reconcile_pbs_utilisation_exact_rights_attestation(
    root: Path, expected_objects: list[dict[str, Any]]
) -> dict[str, Any]:
    attestation = _read(root, PBS_UTILISATION_EXACT_RIGHTS_ATTESTATION)
    screen = _reconcile_pbs_limited_vocabulary_screen(root)
    expected = {
        item["path"]: (item["sha256"], item["byte_count"])
        for item in expected_objects
    }
    authorized = cast(
        "list[dict[str, Any]]", attestation.get("authorized_objects", [])
    )
    observed = {
        item["path"]: (item["sha256"], item["byte_count"])
        for item in authorized
    }
    screen_identities = {
        item["path"]: (item["sha256"], item["byte_count"])
        for item in screen["objects"]
    }
    decision = attestation.get("decision", {})
    checks = (
        attestation.get("schema_id")
        == "global-medicines-atlas.australian-pbs-utilisation-six-object-rights-attestation",
        attestation.get("schema_version") == 1,
        attestation.get("dataset_identity", {}).get("dataset")
        == PBS_UTILISATION_DATASET,
        decision.get("public_release_rights_attested") is True,
        decision.get("scope")
        == "The exact six dataset paths, SHA-256 digests, and byte counts listed below; permission includes all file contents, including any vocabulary previously excluded.",
        decision.get("permission_instrument_existence_and_applicability")
        == "maintainer_attested_not_independently_reviewed",
        decision.get("public_release_performed") is False,
        decision.get("v4_admission") is False,
        decision.get("consumer_canary") is False,
        decision.get(
            "rights_inferred_from_lineage_or_source_category_authorization"
        )
        is False,
        len(authorized) == PBS_UTILISATION_OBJECT_COUNT,
        len(observed) == PBS_UTILISATION_OBJECT_COUNT,
        observed == expected,
        observed == screen_identities,
        attestation.get("boundaries", {}).get("source_payload_files_written")
        is False,
    )
    if not all(checks):
        raise ValueError(
            "PBS utilisation exact rights attestation did not reconcile"
        )
    return attestation


def build_report(root: Path, *, observed_at: str) -> dict[str, Any]:
    overlay = _read(root, FROZEN_OVERLAY)
    pbs_authorization = _read(root, PBS_UTILISATION_AUTHORIZATION)
    objects = overlay["objects"]
    mbs_summary = _reconcile_mbs_silver_attestation(
        objects,
        _read(root, MBS_RIGHTS_ATTESTATION),
        _read(root, MBS_SILVER_PUBLIC_TREE_READBACK),
    )
    mbs_raw_summary = _reconcile_mbs_raw_attestation(
        objects, _read(root, MBS_RAW_RIGHTS_ATTESTATION)
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
    rights_overrides.update({
        item["path"]: MBS_RAW_RIGHTS_STATE
        for item in mbs_raw_summary["objects"]
    })
    pbs_utilisation_objects, pbs_rights_evidence_inputs = (
        _reconcile_pbs_utilisation_authorization(
            root,
            objects,
            pbs_authorization,
            _read(root, PBS_UTILISATION_LINEAGE),
        )
    )
    _reconcile_pbs_limited_vocabulary_screen(root)
    _reconcile_pbs_utilisation_exact_rights_attestation(
        root, pbs_utilisation_objects
    )
    rights_overrides.update({
        item["path"]: PBS_UTILISATION_RIGHTS_STATE
        for item in pbs_utilisation_objects
    })
    rights_overrides.update({
        item["path"]: MBS_AUGUST_RIGHTS_STATE for item in august_mbs_objects
    })
    rights_overrides.update({
        item["path"]: REIMBURSEMENT_MEDALLION_RIGHTS_STATE
        for item in reconcile_reimbursement_medallion_attestation(
            objects, _read(root, REIMBURSEMENT_MEDALLION_RIGHTS_ATTESTATION)
        )
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
    rights_overrides[PBS_SOURCE_PROJECTION_PATH] = (
        PBS_SOURCE_PROJECTION_RIGHTS_STATE
    )
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
        str(MBS_RAW_RIGHTS_ATTESTATION): _sha256(
            root / MBS_RAW_RIGHTS_ATTESTATION
        ),
        str(AUGUST_MBS_RIGHTS_ATTESTATION): _sha256(
            root / AUGUST_MBS_RIGHTS_ATTESTATION
        ),
        str(REIMBURSEMENT_MEDALLION_RIGHTS_ATTESTATION): _sha256(
            root / REIMBURSEMENT_MEDALLION_RIGHTS_ATTESTATION
        ),
        **pbs_rights_evidence_inputs,
        **pbs_raw_rights["evidence_inputs"],
        **supplemental_readbacks["pbs_source_archive"]["evidence_inputs"],
        **supplemental_readbacks["m112_gate"]["evidence_inputs"],
        str(PBS_UTILISATION_LIMITED_SCREEN): _sha256(
            root / PBS_UTILISATION_LIMITED_SCREEN
        ),
        str(PBS_UTILISATION_EXACT_RIGHTS_ATTESTATION): _sha256(
            root / PBS_UTILISATION_EXACT_RIGHTS_ATTESTATION
        ),
        str(M108_ASSESSMENT): _sha256(root / M108_ASSESSMENT),
    }

    return {
        "schema_id": "global-medicines-atlas.australian-m112-current-rights-reconciliation",
        "schema_version": 1,
        "observed_at": observed_at,
        "purpose": "Reconcile effective rights evidence after exact MBS, Reimbursement Atlas, PBS utilisation, and CMS rights decisions without changing object membership, admission, or release state.",
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
        "mbs_raw_object_rights_attestation": {
            **mbs_raw_summary,
            "attestation_path": str(MBS_RAW_RIGHTS_ATTESTATION),
            "attestation_sha256": evidence_inputs[
                str(MBS_RAW_RIGHTS_ATTESTATION)
            ],
            "b1_b2_lineage_or_admission_inferred": False,
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
            "exact_rights_attestation_path": str(
                PBS_UTILISATION_EXACT_RIGHTS_ATTESTATION
            ),
            "exact_rights_attestation_sha256": evidence_inputs[
                str(PBS_UTILISATION_EXACT_RIGHTS_ATTESTATION)
            ],
            "permission_instrument_existence_and_applicability": (
                "maintainer_attested_not_independently_reviewed"
            ),
            "rights_scope_includes_all_file_contents": True,
            "public_release_performed_by_this_reconciliation": False,
            "v4_admission": False,
            "consumer_canary": False,
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
            "rights_exclusion_fully_resolved_by_exact_attestation": True,
            "full_object_release_requires_exclusion_review": False,
            "limited_vocabulary_screen": {
                "path": str(PBS_UTILISATION_LIMITED_SCREEN),
                "sha256": evidence_inputs[str(PBS_UTILISATION_LIMITED_SCREEN)],
                "results": _reconcile_pbs_limited_vocabulary_screen(root)[
                    "results"
                ],
                "rights_exclusion_fully_resolved_by_exact_attestation": True,
                "full_object_release_requires_exclusion_review": False,
            },
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
            "m108_assessment_derived_output_authority": _read(
                root, M108_ASSESSMENT
            )["august_2026_six_table_operation_assessment"]["authorization"][
                "derived_output_authority"
            ],
            "objects": august_mbs_objects,
        },
        "reimbursement_atlas_medallion_projections": {
            "object_count": REIMBURSEMENT_MEDALLION_OBJECT_COUNT,
            "attestation_path": str(REIMBURSEMENT_MEDALLION_RIGHTS_ATTESTATION),
            "attestation_sha256": evidence_inputs[
                str(REIMBURSEMENT_MEDALLION_RIGHTS_ATTESTATION)
            ],
            "rights_state": REIMBURSEMENT_MEDALLION_RIGHTS_STATE,
            "public_redistribution_rights_attested": True,
            "permission_instrument_existence_and_applicability": (
                "maintainer_attested_not_independently_reviewed_or_located_at_maintainer_direction"
            ),
            "public_release_performed": False,
            "v4_admissions": 0,
            "consumer_canaries": 0,
            "objects": reconcile_reimbursement_medallion_attestation(
                objects, _read(root, REIMBURSEMENT_MEDALLION_RIGHTS_ATTESTATION)
            ),
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
            "source_payload_bytes_read": True,
            "source_payload_values_inspected": True,
            "source_payload_values_emitted": False,
            "source_payload_files_written": False,
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
