"""Reconcile each pinned PBS native field to one bounded meaning state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from global_medicines_atlas.pbs_domain_field_semantics import (
    qualify_pbs_domain_fields,
)
from global_medicines_atlas.pbs_observed_domain import load_observed_profile

PACKAGE = (
    "quality/qualifications/"
    "pbs-native-value-package-v2-20261022-39721534876.json"
)
SCREEN = (
    "quality/qualifications/"
    "pbs-native-reference-screen-20261022-39730665004.json"
)
DOMAIN = "quality/qualifications/pbs-domain-field-semantics-20261023.json"
FIELD_STATE = (
    "quality/qualifications/pbs-native-silver-field-state-20261023.json"
)
REFERENCE_REVIEW = (
    "quality/qualifications/pbs-native-reference-meaning-review-20261023.json"
)
PACKAGE_SHA256 = (
    "769a1d88ab52d6ed9ab08d07ce7d7b433dd7f9034e6b501ad30198a9b6e59202"
)
SCREEN_SHA256 = (
    "a1adda4e946365b98bf3febc03b9ae51acdae6db1569c7fc6606f8892c7ae48e"
)
FIELD_STATE_SHA256 = (
    "2f35eebe45c0326dc80e76c461b0a8af23585923479cec8b74dcb9de5019120d"
)
REFERENCE_REVIEW_SHA256 = (
    "545bda85c569705ab0ca90e3e49b434a4c07be9c30baac1d0e3878c8a9aef054"
)
DOMAIN_REPORT_SHA256 = (
    "6999155565770f6112385705ba22b6b819db51508d352b3d16330ec8077c8a72"
)
SOURCE_FIELDS = 18_208_758
SOURCE_PATHS = 5_163
PATH_INVENTORY = (
    "quality/qualifications/pbs-schema-paths-20261022-39667604237.json"
)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entity_path(schema_path: str) -> str:
    if "/attributes/" in schema_path:
        return schema_path.split("/attributes/", maxsplit=1)[0]
    if schema_path.endswith(("/text", "/tail")):
        return schema_path.rsplit("/", maxsplit=1)[0]
    raise ValueError("PBS schema path does not identify a native field")


def reconcile_pbs_field_states(root: Path) -> dict[str, Any]:  # ruff: ignore[too-many-locals, too-many-statements] -- exact receipt bindings and path-level partition are auditable together
    """Assign every field occurrence once; retain unqualified values as native."""
    package_path = root / PACKAGE
    screen_path = root / SCREEN
    field_state_path = root / FIELD_STATE
    reference_review_path = root / REFERENCE_REVIEW
    domain_path = root / DOMAIN
    package_sha = _file_sha256(package_path)
    screen_sha = _file_sha256(screen_path)
    field_state_sha = _file_sha256(field_state_path)
    reference_review_sha = _file_sha256(reference_review_path)
    if (
        package_sha != PACKAGE_SHA256
        or screen_sha != SCREEN_SHA256
        or field_state_sha != FIELD_STATE_SHA256
        or reference_review_sha != REFERENCE_REVIEW_SHA256
    ):
        raise ValueError("PBS field evidence receipt digest differs")
    native = json.loads(field_state_path.read_bytes())
    if (
        native["status"] != "passed"
        or native["field_state_coverage"]["source_fields"] != SOURCE_FIELDS
        or native["package_receipt_sha256"] != package_sha
        or native["screen_receipt_sha256"] != screen_sha
    ):
        raise ValueError("PBS native field-state receipt differs")

    domain_envelope = json.loads(domain_path.read_bytes())
    domain_report = domain_envelope["report"]
    canonical = json.dumps(
        domain_report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if (
        hashlib.sha256(canonical).hexdigest()
        != domain_envelope["report_sha256"]
        or domain_envelope["report_sha256"] != DOMAIN_REPORT_SHA256
    ):
        raise ValueError("PBS field-meaning evidence digest differs")
    if qualify_pbs_domain_fields(root) != domain_report:
        raise ValueError(
            "PBS field-meaning report differs from its source evidence"
        )

    reference_envelope = json.loads(reference_review_path.read_bytes())
    reference_review = reference_envelope["report"]
    reference_canonical = json.dumps(
        reference_review,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if (
        hashlib.sha256(reference_canonical).hexdigest()
        != reference_envelope["report_sha256"]
        or reference_review["source"]["member_sha256"]
        != domain_report["source"]["member_sha256"]
        or reference_review["source"]["native_digest"]
        != domain_report["source"]["native_digest"]
        or reference_review["source"]["native_fields"] != SOURCE_FIELDS
        or reference_review["scope"]["semantic_relationships_qualified"]
        is not False
    ):
        raise ValueError("PBS source-local reference review differs")

    observed_path = (
        root
        / "quality/qualifications/pbs-observed-domain-values-qualification-20261022-39672588063.json"
    )
    observed_envelope = json.loads(observed_path.read_bytes())
    observed_report = observed_envelope["report"]
    observed_canonical = json.dumps(
        observed_report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if (
        hashlib.sha256(observed_canonical).hexdigest()
        != observed_envelope["report_sha256"]
    ):
        raise ValueError("PBS observed-role receipt digest differs")
    observed_qualification = observed_report["qualification"]
    role_counts = observed_qualification["role_field_counts"]
    profile = load_observed_profile(root)
    roles = {
        "items": "interpreted",
        "products": "interpreted",
        "restrictions": "interpreted",
        "prescribing_rules": "interpreted",
        "prices": "interpreted",
        "pricing_components": "interpreted",
        "historical_records": "native_unresolved",
        "organisations": "native_unresolved",
        "references": "native_unresolved",
        "schedules": "native_unresolved",
        "vocabulary_metadata": "native_unresolved",
    }
    if (
        set(role_counts) != set(roles)
        or sum(role_counts.values()) != SOURCE_FIELDS
    ):
        raise ValueError("PBS source role partition does not close")

    meanings = domain_report["domains"]
    expected = {
        "items": meanings["item"]["field_count"],
        "products": meanings["product"]["field_count"],
        "restrictions": role_counts["restrictions"],
        "prescribing_rules": role_counts["prescribing_rules"],
        "prices": role_counts["prices"],
        "pricing_components": role_counts["pricing_components"],
    }
    if (
        expected["items"] != role_counts["items"]
        or expected["products"] != role_counts["products"]
        or meanings["restriction"]["field_count"]
        != role_counts["restrictions"] + role_counts["prescribing_rules"]
        or meanings["price"]["field_count"]
        != role_counts["prices"] + role_counts["pricing_components"]
    ):
        raise ValueError(
            "PBS interpreted role counts differ from meaning evidence"
        )

    interpreted = sum(
        role_counts[name]
        for name, state in roles.items()
        if state == "interpreted"
    )
    unresolved = sum(
        role_counts[name]
        for name, state in roles.items()
        if state == "native_unresolved"
    )
    unavailable = 0
    if interpreted + unresolved + unavailable != SOURCE_FIELDS:
        raise ValueError("PBS field-state denominator does not close")

    meaning_for_role = {
        "items": "item",
        "products": "product",
        "restrictions": "restriction",
        "prescribing_rules": "restriction",
        "prices": "price",
        "pricing_components": "price",
    }
    state_rows = {}
    for name, state in roles.items():
        evidence_key = meaning_for_role.get(name)
        meaning = meanings[evidence_key] if evidence_key is not None else None
        reference_evidence = (
            {
                "profile": reference_review["profile_id"],
                "status": reference_review["status"],
                "source": reference_review["source"],
                "reference_kinds": reference_review["reference_kinds"],
                "exact_source_screen": reference_review["exact_source_screen"],
                "calibration": reference_review["calibration"],
                "semantic_relationships_qualified": False,
            }
            if name == "references"
            else None
        )
        state_rows[name] = {
            "field_count": role_counts[name],
            "state": state,
            "meaning": (
                meaning["meaning"]
                if meaning is not None
                else (
                    "source-local reference literals; target relationships unresolved"
                    if name == "references"
                    else None
                )
            ),
            "interpretation_evidence": (
                {
                    "profile": "pbs-v3-pinned-2026-04-01-domain-fields-v1",
                    "domain": evidence_key,
                    "status": meaning["status"],
                    "source": domain_report["source"],
                    "basis": domain_report["meaning_basis"],
                    "limits": meaning["limits"],
                    "value_interpretation": False,
                }
                if meaning is not None
                else reference_evidence
            ),
        }
    path_inventory = json.loads((root / PATH_INVENTORY).read_bytes())
    path_reconciliation: list[dict[str, Any]] = []
    path_role_counts: dict[str, int] = {}
    for path_row in path_inventory["paths"]:
        role = profile.roles.get(
            _entity_path(path_row["schema_path"]), "unmapped"
        )
        state = roles.get(role, "native_unresolved")
        path_reconciliation.append({
            "schema_path": path_row["schema_path"],
            "field_count": path_row["native_fields"],
            "role": role,
            "state": state,
            "interpretation_domain": meaning_for_role.get(role),
        })
        path_role_counts[role] = (
            path_role_counts.get(role, 0) + path_row["native_fields"]
        )
    if (
        len(path_reconciliation) != SOURCE_PATHS
        or path_role_counts != role_counts
        or sum(row["field_count"] for row in path_reconciliation)
        != SOURCE_FIELDS
    ):
        raise ValueError("PBS schema-path field-state partition does not close")
    return {
        "schema_id": "global-medicines-atlas.pbs-field-state-reconciliation",
        "schema_version": 1,
        "profile_id": "pbs-v3-2026-04-01-field-state-v1",
        "status": "complete_field_denominator_bounded_semantics_with_unresolved_references",
        "domain_semantics_qualified": False,
        "rights_conclusion_changed": False,
        "source": {
            "dataset": native["dataset"],
            "revision": native["revision"],
            "member_sha256": native["candidate_output"]["member_sha256"],
            "native_digest": native["candidate_output"]["native_core_sha256"],
            "source_fields": SOURCE_FIELDS,
            "package_receipt_sha256": package_sha,
            "screen_receipt_sha256": screen_sha,
            "prior_field_state_receipt_sha256": field_state_sha,
            "domain_semantics_report_sha256": domain_envelope["report_sha256"],
            "reference_meaning_report_sha256": reference_envelope[
                "report_sha256"
            ],
            "observed_roles_report_sha256": observed_envelope["report_sha256"],
        },
        "field_state_coverage": {
            "interpreted": interpreted,
            "native_unresolved": unresolved,
            "unavailable": unavailable,
            "source_fields": SOURCE_FIELDS,
            "denominator_closed": True,
            "all_native_values_remain_unresolved": True,
        },
        "role_reconciliation": state_rows,
        "path_reconciliation": path_reconciliation,
        "date_role_overlay": {
            "field_count": meanings["effective_date"]["field_count"]
            + meanings["document_valid_date"]["field_count"],
            "evidence_profile": "pbs-v3-pinned-2026-04-01-date-profile-v1",
            "counted_in_role_partition": True,
            "additive_to_denominator": False,
            "limits": meanings["effective_date"]["limits"]
            + meanings["document_valid_date"]["limits"],
        },
        "interpretation_evidence": {
            key: {
                "meaning": meanings[key]["meaning"],
                "field_count": meanings[key]["field_count"],
                "status": meanings[key]["status"],
                "limits": meanings[key]["limits"],
                "evidence": domain_report["meaning_basis"],
            }
            for key in ("item", "product", "restriction", "price")
        },
        "source_local_reference_review": {
            "report_sha256": reference_envelope["report_sha256"],
            "reference_role_field_count": role_counts["references"],
            "screen_reference_denominator": reference_review[
                "exact_source_screen"
            ]["references"],
            "denominator_note": (
                "The schema-role field-state count and source reference-screen "
                "candidate count are separate measures."
            ),
            "semantic_relationships_qualified": False,
            "promotion_rule": reference_review["calibration"]["promotion_rule"],
        },
        "non_claims": {
            "cross_era_or_jurisdiction_pooling": False,
            "current_listing_status": False,
            "patient_rates": "unavailable: no patient-level numerator/denominator evidence in this source",
            "payable_benefit_or_patient_cost": False,
            "clinical_eligibility": False,
            "semantic_relationships": False,
            "new_sources": 0,
            "new_admissions": 0,
            "consumer_canaries": 0,
            "publications": 0,
        },
        "candidate_output": native["candidate_output"],
    }
