"""Prepare B2 external-reference rows from the approved M-112 event import.

This is a metadata-only projection. It never downloads or validates source
payload bytes, and it does not create native source, storage, rights, or
admission receipts.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, cast

from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceManifest,
    RawEvidenceRecord,
    build_raw_evidence_reference_from_acquisition,
)
from global_medicines_atlas.receipts import AcquisitionEvent

ROOT = Path(__file__).resolve().parents[1]
IMPORT_PATH = Path(
    "quality/qualifications/"
    "australian-mbs-utilisation-raw-reference-import-20261004.json"
)
ACQUISITION_IMPORT_PATH = Path(
    "quality/qualifications/"
    "australian-mbs-utilisation-acquisition-import-20261004.json"
)
GENERATOR_PATH = Path("scripts/prepare_m112_imported_b2_manifest.py")
OUTPUT_PATH = Path(
    "quality/bronze/imported-raw-evidence/"
    "australian-mbs-utilisation-20261017.json"
)
QUALIFICATION_PATH = Path(
    "quality/qualifications/"
    "australian-mbs-utilisation-b2-reference-reconciliation-20261017.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def resolve_repo_file(root: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"path must stay within repository: {relative_path}")
    repository = root.resolve()
    resolved = (repository / candidate).resolve(strict=True)
    try:
        resolved.relative_to(repository)
    except ValueError as error:
        raise ValueError(
            f"path resolves outside repository: {relative_path}"
        ) from error
    if not resolved.is_file():
        raise ValueError(f"expected repository file: {relative_path}")
    return resolved


def _read_records(document: dict[str, Any], label: str) -> list[dict[str, Any]]:
    records = document.get("records")
    if not isinstance(records, list) or any(
        not isinstance(record, dict) for record in records
    ):
        raise TypeError(f"{label} records have invalid shape")
    return cast("list[dict[str, Any]]", records)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pinned_external_url(
    raw_reference: dict[str, Any], relative_record_path: Path
) -> str:
    dataset = raw_reference.get("dataset")
    object_path = raw_reference.get("path")
    if (
        not isinstance(dataset, str)
        or re.fullmatch(r"[^/\s]+/[^/\s]+", dataset) is None
    ):
        raise ValueError(
            f"raw reference dataset identity is invalid: {relative_record_path}"
        )
    if (
        not isinstance(object_path, str)
        or PurePosixPath(object_path).is_absolute()
        or ".." in PurePosixPath(object_path).parts
        or any(character in object_path for character in "\\?#")
    ):
        raise ValueError(
            f"raw reference object path is invalid: {relative_record_path}"
        )
    revision = raw_reference.get("revision")
    if (
        not isinstance(revision, str)
        or re.fullmatch(r"[0-9a-f]{40}", revision) is None
    ):
        raise ValueError(
            f"raw reference revision is not an immutable commit: {relative_record_path}"
        )
    expected_url = (
        "https://huggingface.co/datasets/"
        f"{dataset}/resolve/{revision}/{object_path}"
    )
    if raw_reference.get("state") != "immutable_public_archive_reference":
        raise ValueError(f"raw reference is not pinned: {relative_record_path}")
    if raw_reference.get("url") != expected_url:
        raise ValueError(
            f"raw reference URL does not match pinned identity: {relative_record_path}"
        )
    return expected_url


def _build_binding(
    root: Path,
    item: dict[str, Any],
    acquisition_records: dict[str, dict[str, Any]],
) -> tuple[RawEvidenceRecord, dict[str, Any]]:
    if not isinstance(item.get("path"), str):
        raise TypeError("raw-reference import record has no path")
    relative_record_path = Path(item["path"])
    raw_record_bytes = resolve_repo_file(
        root, str(relative_record_path)
    ).read_bytes()
    if _sha256(raw_record_bytes) != item.get("sha256"):
        raise ValueError(
            f"raw-reference import digest mismatch: {relative_record_path}"
        )
    raw_record = _read_json(resolve_repo_file(root, str(relative_record_path)))

    event_binding = raw_record.get("acquisition_event")
    raw_reference = raw_record.get("raw_reference")
    if not isinstance(event_binding, dict) or not isinstance(
        raw_reference, dict
    ):
        raise TypeError(
            f"raw-reference binding missing: {relative_record_path}"
        )
    event_path_text = event_binding.get("path")
    if not isinstance(event_path_text, str):
        raise TypeError(
            f"acquisition-event path missing: {relative_record_path}"
        )
    event_path = Path(event_path_text)
    event_bytes = resolve_repo_file(root, event_path_text).read_bytes()
    event_sha = _sha256(event_bytes)
    if event_sha != event_binding.get("sha256"):
        raise ValueError(f"acquisition-event digest mismatch: {event_path}")

    import_record = acquisition_records.get(
        str(event_binding.get("acquisition_id"))
    )
    if import_record is None or import_record.get("event_path") != str(
        event_path
    ):
        raise ValueError(
            f"event is not bound by acquisition import: {event_path}"
        )
    if import_record.get("event_sha256") != event_sha:
        raise ValueError(f"imported event digest mismatch: {event_path}")

    event = AcquisitionEvent.model_validate(json.loads(event_bytes))
    expected_url = _pinned_external_url(raw_reference, relative_record_path)
    if (
        event.acquisition_id != event_binding.get("acquisition_id")
        or event.acquisition_id != import_record.get("acquisition_id")
        or event.content_id != raw_reference.get("sha256")
        or event.payload_sha256 != raw_reference.get("sha256")
    ):
        raise ValueError(f"B1 and B2 content identities diverge: {event_path}")

    row = build_raw_evidence_reference_from_acquisition(
        event,
        external_reference=expected_url,
    )
    binding = {
        "acquisition_id": event.acquisition_id,
        "content_id": event.content_id,
        "event_path": str(event_path),
        "event_sha256": event_sha,
        "raw_reference_import_path": str(relative_record_path),
        "raw_reference_import_sha256": item["sha256"],
        "external_reference": expected_url,
        "expected_payload_sha256": raw_reference["sha256"],
        "expected_byte_count": raw_reference["byte_count"],
        "anonymous_digest_evidence": raw_reference["anonymous_digest_evidence"],
        "rights_reference_present": isinstance(
            raw_record.get("rights_reference"), dict
        ),
    }
    return row, binding


def build_reconciliation(
    root: Path = ROOT,
) -> tuple[RawEvidenceManifest, dict[str, Any]]:
    import_bytes = resolve_repo_file(root, str(IMPORT_PATH)).read_bytes()
    import_doc = _read_json(resolve_repo_file(root, str(IMPORT_PATH)))
    acquisition_import_bytes = resolve_repo_file(
        root, str(ACQUISITION_IMPORT_PATH)
    ).read_bytes()
    acquisition_import = _read_json(
        resolve_repo_file(root, str(ACQUISITION_IMPORT_PATH))
    )
    generator_sha = _sha256(
        resolve_repo_file(root, str(GENERATOR_PATH)).read_bytes()
    )
    import_records = _read_records(
        import_doc, "historical raw-reference import"
    )
    acquisition_import_records = _read_records(
        acquisition_import, "historical acquisition import"
    )

    acquisition_records = {
        str(record["acquisition_id"]): record
        for record in acquisition_import_records
        if isinstance(record.get("acquisition_id"), str)
    }
    bindings_by_id: dict[str, dict[str, Any]] = {}
    rows: list[RawEvidenceRecord] = []
    for item in import_records:
        row, binding = _build_binding(root, item, acquisition_records)
        if row.acquisition_id in bindings_by_id:
            raise ValueError(
                f"duplicate acquisition event: {row.acquisition_id}"
            )
        bindings_by_id[row.acquisition_id] = binding
        rows.append(row)

    manifest = RawEvidenceManifest.from_rows(tuple(rows))
    qualification = {
        "schema_id": "global-medicines-atlas.australian-mbs-utilisation-b2-reference-reconciliation",
        "schema_version": 1,
        "recorded_at": "2026-10-16T22:48:47Z",
        "status": "historical_b1_to_b2_references_bound_native_lifecycle_open",
        "input": {
            "path": str(IMPORT_PATH),
            "sha256": _sha256(import_bytes),
        },
        "generator": {
            "path": str(GENERATOR_PATH),
            "sha256": generator_sha,
        },
        "acquisition_import": {
            "path": str(ACQUISITION_IMPORT_PATH),
            "sha256": _sha256(acquisition_import_bytes),
        },
        "output": {
            "path": str(OUTPUT_PATH),
            "manifest_sha256": manifest.manifest_sha256,
            "row_count": manifest.row_count,
        },
        "scope": {
            "approved_m112_denominator": 1759,
            "selected_historical_mbs_utilisation_objects": len(bindings_by_id),
            "selection_is_full_denominator": False,
        },
        "records": [bindings_by_id[key] for key in sorted(bindings_by_id)],
        "counts": {
            "b1_b2_reference_bindings": len(bindings_by_id),
            "native_source_receipts": 0,
            "native_payload_storage_receipts": 0,
            "admission_histories": 0,
        },
        "boundaries": {
            "source_payload_bytes_read": False,
            "source_payload_values_read": False,
            "new_acquisition_performed": False,
            "native_source_receipts_created": False,
            "native_payload_storage_receipts_created": False,
            "durable_replication_qualified": False,
            "processing_admitted": False,
            "v4_admission": False,
            "consumer_canaries": False,
            "m112_federation_accepted": False,
        },
        "interpretation": (
            "The 14 historical acquisition events are bound to B2 external-reference "
            "rows using their exact imported content IDs and revision-pinned public "
            "locators. This metadata projection does not create native source or "
            "storage receipts, qualify replication, establish new remote digest "
            "readback, grant rights, or admit the objects."
        ),
    }
    return manifest, qualification


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest, qualification = build_reconciliation()
    manifest_bytes = manifest.canonical_json()
    qualification_bytes = (
        json.dumps(qualification, indent=2, sort_keys=True) + "\n"
    ).encode()
    output = ROOT / OUTPUT_PATH
    qualification_path = ROOT / QUALIFICATION_PATH
    if args.check:
        if not output.is_file() or output.read_bytes() != manifest_bytes:
            raise SystemExit(f"stale or missing B2 manifest: {OUTPUT_PATH}")
        if (
            not qualification_path.is_file()
            or qualification_path.read_bytes() != qualification_bytes
        ):
            raise SystemExit(
                f"stale or missing qualification: {QUALIFICATION_PATH}"
            )
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(manifest_bytes)
    qualification_path.write_bytes(qualification_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
