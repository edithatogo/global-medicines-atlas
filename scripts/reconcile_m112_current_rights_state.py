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
PBS_UTILISATION_AUTHORIZATION = (
    QUAL / "australian-pbs-utilisation-publication-authorization.json"
)
PBS_UTILISATION_LINEAGE = (
    QUAL / "australian-pbs-utilisation-landed-lineage-20261019.json"
)
M108_ASSESSMENT = QUAL / "australian-m108-derived-products-20261017.json"
OUTPUT = QUAL / "australian-m112-current-rights-reconciliation-20261019.json"

MBS_SILVER_PREFIX = "silver/mbs/v4/2025-07-v3/"
AUGUST_BRONZE_PREFIX = "bronze/mbs/releases/2026-08-01/"
PBS_UTILISATION_DATASET = "edithatogo/australian-pbs-utilisation-archive"
PBS_UTILISATION_RIGHTS_STATE = "maintainer_attested_dataset_publication_permission_with_vocabulary_exclusion"
PBS_UTILISATION_OBJECT_COUNT = 6
CMS_SOURCE_ID = "us_cms_hcpcs_level_ii"
CMS_SOURCE_VERSION = "us_cms_hcpcs_level_ii_2026_07"
CMS_SHA256 = "5591fed257e4d2307c1d2dc9c66abc8e346b1f4c076e9e48559799e2de14b70a"
FROZEN_OBJECT_COUNT = 1759
MBS_SILVER_OBJECT_COUNT = 6
AUGUST_PROJECTION_COUNT = 4
RIGHTS_RESOLVED_STATES = {
    "authorized_exact_source_release_permitted",
    "approved_exact_scope_CC_BY_3_0_AU_publicly_readback_verified",
    "maintainer_attested_exact_public_release_permission_for_silver_object",
    PBS_UTILISATION_RIGHTS_STATE,
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
    objects: list[dict[str, Any]], attestation: dict[str, Any]
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
    return {
        "object_count": len(silver_objects),
        "paths": sorted(paths, key=itemgetter("path")),
        "public_release_authorized": attestation["public_release_authorized"],
        "public_release_performed": attestation["public_release_performed"],
    }


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
        objects, _read(root, MBS_RIGHTS_ATTESTATION)
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
    rights_summary = _reconcile_object_rights(objects, rights_overrides)
    unresolved_count = FROZEN_OBJECT_COUNT - rights_summary["resolved_count"]

    august_bronze = [
        obj
        for obj in objects
        if obj["path"].startswith(AUGUST_BRONZE_PREFIX)
        and obj["candidate_class"] == "existing_data_projection"
    ]
    if len(august_bronze) != AUGUST_PROJECTION_COUNT:
        raise ValueError(
            "the four frozen August Bronze projections did not reconcile"
        )

    cms_reference, cms_evidence_inputs = _reconcile_cms(
        root, _read(root, CMS_REVIEW)
    )

    evidence_inputs = {
        str(FROZEN_OVERLAY): _sha256(root / FROZEN_OVERLAY),
        **cms_evidence_inputs,
        str(MBS_RIGHTS_ATTESTATION): _sha256(root / MBS_RIGHTS_ATTESTATION),
        **pbs_rights_evidence_inputs,
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
            "unresolved_object_count": unresolved_count,
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
        "august_2026_mbs_bronze_projections": {
            "object_count": len(august_bronze),
            "rights_state": "underlying source authorization exists; no projection rights conclusion added",
            "derived_output_authority": m108[
                "august_2026_six_table_operation_assessment"
            ]["authorization"]["derived_output_authority"],
            "objects": [
                {
                    "path": obj["path"],
                    "sha256": obj["identity"]["sha256"],
                    "byte_count": obj["identity"]["byte_count"],
                    "rights_state": obj["rights"]["state"],
                    "lineage_complete": obj["b1_b2_lineage"]["complete"],
                }
                for obj in sorted(august_bronze, key=itemgetter("path"))
            ],
        },
        "cms_hcpcs_external_reference": cms_reference,
        "boundaries": {
            "m112_denominator_changed": False,
            "all_1759_deferrals_preserved": True,
            "v4_admissions": overlay["updated_gate_totals"]["v4_admissions"],
            "consumer_canaries": overlay["updated_gate_totals"][
                "consumer_canaries"
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
