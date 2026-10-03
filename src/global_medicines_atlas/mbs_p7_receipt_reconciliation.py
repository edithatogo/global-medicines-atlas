"""Reconstruct the archived P7 storage receipt without loading workbook bytes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import AnyUrl

from .models import FrozenModel
from .receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)

STORAGE_QUALIFICATION = (
    "quality/qualifications/mbs-workbook-storage-20260830.json"
)
PUBLIC_ARCHIVE_QUALIFICATION = (
    "quality/qualifications/australian-mbs-public-huggingface-20260829.json"
)
SOURCE_ID = "au-mbs-p7-legacy-workbook"
SOURCE_SHA256 = (
    "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
)
SOURCE_BYTES = 87_727
WORKFLOW_COMMIT = "11a8c4f9b97e542b631c7f9a676792168266ef87"
WORKFLOW_RUN = (
    "https://github.com/edithatogo/global-medicines-atlas/actions/runs/"
    "33305281887"
)
TRANSFORMATION_SHA256 = (
    "0e5d1ff9a53abe60a29ea7094f2d7cbb6dbe48e6821b22f69a861c6561cf2749"
)
ARCHIVE_URI = (
    "https://huggingface.co/datasets/edithatogo/"
    "australian-mbs-source-archive/resolve/"
    "4d1dae488ac43522f20e8320a8b2a56bf9138341/raw/mbs/legacy/2024-07/"
    "MBS-2024.07-Group-P7-Genetics.xlsx"
)
EXPECTED_RECEIPT_SHA256 = (
    "ba18c36737f9244b204c9d604dce9853e855ee9e9d6f6fd375618c052fdf0d52"
)


class P7ReceiptReconciliation(FrozenModel):
    """Typed evidence that the old storage receipt is exactly reproducible."""

    schema_id: Literal[
        "global-medicines-atlas.mbs-p7-storage-receipt-reconciliation"
    ] = "global-medicines-atlas.mbs-p7-storage-receipt-reconciliation"
    schema_version: Literal[1] = 1
    source_id: Literal["au-mbs-p7-legacy-workbook"] = SOURCE_ID
    source_sha256: Literal[
        "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
    ] = SOURCE_SHA256
    source_bytes: Literal[87727] = SOURCE_BYTES
    storage_qualification: str = STORAGE_QUALIFICATION
    public_archive_qualification: str = PUBLIC_ARCHIVE_QUALIFICATION
    workflow_commit: Literal["11a8c4f9b97e542b631c7f9a676792168266ef87"] = (
        WORKFLOW_COMMIT
    )
    workflow_run: Literal[
        "https://github.com/edithatogo/global-medicines-atlas/actions/runs/33305281887"
    ] = WORKFLOW_RUN
    retrieved_at: datetime
    archive_uri: str = ARCHIVE_URI
    reconstructed_receipt_sha256: str = EXPECTED_RECEIPT_SHA256
    recorded_receipt_sha256: str = EXPECTED_RECEIPT_SHA256
    exact_receipt_match: Literal[True] = True
    receipt_scope: Literal["archive_storage_qualification_only"] = (
        "archive_storage_qualification_only"
    )
    direct_bronze_qualification: Literal[False] = False
    payload_bytes_read_locally: Literal[False] = False
    source_origin_acquisition_evidenced: Literal[False] = False
    admission_lifecycle_evidenced: Literal[False] = False
    source_date_semantics_qualified: Literal[False] = False
    m112_federation_accepted: Literal[False] = False


def _receipt(*, retrieved_at: datetime) -> SourceReceipt:
    """Rebuild the original metadata receipt from committed identity evidence."""

    payload = PayloadEvidence(sha256=SOURCE_SHA256, byte_count=SOURCE_BYTES)
    return SourceReceipt(
        receipt_id=f"hosted-legacy:{SOURCE_ID}:{SOURCE_SHA256}",
        source=SourceIdentity(
            catalog_id=SOURCE_ID,
            source_id=SOURCE_ID,
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="July 2024 MBS Group P7 genetics workbook",
            catalog_version="legacy-donor-20260829",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(ARCHIVE_URI),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=payload,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(
            "https://github.com/edithatogo/global-medicines-atlas/issues/340"
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id=(f"{SOURCE_ID}-exact-legacy-qualification-v1"),
            transformation_sha256=TRANSFORMATION_SHA256,
            output_sha256=payload.sha256,
            output_byte_count=payload.byte_count,
        ),
    )


def _load_json_object(path: Path) -> dict[str, object]:
    """Load one JSON object with a narrowed mapping type."""

    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return cast("dict[str, object]", value)


def reconcile_p7_storage_receipt(root: Path) -> P7ReceiptReconciliation:
    """Match the prior hosted receipt digest and retain its qualification limit.

    Args:
        root: Repository root containing the archived qualification records.

    Returns:
        A typed reconciliation that does not promote the archive receipt.

    Raises:
        ValueError: If any committed identity or receipt digest differs.
    """

    storage = _load_json_object(root / STORAGE_QUALIFICATION)
    if (
        storage.get("sha256") != SOURCE_SHA256
        or storage.get("bytes") != SOURCE_BYTES
        or storage.get("workflow_commit") != WORKFLOW_COMMIT
        or storage.get("workflow_run") != WORKFLOW_RUN
        or storage.get("retrieved_at") != "2026-08-30T09:58:12+00:00"
    ):
        raise ValueError("P7 storage qualification identity changed")
    details = storage.get("storage_qualification")
    if not isinstance(details, dict):
        raise TypeError("P7 storage qualification details are missing")
    details = cast("dict[str, object]", details)
    if (
        details.get("source_sha256") != SOURCE_SHA256
        or details.get("source_receipt_sha256") != EXPECTED_RECEIPT_SHA256
        or details.get("qualification") != "storage_candidate_only"
        or details.get("domain_mapping_qualified") is not False
        or details.get("publication_performed") is not False
    ):
        raise ValueError("P7 storage receipt evidence changed")
    archive = _load_json_object(root / PUBLIC_ARCHIVE_QUALIFICATION)
    payloads_value = archive.get("raw_payloads")
    if not isinstance(payloads_value, list):
        raise TypeError("P7 archive raw payload list is missing")
    payloads = cast("list[object]", payloads_value)
    payload_match = False
    for item in payloads:
        if not isinstance(item, dict):
            continue
        row = cast("dict[str, object]", item)
        if (
            row.get("source_id") == SOURCE_ID
            and row.get("sha256") == SOURCE_SHA256
            and row.get("bytes") == SOURCE_BYTES
        ):
            payload_match = True
            break
    if not payload_match:
        raise ValueError("P7 exact public archive object is not corroborated")
    if (
        archive.get("dataset") != "edithatogo/australian-mbs-source-archive"
        or archive.get("immutable_revision")
        != "4d1dae488ac43522f20e8320a8b2a56bf9138341"
        or archive.get("anonymous_clean_room_restore") is not True
    ):
        raise ValueError("P7 archive identity or restore evidence changed")
    retrieved_at = datetime.fromisoformat(cast("str", storage["retrieved_at"]))
    receipt = _receipt(retrieved_at=retrieved_at)
    receipt_digest = receipt.digest()
    recorded_digest = cast("str", details["source_receipt_sha256"])
    if receipt_digest != recorded_digest:
        raise ValueError("reconstructed P7 receipt digest does not match")
    return P7ReceiptReconciliation(
        retrieved_at=retrieved_at,
        reconstructed_receipt_sha256=receipt_digest,
        recorded_receipt_sha256=recorded_digest,
    )


def dump_reconciliation(value: P7ReceiptReconciliation) -> str:
    """Serialize a reconciliation as stable JSON."""

    return (
        json.dumps(
            value.model_dump(mode="json"),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def write_reconciliation(root: Path) -> P7ReceiptReconciliation:
    """Write the verified reconciliation under its fixed qualification path."""
    value = reconcile_p7_storage_receipt(root)
    path = root / (
        "quality/qualifications/"
        "mbs-p7-storage-receipt-reconciliation-20261003.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_reconciliation(value), encoding="utf-8")
    return value
