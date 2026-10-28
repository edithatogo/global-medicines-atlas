"""Bind exact PBS utilisation rights and lineage into M-112 object evidence."""

from __future__ import annotations

import hashlib
import json
import operator
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
LINEAGE_OVERLAY = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "pbs-utilisation-lineage.json"
)
LINEAGE = QUAL / "australian-pbs-utilisation-landed-lineage-20261019.json"
RIGHTS_RECONCILIATION = (
    QUAL / "australian-m112-current-rights-reconciliation-20261021.json"
)
RIGHTS_ATTESTATION = QUAL / (
    "australian-pbs-utilisation-six-object-rights-attestation-20261020.json"
)
ROLE_QUALIFICATION = QUAL / (
    "australian-m112-v4-contract-role-evidence-qualification-20261021.json"
)
FROZEN_INVENTORY = (
    QUAL / "australian-m112-frozen-object-inventory-20261018.json"
)
OUTPUT = QUAL / (
    "australian-m112-pbs-utilisation-rights-lineage-"
    "reconciliation-20261028.json"
)
DATASET = "edithatogo/australian-pbs-utilisation-archive"
REVISION = "9f1d53cd50eea251b326da42a96f3ac72ebce97a"
EXPECTED_OBJECTS = 6
EXPECTED_DENOMINATOR = 1759
EXPECTED_ADMISSIONS = 8
EXPECTED_DEFERRED = EXPECTED_DENOMINATOR - EXPECTED_ADMISSIONS
RIGHTS_STATE = (
    "maintainer_attested_exact_public_release_permission_for_pbs_"
    "utilisation_raw_object"
)
UNREVIEWED = "maintainer_attested_not_independently_reviewed"


def _read(path: Path) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def _digest(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _load_evidence() -> dict[str, dict[str, Any]]:
    return {
        "lineage_overlay": _read(LINEAGE_OVERLAY),
        "lineage": _read(LINEAGE),
        "rights_report": _read(RIGHTS_RECONCILIATION),
        "attestation": _read(RIGHTS_ATTESTATION),
        "role_report": _read(ROLE_QUALIFICATION),
        "frozen": _read(FROZEN_INVENTORY),
    }


def _index_evidence(  # ruff: ignore[too-many-locals] -- fixed identity checks
    evidence: dict[str, dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[tuple[str, str, str], dict[str, Any]],
    dict[tuple[str, str, str], dict[str, Any]],
]:
    lineage_overlay = evidence["lineage_overlay"]
    lineage = evidence["lineage"]
    rights_report = evidence["rights_report"]
    attestation = evidence["attestation"]
    role_report = evidence["role_report"]
    frozen = evidence["frozen"]
    pbs_rights = rights_report["pbs_utilisation_raw_objects"]
    attested = attestation["authorized_objects"]
    rights_rows = pbs_rights["objects"]
    lineage_rows = lineage["objects"]
    base_rows = lineage_overlay["objects"]
    frozen_rows = frozen["members"]
    object_keys = [(DATASET, REVISION, row["path"]) for row in attested]
    if not all((
        len(object_keys) == EXPECTED_OBJECTS,
        len(set(object_keys)) == EXPECTED_OBJECTS,
        len(rights_rows) == EXPECTED_OBJECTS,
        len(lineage_rows) == EXPECTED_OBJECTS,
        lineage["scope"]["dataset"] == DATASET,
        lineage["scope"]["revision"] == REVISION,
        lineage["scope"]["lineages_completed"] == EXPECTED_OBJECTS,
        lineage["boundaries"]["source_payload_bytes_read"] is False,
        lineage["boundaries"]["source_payload_values_inspected"] is False,
        lineage_overlay["scope"]["approved_denominator"]
        == EXPECTED_DENOMINATOR,
        lineage_overlay["scope"]["denominator_changed"] is False,
        frozen["scope"]["approved_member_count"] == EXPECTED_DENOMINATOR,
        frozen["scope"]["path_membership_sha256"]
        == lineage_overlay["approved_path_membership_sha256"],
        pbs_rights["object_count"] == EXPECTED_OBJECTS,
        pbs_rights["public_release_authorized_within_scope"] is True,
        pbs_rights["rights_scope_includes_all_file_contents"] is True,
        pbs_rights["permission_instrument_existence_and_applicability"]
        == UNREVIEWED,
        pbs_rights["public_release_performed_by_this_reconciliation"] is False,
        pbs_rights["v4_admission"] is False,
        pbs_rights["consumer_canary"] is False,
        pbs_rights["exact_rights_attestation_path"]
        == RIGHTS_ATTESTATION.as_posix(),
        pbs_rights["exact_rights_attestation_sha256"]
        == _digest(RIGHTS_ATTESTATION),
        pbs_rights["lineage_path"] == LINEAGE.as_posix(),
        pbs_rights["lineage_sha256"] == _digest(LINEAGE),
        attestation["decision"]["v4_admission"] is False,
        attestation["decision"]["consumer_canary"] is False,
        attestation["decision"]["public_release_performed"] is False,
        attestation["dataset_identity"]["dataset"] == DATASET,
        attestation["boundaries"]["frozen_inventory_membership_changed"]
        is False,
        attestation["boundaries"]["v4_admission_performed"] is False,
        attestation["boundaries"]["consumer_canary_performed"] is False,
        role_report["cohort"]["approved_denominator"] == EXPECTED_DENOMINATOR,
        role_report["cohort"]["v4_admissions"] == EXPECTED_ADMISSIONS,
        role_report["cohort"]["consumer_canaries"] == EXPECTED_ADMISSIONS,
        role_report["cohort"]["approved_denominator"]
        - role_report["cohort"]["v4_admissions"]
        == EXPECTED_DEFERRED,
    )):
        raise ValueError("PBS utilisation rights or M-112 scope changed")

    keyed_rights = {row["path"]: row for row in rights_rows}
    keyed_lineage = {row["path"]: row for row in lineage_rows}
    keyed_base = {
        operator.itemgetter("dataset", "revision", "path")(row): row
        for row in base_rows
        if row["dataset"] == DATASET and row["revision"] == REVISION
    }
    keyed_frozen = {
        (
            row["dataset"],
            row["approved_dataset_revision"],
            row["path"],
        ): row
        for row in frozen_rows
        if row["dataset"] == DATASET
        and row["approved_dataset_revision"] == REVISION
    }
    if not all((
        len(keyed_rights) == EXPECTED_OBJECTS,
        len(keyed_lineage) == EXPECTED_OBJECTS,
        len(keyed_base) == EXPECTED_OBJECTS,
        len(keyed_frozen) == EXPECTED_OBJECTS,
    )):
        raise ValueError("PBS utilisation rights identity differs")
    return attested, keyed_rights, keyed_lineage, keyed_base, keyed_frozen


def build_report() -> dict[str, Any]:
    """Reconcile only exact, frozen PBS utilisation paths and prior evidence."""
    evidence = _load_evidence()
    attested, keyed_rights, keyed_lineage, keyed_base, keyed_frozen = (
        _index_evidence(evidence)
    )
    rows: list[dict[str, Any]] = []
    for item in sorted(attested, key=operator.itemgetter("path")):
        path = item["path"]
        key = (DATASET, REVISION, path)
        right = keyed_rights.get(path)
        landed = keyed_lineage.get(path)
        base = keyed_base.get(key)
        frozen_row = keyed_frozen.get(key)
        if not all((right, landed, base, frozen_row)):
            raise ValueError("PBS utilisation rights identity differs")
        if (
            right is None
            or landed is None
            or base is None
            or frozen_row is None
        ):
            raise ValueError("PBS utilisation rights identity differs")
        if not all((
            (right["path"], right["sha256"], right["byte_count"])
            == (path, item["sha256"], item["byte_count"]),
            (landed["path"], landed["content_sha256"], landed["byte_count"])
            == (path, item["sha256"], item["byte_count"]),
            (base["identity"]["sha256"], base["identity"]["byte_count"])
            == (item["sha256"], item["byte_count"]),
            (
                frozen_row["dataset"],
                frozen_row["approved_dataset_revision"],
                frozen_row["path"],
            )
            == (DATASET, REVISION, path),
            base["b1_b2_lineage"]["complete"] is True,
            base["rights"]["state"]
            == (
                "source-specific rights review absent; per-object sidecar has "
                "no rights_state"
            ),
            landed["reviewer_status"] == "unreviewed",
            landed["rights_state"] == "unknown",
            landed["v4_admission"] is False,
            landed["consumer_canary"] is False,
            base["v4_admission"] is False,
            base["consumer_canary"] is False,
            base["disposition"] == "deferred_not_admitted",
            right["historical_acquisition_rights_state"] == "unknown",
        )):
            raise ValueError("PBS utilisation rights identity differs")
        rows.append({
            "dataset": DATASET,
            "revision": REVISION,
            "path": path,
            "sha256": item["sha256"],
            "byte_count": item["byte_count"],
            "rights_state": RIGHTS_STATE,
            "rights_evidence": {
                "path": RIGHTS_ATTESTATION.as_posix(),
                "sha256": _digest(RIGHTS_ATTESTATION),
                "scope": (
                    "exact path, digest, byte count, and all file contents"
                ),
                "permission_instrument_review": UNREVIEWED,
            },
            "b1_b2_lineage_complete": True,
            "lineage_evidence": {
                "path": LINEAGE.as_posix(),
                "sha256": _digest(LINEAGE),
                "landed_admission_reviewer_status": "unreviewed",
            },
            "v4_admission": False,
            "consumer_canary": False,
            "disposition": "deferred_not_admitted",
        })

    return {
        "schema_id": (
            "global-medicines-atlas.m112-pbs-utilisation-rights-lineage-"
            "reconciliation"
        ),
        "schema_version": 1,
        "recorded_at": "2026-10-28",
        "purpose": (
            "Bind the existing exact six-object PBS utilisation rights "
            "attestation to the frozen M-112 identities and landed B1/B2 "
            "lineages; preserve "
            "all admission, canary, and instrument-review gates."
        ),
        "frozen_inventory": {
            "path": FROZEN_INVENTORY.as_posix(),
            "sha256": _digest(FROZEN_INVENTORY),
            "membership_sha256": evidence["frozen"]["scope"][
                "path_membership_sha256"
            ],
            "denominator": EXPECTED_DENOMINATOR,
            "membership_changed": False,
        },
        "scope": {
            "frozen_denominator": EXPECTED_DENOMINATOR,
            "denominator_changed": False,
            "exact_objects": EXPECTED_OBJECTS,
            "rights_attestation_bound": EXPECTED_OBJECTS,
            "complete_b1_b2_lineage": EXPECTED_OBJECTS,
            "v4_admitted": 0,
            "consumer_canaries": 0,
            "disposition": "deferred_not_admitted",
        },
        "current_m112_role_counts": {
            "evidence_path": ROLE_QUALIFICATION.as_posix(),
            "evidence_sha256": _digest(ROLE_QUALIFICATION),
            "v4_admissions": 8,
            "consumer_canaries": 8,
            "deferred_objects": 1751,
        },
        "inputs": [
            {"path": path.as_posix(), "sha256": _digest(path)}
            for path in (
                LINEAGE_OVERLAY,
                LINEAGE,
                RIGHTS_RECONCILIATION,
                RIGHTS_ATTESTATION,
                ROLE_QUALIFICATION,
                FROZEN_INVENTORY,
            )
        ],
        "boundaries": {
            "source_payload_bytes_read": False,
            "source_payload_values_inspected": False,
            "new_sources_added": False,
            "rights_conclusion_added": False,
            "public_release_performed": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
            "frozen_denominator_changed": False,
        },
        "objects": rows,
    }


def main() -> None:
    result = build_report()
    destination = ROOT / OUTPUT
    body = json.dumps(result, ensure_ascii=False, indent=2).encode() + b"\n"
    if destination.exists() and destination.read_bytes() != body:
        raise ValueError(f"append-only reconciliation differs: {OUTPUT}")
    if not destination.exists():
        destination.write_bytes(body)
    print(
        json.dumps(
            {"output": OUTPUT.as_posix(), "objects": len(result["objects"])},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
