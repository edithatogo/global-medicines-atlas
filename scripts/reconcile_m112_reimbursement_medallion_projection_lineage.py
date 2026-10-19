"""Qualify pinned reimbursement-atlas medallion projection lineage."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.request import Request, urlopen

from pydantic import AnyUrl

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
)
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    RawEvidenceRecord,
    RawEvidenceState,
)
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    HttpRetrievalEvidence,
    RetrievalEvidence,
    RightsState,
    acquisition_event_id_for,
)

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
BASE = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "pbs-pdf-archive-lineage.json"
)
OUTPUT = QUAL / (
    "australian-m112-reimbursement-medallion-projection-lineage-20261019.json"
)
OVERLAY_OUTPUT = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "reimbursement-medallion-projection-lineage.json"
)
DATASET = "edithatogo/reimbursement-atlas"
DATASET_REVISION = "8e062578f14e12cf3238700a93946339da9c5d88"
PRODUCER_REPOSITORY = "edithatogo/reimbursement-atlas"
PRODUCER_REVISION = "083be8aa4ff0f8d8e6df5c5d8242f7783be149de"
EXPECTED_DENOMINATOR = 1759
EXPECTED_COMPLETE_PROJECTIONS = 10
EXPECTED_INCOMPLETE_PROJECTIONS = 13
MAX_FILE_BYTES = 5_000_000
TIMEOUT_SECONDS = 90
HTTP_OK = 200
CMS_SOURCE_ID = "us_cms_hcpcs_level_ii"
CMS_SOURCE_VERSION = "us_cms_hcpcs_level_ii_2026_07"
CMS_SOURCE_URL = (
    "https://www.cms.gov/files/zip/july-2026-alpha-numeric-hcpcs-file.zip"
)
CMS_SOURCE_SHA256 = (
    "5591fed257e4d2307c1d2dc9c66abc8e346b1f4c076e9e48559799e2de14b70a"
)
CMS_REPORT_SHA256 = (
    "5f7e0027f11cbb1b4f948bff80866bb4a1d739a7757900adc5a39c6713a874a4"
)
CMS_REPORT_PATH = (
    "data/derived/reviewed_source_bundles/"
    "snapshot_us_cms_hcpcs_level_ii_2026_07_5591fed257e4/validation_report.json"
)
SOURCE_REGISTRY_PATH = "data/seed/source_registry.jsonl"
SOURCE_REGISTRY_SHA256 = (
    "4ee107f5f451d2e7149f534c8a2ba5b7a6ce22ec32d54fd13048561512c63ab8"
)
SOURCE_REGISTRY_BYTES = 41734
ACTOR = "global-medicines-atlas:m112-cms-hcpcs-lineage"
PBS_DATASET = "edithatogo/australian-pbs-source-archive"
PBS_REVISION = "48fd7345fb09277bb5b85644dba72804633a2abb"
PBS_OUTPUT_PATH = "bronze/2026-04-01/pbs-v3-source.parquet"
PBS_OUTPUT_SHA256 = (
    "9e9facc336b47c5a9d514388a95c9797ba3e03474806fba00b6f03c0e601e97d"
)
PBS_OUTPUT_BYTES = 158134
PBS_INPUT_PATH = "raw/2026-04-01/2026-04-01-XML-V3.zip"
PBS_INPUT_SHA256 = (
    "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
)
PBS_INPUT_BYTES = 11156706
PBS_TREE_INVENTORY = (
    QUAL / "australian-m112-current-tree-object-inventory-20261004.json"
)

EXPECTED_OUTPUTS: dict[str, tuple[str, int, int, str]] = {
    "catalogue_b0": (
        "c27b998f9425714c42da0a9c8192e6fb5a613031210548cc0eb8b44388aaa8c4",
        27219,
        64,
        "data/derived/medallion/bronze_source_index.jsonl",
    ),
    "acquisition_b1": (
        "0bd2f7661037b620a21943ed6d7f2dd28a93437d43072d6ceabf3411b5840da1",
        1820758,
        2076,
        "data/derived/medallion/bronze_acquisition_ledger.jsonl",
    ),
    "evidence_b2": (
        "d7d33a8b0b6bd5cf507639286348b53e79d76e59347ef9575ff555a1e66f68c5",
        1767273,
        2056,
        "data/derived/medallion/bronze_evidence.jsonl",
    ),
    "silver": (
        "299b3721f72af235dc80a9b96f590a39ef8fe0b683618764ad56af713e1848a1",
        12732,
        17,
        "data/derived/medallion/medallion_artifacts.jsonl",
    ),
    "gold": (
        "a4d3a99d9b6db9dff6a9e267e73806460b082d8ee8fbdefb55a3c7d077d85532",
        3267,
        2,
        "data/derived/medallion/medallion_artifacts.jsonl",
    ),
    "platinum": (
        "82aa16098cbbdedb8d6583caf367c8a41b34ca00f448e354a3921b12592dc9d6",
        2088,
        3,
        "data/derived/medallion/medallion_artifacts.jsonl",
    ),
    "lineage": (
        "9d73e2f79b44f221486b4ad0e1df576cdbd18763d1aa3fa7adb8e6fe526e639f",
        10763,
        17,
        "data/derived/field_lineage/field_lineage.jsonl",
    ),
    "promotion_decisions": (
        "03036720150f163e471445b594d21eeb51f95e4bd7db1070b74afc27b7d8c5c7",
        1321055,
        2145,
        "data/derived/medallion/promotion_decisions.jsonl",
    ),
    "pbs_pdf_provenance": (
        "24cb8c98f8a09f943ef3369ec63b9a2f7b3e19bfca7cf2a7ec64e1a78dcf4e07",
        871678,
        1049,
        "data/derived/publication/pbs_provenance/pbs_pdf_provenance.jsonl",
    ),
    "pbs_structured_provenance": (
        "fab87f283f31f51db1f5f1bee76b02c3fbe5622bea1deee4632be0ff4768a28c",
        548634,
        655,
        "data/derived/publication/pbs_provenance/pbs_structured_provenance.jsonl",
    ),
    "pbs_archive_verification": (
        "7cea95acfde2f023a8a3b84628b7bcd70a023ab1ebde3d5ac0449eedb36a5f8d",
        811545,
        1049,
        "data/derived/publication/pbs_provenance/pbs_archive_verification.jsonl",
    ),
    "pbs_archive_variants": (
        "e9059e17bf78c099f0350610487bbc78e5b51c8e9d49726b0b117e01e3c4d0db",
        4340,
        5,
        "data/derived/publication/pbs_provenance/pbs_archive_variants.jsonl",
    ),
}

EXACT_COPY_CONFIGS = frozenset({
    "catalogue_b0",
    "acquisition_b1",
    "evidence_b2",
    "lineage",
    "promotion_decisions",
    "pbs_pdf_provenance",
    "pbs_structured_provenance",
    "pbs_archive_verification",
    "pbs_archive_variants",
})
PARTITION_CONFIGS = frozenset({"silver", "gold", "platinum"})
COMPLETE_CONFIGS = EXACT_COPY_CONFIGS | PARTITION_CONFIGS


def _object(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {context}")
    return cast("dict[str, Any]", value)


def _rows(data: bytes, context: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.splitlines(), start=1):
        if not line:
            continue
        try:
            result.append(_object(json.loads(line), f"{context}:{line_number}"))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(
                f"invalid JSONL row: {context}:{line_number}"
            ) from exc
    return result


def _read(path: Path) -> dict[str, Any]:
    return _object(
        json.loads((ROOT / path).read_text(encoding="utf-8")), str(path)
    )


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fetch(url: str) -> bytes:
    request = Request(  # ruff: ignore[suspicious-url-open-usage] -- caller supplies only pinned HTTPS metadata URLs
        url, headers={"User-Agent": "gma-m112-lineage/1"}
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # ruff: ignore[suspicious-url-open-usage] -- pinned public metadata only
        body = response.read(MAX_FILE_BYTES + 1)
    if len(body) > MAX_FILE_BYTES:
        raise ValueError("pinned metadata exceeds the readback size bound")
    return body


def _stream_sha256(url: str) -> dict[str, Any]:
    """Hash one public source response without retaining or parsing its bytes."""
    observed_at = datetime.now(UTC)
    request = Request(  # ruff: ignore[suspicious-url-open-usage] -- URL comes from the exact pinned official source version
        url, headers={"User-Agent": "gma-m112-lineage/1"}
    )
    digest = hashlib.sha256()
    byte_count = 0
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # ruff: ignore[suspicious-url-open-usage] -- exact official source URL from the pinned source version
        status = response.status
        final_url = response.geturl()
        content_length = response.headers.get("Content-Length")
        content_type = response.headers.get("Content-Type")
        content_encoding = response.headers.get("Content-Encoding")
        etag = response.headers.get("ETag")
        last_modified = response.headers.get("Last-Modified")
        while chunk := response.read(64 * 1024):
            byte_count += len(chunk)
            if byte_count > MAX_FILE_BYTES:
                raise ValueError("CMS source exceeds the readback size bound")
            digest.update(chunk)
    return {
        "observed_at": observed_at,
        "http_status": status,
        "final_url": final_url,
        "content_length": int(content_length) if content_length else None,
        "content_type": content_type,
        "content_encoding": content_encoding,
        "etag": etag,
        "last_modified": last_modified,
        "byte_count": byte_count,
        "sha256": digest.hexdigest(),
    }


def _cms_bronze_artifacts(  # ruff: ignore[too-many-locals] -- one acquisition binds B1, B2 and admission
    readback: dict[str, Any], source_version_row: dict[str, Any]
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Create reference-only B1/B2 records for the exact indexed CMS version."""
    retrieved_at = cast("datetime", readback["observed_at"])
    digest = cast("str", readback["sha256"])
    byte_count = cast("int", readback["byte_count"])
    if not all((
        digest == CMS_SOURCE_SHA256,
        source_version_row.get("checksum_sha256") == digest,
        source_version_row.get("source_id") == CMS_SOURCE_ID,
        source_version_row.get("id") == CMS_SOURCE_VERSION,
        source_version_row.get("source_url") == CMS_SOURCE_URL,
        cast("int", readback["http_status"]) == HTTP_OK,
        byte_count > 0,
    )):
        raise ValueError(
            "CMS readback does not match its pinned source version"
        )

    acquisition_id = acquisition_event_id_for(
        source_id=CMS_SOURCE_ID,
        payload_sha256=digest,
        retrieved_at=retrieved_at,
        source_version=CMS_SOURCE_VERSION,
        original_uri=CMS_SOURCE_URL,
    )
    event = AcquisitionEvent(
        acquisition_id=acquisition_id,
        content_id=digest,
        source_id=CMS_SOURCE_ID,
        source_version=CMS_SOURCE_VERSION,
        retrieved_at=retrieved_at,
        payload_sha256=digest,
        retrieval=RetrievalEvidence(
            uri=AnyUrl(CMS_SOURCE_URL),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
            http=HttpRetrievalEvidence(
                original_uri=AnyUrl(CMS_SOURCE_URL),
                final_uri=AnyUrl(cast("str", readback["final_url"])),
                http_method="GET",
                http_status=200,
                content_length=readback["content_length"],
                content_type=readback["content_type"],
                content_encoding=readback["content_encoding"],
                etag=readback["etag"],
                last_modified=readback["last_modified"],
                observed_byte_length=byte_count,
                source_native_version=CMS_SOURCE_VERSION,
                acquisition_agent_version="m112-cms-hcpcs-lineage-readback-v1",
            ),
        ),
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.HISTORICAL,
    )
    event_path = Path(
        "quality/bronze/imported-acquisitions/us-cms-hcpcs/"
        f"{acquisition_id}.json"
    )
    event_bytes = event.canonical_json() + b"\n"

    b2_record = RawEvidenceRecord(
        source_id=CMS_SOURCE_ID,
        acquisition_id=acquisition_id,
        content_id=digest,
        kind=RawEvidenceKind.PAYLOAD,
        state=RawEvidenceState.EXTERNAL_REFERENCE_ONLY,
        external_reference=CMS_SOURCE_URL,
        payload_contents_in_metadata=False,
    )
    b2_manifest = RawEvidenceManifest.from_rows((b2_record,))
    b2_path = Path(
        "quality/bronze/raw-evidence/us-cms-hcpcs/"
        f"{acquisition_id}/manifest.json"
    )
    b2_bytes = b2_manifest.canonical_json()

    admission = create_admission_decision(
        acquisition_id=acquisition_id,
        content_id=digest,
        state=BronzeAdmissionState.LANDED,
        reason_codes=(
            "exact_existing_source_version_retrieved",
            "rights_unresolved",
            "unreviewed_not_admitted_to_processing",
        ),
        validation_results=(
            ValidationResult(
                check_id="source-version-digest-and-observed-size",
                passed=True,
                message=(
                    "streamed SHA-256 matches the pinned source-version "
                    "checksum; observed response byte count is recorded"
                ),
            ),
        ),
        reviewer_status="unreviewed",
        actor=ACTOR,
        decided_at=retrieved_at,
    )
    admission_path = Path(
        "quality/bronze/admissions/us-cms-hcpcs/"
        f"{acquisition_id}/{admission.decision_id}.json"
    )
    admission_bytes = admission.model_dump_json().encode() + b"\n"
    artifacts = {
        event_path.as_posix(): event_bytes,
        b2_path.as_posix(): b2_bytes,
        admission_path.as_posix(): admission_bytes,
    }
    bindings = {path: _sha(data) for path, data in artifacts.items()}
    return artifacts, {
        "source_id": CMS_SOURCE_ID,
        "source_version": CMS_SOURCE_VERSION,
        "content_sha256": digest,
        "byte_count": byte_count,
        "rights_state": "unknown",
        "admission_state": "landed",
        "reviewer_status": "unreviewed",
        "v4_admission": False,
        "consumer_canary": False,
        "payload_persisted": False,
        "payload_values_inspected": False,
        "acquisition_id": acquisition_id,
        "event_path": event_path.as_posix(),
        "b2_manifest_path": b2_path.as_posix(),
        "admission_path": admission_path.as_posix(),
        "output_bindings": bindings,
    }


def reuse_cms_readback() -> (
    tuple[dict[str, Any], dict[str, Any], dict[str, bytes]] | None
):
    """Reuse an already persisted readback instead of creating duplicate B1 events."""
    path = ROOT / OUTPUT
    if not path.exists():
        return None
    report = _read(OUTPUT)
    lineage = report.get("lineage_inputs", {})
    readback = lineage.get("cms_b1_b2_readback")
    bronze = report.get("cms_bronze_records")
    if not isinstance(readback, dict) or not isinstance(bronze, dict):
        return None
    readback = cast("dict[str, Any]", readback)
    bronze = cast("dict[str, Any]", bronze)
    observed_at = readback.get("observed_at")
    output_bindings = bronze.get("output_bindings")
    if not isinstance(observed_at, str) or not isinstance(
        output_bindings, dict
    ):
        return None
    output_bindings = cast("dict[str, Any]", output_bindings)
    artifacts: dict[str, bytes] = {}
    for relative_path, expected_digest in output_bindings.items():
        artifact_path = ROOT / relative_path
        if not artifact_path.is_file():
            continue
        content = artifact_path.read_bytes()
        if _sha(content) == expected_digest:
            artifacts[relative_path] = content
    if set(artifacts) != set(output_bindings) or not all((
        readback.get("sha256") == CMS_SOURCE_SHA256,
        readback.get("byte_count", 0) > 0,
        readback.get("http_status") == HTTP_OK,
        readback.get("payload_persisted") is False,
        readback.get("payload_values_inspected") is False,
        bronze.get("source_id") == CMS_SOURCE_ID,
        bronze.get("source_version") == CMS_SOURCE_VERSION,
        bronze.get("content_sha256") == CMS_SOURCE_SHA256,
        bronze.get("payload_persisted") is False,
    )):
        return None
    readback_value = dict(readback)
    readback_value["observed_at"] = datetime.fromisoformat(observed_at)
    return readback_value, bronze, artifacts


def _dataset_url(path: str) -> str:
    return _dataset_url_for(DATASET, DATASET_REVISION, path)


def _dataset_url_for(dataset: str, revision: str, path: str) -> str:
    return (
        f"https://huggingface.co/datasets/{dataset}/resolve/{revision}/{path}"
    )


def _producer_url(path: str) -> str:
    return (
        f"https://raw.githubusercontent.com/{PRODUCER_REPOSITORY}/"
        f"{PRODUCER_REVISION}/{path}"
    )


def _assert_identity(
    data: bytes, *, digest: str, byte_count: int, context: str
) -> None:
    if len(data) != byte_count or _sha(data) != digest:
        raise ValueError(f"exact digest or byte count mismatch: {context}")


def _verify_record_joins(  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- verifies independent B0/B1/B2 and derivative joins
    projection_rows: dict[str, list[dict[str, Any]]],
    inventory: list[dict[str, Any]],
    *,
    cms_source_sha256: str,
) -> dict[str, Any]:
    acquisitions = projection_rows["acquisition_b1"]
    evidence = projection_rows["evidence_b2"]
    catalogue = projection_rows["catalogue_b0"]
    event_ids = {row.get("event_id") for row in acquisitions}
    acquisition_ids = {row.get("acquisition_id") for row in acquisitions}
    payload_digests = {
        row.get("payload_sha256")
        for row in acquisitions
        if isinstance(row.get("payload_sha256"), str)
    }
    evidence_digests = {
        row.get("payload_sha256")
        for row in evidence
        if isinstance(row.get("payload_sha256"), str)
    }
    if len(event_ids) != len(acquisitions):
        raise ValueError("producer B1 event identifiers are not unique")
    if (
        len(evidence) != len(evidence_digests)
        or evidence_digests - payload_digests
    ):
        raise ValueError(
            "producer B2 rows do not resolve to B1 payload digests"
        )
    if len(evidence_digests) != len(evidence):
        raise ValueError("producer B2 contains duplicate payload digests")
    if any(
        row.get("acquisition_id") not in acquisition_ids for row in evidence
    ):
        raise ValueError("producer B2 acquisition reference lacks a B1 row")

    raw_by_digest = {
        row.get("identity", {}).get("sha256"): row
        for row in inventory
        if row.get("candidate_class") == "raw_source_payload"
    }
    archive_variants = projection_rows["pbs_archive_variants"]
    variant_matches = [
        raw_by_digest.get(row.get("checksum_sha256"))
        for row in archive_variants
    ]
    if any(row is None for row in variant_matches) or any(
        not row.get("b1_b2_lineage", {}).get("complete")
        for row in variant_matches
        if row is not None
    ):
        raise ValueError(
            "an archive variant lacks a complete frozen B1/B2 join"
        )

    failed_events = {
        row.get("source_version_id")
        for row in acquisitions
        if row.get("outcome") == "failed" and not row.get("payload_sha256")
    }
    provenance_counts: dict[str, dict[str, int]] = {}
    for name in (
        "pbs_pdf_provenance",
        "pbs_archive_verification",
        "pbs_structured_provenance",
    ):
        rows = projection_rows[name]
        digests = [
            row.get("checksum_sha256") or row.get("local_checksum_sha256")
            for row in rows
        ]
        bound = sum(
            isinstance(digest, str)
            and digest in payload_digests
            and digest in evidence_digests
            for digest in digests
        )
        no_digest = [
            row
            for row, digest in zip(rows, digests, strict=True)
            if not isinstance(digest, str)
        ]
        failed_bound = sum(
            row.get("source_version_id") in failed_events for row in no_digest
        )
        if bound + failed_bound != len(rows):
            raise ValueError(
                f"provenance rows lack B1/B2 or failed-event join: {name}"
            )
        provenance_counts[name] = {
            "rows": len(rows),
            "payload_digest_b1_b2_joins": bound,
            "failed_b1_event_joins_without_payload": failed_bound,
        }

    source_ids = {row.get("source_id") for row in catalogue}
    acquired_source_ids = {
        row.get("source_id") for row in acquisitions if row.get("source_id")
    }
    catalogue_statuses = {
        row.get("source_id"): row.get("acquisition_status") for row in catalogue
    }
    for source_id, status in catalogue_statuses.items():
        if (status == "acquired") != (source_id in acquired_source_ids):
            raise ValueError(
                "B0 acquisition status disagrees with B1 source IDs"
            )
        if status not in {"acquired", "not_attempted"}:
            raise ValueError("B0 contains an unclassified acquisition state")

    gold_platinum_ids = {
        row.get("artifact_id")
        for name in ("gold", "platinum")
        for row in projection_rows[name]
    }
    promotion_subjects = [
        row.get("subject_id") for row in projection_rows["promotion_decisions"]
    ]
    resolved_subjects = sum(
        subject in acquisition_ids
        or (
            isinstance(subject, str)
            and subject.startswith("catalog_")
            and subject.removeprefix("catalog_") in source_ids
        )
        or subject in gold_platinum_ids
        for subject in promotion_subjects
    )
    if resolved_subjects != len(promotion_subjects):
        raise ValueError(
            "promotion decision has no exact B0/B1/product subject"
        )

    artifacts = [
        row for name in PARTITION_CONFIGS for row in projection_rows[name]
    ]
    artifact_hashes = {
        row.get("sha256") for row in artifacts if row.get("sha256")
    }
    silver_inputs = {
        digest
        for row in projection_rows["silver"]
        for digest in row.get("input_sha256", [])
    }
    b0_metadata_inputs = silver_inputs & {SOURCE_REGISTRY_SHA256}
    b1_b2_inputs = silver_inputs & payload_digests
    cms_report_input = silver_inputs & {CMS_REPORT_SHA256}
    if cms_report_input and cms_source_sha256 == CMS_SOURCE_SHA256:
        b1_b2_inputs |= cms_report_input
    missing_silver_inputs = sorted(
        silver_inputs - b0_metadata_inputs - b1_b2_inputs
    )
    if b0_metadata_inputs != {SOURCE_REGISTRY_SHA256} or missing_silver_inputs:
        raise ValueError("Silver inputs do not resolve to B0 or B1/B2 evidence")
    gold_input_hashes = {
        digest
        for row in projection_rows["gold"]
        for digest in row.get("input_sha256", [])
    }
    silver_output_hashes = {
        row.get("sha256") for row in projection_rows["silver"]
    }
    platinum_input_hashes = {
        digest
        for row in projection_rows["platinum"]
        for digest in row.get("input_sha256", [])
    }
    gold_output_hashes = {row.get("sha256") for row in projection_rows["gold"]}
    if gold_input_hashes != silver_output_hashes:
        raise ValueError("Gold artifacts do not bind the exact Silver outputs")
    if platinum_input_hashes != gold_output_hashes:
        raise ValueError(
            "Platinum artifacts do not bind the exact Gold outputs"
        )

    return {
        "b0_catalogue": {
            "rows": len(catalogue),
            "acquired_source_ids_linked_to_b1": len(
                source_ids & acquired_source_ids
            ),
            "not_attempted_source_ids_explicit": sum(
                status == "not_attempted"
                for status in catalogue_statuses.values()
            ),
        },
        "b1_b2": {
            "b1_acquisition_events": len(acquisitions),
            "b1_events_with_payload_sha256": sum(
                isinstance(row.get("payload_sha256"), str)
                for row in acquisitions
            ),
            "unique_b1_payload_sha256": len(payload_digests),
            "b2_evidence_records": len(evidence),
            "b2_payload_digests_linked_to_b1": len(evidence_digests),
            "b1_failed_or_blocked_without_payload": sum(
                not row.get("payload_sha256") for row in acquisitions
            ),
        },
        "archive_variants": {
            "producer_rows": len(archive_variants),
            "exact_frozen_raw_paths_with_complete_lineage": len(
                variant_matches
            ),
        },
        "source_provenance_tables": provenance_counts,
        "promotion_decisions": {
            "rows": len(promotion_subjects),
            "subjects_resolved_to_b0_b1_or_product_artifacts": resolved_subjects,
        },
        "artifact_partitions": {
            "silver_records": len(projection_rows["silver"]),
            "gold_records": len(projection_rows["gold"]),
            "platinum_records": len(projection_rows["platinum"]),
            "unique_silver_input_sha256": len(silver_inputs),
            "silver_input_sha256_linked_to_b1": len(
                silver_inputs & payload_digests
            ),
            "silver_input_sha256_linked_to_b1_b2_including_cms": len(
                b1_b2_inputs
            ),
            "cms_validation_report_inputs_linked_to_raw_b1_b2": len(
                cms_report_input
            ),
            "silver_input_sha256_linked_to_b0_metadata": len(
                b0_metadata_inputs
            ),
            "silver_input_sha256_unresolved": missing_silver_inputs,
            "gold_inputs_linked_to_silver_outputs": len(gold_input_hashes),
            "platinum_inputs_linked_to_gold_outputs": len(
                platinum_input_hashes
            ),
            "all_artifact_output_sha256": len(artifact_hashes),
        },
        "lineage_rows": len(projection_rows["lineage"]),
    }


def _verify_pbs_source_parquet(  # ruff: ignore[too-many-branches,too-many-locals] -- validates immutable projection, receipt and admission identities
    base: dict[str, Any],
) -> dict[str, Any]:
    """Bind the PBS Parquet LFS identity to its admitted raw B2 source."""
    key = (PBS_DATASET, PBS_REVISION, PBS_OUTPUT_PATH)
    inventory = cast("list[dict[str, Any]]", base["objects"])
    target = next(
        (
            row
            for row in inventory
            if (row.get("dataset"), row.get("revision"), row.get("path")) == key
        ),
        None,
    )
    if target is None or not all((
        target.get("candidate_class") == "existing_data_projection",
        target.get("b1_b2_lineage", {}).get("complete") is False,
        target.get("identity", {}).get("sha256") == PBS_OUTPUT_SHA256,
        target.get("identity", {}).get("byte_count") == PBS_OUTPUT_BYTES,
    )):
        raise ValueError("frozen PBS Parquet projection identity changed")

    tree = _read(PBS_TREE_INVENTORY)
    observations = tree.get("observations")
    if not isinstance(observations, list):
        raise TypeError("PBS current-tree observations are missing")
    observations = cast("list[object]", observations)
    matching_observations: list[dict[str, Any]] = []
    for row in observations:
        if not isinstance(row, dict):
            continue
        observation = cast("dict[str, Any]", row)
        if (
            observation.get("dataset") == PBS_DATASET
            and observation.get("revision") == PBS_REVISION
            and observation.get("path") == PBS_OUTPUT_PATH
        ):
            matching_observations.append(observation)
    if len(matching_observations) != 1:
        raise ValueError("PBS Parquet tree identity is not unique")
    observed = matching_observations[0]
    expected_tree_sha = target["identity"]["tree_inventory_evidence"]["sha256"]
    if not all((
        tree["schema_id"]
        == "global-medicines-atlas.australian-m112-current-tree-object-metadata-inventory",
        _sha((ROOT / PBS_TREE_INVENTORY).read_bytes()) == expected_tree_sha,
        observed.get("git_blob_oid_match") is True,
        observed.get("byte_count_match") is True,
        observed.get("lfs_sha256_match") is True,
        observed.get("observed_git_blob_oid")
        == target["identity"]["git_blob_oid"],
        observed.get("observed_bytes") == PBS_OUTPUT_BYTES,
        observed.get("observed_lfs_sha256") == PBS_OUTPUT_SHA256,
    )):
        raise ValueError(
            "PBS Parquet LFS tree evidence does not match frozen identity"
        )

    manifest_bytes = _fetch(
        _dataset_url_for(PBS_DATASET, PBS_REVISION, "manifest.json")
    )
    manifest = _object(
        json.loads(manifest_bytes), "PBS source archive manifest"
    )
    output = _object(
        manifest.get("source_parquet"), "PBS Parquet manifest output"
    )
    source = _object(manifest.get("archive"), "PBS raw source archive")
    source_receipt_ref = _object(
        manifest.get("source_receipt"), "PBS source receipt reference"
    )
    admission_ref = _object(
        manifest.get("admission"), "PBS admission reference"
    )
    if not all((
        manifest.get("destination_dataset") == PBS_DATASET,
        manifest.get("parquet_is_rebuildable_projection") is True,
        manifest.get("raw_bytes_are_source_of_truth") is True,
        manifest.get("amt_terminology_bytes_included") is False,
        output.get("path") == PBS_OUTPUT_PATH,
        output.get("sha256") == PBS_OUTPUT_SHA256,
        output.get("size_bytes") == PBS_OUTPUT_BYTES,
        source.get("path") == PBS_INPUT_PATH,
        source.get("sha256") == PBS_INPUT_SHA256,
        source.get("size_bytes") == PBS_INPUT_BYTES,
    )):
        raise ValueError(
            "PBS manifest does not bind the exact projection and raw input"
        )

    raw_parent = next(
        (
            row
            for row in cast("list[dict[str, Any]]", base["objects"])
            if row.get("dataset") == PBS_DATASET
            and row.get("revision") == PBS_REVISION
            and row.get("path") == PBS_INPUT_PATH
        ),
        None,
    )
    if raw_parent is None or not all((
        raw_parent.get("candidate_class") == "raw_source_payload",
        raw_parent.get("identity", {}).get("sha256") == PBS_INPUT_SHA256,
        raw_parent.get("identity", {}).get("byte_count") == PBS_INPUT_BYTES,
        raw_parent.get("b1_b2_lineage", {}).get("complete") is True,
    )):
        raise ValueError(
            "PBS Parquet raw source lacks complete frozen B1/B2 lineage"
        )

    receipt_bytes = _fetch(
        _dataset_url_for(
            PBS_DATASET,
            PBS_REVISION,
            cast("str", source_receipt_ref.get("path")),
        )
    )
    if _sha(receipt_bytes) != source_receipt_ref.get("sha256"):
        raise ValueError(
            "PBS source receipt digest does not match its manifest"
        )
    receipt = _object(json.loads(receipt_bytes), "PBS canonical source receipt")
    receipt_payload = _object(receipt.get("payload"), "PBS receipt payload")
    receipt_temporal = _object(receipt.get("temporal"), "PBS receipt temporal")
    receipt_source = _object(receipt.get("source"), "PBS receipt source")
    if not all((
        source_receipt_ref.get("path")
        == "bronze/2026-04-01/source-receipt.json",
        receipt_payload.get("sha256") == PBS_INPUT_SHA256,
        receipt_payload.get("byte_count") == PBS_INPUT_BYTES,
        receipt_source.get("source_id") == manifest.get("source_id"),
        receipt_temporal.get("acquisition_id")
        == source_receipt_ref.get("acquisition_id"),
        receipt.get("rights_state") == "permitted",
        receipt.get("retrieval", {}).get("status") == "succeeded",
    )):
        raise ValueError("PBS receipt does not bind its B1 input identity")

    admission_bytes = _fetch(
        _dataset_url_for(
            PBS_DATASET, PBS_REVISION, cast("str", admission_ref.get("path"))
        )
    )
    if _sha(admission_bytes) != admission_ref.get("sha256"):
        raise ValueError(
            "PBS landed-admission digest does not match its manifest"
        )
    admission = _object(json.loads(admission_bytes), "PBS source admission")
    if not all((
        admission.get("state") == "accepted",
        admission.get("acquisition_id")
        == source_receipt_ref.get("acquisition_id"),
        admission.get("content_id") == PBS_INPUT_SHA256,
    )):
        raise ValueError("PBS admission does not bind the exact B1/B2 source")

    return {
        "dataset": PBS_DATASET,
        "revision": PBS_REVISION,
        "projection_path": PBS_OUTPUT_PATH,
        "projection_sha256": PBS_OUTPUT_SHA256,
        "projection_byte_count": PBS_OUTPUT_BYTES,
        "projection_git_blob_oid": observed["observed_git_blob_oid"],
        "lfs_pointer_readback": True,
        "source_of_truth_path": PBS_INPUT_PATH,
        "source_of_truth_sha256": PBS_INPUT_SHA256,
        "source_of_truth_byte_count": PBS_INPUT_BYTES,
        "source_b1_acquisition_id": source_receipt_ref["acquisition_id"],
        "source_receipt_path": source_receipt_ref["path"],
        "source_receipt_sha256": source_receipt_ref["sha256"],
        "source_admission_path": admission_ref["path"],
        "source_admission_sha256": admission_ref["sha256"],
        "source_admission_state": admission["state"],
        "raw_parent_b1_b2_lineage": raw_parent["b1_b2_lineage"],
        "source_rights_evidence": receipt["rights_state"],
        "m112_rights_state_changed": False,
        "payload_values_inspected": False,
        "payload_persisted_locally": False,
        "lineage_complete": True,
    }


def build_report() -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- one deterministic report binds the full pinned object set
    """Fetch and qualify the exact pinned producer and dataset projections."""
    base = _read(BASE)
    base_objects = cast("list[dict[str, Any]]", base["objects"])
    totals = base["updated_gate_totals"]
    if not all((
        base["scope"]["approved_denominator"] == EXPECTED_DENOMINATOR,
        totals["complete_projection_lineage"] == EXPECTED_COMPLETE_PROJECTIONS,
        len([
            row
            for row in base_objects
            if (
                row.get("candidate_class") == "existing_data_projection"
                and not row["b1_b2_lineage"]["complete"]
            )
        ])
        == EXPECTED_INCOMPLETE_PROJECTIONS,
        base["scope"]["denominator_changed"] is False,
    )):
        raise ValueError("frozen M-112 baseline changed")

    manifest_bytes = _fetch(_dataset_url("medallion_manifest.json"))
    manifest = _object(json.loads(manifest_bytes), "medallion manifest")
    configs = manifest.get("configs")
    if not isinstance(configs, list):
        raise TypeError("producer medallion config collection is not a list")
    configs = cast("list[object]", configs)
    if len(configs) != len(EXPECTED_OUTPUTS):
        raise ValueError("producer medallion config denominator changed")

    inventory = base_objects
    pbs_projection_lineage = _verify_pbs_source_parquet(base)
    by_key = {
        (row.get("dataset"), row.get("revision"), row.get("path")): row
        for row in inventory
    }
    report_rows: list[dict[str, Any]] = []
    parsed_outputs: dict[str, list[dict[str, Any]]] = {}
    source_cache: dict[str, bytes] = {}
    seen: set[str] = set()
    artifact_source_rows: list[dict[str, Any]] | None = None

    for raw in configs:
        config = _object(raw, "medallion config")
        name = config.get("config_name")
        if not isinstance(name, str) or name not in EXPECTED_OUTPUTS:
            raise ValueError("unexpected medallion config")
        expected_sha, expected_bytes, expected_rows, expected_source = (
            EXPECTED_OUTPUTS[name]
        )
        path = config.get("path")
        source_path = config.get("source_path")
        if not isinstance(path, str) or not isinstance(source_path, str):
            raise TypeError(f"manifest paths are not strings: {name}")
        key = (DATASET, DATASET_REVISION, path)
        target = by_key.get(key)
        if not all((
            name not in seen,
            path == f"data/medallion/{name}/data.jsonl",
            source_path == expected_source,
            config.get("sha256") == expected_sha,
            config.get("row_count") == expected_rows,
            target is not None,
            target is not None and target["identity"]["sha256"] == expected_sha,
            target is not None
            and target["identity"]["byte_count"] == expected_bytes,
            target is not None and target["b1_b2_lineage"]["complete"] is False,
        )):
            raise ValueError(f"manifest or frozen identity changed: {name}")
        seen.add(name)
        output_bytes = _fetch(_dataset_url(path))
        _assert_identity(
            output_bytes,
            digest=expected_sha,
            byte_count=expected_bytes,
            context=f"dataset output {name}",
        )
        output_rows = _rows(output_bytes, path)
        if len(output_rows) != expected_rows:
            raise ValueError(f"output row count changed: {name}")
        parsed_outputs[name] = output_rows
        if source_path not in source_cache:
            source_cache[source_path] = _fetch(_producer_url(source_path))
        source_bytes = source_cache[source_path]
        source_rows = _rows(source_bytes, source_path)
        source_sha = _sha(source_bytes)
        source_count = len(source_rows)

        if name in EXACT_COPY_CONFIGS:
            if output_bytes != source_bytes:
                raise ValueError(
                    f"projection differs from exact producer file: {name}"
                )
            relation = "byte_identical_to_exact_producer_source_path"
        else:
            if artifact_source_rows is None:
                artifact_source_rows = source_rows
            layer_rows = [
                row for row in source_rows if row.get("layer") == name
            ]
            if output_rows != layer_rows:
                raise ValueError(
                    f"layer partition differs from source artifacts: {name}"
                )
            relation = "exact_layer_partition_of_medallion_artifacts"

        report_rows.append({
            "config_name": name,
            "dataset_path": path,
            "dataset_sha256": expected_sha,
            "dataset_byte_count": expected_bytes,
            "row_count": expected_rows,
            "producer_source_path": source_path,
            "producer_source_sha256": source_sha,
            "producer_source_byte_count": len(source_bytes),
            "producer_source_row_count": source_count,
            "projection_relation": relation,
            "b1_b2_lineage_complete": name in COMPLETE_CONFIGS,
        })

    if seen != set(EXPECTED_OUTPUTS):
        raise ValueError("producer config set is incomplete")
    source_versions_path = "data/seed/source_versions.jsonl"
    source_versions_bytes = _fetch(_producer_url(source_versions_path))
    source_version_rows = _rows(source_versions_bytes, source_versions_path)
    source_version_matches = [
        row
        for row in source_version_rows
        if row.get("source_id") == CMS_SOURCE_ID
        and row.get("id") == CMS_SOURCE_VERSION
    ]
    if len(source_version_matches) != 1:
        raise ValueError("pinned CMS source version is not unique")
    source_version_row = source_version_matches[0]
    if not all((
        source_version_row.get("checksum_sha256") == CMS_SOURCE_SHA256,
        source_version_row.get("source_url") == CMS_SOURCE_URL,
        source_version_row.get("retrieved_at") == "2026-07-23T00:00:00Z",
    )):
        raise ValueError("CMS source-version metadata changed")

    validation_report_bytes = _fetch(_producer_url(CMS_REPORT_PATH))
    _assert_identity(
        validation_report_bytes,
        digest=CMS_REPORT_SHA256,
        byte_count=886,
        context="CMS validation report",
    )
    validation_report = _object(
        json.loads(validation_report_bytes), "CMS validation report"
    )
    if not all((
        validation_report.get("source_id") == CMS_SOURCE_ID,
        validation_report.get("source_version_id") == CMS_SOURCE_VERSION,
        validation_report.get("source_url") == CMS_SOURCE_URL,
        validation_report.get("raw_sha256") == CMS_SOURCE_SHA256,
        validation_report.get("raw_file_copied") is False,
        validation_report.get("review_required_before_publication") is True,
    )):
        raise ValueError("CMS validation report does not bind its raw input")

    source_registry_bytes = _fetch(_producer_url(SOURCE_REGISTRY_PATH))
    _assert_identity(
        source_registry_bytes,
        digest=SOURCE_REGISTRY_SHA256,
        byte_count=SOURCE_REGISTRY_BYTES,
        context="B0 source registry metadata",
    )
    prior_readback = reuse_cms_readback()
    if prior_readback is None:
        cms_readback = _stream_sha256(CMS_SOURCE_URL)
        cms_artifacts, cms_bronze = _cms_bronze_artifacts(
            cms_readback, source_version_row
        )
    else:
        cms_readback, cms_bronze, cms_artifacts = prior_readback
    joins = _verify_record_joins(
        parsed_outputs, inventory, cms_source_sha256=CMS_SOURCE_SHA256
    )
    unresolved: list[str] = []
    report = {
        "schema_id": "global-medicines-atlas.australian-m112-reimbursement-medallion-projection-lineage",
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "scope": {
            "dataset": DATASET,
            "dataset_revision": DATASET_REVISION,
            "producer_repository": PRODUCER_REPOSITORY,
            "producer_revision": PRODUCER_REVISION,
            "frozen_inventory_count": EXPECTED_DENOMINATOR,
            "reimbursement_projection_path_count": len(EXPECTED_OUTPUTS),
            "additional_pbs_projection_path_count": 1,
            "projection_path_count": len(EXPECTED_OUTPUTS) + 1,
            "new_sources_added": False,
            "producer_repository_modified": False,
            "payload_values_inspected": False,
        },
        "manifest": {
            "path": "medallion_manifest.json",
            "sha256": _sha(manifest_bytes),
            "config_count": len(configs),
        },
        "lineage_inputs": {
            "source_registry_b0": {
                "producer_path": SOURCE_REGISTRY_PATH,
                "producer_sha256": SOURCE_REGISTRY_SHA256,
                "producer_byte_count": SOURCE_REGISTRY_BYTES,
                "lineage_role": "B0 source registry metadata",
            },
            "cms_validation_report": {
                "producer_path": CMS_REPORT_PATH,
                "producer_sha256": CMS_REPORT_SHA256,
                "producer_byte_count": len(validation_report_bytes),
                "raw_source_sha256": CMS_SOURCE_SHA256,
                "raw_file_copied_by_producer": False,
                "review_required_before_publication": True,
            },
            "cms_source_version": {
                "producer_path": source_versions_path,
                "producer_file_sha256": _sha(source_versions_bytes),
                "source_id": CMS_SOURCE_ID,
                "source_version": CMS_SOURCE_VERSION,
                "source_url": CMS_SOURCE_URL,
                "producer_retrieved_at": source_version_row.get("retrieved_at"),
                "producer_checksum_sha256": CMS_SOURCE_SHA256,
            },
            "cms_b1_b2_readback": {
                "observed_at": cms_readback["observed_at"]
                .isoformat()
                .replace("+00:00", "Z"),
                "http_status": cms_readback["http_status"],
                "final_url": cms_readback["final_url"],
                "sha256": cms_readback["sha256"],
                "byte_count": cms_readback["byte_count"],
                "payload_persisted": False,
                "payload_values_inspected": False,
                "source_owner_modified": False,
                "rights_state": "unknown",
                "admission_state": "landed",
                "reviewer_status": "unreviewed",
                "acquisition_id": cms_bronze["acquisition_id"],
                "event_path": cms_bronze["event_path"],
                "b2_manifest_path": cms_bronze["b2_manifest_path"],
                "admission_path": cms_bronze["admission_path"],
                "output_bindings": cms_bronze["output_bindings"],
            },
        },
        "objects": report_rows,
        "pbs_source_parquet_lineage": pbs_projection_lineage,
        "record_joins": joins,
        "lineage_disposition": {
            "complete_configs": sorted(COMPLETE_CONFIGS),
            "incomplete_configs": unresolved,
            "incomplete_reason": None,
            "unresolved_input_sha256": joins["artifact_partitions"][
                "silver_input_sha256_unresolved"
            ],
        },
        "boundaries": {
            "rights_changed": False,
            "v4_admission_performed": False,
            "consumer_canaries_performed": False,
            "public_publication": False,
            "denominator_changed": False,
            "pbs_parquet_payload_bytes_read": False,
        },
    }
    report["cms_bronze_records"] = cms_bronze
    overlay = _build_overlay(base, report)
    overlay["cms_input_lineage_increment"] = {
        "source_id": CMS_SOURCE_ID,
        "source_version": CMS_SOURCE_VERSION,
        "source_sha256": CMS_SOURCE_SHA256,
        "source_byte_count": cms_readback["byte_count"],
        "source_owner_repository_modified": False,
        "rights_state": "unknown",
        "landed_but_unreviewed": True,
        "v4_admission": False,
        "consumer_canary": False,
    }
    overlay["pbs_source_parquet_lineage_increment"] = {
        "qualification_path": OUTPUT.as_posix(),
        "dataset": PBS_DATASET,
        "revision": PBS_REVISION,
        "projection_path": PBS_OUTPUT_PATH,
        "lineage_complete": True,
        "rights_changed": False,
        "v4_admission": False,
        "consumer_canary": False,
    }
    return report, overlay, cms_artifacts


def _build_overlay(
    base: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any]:
    overlay = copy.deepcopy(base)
    evidence = {
        "path": OUTPUT.as_posix(),
        "sha256": _sha(
            (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
        ),
    }
    complete = set(report["lineage_disposition"]["complete_configs"])
    for row in overlay["objects"]:
        if (
            row.get("candidate_class") != "existing_data_projection"
            or row.get("dataset") != DATASET
            or row.get("revision") != DATASET_REVISION
        ):
            continue
        name = (
            row["path"]
            .removeprefix("data/medallion/")
            .removesuffix("/data.jsonl")
        )
        if name not in EXPECTED_OUTPUTS:
            continue
        row["b1_b2_lineage"] = {
            "complete": name in complete,
            "evidence": evidence,
            "state": (
                "complete: exact producer source path and pinned projection "
                "are bound; all applicable B1/B2 references resolve"
                if name in complete
                else "unresolved: exact producer-to-projection or B1/B2 "
                "parent evidence is incomplete"
            ),
        }

    pbs = report["pbs_source_parquet_lineage"]
    pbs_target = next(
        (
            row
            for row in overlay["objects"]
            if row.get("dataset") == pbs["dataset"]
            and row.get("revision") == pbs["revision"]
            and row.get("path") == pbs["projection_path"]
        ),
        None,
    )
    if (
        pbs_target is None
        or pbs_target["b1_b2_lineage"]["complete"] is not False
    ):
        raise ValueError("frozen PBS projection state changed")
    pbs_target["b1_b2_lineage"] = {
        "complete": True,
        "evidence": evidence,
        "state": (
            "complete: pinned LFS digest and manifest bind this rebuildable "
            "projection to its exact source archive receipt, admission, and "
            "frozen raw B1/B2 lineage"
        ),
    }

    count = sum(
        row.get("candidate_class") == "existing_data_projection"
        and row.get("b1_b2_lineage", {}).get("complete")
        for row in overlay["objects"]
    )
    if count != EXPECTED_COMPLETE_PROJECTIONS + len(complete) + 1:
        raise ValueError("projection lineage total changed unexpectedly")
    overlay["lineage_counts_after_expansion"].update({
        "complete_projection_lineages": count,
        "incomplete_projection_lineages": 23 - count,
        "complete_lineage_objects": (
            overlay["lineage_counts_after_expansion"]["complete_raw_lineages"]
            + count
        ),
    })
    overlay["updated_gate_totals"].update({
        "complete_projection_lineage": count,
        "complete_b1_b2_lineage_objects": (
            overlay["lineage_counts_after_expansion"][
                "complete_lineage_objects"
            ]
        ),
    })
    overlay["projection_b1_b2_lineage_expansion"] = {
        "previous_complete_projections": EXPECTED_COMPLETE_PROJECTIONS,
        "new_complete_projections": len(complete) + 1,
        "complete_projections_after_expansion": count,
        "incomplete_projections_after_expansion": 23 - count,
        "qualification_path": OUTPUT.as_posix(),
        "qualification_sha256": evidence["sha256"],
    }
    return overlay


def main() -> None:
    """Write the exact projection-lineage qualification and inventory overlay."""
    report, overlay, artifacts = build_report()
    for relative_path, payload in artifacts.items():
        target_path = ROOT / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists() and target_path.read_bytes() != payload:
            raise ValueError(f"append-only evidence collision: {relative_path}")
        target_path.write_bytes(payload)
    for path, value in ((OUTPUT, report), (OVERLAY_OUTPUT, overlay)):
        (ROOT / path).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        "complete projection lineages: "
        f"{overlay['updated_gate_totals']['complete_projection_lineage']}"
    )
    print(
        "incomplete projection lineages: "
        f"{overlay['lineage_counts_after_expansion']['incomplete_projection_lineages']}"
    )


if __name__ == "__main__":
    main()
