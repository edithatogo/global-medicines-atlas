"""Validate one PBS listing-to-public-B1-receipt metadata binding."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, cast

HTTP_OK = 200
PBS_RECEIPT_PATH = "bronze/2026-04-01/source-receipt.json"
PBS_RECEIPT_ACQUISITION_ID = (
    "7c964aef63666d334fafd9a461f5a4f8476018a4da5809cf8fefe3a6b8bee727"
)
PBS_RECEIPT_SHA256 = (
    "a5eb06cf7e655eb0e0d8fe5d244297721ebede51e96c237333f7dffd76e1ccd1"
)
PBS_RECEIPT_BYTES = 3143
PBS_RECEIPT_ID = (
    "hosted-pbs-v3:f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20:"
    "2026-08-30T03:31:25+00:00"
)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return cast("dict[str, Any]", value)


def _unique_matching(
    values: object, predicate: Callable[[object], bool], label: str
) -> dict[str, Any]:
    if not isinstance(values, list):
        raise TypeError(f"{label} must be a list")
    matches = [
        _mapping(value, label)
        for value in cast("list[object]", values)
        if predicate(value)
    ]
    if len(matches) != 1:
        raise ValueError(f"{label} must contain exactly one matching row")
    return matches[0]


def validate_pbs_receipt_binding(  # ruff: ignore[too-many-branches, too-many-locals, too-many-statements] -- every source identity is independently checked
    schedule_index_value: object,
    source_identities_value: object,
    m112_value: object,
    readback_value: object,
    rights_value: object,
) -> dict[str, Any]:
    """Bind a public PBS listing URL to its observed manifest and B1 metadata.

    This validates metadata only. It does not verify upstream licence terms,
    inspect source bytes, or admit the object to M-112 v4.
    """
    schedule_index = _mapping(schedule_index_value, "PBS schedule index")
    source_identities = _mapping(
        source_identities_value, "M-109 source-era identities"
    )
    m112 = _mapping(m112_value, "M-112 per-object report")
    readback = _mapping(readback_value, "anonymous public readback")
    rights = _mapping(rights_value, "PBS source-rights entry")

    if (
        readback.get("schema_id")
        != "global-medicines-atlas.australian-pbs-m107-known-object-manifest-readback"
        or readback.get("schema_version") != 1
        or readback.get("status")
        != "anonymous_manifest_and_source_receipt_metadata_readback"
    ):
        raise ValueError("PBS public readback schema or status is unsupported")
    canonical_source = dict(readback)
    canonical_digest = canonical_source.pop("canonical_sha256", None)
    canonical_byte_count = canonical_source.pop("canonical_byte_count", None)
    canonical_bytes = json.dumps(
        canonical_source,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if canonical_digest != hashlib.sha256(
        canonical_bytes
    ).hexdigest() or canonical_byte_count != len(canonical_bytes):
        raise ValueError("PBS public readback self-digest is invalid")
    boundary = _mapping(readback.get("request_boundary"), "request boundary")
    if (
        boundary.get("authenticated") is not False
        or boundary.get("source_payload_requested") is not False
        or boundary.get("source_payload_read") is not False
        or boundary.get("only_manifest_and_b1_receipt_metadata_read")
        is not True
    ):
        raise ValueError(
            "PBS public readback exceeds its metadata-only boundary"
        )

    manifest = _mapping(readback.get("manifest"), "manifest metadata")
    official = _mapping(readback.get("official_object"), "official object")
    archive = _mapping(official.get("archive"), "archive identity")
    receipt = _mapping(readback.get("source_receipt"), "source receipt")
    manifest_receipt_reference = _mapping(
        readback.get("manifest_source_receipt"),
        "manifest source receipt reference",
    )
    receipt_metadata = _mapping(
        readback.get("source_receipt_metadata_readback"),
        "source receipt metadata readback",
    )
    payload = _mapping(receipt.get("payload"), "receipt payload")
    bronze_admission = _mapping(
        readback.get("bronze_admission"), "Bronze admission metadata"
    )
    if (
        readback.get("dataset")  # ruff: ignore[too-many-boolean-expressions] -- independent manifest and receipt gates
        != "edithatogo/australian-pbs-source-archive"
        or manifest.get("path") != "manifest.json"
        or manifest.get("http_status") != HTTP_OK
        or not isinstance(manifest.get("sha256"), str)
        or manifest.get("byte_count", 0) <= 0
        or receipt.get("http_status") != HTTP_OK
        or receipt.get("receipt_type") != "source"
        or receipt.get("retrieval_status") != "succeeded"
        or bronze_admission.get("state") != "accepted"
    ):
        raise ValueError(
            "PBS public manifest or receipt readback is incomplete"
        )
    expected_manifest_receipt_reference = {
        "acquisition_id": PBS_RECEIPT_ACQUISITION_ID,
        "path": PBS_RECEIPT_PATH,
        "retrieved_at": "2026-08-30T03:31:25+00:00",
        "sha256": PBS_RECEIPT_SHA256,
    }
    expected_receipt_metadata = {
        "anonymous": True,
        "byte_count": PBS_RECEIPT_BYTES,
        "http_status": HTTP_OK,
        "sha256": PBS_RECEIPT_SHA256,
    }
    if (
        manifest_receipt_reference != expected_manifest_receipt_reference  # ruff: ignore[too-many-boolean-expressions] -- all independent receipt-reference bindings are mandatory
        or receipt_metadata != expected_receipt_metadata
        or receipt.get("path") != manifest_receipt_reference.get("path")
        or receipt.get("sha256") != manifest_receipt_reference.get("sha256")
        or receipt.get("acquisition_id")
        != manifest_receipt_reference.get("acquisition_id")
        or receipt.get("receipt_id") != PBS_RECEIPT_ID
        or receipt.get("retrieved_at") != "2026-08-30T03:31:25Z"
    ):
        raise ValueError(
            "PBS receipt does not match the pinned manifest receipt reference"
        )

    link = _unique_matching(
        [
            link
            for page in cast(
                "list[object]", schedule_index.get("year_pages", [])
            )
            for link in _mapping(page, "PBS year page").get(
                "schedule_data_links", []
            )
        ],
        lambda value: (
            isinstance(value, dict)
            and cast("dict[str, Any]", value).get(
                "effective_date_from_page_heading"
            )
            == "2026-04-01"
            and cast("dict[str, Any]", value).get("format_label_classification")
            == "xml_v3"
        ),
        "April 2026 PBS XML V3 listing",
    )

    pbs_identity = _mapping(source_identities.get("readback"), "readback")
    pbs_readback = _mapping(pbs_identity.get("pbs"), "PBS identity readback")
    pbs_source = _unique_matching(
        _mapping(source_identities.get("pbs"), "PBS identities").get("sources"),
        lambda value: (
            isinstance(value, dict)
            and cast("dict[str, Any]", value).get("source_era")
            == "2026-04-01-xml-v3"
        ),
        "April 2026 PBS source identity",
    )
    identity_archive = _mapping(pbs_source.get("archive"), "identity archive")
    if (
        readback.get("revision") != pbs_readback.get("current_revision")  # ruff: ignore[too-many-boolean-expressions] -- all index, identity, and manifest fields must agree
        or manifest.get("sha256") != pbs_readback.get("manifest_sha256")
        or manifest.get("byte_count") != pbs_readback.get("manifest_bytes")
        or official.get("source_id") != pbs_source.get("source_id")
        or official.get("source_effective_date")
        != pbs_source.get("effective_at")
        or official.get("source_url") != link.get("url")
        or archive.get("path") != identity_archive.get("path")
        or archive.get("sha256") != identity_archive.get("sha256")
        or archive.get("size_bytes") != identity_archive.get("bytes")
    ):
        raise ValueError(
            "PBS public manifest does not match official link and identity"
        )

    m112_object = _unique_matching(
        m112.get("objects"),
        lambda value: (
            isinstance(value, dict)
            and cast("dict[str, Any]", value).get("dataset")
            == readback.get("dataset")
            and cast("dict[str, Any]", value).get("path") == archive.get("path")
        ),
        "M-112 PBS raw object",
    )
    identity = _mapping(m112_object.get("identity"), "M-112 object identity")
    if identity.get("anonymous_digest_readback") is not True:
        raise ValueError(
            "PBS M-112 object lacks anonymous raw-object digest readback"
        )
    if (
        m112_object.get("revision") != readback.get("revision")
        or identity.get("sha256") != archive.get("sha256")
        or identity.get("byte_count") != archive.get("size_bytes")
        or identity.get("current_tree_path_present") is not True
    ):
        raise ValueError(
            "PBS M-112 raw object identity differs from public manifest"
        )

    receipt_urls = (
        official.get("source_url"),
        receipt.get("retrieval_uri"),
        receipt.get("original_uri"),
        receipt.get("final_uri"),
    )
    receipt_identity = (
        receipt.get("source_id"),
        official.get("source_id"),
        payload.get("sha256"),
        archive.get("sha256"),
        payload.get("byte_count"),
        archive.get("size_bytes"),
        receipt.get("acquisition_id"),
        manifest_receipt_reference.get("acquisition_id"),
    )
    if len(set(receipt_urls)) != 1:
        raise ValueError("PBS source URL bindings do not match exactly")
    if (
        receipt_identity[0] != "au-pbs-historical-xml"  # ruff: ignore[too-many-boolean-expressions] -- every B1 identity field is required
        or receipt_identity[0] != receipt_identity[1]
        or receipt_identity[2] != receipt_identity[3]
        or receipt_identity[4] != receipt_identity[5]
        or receipt_identity[6] != receipt_identity[7]
        or receipt.get("sha256") != PBS_RECEIPT_SHA256
        or receipt.get("path") != PBS_RECEIPT_PATH
    ):
        raise ValueError(
            "PBS receipt payload identities do not match the archive"
        )

    if (
        rights.get("source_id") != "au-pbs-historical-xml"
        or rights.get("disposition") != "catalogue_only"
        or rights.get("redistribute") != "unknown"
    ):
        rights_status = "source_rights_ledger_requires_current_reconciliation"
    elif receipt.get("rights_state_claimed_by_receipt") == "permitted":
        rights_status = "receipt_permitted_claim_source_ledger_unknown"
    else:
        rights_status = "source_rights_terms_unresolved"

    return {
        "status": "exact_official_url_to_b1_receipt_metadata",
        "official_url": official.get("source_url"),
        "source_effective_date": official.get("source_effective_date"),
        "dataset": readback.get("dataset"),
        "revision": readback.get("revision"),
        "manifest": {
            "path": manifest.get("path"),
            "sha256": manifest.get("sha256"),
            "byte_count": manifest.get("byte_count"),
        },
        "archive": {
            "path": archive.get("path"),
            "sha256": archive.get("sha256"),
            "byte_count": archive.get("size_bytes"),
        },
        "b1_receipt": {
            "path": receipt.get("path"),
            "sha256": receipt.get("sha256"),
            "receipt_id": receipt.get("receipt_id"),
            "acquisition_id": receipt.get("acquisition_id"),
            "retrieved_at": receipt.get("retrieved_at"),
            "payload_sha256": payload.get("sha256"),
            "payload_byte_count": payload.get("byte_count"),
            "rights_state_claimed_by_receipt": receipt.get(
                "rights_state_claimed_by_receipt"
            ),
        },
        "bronze_admission_state": bronze_admission.get("state"),
        "m112_object_remains_deferred": (
            m112_object.get("disposition") == "deferred_not_admitted"
        ),
        "m112_b1_b2_lineage_complete": (
            _mapping(m112_object.get("b1_b2_lineage"), "B1/B2 lineage").get(
                "complete"
            )
            is True
        ),
        "rights_reconciliation_status": rights_status,
        "m112_v4_admission": m112_object.get("v4_admission"),
        "m112_consumer_canary": m112_object.get("consumer_canary"),
        "boundaries": {
            "source_payload_requested": False,
            "source_payload_read": False,
            "source_rights_concluded": False,
            "m107_accepted": False,
            "m112_v4_admission": False,
        },
    }
