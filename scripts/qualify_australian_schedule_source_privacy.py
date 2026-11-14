"""Bind retained MBS and PBS source privacy metadata without admitting outputs."""

from __future__ import annotations

import argparse
import json
from operator import itemgetter
from pathlib import Path
from typing import Any

from scripts.qualify_australian_existing_derived_gates import (
    DATASET,
    INPUTS,
    MBS_RIGHTS_REVISION,
    ROOT,
)
from scripts.qualify_m112_existing_reimbursement_batch import (
    metadata_rows,
    read_bound_metadata,
)

SOURCE_SHA = "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
SOURCE_BYTES = 8_293_331
SOURCE_PATH = f"raw/mbs/releases/2026-08-01/{SOURCE_SHA}.xml"
EVENT_SCHEMA_VERSION = 3
PRODUCT_COUNT = 2
OBJECT_COUNT = 4
OBJECTS_PER_PRODUCT = 2
SOURCE_RECEIPTS = {
    "fd32879190b69ad98cd2f207ec3b70b725ab8f524218f783ec08bf98b7ffcecd": (
        "quality/bronze/acquisitions/au-mbs/fd32879190b69ad98cd2f207ec3b70b725ab8f524218f783ec08bf98b7ffcecd.json",
        "0473edd93fe9c2781701116febbd68a0c68262b74be5b4de52409d5c52570d30",
    ),
    "f5626f2deb09f4301989480f112ec117ccad9efafc54c04d161100d6c5ca08e1": (
        "quality/bronze/acquisitions/au-mbs/f5626f2deb09f4301989480f112ec117ccad9efafc54c04d161100d6c5ca08e1.json",
        "f0539528fff8f48781554e83ff3520579efc9a61daa04c5ca14d75e835bbacba",
    ),
}
PBS_EVENT_ID = (
    "712fd306658de6db5ae0aaa2be39d554e5a18c306987cc614152efbed53f30f4"
)
PBS_ARCHIVE_SHA = (
    "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
)
PBS_ARCHIVE_BYTES = 11_156_706
PBS_MEMBER_SHA = (
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
)
PBS_SOURCE_PATH = "raw/2026-04-01/2026-04-01-XML-V3.zip"
PBS_EVENT = (
    f"quality/bronze/imported-acquisitions/au-pbs/{PBS_EVENT_ID}.json",
    "dbfab903b4d24feb62fa77c141422a4cb33a85eb08583d3a7d40f0200f6190e3",
)
PBS_LINEAGE = (
    "quality/qualifications/australian-m112-pbs-projected-b1-b2-lineage-20261019.json",
    "aa4a0df6df4ec723e7b65f55379f47ae7912e4777a6b9d3bb3454c1accf3a16f",
)


def qualify_documents(
    scope: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate the exact source classifications and prior product bindings."""
    if set(receipts) != set(SOURCE_RECEIPTS):
        raise ValueError("MBS source receipt identities differ")
    for identity, event in receipts.items():
        sensitivity = event["sensitivity"]
        retrieval = event["retrieval"]
        if not all((
            event.get("schema_id")
            == "global-medicines-atlas.bronze-acquisition-event",
            event.get("schema_version") == EVENT_SCHEMA_VERSION,
            event.get("acquisition_id") == identity,
            event.get("evidence_class") == "live",
            event.get("source_id") == event["source"]["source_id"] == "au-mbs",
            event["source"]["catalog_version"] == "2026-08-01",
            event.get("content_id")
            == event.get("payload_sha256")
            == SOURCE_SHA,
            retrieval.get("status") == "succeeded",
            retrieval["http"]["observed_byte_length"] == SOURCE_BYTES,
            sensitivity.get("schema_id")
            == "global-medicines-atlas.bronze-sensitivity-classification",
            sensitivity.get("schema_version") == 1,
            sensitivity.get("data_sensitivity") == "non_sensitive",
            sensitivity.get("personal_data") == "none",
            sensitivity.get("publication") == "permitted",
            set(sensitivity.get("reason_codes", []))
            == {"qualified_official_mbs_schedule", "exact_release_approval"},
        )):
            raise ValueError("MBS source privacy receipt differs")
    if not all((
        scope.get("dataset") == DATASET,
        scope.get("revision") == MBS_RIGHTS_REVISION,
        scope["scope"]["frozen_inventory_membership_changed"] is False,
    )):
        raise ValueError("MBS source scope differs")
    products = metadata_rows(scope.get("products"))
    objects = metadata_rows(scope.get("objects"))
    product_ids = {row["product_id"] for row in products}
    if (
        len(products) != PRODUCT_COUNT
        or len(product_ids) != PRODUCT_COUNT
        or len(objects) != OBJECT_COUNT
        or len({row["path"] for row in objects}) != OBJECT_COUNT
        or {row["product_id"] for row in objects} != product_ids
    ):
        raise ValueError("MBS source product identities differ")
    if any(row.get("in_frozen_m112_inventory") is not False for row in objects):
        raise ValueError("MBS source frozen inventory scope differs")
    result: list[dict[str, Any]] = []
    for product in sorted(products, key=itemgetter("product_id")):
        if product.get("source") != {
            "path": SOURCE_PATH,
            "sha256": SOURCE_SHA,
            "byte_count": SOURCE_BYTES,
        }:
            raise ValueError("MBS projection source binding differs")
        count = sum(
            row["product_id"] == product["product_id"] for row in objects
        )
        if count != OBJECTS_PER_PRODUCT:
            raise ValueError("MBS projection source object count differs")
        result.append({
            "product_id": product["product_id"],
            "object_count": count,
            "source_privacy": "non_sensitive_in_exact_source_receipts",
            "projection_privacy": "not_qualified_by_source_classification",
            "v4_admission": "not_performed",
            "consumer_check": "not_performed",
        })
    return result


def qualify_pbs_source(
    event: dict[str, Any], lineage: dict[str, Any], package: dict[str, Any]
) -> dict[str, Any]:
    """Preserve the exact imported source's unknown privacy classification."""
    member = package["member_binding"]
    sensitivity = event["sensitivity"]
    if not all((
        event.get("schema_id")
        == "global-medicines-atlas.bronze-acquisition-event",
        event.get("schema_version") == EVENT_SCHEMA_VERSION,
        event.get("acquisition_id") == PBS_EVENT_ID,
        event.get("source_id") == "au_pbs",
        event.get("evidence_class") == "historical",
        event.get("content_id")
        == event.get("payload_sha256")
        == PBS_ARCHIVE_SHA,
        sensitivity.get("data_sensitivity") == "unknown",
        sensitivity.get("personal_data") == "unknown",
        sensitivity.get("publication") == "review_required",
        sensitivity.get("reason_codes") == ["unassessed"],
        member["archive_payload"]["sha256"] == PBS_ARCHIVE_SHA,
        member["archive_payload"]["byte_count"] == PBS_ARCHIVE_BYTES,
        member["member_payload"]["sha256"] == PBS_MEMBER_SHA,
        member["source"]["source_id"] == "au-pbs-historical-xml",
    )):
        raise ValueError("PBS imported source privacy binding differs")
    rows = [
        row
        for row in metadata_rows(lineage.get("objects"))
        if row.get("dataset") == "edithatogo/australian-pbs-source-archive"
        and row.get("path") == PBS_SOURCE_PATH
    ]
    if len(rows) != 1:
        raise ValueError("PBS archive lineage identity differs")
    row = rows[0]
    if not all((
        row.get("content_sha256") == PBS_ARCHIVE_SHA,
        row.get("byte_count") == PBS_ARCHIVE_BYTES,
        row["local_records"]["acquisition_event_path"] == PBS_EVENT[0],
        row["producer_b1"]["event_id"] == f"event:{PBS_EVENT_ID}",
        row.get("processing_admission") is False,
        row.get("v4_admission") is False,
    )):
        raise ValueError("PBS archive lineage binding differs")
    return {
        "archive_sha256": PBS_ARCHIVE_SHA,
        "archive_bytes": PBS_ARCHIVE_BYTES,
        "member_sha256": PBS_MEMBER_SHA,
        "source_privacy": "unknown_in_imported_acquisition_record",
        "output_privacy": "not_qualified_by_source_classification",
        "v4_admission": "not_performed",
        "consumer_check": "not_performed",
    }


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Produce a value-free report from exact existing metadata only."""
    scope = read_bound_metadata(root, *INPUTS["mbs_scope"])
    receipts = {
        identity: read_bound_metadata(root, *binding)
        for identity, binding in SOURCE_RECEIPTS.items()
    }
    pbs = qualify_pbs_source(
        read_bound_metadata(root, *PBS_EVENT),
        read_bound_metadata(root, *PBS_LINEAGE),
        read_bound_metadata(root, *INPUTS["pbs_package"]),
    )
    return {
        "schema_id": "global-medicines-atlas.australian-schedule-source-privacy-check",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "mbs_source": {"sha256": SOURCE_SHA, "byte_count": SOURCE_BYTES},
        "scope_input": dict(
            zip(("path", "sha256"), INPUTS["mbs_scope"], strict=True)
        ),
        "receipt_inputs": [
            {"acquisition_id": key, "path": value[0], "sha256": value[1]}
            for key, value in sorted(SOURCE_RECEIPTS.items())
        ],
        "mbs_products": qualify_documents(scope, receipts),
        "pbs_source": pbs,
        "pbs_inputs": {
            "imported_event": dict(
                zip(("path", "sha256"), PBS_EVENT, strict=True)
            ),
            "archive_lineage": dict(
                zip(("path", "sha256"), PBS_LINEAGE, strict=True)
            ),
            "package": dict(
                zip(("path", "sha256"), INPUTS["pbs_package"], strict=True)
            ),
        },
        "limitations": [
            "The retained scope metadata names the source; source classification does not qualify the transformations or derived outputs.",
            "The source receipts are separate observations of the same source bytes, not independent privacy assessments of the outputs.",
            "The PBS imported-event privacy status is separate from the output's exact rights attestation and public location.",
        ],
        "boundaries": {
            "source_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_published_or_modified": False,
            "output_privacy_qualified": False,
            "new_admission": False,
            "consumer_check": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--report", type=Path)
    mode.add_argument("--check", type=Path)
    args = parser.parse_args()
    report = build_report()
    if args.report:
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    elif json.loads(args.check.read_text(encoding="utf-8")) != report:
        raise ValueError("stored Australian source privacy report differs")
    print(
        json.dumps({
            "mbs_products": len(report["mbs_products"]),
            "pbs_source_privacy": report["pbs_source"]["source_privacy"],
            "new_admissions": 0,
        })
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
