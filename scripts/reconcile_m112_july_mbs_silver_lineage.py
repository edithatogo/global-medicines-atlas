"""Bind the six July 2025 MBS Silver tables to their frozen source lineage."""

from __future__ import annotations

import copy
import hashlib
import json
from operator import itemgetter
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.mbs_silver_qualification import (
    MbsSilverQualification,
)
from global_medicines_atlas.receipts import SourceReceipt, require_temporal

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
BASE = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "july-mbs-source-lineage-reviewed.json"
)
FROZEN_INVENTORY = (
    QUAL / "australian-m112-frozen-object-inventory-20261018.json"
)
TREE_INVENTORY = (
    QUAL / "australian-m112-current-tree-object-inventory-20261004.json"
)
SOURCE_LINEAGE = (
    QUAL / "australian-m112-july-mbs-source-lineage-reviewed-20261019.json"
)
SOURCE_RECEIPT = Path(
    "quality/bronze/receipts/au-mbs/"
    "bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d.json"
)
MANIFEST = QUAL / "australian-mbs-v4-candidate-2025-07/manifest.json"
PUBLIC_QUALIFICATION = (
    QUAL / "australian-mbs-v4-candidate-2025-07/qualification.json"
)
CANDIDATE_REPORT = (
    QUAL / "australian-mbs-silver-candidate-qualification-20261017.json"
)
PUBLIC_READBACK = QUAL / "australian-m108-derived-products-20261017.json"
DATASET = "edithatogo/australian-mbs-source-archive"
INVENTORY_REVISION = "40891976f77ee5e7688edceed25c9ac98a77547e"
SOURCE_VERSION = "2025-07-version-3"
SOURCE_PATH = "raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML"
SOURCE_SHA256 = (
    "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
)
SOURCE_BYTES = 8_194_522
SOURCE_RECEIPT_SHA256 = (
    "c8c3e3baeee4c08dba1a944c19652ec184d90de850968fc4d6a124747d994e03"
)
PREFIX = "silver/mbs/v4/2025-07-v3"
TABLES = {"benefits", "caps", "descriptions", "fees", "hierarchy", "services"}
EXPECTED_DENOMINATOR = 1759
EXPECTED_COMPLETE_RAW = 22
EXPECTED_PROJECTION_PATHS = 23
EXPECTED_TABLE_COUNT = 6
EXPECTED_PUBLIC_OBJECT_COUNT = 9
EXPECTED_TOTAL_LINEAGES = 28
SHA256_HEX_LENGTH = 64
OBSERVED_AT = "2026-10-19T07:12:00+10:00"
SUPERSEDED_OUTPUT = (
    QUAL / "australian-m112-july-mbs-silver-lineage-20261019.json"
)
SUPERSEDED_OUTPUT_SHA256 = (
    "28025391fa112bd532eea2544a986840c3d9dcccb10f40f90f5dbea6732eebfb"
)
OUTPUT = QUAL / "australian-m112-july-mbs-silver-lineage-reviewed-20261019.json"
OVERLAY_OUTPUT = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "july-mbs-silver-lineage-reviewed.json"
)
BindingResult = tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]


def _read(path: Path) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _write_bound(path: Path, payload: bytes) -> str:
    target = ROOT / path
    if target.exists():
        if target.read_bytes() != payload:
            raise ValueError(f"immutable evidence conflict: {path}")
        return hashlib.sha256(payload).hexdigest()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _unique(rows: list[dict[str, Any]], *, path: str) -> dict[str, Any]:
    matches = [row for row in rows if row.get("path") == path]
    if len(matches) != 1:
        raise ValueError(f"expected one row for {path}; found {len(matches)}")
    return matches[0]


def _build_bindings() -> BindingResult:  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- each evidence role is checked explicitly
    """Cross-check frozen identity, source receipt, transformation, and output."""
    base = _read(BASE)
    frozen = _read(FROZEN_INVENTORY)
    tree = _read(TREE_INVENTORY)
    manifest = _read(MANIFEST)
    public_qualification = _read(PUBLIC_QUALIFICATION)
    candidate = _read(CANDIDATE_REPORT)
    readback = _read(PUBLIC_READBACK)
    source_lineage = _read(SOURCE_LINEAGE)

    totals = base["updated_gate_totals"]
    if not all((
        totals.get("approved_denominator") == EXPECTED_DENOMINATOR,
        totals.get("complete_raw_b1_b2_lineage") == EXPECTED_COMPLETE_RAW,
        totals.get("preserved_deferrals") == EXPECTED_DENOMINATOR,
        totals.get("v4_admissions") == 0,
        totals.get("consumer_canaries") == 0,
        base["scope"].get("approved_projection_paths")
        == EXPECTED_PROJECTION_PATHS,
    )):
        raise ValueError("M-112 frozen scope or independent gates changed")

    source_receipt_bytes = (ROOT / SOURCE_RECEIPT).read_bytes()
    receipt = SourceReceipt.model_validate_json(source_receipt_bytes)
    temporal = require_temporal(receipt.temporal)
    if not all((
        receipt.digest() == SOURCE_RECEIPT_SHA256,
        temporal.content_id == SOURCE_SHA256,
        temporal.source_version == SOURCE_VERSION,
        receipt.payload.byte_count == SOURCE_BYTES,
        source_lineage["lineage"]["source_receipt_sha256"]
        == SOURCE_RECEIPT_SHA256,
        source_lineage["inventory"]["revision"] == INVENTORY_REVISION,
        source_lineage["inventory"]["path"] == SOURCE_PATH,
    )):
        raise ValueError(
            "July source receipt does not bind the frozen raw object"
        )

    manifest_source = manifest.get("source", {})
    if not all((
        manifest.get("dataset") == DATASET,
        manifest.get("destination_prefix") == PREFIX,
        manifest.get("candidate_only") is True,
        manifest_source.get("source_path") == SOURCE_PATH,
        manifest_source.get("source_revision") == SOURCE_VERSION,
        manifest_source.get("sha256") == SOURCE_SHA256,
        manifest_source.get("byte_count") == SOURCE_BYTES,
        manifest_source.get("receipt_sha256") == SOURCE_RECEIPT_SHA256,
    )):
        raise ValueError("Silver manifest does not bind the exact July source")
    if (
        public_qualification.get("qualification", {}).get(
            "qualification_sha256"
        )
        != manifest.get("qualification_sha256")
        or public_qualification.get("candidate_only") is not True
    ):
        raise ValueError("Silver manifest qualification binding changed")

    if not all((
        candidate.get("public_v4_identity", {}).get("status") == "verified",
        candidate.get("public_v4_identity", {}).get("manifest_sha256")
        == _sha(MANIFEST),
        candidate.get("public_v4_identity", {}).get("source_sha256")
        == SOURCE_SHA256,
        candidate.get("qualification", {}).get("source_sha256")
        == SOURCE_SHA256,
        candidate.get("qualification", {}).get("promotion_status")
        == "candidate_only",
        candidate.get("profiled_schema_compatibility", {}).get("status")
        == "verified",
        candidate.get("profiled_schema_compatibility", {}).get(
            "source_values_included"
        )
        is False,
        candidate.get("profiled_schema_compatibility", {}).get("b2_sha256")
        == SOURCE_SHA256,
    )):
        raise ValueError("source-faithful candidate qualification changed")

    products = [
        row
        for row in readback.get("products", [])
        if row.get("product_id") == "mbs-2025-07-silver-v4-candidate"
    ]
    if len(products) != 1:
        raise ValueError(
            "M-108 does not uniquely describe the July Silver candidate"
        )
    product = products[0]
    if not all((
        product.get("dataset") == DATASET,
        product.get("publication_revision")
        == candidate.get("public_v4_identity", {}).get("publication_revision"),
        product.get("product_prefix") == PREFIX,
        product.get("candidate_only") is True,
        product.get("typed_federation_v4_admission") is False,
        product.get("manifest", {}).get("sha256") == _sha(MANIFEST),
        product.get("publication_receipt", {}).get(
            "current_tree_matches_receipt"
        )
        is True,
        product.get("publication_receipt", {}).get(
            "workflow_anonymous_verified_objects"
        )
        == EXPECTED_PUBLIC_OBJECT_COUNT,
    )):
        raise ValueError(
            "anonymous public readback does not bind the candidate manifest"
        )

    manifest_objects = [
        row
        for row in manifest.get("objects", [])
        if row.get("role") == "source_faithful_silver_table"
    ]
    qualified_tables = candidate.get("qualification", {}).get("tables", [])
    product_outputs = product.get("outputs", [])
    if not all((
        len(manifest_objects) == EXPECTED_TABLE_COUNT,
        len(qualified_tables) == EXPECTED_TABLE_COUNT,
        len(product_outputs) == EXPECTED_TABLE_COUNT,
        {Path(row["path"]).stem for row in manifest_objects} == TABLES,
        {row.get("table") for row in qualified_tables} == TABLES,
        {Path(row["path"]).stem for row in product_outputs} == TABLES,
    )):
        raise ValueError(
            "the exact six table outputs or qualification rows changed"
        )

    frozen_paths = {
        row["path"]
        for row in frozen.get("members", [])
        if row.get("dataset") == DATASET
    }
    if not all(row["path"] in frozen_paths for row in manifest_objects):
        raise ValueError("a July Silver table is outside the frozen inventory")

    output_rows: list[dict[str, Any]] = []
    base_objects = base.get("objects", [])
    tree_rows = tree.get("observations", [])
    candidate_qualification = MbsSilverQualification.model_validate(
        candidate.get("qualification")
    )
    public_qualification_model = MbsSilverQualification.model_validate(
        public_qualification.get("qualification")
    )
    candidate_lineages = {
        row.table: row.model_dump(mode="json")
        for row in candidate_qualification.tables
    }
    public_lineages = {
        row.table: row.model_dump(mode="json")
        for row in public_qualification_model.tables
    }
    if not all((
        set(candidate_lineages) == TABLES,
        set(public_lineages) == TABLES,
        candidate_lineages == public_lineages,
    )):
        raise ValueError(
            "candidate table lineage differs from manifest-bound qualification"
        )
    lineages = candidate_lineages
    public_outputs = {row["path"]: row for row in product_outputs}
    for output in sorted(manifest_objects, key=itemgetter("path")):
        path = output["path"]
        table = Path(path).stem
        frozen_row = _unique(
            [row for row in frozen["members"] if row.get("dataset") == DATASET],
            path=path,
        )
        base_row = _unique(
            [
                row
                for row in base_objects
                if row.get("dataset") == DATASET
                and row.get("revision") == INVENTORY_REVISION
            ],
            path=path,
        )
        tree_row = _unique(
            [
                row
                for row in tree_rows
                if row.get("dataset") == DATASET
                and row.get("revision") == INVENTORY_REVISION
            ],
            path=path,
        )
        public_output = public_outputs.get(path)
        lineage = lineages.get(table)
        identity = base_row.get("identity", {})
        if public_output is None or lineage is None:
            raise ValueError(
                f"missing public output or qualification lineage: {path}"
            )
        sha256 = output.get("sha256")
        byte_count = output.get("byte_count")
        if not all((
            frozen_row.get("object_class") == "existing_data_projection",
            frozen_row.get("current_reconciliation_revision")
            == INVENTORY_REVISION,
            base_row.get("candidate_class") == "existing_data_projection",
            base_row.get("approved_denominator_member") is True,
            base_row.get("b1_b2_lineage", {}).get("complete") is False,
            identity.get("sha256") == sha256,
            identity.get("byte_count") == byte_count,
            output.get("role") == "source_faithful_silver_table",
            public_output.get("sha256") == sha256,
            public_output.get("byte_count") == byte_count,
            tree_row.get("git_blob_oid_match") is True,
            tree_row.get("byte_count_match") is True,
            tree_row.get("observed_git_blob_oid")
            == identity.get("git_blob_oid"),
            tree_row.get("expected_git_blob_oid")
            == identity.get("git_blob_oid"),
            tree_row.get("observed_bytes") == byte_count,
            tree_row.get("expected_bytes") == byte_count,
            tree_row.get("observed_lfs_sha256") == sha256,
            tree_row.get("expected_lfs_sha256") == sha256,
            lineage.get("row_count")
            == candidate["qualification"].get("source_record_count"),
            isinstance(lineage.get("lineage_sha256"), str),
            len(lineage["lineage_sha256"]) == SHA256_HEX_LENGTH,
        )):
            raise ValueError(
                f"frozen output, transformation, or readback mismatch: {path}"
            )
        output_rows.append({
            "dataset": DATASET,
            "inventory_revision": INVENTORY_REVISION,
            "path": path,
            "table": table,
            "sha256": sha256,
            "byte_count": byte_count,
            "source": {
                "dataset": DATASET,
                "revision": INVENTORY_REVISION,
                "path": SOURCE_PATH,
                "sha256": SOURCE_SHA256,
                "byte_count": SOURCE_BYTES,
                "source_version": SOURCE_VERSION,
                "source_receipt_path": SOURCE_RECEIPT.as_posix(),
                "source_receipt_sha256": SOURCE_RECEIPT_SHA256,
            },
            "transformation": {
                "candidate_report_path": CANDIDATE_REPORT.as_posix(),
                "candidate_report_sha256": _sha(CANDIDATE_REPORT),
                "producer_commit": manifest["producer_commit"],
                "table_lineage_sha256": lineage["lineage_sha256"],
                "row_count": lineage["row_count"],
                "field_count": lineage["field_count"],
                "field_occurrence_count": lineage["field_occurrence_count"],
                "candidate_only": True,
            },
            "public_identity": {
                "publication_revision": product["publication_revision"],
                "anonymous_readback_revision": product["publication_receipt"][
                    "latest_anonymous_tree_revision"
                ],
                "manifest_path": MANIFEST.as_posix(),
                "manifest_sha256": _sha(MANIFEST),
                "readback_matches_manifest": True,
                "observed_git_blob_oid": tree_row["observed_git_blob_oid"],
                "observed_lfs_sha256": tree_row["observed_lfs_sha256"],
                "observed_byte_count": tree_row["observed_bytes"],
                "tree_identity_matches_frozen_identity": True,
            },
        })

    return base, product, output_rows


def build_report() -> dict[str, Any]:
    if _sha(SUPERSEDED_OUTPUT) != SUPERSEDED_OUTPUT_SHA256:
        raise ValueError("superseded qualification digest changed")
    _base, product, outputs = _build_bindings()
    return {
        "schema_id": "global-medicines-atlas.m112-july-mbs-silver-source-lineage",
        "schema_version": 1,
        "observed_at": OBSERVED_AT,
        "supersedes": {
            "path": SUPERSEDED_OUTPUT.as_posix(),
            "sha256": SUPERSEDED_OUTPUT_SHA256,
        },
        "status": "six_candidate_silver_tables_bound_to_frozen_source_lineage",
        "scope": {
            "dataset": DATASET,
            "inventory_revision": INVENTORY_REVISION,
            "frozen_denominator": EXPECTED_DENOMINATOR,
            "frozen_projection_count": EXPECTED_PROJECTION_PATHS,
            "objects_qualified": len(outputs),
            "all_objects_candidate_only": True,
        },
        "source": {
            "path": SOURCE_PATH,
            "sha256": SOURCE_SHA256,
            "byte_count": SOURCE_BYTES,
            "source_version": SOURCE_VERSION,
            "receipt_path": SOURCE_RECEIPT.as_posix(),
            "receipt_sha256": SOURCE_RECEIPT_SHA256,
            "source_payload_bytes_requested_or_inspected": False,
        },
        "candidate_product": {
            "prefix": PREFIX,
            "publication_revision": product["publication_revision"],
            "current_tree_revision": product["current_revision"],
            "manifest_sha256": _sha(MANIFEST),
            "candidate_only": True,
            "typed_v4_admission": False,
            "derived_product_rights_conclusion": False,
            "publication_performed": False,
        },
        "outputs": outputs,
        "input_bindings": {
            path.as_posix(): _sha(path)
            for path in (
                BASE,
                FROZEN_INVENTORY,
                TREE_INVENTORY,
                SOURCE_LINEAGE,
                SOURCE_RECEIPT,
                MANIFEST,
                PUBLIC_QUALIFICATION,
                CANDIDATE_REPORT,
                PUBLIC_READBACK,
            )
        },
        "implementation": {
            "path": "scripts/reconcile_m112_july_mbs_silver_lineage.py",
            "sha256": _sha(
                Path("scripts/reconcile_m112_july_mbs_silver_lineage.py")
            ),
        },
        "scope_limits": {
            "new_source_or_dataset_added": False,
            "frozen_inventory_changed": False,
            "rights_or_licensing_conclusion_added": False,
            "per_object_rights_gate_closed": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
            "source_payload_bytes_requested_or_inspected": False,
            "source_values_retained": False,
            "public_release_performed": False,
        },
    }


def update_overlay(qualification: dict[str, Any]) -> dict[str, Any]:
    """Mark only the six exact frozen projection rows as lineage-complete."""
    report = copy.deepcopy(_read(BASE))
    if report["updated_gate_totals"].get("complete_projection_lineage", 0) != 0:
        raise ValueError("projection lineage baseline changed")
    for output in qualification["outputs"]:
        target = _unique(
            [
                row
                for row in report["objects"]
                if row.get("dataset") == DATASET
                and row.get("revision") == INVENTORY_REVISION
            ],
            path=output["path"],
        )
        if target["b1_b2_lineage"].get("complete") is not False:
            raise ValueError(
                f"projection lineage already changed: {output['path']}"
            )
        target["b1_b2_lineage"] = {
            "complete": True,
            "state": (
                "The existing candidate source receipt, raw B2 identity, table-specific "
                "transformation lineage, manifest output digest, and anonymous public "
                "metadata readback bind this exact frozen Silver projection. The object "
                "remains candidate-only and its separate rights and v4 admission gates "
                "remain open."
            ),
            "evidence": output,
        }
        target["lineage_kind"] = "source_faithful_silver_projection"
    report["observed_at"] = OBSERVED_AT
    report["purpose"] = (
        "Preserve the approved 1,759-object inventory while binding the six existing "
        "July 2025 MBS Silver candidate tables to their exact source receipt, table "
        "lineage, output identity, and public metadata readback."
    )
    report["updated_gate_totals"]["complete_projection_lineage"] = len(
        qualification["outputs"]
    )
    report["updated_gate_totals"]["complete_b1_b2_lineage_objects"] = (
        report["updated_gate_totals"]["complete_raw_b1_b2_lineage"]
        + report["updated_gate_totals"]["complete_projection_lineage"]
    )
    report["projection_b1_b2_lineage_expansion"] = {
        "prior_complete_raw_lineages": EXPECTED_COMPLETE_RAW,
        "new_complete_projection_lineages": len(qualification["outputs"]),
        "complete_raw_lineages_after_expansion": EXPECTED_COMPLETE_RAW,
        "complete_projection_lineages_after_expansion": len(
            qualification["outputs"]
        ),
        "complete_object_lineages_after_expansion": report[
            "updated_gate_totals"
        ]["complete_b1_b2_lineage_objects"],
        "qualification_path": OUTPUT.as_posix(),
        "qualification_sha256": _sha(OUTPUT),
        "scope_limits": qualification["scope_limits"],
    }
    if not all((
        len(qualification["outputs"]) == EXPECTED_TABLE_COUNT,
        report["scope"]["approved_denominator"] == EXPECTED_DENOMINATOR,
        report["updated_gate_totals"]["complete_raw_b1_b2_lineage"]
        == EXPECTED_COMPLETE_RAW,
        report["updated_gate_totals"]["complete_projection_lineage"]
        == EXPECTED_TABLE_COUNT,
        report["updated_gate_totals"]["complete_b1_b2_lineage_objects"]
        == EXPECTED_TOTAL_LINEAGES,
        report["updated_gate_totals"]["preserved_deferrals"]
        == EXPECTED_DENOMINATOR,
        report["updated_gate_totals"]["v4_admissions"] == 0,
        report["updated_gate_totals"]["consumer_canaries"] == 0,
    )):
        raise ValueError(
            "Silver lineage update changed inventory or independent gates"
        )
    return report


def main() -> None:
    report = build_report()
    _write_bound(
        OUTPUT,
        json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
        + b"\n",
    )
    overlay = update_overlay(report)
    _write_bound(
        OVERLAY_OUTPUT,
        json.dumps(overlay, ensure_ascii=False, indent=2).encode("utf-8")
        + b"\n",
    )
    print(OUTPUT.as_posix())
    print(OVERLAY_OUTPUT.as_posix())


if __name__ == "__main__":
    main()
