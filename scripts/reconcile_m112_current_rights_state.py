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

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
FROZEN_OVERLAY = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "july-mbs-silver-rights-attested.json"
)
CMS_REVIEW = QUAL / "cms-hcpcs-rights-review-20261019.json"
MBS_RIGHTS_ATTESTATION = QUAL / (
    "australian-mbs-v4-public-release-rights-attestation-20261019.json"
)
M108_ASSESSMENT = QUAL / "australian-m108-derived-products-20261017.json"
OUTPUT = QUAL / "australian-m112-current-rights-reconciliation-20261019.json"

MBS_SILVER_PREFIX = "silver/mbs/v4/2025-07-v3/"
AUGUST_BRONZE_PREFIX = "bronze/mbs/releases/2026-08-01/"
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


def _reconcile_object_rights(objects: list[dict[str, Any]]) -> dict[str, Any]:
    paths = [obj["path"] for obj in objects]
    if len(objects) != FROZEN_OBJECT_COUNT or len(set(paths)) != len(paths):
        raise ValueError(
            "frozen M-112 membership is not the approved 1,759 paths"
        )
    groups = Counter(
        (
            obj["dataset"],
            obj["candidate_class"],
            obj["rights"]["state"],
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
            obj["rights"]["state"] in RIGHTS_RESOLVED_STATES
            and obj["rights"]["decision_evidence"] is not None
            for obj in objects
        ),
    }


def build_report(root: Path, *, observed_at: str) -> dict[str, Any]:
    overlay = _read(root, FROZEN_OVERLAY)
    review = _read(root, CMS_REVIEW)
    mbs_attestation = _read(root, MBS_RIGHTS_ATTESTATION)
    m108 = _read(root, M108_ASSESSMENT)
    objects = overlay["objects"]
    rights_summary = _reconcile_object_rights(objects)
    unresolved_count = FROZEN_OBJECT_COUNT - rights_summary["resolved_count"]

    mbs_silver = [
        obj for obj in objects if obj["path"].startswith(MBS_SILVER_PREFIX)
    ]
    if len(mbs_silver) != MBS_SILVER_OBJECT_COUNT or any(
        obj["rights"]["state"]
        != "maintainer_attested_exact_public_release_permission_for_silver_object"
        for obj in mbs_silver
    ):
        raise ValueError(
            "the exact six-object MBS Silver attestation did not reconcile"
        )
    authorized_identities = {
        item["path"]: (item["sha256"], item["byte_count"])
        for item in mbs_attestation["authorized_objects"]
    }
    if (
        not mbs_attestation["public_release_authorized"]
        or len(authorized_identities) != MBS_SILVER_OBJECT_COUNT
    ):
        raise ValueError(
            "the exact six-object MBS rights attestation is incomplete"
        )
    for obj in mbs_silver:
        if obj["rights"]["decision_evidence"]["sha256"] != _sha256(
            root / MBS_RIGHTS_ATTESTATION
        ):
            raise ValueError(
                f"MBS Silver rights evidence mismatch: {obj['path']}"
            )
        if authorized_identities.get(obj["path"]) != (
            obj["identity"]["sha256"],
            obj["identity"]["byte_count"],
        ):
            raise ValueError(
                f"MBS Silver attestation identity mismatch: {obj['path']}"
            )

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

    cms_reference, cms_evidence_inputs = _reconcile_cms(root, review)

    evidence_inputs = {
        str(FROZEN_OVERLAY): _sha256(root / FROZEN_OVERLAY),
        **cms_evidence_inputs,
        str(MBS_RIGHTS_ATTESTATION): _sha256(root / MBS_RIGHTS_ATTESTATION),
        str(M108_ASSESSMENT): _sha256(root / M108_ASSESSMENT),
    }

    return {
        "schema_id": "global-medicines-atlas.australian-m112-current-rights-reconciliation",
        "schema_version": 1,
        "observed_at": observed_at,
        "purpose": "Reconcile effective rights evidence after the exact MBS Silver attestation and CMS HCPCS rights decision without changing object membership or release state.",
        "frozen_inventory": {
            "path": str(FROZEN_OVERLAY),
            "sha256": evidence_inputs[str(FROZEN_OVERLAY)],
            "membership_sha256": overlay["approved_path_membership_sha256"],
            "object_count": len(objects),
            "raw_paths": overlay["scope"]["approved_raw_paths"],
            "projection_paths": overlay["scope"]["approved_projection_paths"],
            "membership_changed": False,
        },
        "effective_m112_rights": {
            "resolved_object_count": rights_summary["resolved_count"],
            "unresolved_object_count": unresolved_count,
            "state_counts": rights_summary["counts"],
            "rights_evidence_does_not_imply_admission": True,
        },
        "exact_july_2025_mbs_silver": {
            "object_count": len(mbs_silver),
            "attestation_path": str(MBS_RIGHTS_ATTESTATION),
            "attestation_sha256": evidence_inputs[str(MBS_RIGHTS_ATTESTATION)],
            "rights_state": "maintainer_attested_exact_public_release_permission_for_silver_object",
            "public_release_authorized": mbs_attestation[
                "public_release_authorized"
            ],
            "public_release_performed": mbs_attestation[
                "public_release_performed"
            ],
            "paths": [
                {
                    "path": obj["path"],
                    "sha256": obj["identity"]["sha256"],
                    "byte_count": obj["identity"]["byte_count"],
                }
                for obj in sorted(mbs_silver, key=itemgetter("path"))
            ],
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
            "external_publication_performed": mbs_attestation[
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
