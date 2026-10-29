"""Reconcile existing hosted MBS utilisation receipts to M-112 candidates.

This binds no v4 contract and performs no admission. It records exact-object
publication and token-free anonymous restore receipts as candidate evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
if __package__:
    from . import qualify_m112_v3_replay
else:
    import qualify_m112_v3_replay

ROLE_REPORT = "quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261019.json"
DIGEST_REPORT = "quality/qualifications/australian-m112-utilisation-digest-reconciliation-20261004.json"
DISCOVERY_REPORT = "quality/qualifications/australian-m112-v4-discovery-role-evidence-20261020.json"
SOURCE_SEMANTICS_REPORT = "quality/qualifications/australian-m112-mbs-group-2016-source-semantics-20261020.json"
PHYSICAL_LAYOUT_REPORT = (
    "quality/qualifications/"
    "australian-mbs-demographics-q1hr-workbook-layout-candidate-20261021.json"
)
OVERLAY_REPORT = (
    "quality/qualifications/"
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "reimbursement-medallion-projection-lineage.json"
)
V3_REPLAY_REPORT = (
    "quality/qualifications/australian-m112-v3-replay-execution-20261020.json"
)
V3_REPLAY_PLAN = (
    "quality/qualifications/australian-m112-v3-replay-plan-20261020.json"
)
V3_REPLAY_MANIFEST = (
    "quality/qualifications/australian-m112-v3-replay-readbacks-20261021.json"
)
SOURCE_SEMANTICS_UNRESOLVED_PATH = (
    "raw/mbs/utilisation/group/mbs-demographics-historical-2013-2015.zip"
)
OUTPUT = "quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261021.json"
DATASET = "edithatogo/australian-mbs-utilisation-archive"
PINNED_REVISION = "dee9a5b0580dfe394474dc26b372559462e157e7"
WORKFLOW_COMMIT = "979f806fcf92267f9595eb78a88707e4ec2e503c"
WORKFLOW_RUN = "36333396964"
PUBLICATION_RECEIPT_URL = "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5857784415"
PUBLICATION_RECEIPT_SHA256 = (
    "6bce093347564588b320f81344c4903c038f4659d5aeb96bca4b2802073c9c1d"
)
VERIFICATION_RECEIPT_URL = "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5857784489"
VERIFICATION_RECEIPT_SHA256 = (
    "5069e57b54a2c3d2aff9901389738998a8944de006505a8f3ac0e02bb4e87a15"
)
EXPECTED_PATHS = 14
EXPECTED_CANDIDATES = 16
EXPECTED_SOURCE_SEMANTICS_OBJECTS = 13
EXPECTED_MANIFEST_FILES = 28
V3_REPLAY_TIMEOUT_MINUTES = 15
APPROVED_DENOMINATOR = 1_759
MIN_V4_RECEIPT_ROLES = 10
OBSERVED_AT = "2026-10-19T16:13:05Z"
ROLE_REPORT_RECORDED_AT = "2026-10-21T09:34:41Z"
CONTRACT_REPOSITORY = "edithatogo/global-medicines-atlas"
CONTRACT_COMMIT = "a5753b1c79ccedd9bb54112bf803882ffc9deb96"
CONTRACT_SCHEMA_PATH = "contracts/medallion/v4.1/federation.schema.json"
CONTRACT_SCHEMA_SHA256 = (
    "03acfbafd80daf0b8b768f7814dbb29a9bd13e7c9d5d68797b30261da29770c6"
)
PRODUCER_WORKFLOW = ".github/workflows/australian-mbs-utilisation-harvest.yml"
SHA256_HEX_LENGTH = 64
SOURCE_SEMANTICS_PATH = "raw/mbs/utilisation/group/mbs-group-2016hr-july.xlsx"
PHYSICAL_LAYOUT_PATH = (
    "raw/mbs/utilisation/demographics/mbs-demographics-2016-qtr1-marchhr.xlsx"
)
V3_REPLAY_PATH = "raw/mbs/utilisation/group/mbs-group-2016hr-july.xlsx"
V3_REPLAY_COMMIT = "dd7a01bcd3da60190f821395ceb1260a3d9ddad9"
V3_REPLAY_RUN_ID = "39289077989"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_compact(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    value: Any = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {relative}")
    return cast("dict[str, Any]", value)


def _verify_local_evidence_reference(
    root: Path, reference: dict[str, Any]
) -> None:
    path = reference.get("path")
    expected = reference.get("sha256")
    if not isinstance(path, str) or not isinstance(expected, str):
        raise TypeError("location digest reference needs path and SHA-256")
    evidence_path = root / path
    if (
        not evidence_path.is_file()
        or _sha256(evidence_path.read_bytes()) != expected
    ):
        raise ValueError(f"location digest evidence does not verify: {path}")


def _receipt_ref(url: str, digest: str) -> dict[str, str]:
    return {"url": url, "sha256": digest}


def _find_archive(archives: list[Any]) -> dict[str, Any]:
    for item_value in archives:
        if not isinstance(item_value, dict):
            continue
        item = cast("dict[str, Any]", item_value)
        if (
            item.get("dataset") == DATASET
            and item.get("revision") == PINNED_REVISION
        ):
            return item
    raise TypeError("exact MBS utilisation archive receipt is missing")


def _verify_archive_receipt(archive: dict[str, Any]) -> dict[str, Any]:
    historical = archive.get("historical_verification_receipt")
    if not isinstance(historical, dict):
        raise TypeError("hosted anonymous restore receipt is missing")
    historical = cast("dict[str, Any]", historical)
    expected: dict[str, Any] = {
        "workflow_run": WORKFLOW_RUN,
        "workflow_commit": WORKFLOW_COMMIT,
        "workflow_conclusion": "success",
        "anonymous_digest_verification": "passed",
        "temporary_source_bytes_removed": True,
        "verified_file_count": EXPECTED_MANIFEST_FILES,
        "issue_comment_body_sha256": VERIFICATION_RECEIPT_SHA256,
    }
    if any(historical.get(key) != value for key, value in expected.items()):
        raise ValueError("hosted publication/restore receipt does not qualify")
    if (
        archive.get("manifest_object_count") != EXPECTED_MANIFEST_FILES
        or archive.get("raw_candidate_object_count") != EXPECTED_PATHS
    ):
        raise ValueError(
            "hosted manifest no longer covers the expected raw cohort"
        )
    return historical


def _manifest_match(item_value: Any, identity: tuple[Any, ...]) -> bool:
    if not isinstance(item_value, dict):
        return False
    item = cast("dict[str, Any]", item_value)
    return (
        item.get("dataset") == identity[0]
        and item.get("revision") == identity[1]
        and item.get("path") == identity[2]
        and item.get("sha256") == identity[3]
        and item.get("byte_count") == identity[4]
        and item.get("matched_hosted_verified_manifest") is True
    )


def _bind_authority_candidate(candidate: dict[str, Any], root: Path) -> None:
    if (
        _sha256((root / CONTRACT_SCHEMA_PATH).read_bytes())
        != CONTRACT_SCHEMA_SHA256
    ):
        raise ValueError("pinned v4.1 schema digest differs from current bytes")
    states_value = candidate.get("contract_role_states")
    if not isinstance(states_value, dict):
        raise TypeError("candidate has no v4 contract role states")
    states = cast("dict[str, Any]", states_value)
    states["authority"] = "candidate_identity_available_unbound"
    candidate["authority_candidate"] = {
        "producer_repository": CONTRACT_REPOSITORY,
        "contract_repository": CONTRACT_REPOSITORY,
        "contract_commit": CONTRACT_COMMIT,
        "schema_path": CONTRACT_SCHEMA_PATH,
        "schema_sha256": CONTRACT_SCHEMA_SHA256,
        "producer_workflow": PRODUCER_WORKFLOW,
        "producer_workflow_commit": WORKFLOW_COMMIT,
        "producer_workflow_run": (
            f"https://github.com/{CONTRACT_REPOSITORY}/actions/runs/{WORKFLOW_RUN}"
        ),
        "contract_role_state": "candidate_identity_available_unbound",
    }


def _bind_candidate(
    candidate: dict[str, Any],
    verified_objects: list[Any],
    archive: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    identity = (
        candidate.get("dataset"),
        candidate.get("revision"),
        candidate.get("path"),
        candidate.get("sha256"),
        candidate.get("bytes"),
    )
    matches: list[dict[str, Any]] = [
        cast("dict[str, Any]", item)
        for item in verified_objects
        if _manifest_match(item, identity)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"candidate has no unique hosted manifest match: {identity[2]}"
        )
    digest_match = matches[0]
    states_value = candidate.get("contract_role_states")
    if not isinstance(states_value, dict):
        raise TypeError("candidate has no v4 contract role states")
    states = cast("dict[str, Any]", states_value)
    states["publication"] = "candidate_receipt_available_unbound"
    states["verification"] = "candidate_receipt_available_unbound"
    candidate["authority_candidate"] = {
        "producer_repository": CONTRACT_REPOSITORY,
        "contract_repository": CONTRACT_REPOSITORY,
        "contract_commit": CONTRACT_COMMIT,
        "schema_path": CONTRACT_SCHEMA_PATH,
        "schema_sha256": CONTRACT_SCHEMA_SHA256,
        "producer_workflow": PRODUCER_WORKFLOW,
        "producer_workflow_commit": WORKFLOW_COMMIT,
        "producer_workflow_run": (
            f"https://github.com/{CONTRACT_REPOSITORY}/actions/runs/{WORKFLOW_RUN}"
        ),
        "contract_role_state": "candidate_identity_available_unbound",
    }
    candidate["publication_candidate_receipt"] = {
        "dataset": DATASET,
        "revision": PINNED_REVISION,
        "path": candidate["path"],
        "bytes": candidate["bytes"],
        "sha256": candidate["sha256"],
        "workflow": ".github/workflows/australian-mbs-utilisation-harvest.yml",
        "workflow_commit": WORKFLOW_COMMIT,
        "workflow_run": f"https://github.com/edithatogo/global-medicines-atlas/actions/runs/{WORKFLOW_RUN}",
        "receipt": _receipt_ref(
            PUBLICATION_RECEIPT_URL, PUBLICATION_RECEIPT_SHA256
        ),
        "manifest": {
            "path": "manifest.json",
            "sha256": archive["manifest_sha256"],
            "file_count": archive["manifest_object_count"],
            "exact_object_match": True,
        },
        "contract_role_state": "candidate_receipt_available_unbound",
    }
    candidate["verification_candidate_receipt"] = {
        "dataset": DATASET,
        "revision": PINNED_REVISION,
        "path": candidate["path"],
        "bytes": candidate["bytes"],
        "sha256": candidate["sha256"],
        "anonymous": True,
        "token_free": True,
        "clean_room": True,
        "status": "passed",
        "verified_at": "2026-09-27T16:44:12Z",
        "receipt": _receipt_ref(
            VERIFICATION_RECEIPT_URL, VERIFICATION_RECEIPT_SHA256
        ),
        "workflow_commit": WORKFLOW_COMMIT,
        "workflow_run": f"https://github.com/edithatogo/global-medicines-atlas/actions/runs/{WORKFLOW_RUN}",
        "verifier": "hf_hub_download(token=False) against exact just-published revision; all 28 manifest objects digest-verified",
        "temporary_source_bytes_removed": True,
        "exact_object_manifest_match": {
            "path": DIGEST_REPORT,
            "sha256": _sha256((root / DIGEST_REPORT).read_bytes()),
            "manifest_match": digest_match["matched_hosted_verified_manifest"],
        },
        "contract_role_state": "candidate_receipt_available_unbound",
    }
    return candidate


def _bind_discovery_candidate(
    candidate: dict[str, Any], discovery: dict[str, Any], root: Path
) -> None:
    identity = {
        key: candidate.get(key)
        for key in ("dataset", "revision", "path", "bytes", "sha256")
    }
    matches = [
        row
        for row_value in cast("list[Any]", discovery.get("objects", []))
        if isinstance(row_value, dict)
        for row in [cast("dict[str, Any]", row_value)]
        if all(row.get(key) == value for key, value in identity.items())
    ]
    if len(matches) != 1:
        raise ValueError(
            f"discovery evidence does not uniquely bind candidate: {candidate.get('path')}"
        )
    datasets = cast("list[Any]", discovery.get("dataset_access", []))
    access = [
        cast("dict[str, Any]", value)
        for value in datasets
        if isinstance(value, dict)
        and cast("dict[str, Any]", value).get("dataset")
        == candidate.get("dataset")
    ]
    if (
        len(access) != 1
        or access[0].get("private") is not False
        or access[0].get("gated") is not False
    ):
        raise ValueError(
            "discovery dataset is not confirmed public and ungated"
        )
    estate_value = discovery.get("estate_registry")
    if not isinstance(estate_value, dict):
        raise TypeError("discovery estate registry is malformed")
    estate_registry = cast("dict[str, Any]", estate_value)
    entries_value = estate_registry.get("entries", [])
    entries = [
        cast("dict[str, Any]", value)
        for value in cast("list[Any]", entries_value)
        if isinstance(value, dict)
        and cast("dict[str, Any]", value).get("repo_id")
        == candidate.get("dataset")
    ]
    if len(entries) != 1 or entries[0].get("access") != "public":
        raise ValueError(
            "public estate entry is missing for discovery candidate"
        )
    if entries[0].get("rights_status") != "source_specific_review_required":
        raise ValueError(
            "estate rights state changed; do not infer a new decision"
        )
    collection_value = discovery.get("collection")
    if not isinstance(collection_value, dict):
        raise TypeError("discovery collection evidence is malformed")
    collection = cast("dict[str, Any]", collection_value)
    if candidate.get("dataset") not in collection.get(
        "matching_dataset_members", []
    ):
        raise ValueError(
            "candidate dataset is absent from the exact collection"
        )
    states_value = candidate.get("contract_role_states")
    if not isinstance(states_value, dict):
        raise TypeError("candidate has no v4 contract role states")
    cast("dict[str, Any]", states_value)["discovery"] = (
        "candidate_receipt_available_unbound"
    )
    candidate["discovery_candidate_receipt"] = {
        "collection": collection.get("url"),
        "collection_response_sha256": collection.get("response_sha256"),
        "estate_entry": {
            "url": estate_registry.get("catalog_url"),
            "sha256": estate_registry.get("catalog_sha256"),
            "dataset": candidate["dataset"],
            "status": entries[0].get("status"),
            "rights_status": entries[0].get("rights_status"),
        },
        "dataset_access_response_sha256": access[0].get("response_sha256"),
        "evidence_report": {
            "path": DISCOVERY_REPORT,
            "sha256": _sha256((root / DISCOVERY_REPORT).read_bytes()),
        },
        "contract_role_state": "candidate_receipt_available_unbound",
    }


def _bind_location_candidate(
    candidate: dict[str, Any], discovery: dict[str, Any], root: Path
) -> None:
    if candidate.get("anonymous_digest_readback") is not True:
        raise ValueError(
            "location candidate lacks exact anonymous digest readback"
        )
    digest_ref = candidate.get("digest_evidence")
    if not isinstance(digest_ref, dict):
        raise TypeError(
            "location candidate lacks its digest evidence reference"
        )
    _verify_local_evidence_reference(root, cast("dict[str, Any]", digest_ref))
    access_rows = cast("list[Any]", discovery.get("dataset_access", []))
    matching_access = [
        cast("dict[str, Any]", item)
        for item in access_rows
        if isinstance(item, dict)
        and cast("dict[str, Any]", item).get("dataset")
        == candidate.get("dataset")
    ]
    if (
        len(matching_access) != 1
        or matching_access[0].get("private") is not False
        or matching_access[0].get("gated") is not False
    ):
        raise ValueError(
            "location repository is not confirmed public and ungated"
        )
    states_value = candidate.get("contract_role_states")
    if not isinstance(states_value, dict):
        raise TypeError("candidate has no v4 contract role states")
    cast("dict[str, Any]", states_value)["location"] = (
        "candidate_receipt_available_unbound"
    )
    candidate["location_candidate_receipt"] = {
        "dataset": candidate["dataset"],
        "revision": candidate["revision"],
        "path": candidate["path"],
        "bytes": candidate["bytes"],
        "sha256": candidate["sha256"],
        "private": False,
        "gated": False,
        "dataset_access_response_sha256": matching_access[0].get(
            "response_sha256"
        ),
        "anonymous_digest_readback": True,
        "digest_evidence": digest_ref,
        "contract_role_state": "candidate_receipt_available_unbound",
    }


def _bind_recovery_candidate(
    candidate: dict[str, Any], archive: dict[str, Any]
) -> None:
    if candidate.get("dataset") != DATASET:
        return
    historical = _verify_archive_receipt(archive)
    states_value = candidate.get("contract_role_states")
    if not isinstance(states_value, dict):
        raise TypeError("candidate has no v4 contract role states")
    cast("dict[str, Any]", states_value)["recovery"] = (
        "candidate_receipt_available_unbound"
    )
    candidate["recovery_candidate_receipt"] = {
        "role": "primary",
        "independent": False,
        "administrative_domain": "huggingface:edithatogo/australian-mbs-utilisation-archive",
        "primary_administrative_domain": "huggingface:edithatogo/australian-mbs-utilisation-archive",
        "region": "unverified",
        "primary_region": "unverified",
        "rpo_seconds": None,
        "rto_seconds": None,
        "checksum_inventory": {
            "url": (
                "https://huggingface.co/datasets/"
                f"{DATASET}/resolve/{PINNED_REVISION}/manifest.json"
            ),
            "sha256": archive["manifest_sha256"],
        },
        "restore_receipt": {
            "url": VERIFICATION_RECEIPT_URL,
            "sha256": historical["issue_comment_body_sha256"],
        },
        "authorization_receipt": None,
        "verified_manifest_object_count": historical["verified_file_count"],
        "temporary_source_bytes_removed": historical[
            "temporary_source_bytes_removed"
        ],
        "contract_role_state": "candidate_receipt_available_unbound",
    }


def _bind_source_semantics_candidate(
    candidate: dict[str, Any], semantics: dict[str, Any], root: Path
) -> None:
    if candidate.get("dataset") != DATASET:
        return
    object_rows_value = semantics.get("objects")
    if not isinstance(object_rows_value, list):
        raise TypeError("source semantics evidence has no object list")
    object_rows = cast("list[Any]", object_rows_value)
    candidate_identity = {
        key: candidate.get(key)
        for key in ("dataset", "revision", "path", "bytes", "sha256")
    }
    matches = [
        cast("dict[str, Any]", row)
        for row in object_rows
        if isinstance(row, dict)
        and all(
            cast("dict[str, Any]", row).get(key) == value
            for key, value in candidate_identity.items()
        )
    ]
    if not matches:
        return
    if len(matches) != 1:
        raise ValueError("source semantics identity is not unique")
    source_row = matches[0]
    if (
        semantics.get("status")
        != "source_temporal_semantics_candidates_available_unbound_schema_layout_unqualified"
        or semantics.get("boundaries", {}).get("raw_source_objects_inspected")
        is not False
    ):
        raise ValueError("source semantics evidence exceeded its stated scope")
    if len(object_rows) != EXPECTED_SOURCE_SEMANTICS_OBJECTS:
        raise ValueError(
            "source semantics evidence does not cover the qualified cohort"
        )
    temporal = source_row.get("temporal_semantics")
    resource = source_row.get("resource")
    metadata = source_row.get("metadata_readback")
    if not isinstance(temporal, dict) or not isinstance(resource, dict):
        raise TypeError("source temporal or resource metadata is missing")
    if not isinstance(metadata, dict):
        raise TypeError("source metadata readback is missing")
    _validate_source_semantics_fields(
        candidate,
        source_row,
        cast("dict[str, Any]", temporal),
        cast("dict[str, Any]", resource),
    )
    response_digest = cast("dict[str, Any]", metadata).get("response_sha256")
    if not isinstance(response_digest, str):
        raise TypeError("source metadata readback digest is missing")
    if not re.fullmatch(
        rf"[0-9a-f]{{{SHA256_HEX_LENGTH}}}",
        response_digest,
    ):
        raise ValueError("source metadata readback digest is malformed")
    states_value = candidate.get("contract_role_states")
    if not isinstance(states_value, dict):
        raise TypeError("candidate has no v4 contract role states")
    cast("dict[str, Any]", states_value)["source"] = (
        "candidate_receipt_available_unbound"
    )
    candidate["source_candidate_receipt"] = {
        "source_id": candidate["source_id"],
        "acquisition_id": candidate["acquisition_id"],
        "layer": "bronze",
        "bronze_stratum": "B2",
        "representation": "raw",
        "schema_era": source_row["schema_era"],
        "comparison_cohort": temporal["cohort"],
        "effective_date": temporal["effective_date"],
        "retrieved_at": source_row["retrieved_at"],
        "temporal_semantics": temporal,
        "source_metadata_readback": {
            "url": metadata["url"],
            "http_status": metadata["http_status"],
            "response_sha256": response_digest,
            "resource_id": cast("dict[str, Any]", resource).get("id"),
            "evidence_report": {
                "path": SOURCE_SEMANTICS_REPORT,
                "sha256": _sha256(
                    (root / SOURCE_SEMANTICS_REPORT).read_bytes()
                ),
            },
        },
        "native_schema_layout_qualified": False,
        "contract_role_state": "candidate_receipt_available_unbound",
    }


def _bind_physical_layout_evidence(
    candidates: list[Any], layout: dict[str, Any], root: Path
) -> int:
    """Bind the Q1 HR physical layout without promoting semantic roles."""
    expected_source = {
        "dataset": DATASET,
        "revision": PINNED_REVISION,
        "path": PHYSICAL_LAYOUT_PATH,
        "byte_count": 21_966_140,
        "sha256": "d44522cbd1847e73ee69cb5374c207296133254cd82be61e751f78db1a456d4d",
    }
    source_value = layout.get("source")
    boundaries_value = layout.get("boundaries")
    qualification_value = layout.get("layout_qualification")
    if not isinstance(source_value, dict):
        raise TypeError("Q1 HR physical-layout evidence source is malformed")
    source = cast("dict[str, Any]", source_value)
    if any(source.get(key) != value for key, value in expected_source.items()):
        raise ValueError("Q1 HR physical-layout evidence identity changed")
    expected_boundaries = {
        "native_workbook_layout_qualified": True,
        "source_field_semantics_qualified": False,
        "formula_semantics_qualified": False,
        "v4_admission_performed": False,
        "consumer_canary_performed": False,
    }
    if not isinstance(boundaries_value, dict):
        raise TypeError("Q1 HR physical-layout boundaries are malformed")
    boundaries = cast("dict[str, Any]", boundaries_value)
    if any(
        boundaries.get(key) is not value
        for key, value in expected_boundaries.items()
    ):
        raise ValueError("Q1 HR physical-layout evidence exceeded its scope")
    if not isinstance(qualification_value, dict):
        raise TypeError("Q1 HR physical-layout qualification is malformed")
    qualification = cast("dict[str, Any]", qualification_value)
    if (
        layout.get("status")
        != "physical_layout_qualified_source_field_semantics_open"
        or qualification.get("state")
        != "qualified_for_exact_pinned_physical_structure"
    ):
        raise ValueError("Q1 HR physical-layout evidence exceeded its scope")

    expected_candidate: dict[str, Any] = {
        "dataset": DATASET,
        "revision": PINNED_REVISION,
        "path": PHYSICAL_LAYOUT_PATH,
        "bytes": 21_966_140,
        "sha256": expected_source["sha256"],
    }
    matches: list[dict[str, Any]] = []
    for candidate_value in candidates:
        if not isinstance(candidate_value, dict):
            continue
        candidate = cast("dict[str, Any]", candidate_value)
        if all(
            candidate.get(key) == value
            for key, value in expected_candidate.items()
        ):
            matches.append(candidate)
    if len(matches) != 1:
        raise ValueError("Q1 HR physical-layout identity is not unique")
    candidate = matches[0]
    candidate["physical_layout_evidence"] = {
        "report": {
            "path": PHYSICAL_LAYOUT_REPORT,
            "sha256": _sha256((root / PHYSICAL_LAYOUT_REPORT).read_bytes()),
        },
        "state": qualification["state"],
        "scope": qualification["scope"],
        "native_workbook_layout_qualified": True,
        "source_field_semantics_qualified": False,
        "formula_semantics_qualified": False,
        "admission_performed": False,
        "consumer_canary_performed": False,
    }
    return len(matches)


def _validate_source_semantics_fields(
    candidate: dict[str, Any],
    source_row: dict[str, Any],
    temporal: dict[str, Any],
    resource: dict[str, Any],
) -> None:
    if (
        temporal.get("effective_date") != temporal.get("period_end")
        or not isinstance(temporal.get("period_end"), str)
        or temporal.get("cohort") != "legacy"
        or temporal.get("service_month_basis")
        != "claim_processing_date_not_service_provision_date"
    ):
        raise ValueError("source temporal semantics do not bind this candidate")
    if (
        source_row.get("source_id") != candidate.get("source_id")
        or source_row.get("acquisition_id") != candidate.get("acquisition_id")
        or source_row.get("retrieved_at") is None
    ):
        raise ValueError("source acquisition identity differs")
    if (
        resource.get("url") is None
        or resource.get("id") is None
        or not str(resource.get("url")).startswith(
            "https://data.gov.au/data/dataset/"
        )
    ):
        raise ValueError("source resource metadata is not exact and public")
    schema_era = source_row.get("schema_era")
    if not isinstance(schema_era, str) or not schema_era.startswith(
        "unqualified-native-schema;"
    ):
        raise ValueError("native schema uncertainty was not preserved")


def _update_summary(
    report: dict[str, Any],
    root: Path,
    matched_count: int,
    v3_replay_count: int,
    admission_count: int,
    consumer_canary_count: int,
) -> None:
    report["cohort"]["publication_candidate_receipts"] = matched_count
    report["cohort"]["verification_candidate_receipts"] = matched_count
    report["observed_hub_revision_metadata"] = {
        "url": f"https://huggingface.co/api/datasets/{DATASET}/revision/{PINNED_REVISION}",
        "dataset": DATASET,
        "revision": PINNED_REVISION,
        "private": False,
        "gated": False,
        "observed_at": OBSERVED_AT,
    }
    for role_value in cast("list[Any]", report.get("roles", [])):
        if not isinstance(role_value, dict):
            continue
        role = cast("dict[str, Any]", role_value)
        if role.get("role") == "authority":
            role["state"] = "candidate_identity_available_unbound_for_16_of_16"
            role["evidence"] = (
                "The successful MBS utilisation producer workflow belongs to "
                "edithatogo/global-medicines-atlas. All 16 candidate objects "
                "now bind the exact v4.1 schema digest and an exact-main commit "
                "containing those schema bytes. The identity remains unbound "
                "until referenced by each complete v4 contract."
            )
        if role.get("role") in {"publication", "verification"}:
            role["state"] = "candidate_receipts_available_unbound_for_14_of_16"
            role["evidence"] = (
                "14 MBS utilisation paths exactly match the 28-object published manifest and token-free anonymous restore receipt; the two August paths lack this receipt. Candidate evidence is not bound to live v4.1 contracts."
            )
        if role.get("role") == "discovery":
            role["state"] = "candidate_receipt_available_unbound_for_16_of_16"
            role["evidence"] = (
                "All 16 exact candidate paths bind to their public dataset entry, "
                "a current collection membership, and the pinned dataset-estate "
                "catalog. The estate entries remain not_assessed and "
                "source_specific_review_required; discovery evidence is not a "
                "rights or admission conclusion."
            )
        if role.get("role") == "location":
            role["state"] = "candidate_receipt_available_unbound_for_16_of_16"
            role["evidence"] = (
                "All 16 exact dataset/revision/path/byte-count/SHA-256 identities "
                "bind to the existing anonymous digest evidence and current public, "
                "ungated repository metadata. The evidence remains unbound until "
                "referenced by each complete v4 contract."
            )
        if role.get("role") == "recovery":
            role["state"] = "candidate_receipts_available_unbound_for_14_of_16"
            role["evidence"] = (
                "The 14 utilisation objects bind to the exact published manifest "
                "and successful token-free 28-object restore receipt. This is a "
                "primary, non-independent recovery role only; region and RPO/RTO "
                "remain unverified or null. Two August source-archive objects "
                "have no such receipt."
            )
        if role.get("role") == "lineage.v3_replay":
            role["state"] = (
                f"candidate_receipts_available_unbound_for_"
                f"{v3_replay_count}_of_16"
            )
            role["evidence"] = (
                f"{v3_replay_count} exact M-112 raw B2 identities have successful, "
                "anonymous, token-free hosted v3 replay receipts with byte-count/"
                "SHA-256 verification and temporary-byte cleanup. They remain "
                "candidate-only and unbound; replay roles for the remaining "
                f"{EXPECTED_CANDIDATES - v3_replay_count} candidates are missing."
            )
        if role.get("role") == "cache":
            role["state"] = (
                f"candidate_cleanup_receipts_available_unbound_for_"
                f"{v3_replay_count}_of_16"
            )
            role["evidence"] = (
                "The exact hosted v3 replay receipts bind a bounded temporary "
                "runner cache, expiry, token-free cleanup, and removal for "
                f"{v3_replay_count} object(s). This is temporary acquisition "
                "cache evidence, not a durable reader cache or consumer claim."
            )
        if role.get("role") == "source":
            role["state"] = "candidate_receipts_available_unbound_for_13_of_16"
            role["evidence"] = (
                "Official data.gov.au resource metadata qualifies reporting "
                "period, processing-month basis, and retrieval identity for 13 "
                "exact MBS utilisation B2 objects. Native workbook/archive schema "
                "layouts remain unqualified. Two August MBS XML objects and one "
                "historical archive with a source-period mismatch remain partial; "
                "the candidate source-role receipts are unbound."
            )
        if role.get("role") == "consumers":
            role["state"] = (
                f"qualified_consumer_canaries_for_{consumer_canary_count}_of_"
                f"{admission_count}_current_admissions"
            )
            role["evidence"] = (
                f"{consumer_canary_count} exact admitted M-112 objects have "
                "successful bounded readbacks through the FederatedReader, "
                "with remote and consumer-stream digest matches and zero "
                "reader-cache bytes after close. This is cumulative receipt "
                "evidence; this candidate-role refresh performed no canary. "
                "Objects outside the admitted cohort remain untested."
            )
    report["authority_identity"] = {
        "producer_repository": CONTRACT_REPOSITORY,
        "contract_repository": CONTRACT_REPOSITORY,
        "contract_commit": CONTRACT_COMMIT,
        "schema_path": CONTRACT_SCHEMA_PATH,
        "schema_sha256": CONTRACT_SCHEMA_SHA256,
        "producer_workflow": PRODUCER_WORKFLOW,
        "producer_workflow_commit": WORKFLOW_COMMIT,
        "producer_workflow_run": (
            f"https://github.com/{CONTRACT_REPOSITORY}/actions/runs/{WORKFLOW_RUN}"
        ),
        "candidate_objects": EXPECTED_CANDIDATES,
        "state": "candidate_identity_available_unbound_for_16_of_16",
    }
    report["decision"] = (
        "The exact v4.1 schema identity and successful producer workflow are "
        "now bound as candidate authority evidence for all 16 MBS utilisation "
        "objects; publication and token-free anonymous restore receipts remain "
        "unbound candidate evidence for 14 of 16 paths. Authority is not yet "
        "referenced by complete v4 contracts. Two August paths, source "
        "semantics, discovery, recovery/cache, and consumers remain "
        "incomplete. Official source temporal semantics are qualified for 13 "
        "utilisation objects; their native schema layouts and three source-role "
        "candidates remain unresolved. Location and discovery evidence now cover all 16 paths but "
        "remain unbound until referenced by complete per-object v4 contracts. "
        f"V3 replay evidence is candidate-only for {v3_replay_count} of 16 "
        "objects. Recovery evidence covers only the 14 utilisation paths; "
        f"hosted cache-cleanup candidates bind {v3_replay_count} of 16 paths. "
        "Consumer cache behavior remains a post-admission check. Current "
        "independently evidenced state is "
        f"{admission_count} v4 admissions and {consumer_canary_count} "
        "admitted-object consumer canaries; this candidate-role refresh "
        "performed no admission or canary."
    )
    report["recorded_at"] = ROLE_REPORT_RECORDED_AT
    report["supersedes"] = {
        "path": ROLE_REPORT,
        "sha256": _sha256((root / ROLE_REPORT).read_bytes()),
    }


def _validate_source_semantics_scope(semantics: dict[str, Any]) -> None:
    object_rows_value = semantics.get("objects")
    unresolved = semantics.get("unresolved")
    if (
        semantics.get("status")
        != "source_temporal_semantics_candidates_available_unbound_schema_layout_unqualified"
        or not isinstance(object_rows_value, list)
        or not isinstance(unresolved, list)
    ):
        raise ValueError("source temporal evidence coverage changed")
    object_rows = cast("list[Any]", object_rows_value)
    unresolved_rows = cast("list[Any]", unresolved)
    if (
        len(object_rows) != EXPECTED_SOURCE_SEMANTICS_OBJECTS
        or len(unresolved_rows) != 1
    ):
        raise ValueError("source temporal evidence coverage changed")
    unresolved_row = unresolved_rows[0]
    if not isinstance(unresolved_row, dict):
        raise TypeError("unresolved source ambiguity record is malformed")
    unresolved_record = cast("dict[str, Any]", unresolved_row)
    if (
        unresolved_record.get("path") != SOURCE_SEMANTICS_UNRESOLVED_PATH
        or unresolved_record.get("state")
        != "source_metadata_period_conflicts_with_resource_name"
        or not _raw_source_inspection_is_false(semantics)
    ):
        raise ValueError("source ambiguity or raw-source boundary changed")


def _raw_source_inspection_is_false(semantics: dict[str, Any]) -> bool:
    boundaries = semantics.get("boundaries")
    return (
        isinstance(boundaries, dict)
        and cast("dict[str, Any]", boundaries).get(
            "raw_source_objects_inspected"
        )
        is False
    )


def _read_v3_replay_section(
    receipt: dict[str, Any], name: str
) -> dict[str, Any]:
    value = receipt.get(name)
    if not isinstance(value, dict):
        raise TypeError("hosted v3 replay receipt sections are malformed")
    return cast("dict[str, Any]", value)


def _validate_v3_replay_receipt(  # ruff: ignore[too-many-locals] -- validate the exact replay artifact closure
    root: Path, entry: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], str, str, str, str]:
    """Verify a manifest entry's exact hosted artifact and deterministic plan."""
    receipt_ref = entry.get("receipt")
    plan_ref = entry.get("plan")
    if not isinstance(receipt_ref, dict) or not isinstance(plan_ref, dict):
        raise TypeError("v3 replay manifest artifact references are malformed")
    receipt_ref = cast("dict[str, Any]", receipt_ref)
    plan_ref = cast("dict[str, Any]", plan_ref)
    receipt_path = receipt_ref.get("path")
    plan_path = plan_ref.get("path")
    if not isinstance(receipt_path, str) or not isinstance(plan_path, str):
        raise TypeError("v3 replay manifest artifact paths are missing")
    if not receipt_path.startswith(
        "quality/qualifications/"
    ) or not plan_path.startswith("quality/qualifications/"):
        raise ValueError(
            "v3 replay artifacts must remain qualification records"
        )
    receipt = _read_json(root, receipt_path)
    plan = _read_json(root, plan_path)
    if _sha256((root / receipt_path).read_bytes()) != receipt_ref.get(
        "sha256"
    ) or _sha256((root / plan_path).read_bytes()) != plan_ref.get("sha256"):
        raise ValueError(
            "v3 replay artifact digest differs from readback manifest"
        )
    scope = _read_v3_replay_section(receipt, "scope")
    workflow = _read_v3_replay_section(receipt, "hosted_workflow")
    replay = _read_v3_replay_section(receipt, "replay")
    verification = _read_v3_replay_section(receipt, "verification")
    boundaries = _read_v3_replay_section(receipt, "boundaries")
    snapshots_value = plan.get("snapshots")
    if not isinstance(snapshots_value, list):
        raise TypeError("v3 replay plan snapshots are malformed")
    snapshots = cast("list[Any]", snapshots_value)
    if len(snapshots) != 1:
        raise ValueError("v3 replay plan no longer identifies one snapshot")
    snapshot_value = snapshots[0]
    if not isinstance(snapshot_value, dict):
        raise TypeError("v3 replay snapshot is malformed")
    snapshot = cast("dict[str, Any]", snapshot_value)
    expected_scope = {
        "dataset": entry.get("dataset"),
        "revision": entry.get("revision"),
        "path": entry.get("path"),
        "sha256": entry.get("sha256"),
        "byte_count": entry.get("bytes"),
    }
    target_path = expected_scope["path"]
    if not isinstance(target_path, str):
        raise TypeError("v3 replay manifest target path is malformed")
    expected_plan = qualify_m112_v3_replay.qualify(
        root, target_path=target_path, allow_existing=True
    )
    if plan != expected_plan:
        raise ValueError(
            "v3 replay plan differs from deterministic qualification"
        )
    run_id = entry.get("run_id")
    expected_url = (
        f"https://github.com/{CONTRACT_REPOSITORY}/actions/runs/{run_id}"
    )
    commit = entry.get("commit")
    registration_value = replay.get("registration")
    if not isinstance(registration_value, dict):
        raise TypeError("v3 replay registration is missing")
    registration = cast("dict[str, Any]", registration_value)
    if not all((
        receipt.get("schema_id")
        == "global-medicines-atlas.m112-v3-replay-execution-receipt",
        receipt.get("status") == "passed",
        receipt.get("candidate_only") is True,
        scope == expected_scope,
        workflow.get("repository") == CONTRACT_REPOSITORY,
        workflow.get("commit") == commit,
        workflow.get("run_id") == run_id,
        workflow.get("run_attempt") == entry.get("attempt"),
        workflow.get("run_url") == expected_url,
        replay.get("vocabulary_version") == "3.0.0",
        replay.get("snapshot_id") == snapshot.get("snapshot_id"),
        replay.get("partition_id") == snapshot.get("partition_id"),
        replay.get("plan_sha256") == _sha256(_canonical_compact(plan)),
        entry.get("status") == "success",
        entry.get("completed_at") is not None,
        entry.get("started_at") is not None,
        isinstance(snapshot.get("partition_value"), str)
        and cast("str", snapshot.get("partition_value")).endswith(
            f":{target_path}"
        ),
        replay.get("registration_sha256")
        == _sha256(_canonical_compact(registration)),
        registration.get("payload_sha256") == expected_scope["sha256"],
        registration.get("byte_count") == expected_scope["byte_count"],
        registration.get("payload_values_read") is False,
    )) or not all((
        verification.get("anonymous") is True,
        verification.get("token_free") is True,
        verification.get("payload_values_read") is False,
        verification.get("temporary_source_bytes_removed") is True,
        boundaries.get("v4_admission_performed") is False,
        boundaries.get("m112_consumer_canary_performed") is False,
        boundaries.get("public_dataset_mutation") is False,
        boundaries.get("source_values_or_rows_included") is False,
    )):
        raise ValueError(
            "hosted v3 replay receipt differs from its pinned plan"
        )
    return (
        replay,
        expected_scope,
        expected_url,
        _sha256((root / receipt_path).read_bytes()),
        receipt_path,
        plan_path,
    )


def _bind_v3_replay_candidate(  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- bind each exact hosted replay receipt
    candidates: list[dict[str, Any]], root: Path
) -> int:
    """Bind each independently verified hosted replay to its frozen object."""
    manifest = _read_json(root, V3_REPLAY_MANIFEST)
    entries_value = manifest.get("entries")
    manifest_scope = manifest.get("scope")
    manifest_boundaries = manifest.get("boundaries")
    if (
        not isinstance(entries_value, list)
        or not isinstance(manifest_scope, dict)
        or not isinstance(manifest_boundaries, dict)
    ):
        raise TypeError("v3 replay readback manifest sections are malformed")
    entries_value = cast("list[Any]", entries_value)
    manifest_scope = cast("dict[str, Any]", manifest_scope)
    manifest_boundaries = cast("dict[str, Any]", manifest_boundaries)
    if not all((
        manifest.get("schema_id")
        == "global-medicines-atlas.m112-v3-replay-readback-manifest",
        manifest.get("status") == "successful_exact_hosted_v3_replay_readbacks",
        manifest_scope.get("approved_denominator") == APPROVED_DENOMINATOR,
        manifest_scope.get("v4_admissions_added") == 0,
        manifest_scope.get("consumer_canaries_added") == 0,
        manifest_boundaries.get("public_dataset_mutated") is False,
        manifest_boundaries.get("source_values_or_rows_read") is False,
        manifest_boundaries.get("temporary_source_bytes_removed") is True,
    )):
        raise ValueError("v3 replay readback manifest is not qualified")
    entries = entries_value
    if len(entries) != manifest.get("scope", {}).get("replay_objects"):
        raise ValueError("v3 replay manifest object count is inconsistent")
    # Verify every referenced byte digest first. This prevents later plan
    # reconstruction from obscuring a tampered hosted receipt with an
    # unrelated unavailable local lineage input.
    for entry_value in entries:
        if not isinstance(entry_value, dict):
            raise TypeError("v3 replay manifest entry is malformed")
        entry_value = cast("dict[str, Any]", entry_value)
        for role in ("receipt", "plan"):
            reference = entry_value.get(role)
            if not isinstance(reference, dict):
                raise TypeError(
                    "v3 replay manifest artifact reference is malformed"
                )
            reference = cast("dict[str, Any]", reference)
            relative = reference.get("path")
            expected_sha256 = reference.get("sha256")
            if (
                not isinstance(relative, str)
                or not relative.startswith("quality/qualifications/")
                or ".." in Path(relative).parts
                or not isinstance(expected_sha256, str)
                or _sha256((root / relative).read_bytes()) != expected_sha256
            ):
                raise ValueError(
                    "v3 replay artifact digest differs from readback manifest"
                )
    seen: set[tuple[Any, ...]] = set()
    for entry_value in entries:
        if not isinstance(entry_value, dict):
            raise TypeError("v3 replay manifest entry is malformed")
        entry = cast("dict[str, Any]", entry_value)
        (
            replay,
            expected_scope,
            expected_url,
            receipt_sha256,
            receipt_path,
            plan_path,
        ) = _validate_v3_replay_receipt(root, entry)
        identity = tuple(
            expected_scope.get(key)
            for key in ("dataset", "revision", "path", "sha256", "byte_count")
        )
        if identity in seen:
            raise ValueError("v3 replay manifest repeats an object identity")
        seen.add(identity)
        matched = [
            candidate
            for candidate in candidates
            if tuple(
                candidate.get(key)
                for key in ("dataset", "revision", "path", "sha256", "bytes")
            )
            == identity
        ]
        if len(matched) != 1:
            raise ValueError(
                "v3 replay receipt does not bind one frozen M-112 object"
            )
        candidate = matched[0]
        states_value = candidate.get("contract_role_states")
        if not isinstance(states_value, dict):
            raise TypeError("v3 replay candidate lacks contract role states")
        states = cast("dict[str, Any]", states_value)
        if states.get("lineage.v3_replay") != "missing":
            raise ValueError(
                "v3 replay role state changed before receipt binding"
            )
        states["lineage.v3_replay"] = "candidate_receipt_available_unbound"
        candidate["v3_replay_candidate_receipt"] = {
            "candidate_only": True,
            "contract_role_state": "candidate_receipt_available_unbound",
            "receipt": {"path": receipt_path, "sha256": receipt_sha256},
            "plan": {
                "path": plan_path,
                "sha256": _sha256((root / plan_path).read_bytes()),
            },
            "snapshot_id": replay["snapshot_id"],
            "partition_id": replay["partition_id"],
            "registration_sha256": replay["registration_sha256"],
            "workflow_commit": entry["commit"],
            "workflow_run": expected_url,
            "anonymous_digest_verified": True,
            "temporary_source_bytes_removed": True,
        }
        started_at = datetime.fromisoformat(
            cast("str", entry.get("started_at"))
        )
        expires_at = started_at + timedelta(minutes=V3_REPLAY_TIMEOUT_MINUTES)
        states["cache"] = "candidate_receipt_available_unbound"
        candidate["cache_candidate_receipt"] = {
            "origin": "github_actions",
            "state": "removed",
            "max_bytes": entry["bytes"],
            "created_at": started_at
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "expires_at": expires_at
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "cleanup_receipt": {
                "path": receipt_path,
                "sha256": receipt_sha256,
            },
            "offline_behavior": "fail_closed",
            "contract_role_state": "candidate_receipt_available_unbound",
        }
    return len(seen)


def _current_admission_evidence(  # ruff: ignore[too-many-branches,too-many-statements,too-many-locals] -- verify and count exact per-object admission receipts
    root: Path,
) -> tuple[int, int, list[dict[str, Any]]]:
    """Count only exact contract identities with durable admission reports."""
    qualification_dir = root / "quality/qualifications"
    contracts: dict[str, tuple[str, dict[str, Any]]] = {}
    for contract_path in sorted(
        qualification_dir.glob("australian-m112-v4-*-raw-b2-contract.json")
    ):
        raw = contract_path.read_bytes()
        contract = json.loads(raw)
        if not isinstance(contract, dict):
            raise TypeError("M-112 v4 contract must be a JSON object")
        contract = cast("dict[str, Any]", contract)
        digest = _sha256(raw)
        location = contract.get("location")
        if not isinstance(location, dict):
            raise TypeError("M-112 v4 contract location must be an object")
        if contract.get("evidence_kind") != "live":
            continue
        contracts[digest] = (
            contract_path.relative_to(root).as_posix(),
            contract,
        )

    admitted: dict[str, dict[str, Any]] = {}
    canaried: dict[str, dict[str, Any]] = {}
    report_paths = sorted(
        set(
            qualification_dir.glob(
                "australian-m112-v4-*-consumer-canary-*.json"
            )
        )
        | set(
            qualification_dir.glob(
                "australian-m112-v4-*-admission-qualification-*.json"
            )
        )
    )
    for report_path in report_paths:
        report = json.loads(report_path.read_bytes())
        if not isinstance(report, dict):
            raise TypeError("M-112 v4 consumer qualification must be an object")
        report = cast("dict[str, Any]", report)
        contract_path_value = report.get("contract_path")
        expected_digest = report.get("contract_sha256")
        admission = report.get("admission")
        if (
            report.get("schema_id")
            != "global-medicines-atlas.m112-v4-admission-qualification"
            or report.get("status")
            not in {
                "admitted_with_consumer_canary",
                "admitted_pending_consumer_canary",
            }
            or not isinstance(contract_path_value, str)
            or not isinstance(expected_digest, str)
            or not isinstance(admission, dict)
        ):
            continue
        admission = cast("dict[str, Any]", admission)
        contract_path = root / contract_path_value
        if not contract_path.is_file():
            raise ValueError(
                "admission report references a missing v4 contract"
            )
        actual_digest = _sha256(contract_path.read_bytes())
        if actual_digest != expected_digest or actual_digest not in contracts:
            raise ValueError(
                "admission report does not bind an exact local contract"
            )
        contract_relative, contract = contracts[actual_digest]
        location = cast("dict[str, Any]", contract["location"])
        closure = report.get("receipt_closure")
        if not isinstance(closure, dict):
            raise TypeError("admission receipt closure must be an object")
        closure = cast("dict[str, Any]", closure)
        receipt_roles = closure.get("roles")
        receipt_payloads = closure.get("receipts")
        if not isinstance(receipt_roles, list) or not isinstance(
            receipt_payloads, list
        ):
            raise TypeError("admission receipt closure arrays are malformed")
        receipt_roles = cast("list[Any]", receipt_roles)
        receipt_payloads = cast("list[Any]", receipt_payloads)
        if not all((
            report.get("approved_denominator") == APPROVED_DENOMINATOR,
            report.get("admissions") == 1,
            report.get("consumer_canaries") in {0, 1},
            closure.get("contract_sha256") == actual_digest,
            len(receipt_roles) >= MIN_V4_RECEIPT_ROLES,
            bool(receipt_payloads),
            admission.get("contract_sha256") == actual_digest,
            admission.get("dataset") == location.get("dataset"),
            admission.get("revision") == location.get("revision"),
            admission.get("path") == location.get("path"),
            admission.get("sha256") == location.get("sha256"),
            admission.get("byte_count") == location.get("bytes"),
        )):
            raise ValueError(
                "independent admission identity differs from contract"
            )
        admitted[actual_digest] = {
            "contract_path": contract_relative,
            "contract_sha256": actual_digest,
            "dataset": location.get("dataset"),
            "revision": location.get("revision"),
            "path": location.get("path"),
            "sha256": location.get("sha256"),
        }
        canary = report.get("consumer_canary")
        if canary is None:
            continue
        if not isinstance(canary, dict):
            raise TypeError("consumer canary record is malformed")
        canary = cast("dict[str, Any]", canary)
        canary_identity = canary.get("object")
        boundaries = canary.get("boundaries")
        verification = canary.get("verification")
        if (
            not isinstance(canary_identity, dict)
            or not isinstance(boundaries, dict)
            or not isinstance(verification, dict)
        ):
            raise TypeError(
                "consumer canary identity, boundaries, or verification are malformed"
            )
        canary_identity = cast("dict[str, Any]", canary_identity)
        boundaries = cast("dict[str, Any]", boundaries)
        verification = cast("dict[str, Any]", verification)
        consumer = canary.get("consumer")
        workflow = canary.get("hosted_workflow")
        if not isinstance(consumer, dict) or not isinstance(workflow, dict):
            raise TypeError("consumer canary provenance is malformed")
        consumer = cast("dict[str, Any]", consumer)
        workflow = cast("dict[str, Any]", workflow)
        workflow_run_id = workflow.get("run_id")
        if not all((
            consumer.get("repository") == CONTRACT_REPOSITORY,
            consumer.get("module")
            == "global_medicines_atlas.federation_reader.FederatedReader",
            consumer.get("binding_module")
            == "global_medicines_atlas.federation_consumer.bind_consumer_contract",
            isinstance(consumer.get("commit"), str),
            workflow.get("repository") == CONTRACT_REPOSITORY,
            workflow.get("commit") == consumer.get("commit"),
            isinstance(workflow_run_id, int) and workflow_run_id > 0,
            workflow.get("run_url")
            == (
                f"https://github.com/{CONTRACT_REPOSITORY}/actions/runs/"
                f"{workflow_run_id}"
            ),
            canary.get("status") == "passed",
            canary.get("contract_sha256") == actual_digest,
            canary_identity.get("dataset") == location.get("dataset"),
            canary_identity.get("revision") == location.get("revision"),
            canary_identity.get("path") == location.get("path"),
            canary_identity.get("sha256") == location.get("sha256"),
            canary_identity.get("bytes") == location.get("bytes"),
            boundaries.get("admission_used") is True,
            boundaries.get("source_values_or_rows_included") is False,
            boundaries.get("public_dataset_mutated") is False,
            boundaries.get("source_payload_bytes_retained") is False,
            verification.get("source_values_or_rows_interpreted") is False,
            verification.get("origin") == "remote",
            verification.get("remote_digest_match") is True,
            verification.get("consumer_stream_digest_match") is True,
            verification.get("reader_cache_bytes_after_close") == 0,
        )):
            raise ValueError(
                "consumer canary does not verify the admitted identity"
            )
        canaried[actual_digest] = admitted[actual_digest]

    return len(admitted), len(canaried), list(admitted.values())


def _bind_candidates(
    candidates: list[Any],
    discovery: dict[str, Any],
    source_semantics: dict[str, Any],
    verified_objects: list[Any],
    archive: dict[str, Any],
    root: Path,
) -> tuple[list[dict[str, Any]], int]:
    matched: list[dict[str, Any]] = []
    for candidate_value in candidates:
        if not isinstance(candidate_value, dict):
            raise TypeError("malformed M-112 candidate")
        candidate = cast("dict[str, Any]", candidate_value)
        _bind_authority_candidate(candidate, root)
        _bind_discovery_candidate(candidate, discovery, root)
        _bind_location_candidate(candidate, discovery, root)
        _bind_source_semantics_candidate(candidate, source_semantics, root)
        if candidate.get("dataset") == DATASET:
            bound = _bind_candidate(candidate, verified_objects, archive, root)
            _bind_recovery_candidate(bound, archive)
            matched.append(bound)
    source_count = sum(
        "source_candidate_receipt" in cast("dict[str, Any]", item)
        for item in candidates
    )
    if source_count != EXPECTED_SOURCE_SEMANTICS_OBJECTS:
        raise ValueError(
            "source semantics did not bind the exact 13-object cohort"
        )
    return matched, source_count


def qualify(root: Path = ROOT) -> dict[str, Any]:  # ruff: ignore[too-many-locals] -- reconcile bounded evidence sets
    """Return a deterministic role report enriched with bound candidate receipts."""
    report = copy.deepcopy(_read_json(root, ROLE_REPORT))
    report["source_qualification"] = {
        "path": OVERLAY_REPORT,
        "sha256": _sha256((root / OVERLAY_REPORT).read_bytes()),
    }
    digest_report = _read_json(root, DIGEST_REPORT)
    discovery_report = _read_json(root, DISCOVERY_REPORT)
    source_semantics = _read_json(root, SOURCE_SEMANTICS_REPORT)
    physical_layout = _read_json(root, PHYSICAL_LAYOUT_REPORT)
    candidates = report.get("objects")
    verified_objects = digest_report.get("verified_objects")
    archives = digest_report.get("archives")
    if not isinstance(candidates, list):
        raise TypeError("M-112 role report has no object list")
    candidate_values = cast("list[Any]", candidates)
    if len(candidate_values) != EXPECTED_CANDIDATES:
        raise ValueError("the frozen 16-object exact-rights MBS cohort changed")
    if (
        report.get("cohort", {}).get("approved_denominator")
        != APPROVED_DENOMINATOR
    ):
        raise ValueError("M-112 approved denominator changed")
    _validate_source_semantics_scope(source_semantics)
    if not isinstance(verified_objects, list) or not isinstance(archives, list):
        raise TypeError("digest reconciliation is incomplete")
    physical_layout_count = _bind_physical_layout_evidence(
        candidate_values, physical_layout, root
    )
    if (
        discovery_report.get("scope", {}).get("candidate_objects")
        != EXPECTED_CANDIDATES
        or discovery_report.get("scope", {}).get("discovery_objects")
        != EXPECTED_CANDIDATES
        or discovery_report.get("role_state")
        != "candidate_evidence_available_unbound_for_16_of_16"
    ):
        raise ValueError(
            "M-112 discovery evidence does not cover the frozen cohort"
        )

    verified_values = cast("list[Any]", verified_objects)
    archive = _find_archive(cast("list[Any]", archives))
    _verify_archive_receipt(archive)
    if archive.get("public") is not True or archive.get("gated") is not False:
        raise ValueError("pinned MBS archive is not public and ungated")

    matched, source_bound_count = _bind_candidates(
        candidate_values,
        discovery_report,
        source_semantics,
        verified_values,
        archive,
        root,
    )

    if len(matched) != EXPECTED_PATHS:
        raise ValueError(
            f"expected {EXPECTED_PATHS} MBS utilisation candidates, got {len(matched)}"
        )
    v3_replay_count = _bind_v3_replay_candidate(matched, root)
    admission_count, consumer_canary_count, admitted_objects = (
        _current_admission_evidence(root)
    )
    report["cohort"]["v4_admissions"] = admission_count
    report["cohort"]["consumer_canaries"] = consumer_canary_count
    report["current_admission_evidence"] = admitted_objects
    report["discovery_candidate_evidence"] = {
        "path": DISCOVERY_REPORT,
        "sha256": _sha256((root / DISCOVERY_REPORT).read_bytes()),
        "objects": EXPECTED_CANDIDATES,
        "state": "candidate_receipt_available_unbound_for_16_of_16",
    }
    report["source_semantics_candidate_evidence"] = {
        "path": SOURCE_SEMANTICS_REPORT,
        "sha256": _sha256((root / SOURCE_SEMANTICS_REPORT).read_bytes()),
        "objects": source_bound_count,
        "state": "candidate_receipts_available_unbound_for_13_of_16",
        "native_schema_layout_qualified": False,
    }
    report["physical_layout_candidate_evidence"] = {
        "path": PHYSICAL_LAYOUT_REPORT,
        "sha256": _sha256((root / PHYSICAL_LAYOUT_REPORT).read_bytes()),
        "objects": physical_layout_count,
        "state": "qualified_for_exact_pinned_physical_structure",
        "source_field_semantics_qualified": False,
        "formula_semantics_qualified": False,
    }
    report["location_candidate_evidence"] = {
        "objects": EXPECTED_CANDIDATES,
        "state": "candidate_receipt_available_unbound_for_16_of_16",
    }
    report["recovery_candidate_evidence"] = {
        "objects": len(matched),
        "state": "candidate_receipts_available_unbound_for_14_of_16",
    }
    report["v3_replay_candidate_evidence"] = {
        "path": V3_REPLAY_MANIFEST,
        "sha256": _sha256((root / V3_REPLAY_MANIFEST).read_bytes()),
        "objects": v3_replay_count,
        "state": (
            f"candidate_receipts_available_unbound_for_{v3_replay_count}_of_16"
        ),
    }
    report["cache_candidate_evidence"] = {
        "objects": v3_replay_count,
        "state": (
            f"candidate_cleanup_receipts_available_unbound_for_"
            f"{v3_replay_count}_of_16"
        ),
    }
    _update_summary(
        report,
        root,
        len(matched),
        v3_replay_count,
        admission_count,
        consumer_canary_count,
    )
    return report


def _canonical_bytes(report: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            report, ensure_ascii=False, sort_keys=True, indent=2
        ).encode()
        + b"\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = _canonical_bytes(qualify())
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != expected:
            raise SystemExit(
                f"M-112 v4 role receipt report is stale: {args.output}"
            )
        print(
            f"M-112 v4 receipt reconciliation passed: {EXPECTED_PATHS} "
            f"publication/restore and {qualify()['v3_replay_candidate_evidence']['objects']} "
            "v3 replay candidate bindings"
        )
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(expected)
    print(f"wrote {args.output} sha256={_sha256(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
