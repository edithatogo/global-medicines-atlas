#!/usr/bin/env python3
"""Qualify the exact approved international public archive as Bronze B2."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast

from pydantic import AnyUrl

from global_medicines_atlas.bronze_landing import (
    BronzeLanding,
    SourceRecordBatch,
    land_bronze_payload,
)
from global_medicines_atlas.bronze_raw_evidence import build_document_manifest
from global_medicines_atlas.bronze_recovery import reconstruct_bronze
from global_medicines_atlas.international_public_archive import SOURCE_RIGHTS
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    DataSensitivity,
    EvidenceClass,
    PayloadEvidence,
    PersonalDataState,
    PublicationDisposition,
    RetrievalEvidence,
    RightsState,
    SensitivityClassification,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
    require_temporal,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import (
    ReuseCandidateKind,
    ReuseDisposition,
    ReuseGateDecision,
    evaluate_reuse_gate,
)
from global_medicines_atlas.source_catalog import (
    MedicineDataSource,
    load_source_catalog,
)
from global_medicines_atlas.union_register_acquisition import (
    union_register_source_record_batch,
)
from global_medicines_atlas.us_live_bronze import copy_evidentiary_truth

ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_RECEIPT = (
    ROOT
    / "quality/qualifications/international-public-huggingface-20260821.json"
)
DATASET = "edithatogo/global-medicines-atlas-international-permissive-20260821"
REVISION = "e6aa97ffe46eb32a41d7c73550fbd52811a9701b"
DERIVED_ONLY_SOURCE_IDS = frozenset({"global-rxnorm", "us-rxnorm-api"})
MANIFEST_NAME = "international-public-bronze-qualification.json"
RIGHTS_REFERENCES = {
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "Etalab-2.0": "https://www.etalab.gouv.fr/licence-ouverte-open-licence/",
    "OGL-3.0": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
    "OGL-3.0-with-exclusions": "https://www.nhsbsa.nhs.uk/our-policies/copyright",
}


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _verify_public_revision(
    input_dir: Path, publication_receipt_path: Path
) -> tuple[dict[str, object], ...]:
    publication = cast(
        "dict[str, object]",
        json.loads(publication_receipt_path.read_text(encoding="utf-8")),
    )
    expected_ids = sorted(SOURCE_RIGHTS)
    expected_identity = {
        "dataset": DATASET,
        "immutable_revision": REVISION,
        "archived_source_count": len(expected_ids),
        "source_ids": expected_ids,
    }
    if (
        any(
            publication.get(key) != value
            for key, value in expected_identity.items()
        )
        or publication.get("repository_private") is not False
        or publication.get("repository_gated") is not False
    ):
        raise ValueError("international publication identity drifted")
    manifest_path = input_dir / "manifest.json"
    if _digest(manifest_path) != publication.get("manifest_sha256"):
        raise ValueError("international public manifest digest drifted")
    manifest = cast(
        "dict[str, object]",
        json.loads(manifest_path.read_text(encoding="utf-8")),
    )
    files = cast("list[dict[str, object]]", manifest.get("files"))
    if (
        manifest.get("schema_id")
        != "global-medicines-atlas.international-public-archive"
        or manifest.get("archived_source_count") != len(expected_ids)
        or manifest.get("coverage_complete") is not False
        or len(files) != publication.get("file_count")
        or {str(item.get("source_id")) for item in files} != set(expected_ids)
    ):
        raise ValueError("international public archive inventory drifted")
    observed_paths: set[str] = set()
    for item in files:
        relative = str(item.get("path"))
        path = input_dir / relative
        source_id = str(item.get("source_id"))
        if (
            relative in observed_paths
            or item.get("rights") != SOURCE_RIGHTS[source_id]
            or not path.is_file()
            or path.stat().st_size != item.get("byte_count")
            or _digest(path) != item.get("sha256")
        ):
            raise ValueError("international archive file drifted")
        observed_paths.add(relative)
    return tuple(files)


def _source_record_factory(
    source_id: str, payload: bytes, media_hint: str
) -> SourceRecordBatch | None:
    return union_register_source_record_batch(source_id, payload, media_hint)


def _landing_media_hint(path: Path) -> str:
    """Keep legacy Latin-1 text opaque until a source schema is reviewed."""
    media_hint = path.suffix.lstrip(".") or "bin"
    return "bin" if media_hint == "txt" else media_hint


def _archive_candidate(
    source_id: str,
    paths: tuple[str, ...],
    catalog: tuple[MedicineDataSource, ...],
) -> tuple[ReuseGateDecision, str]:
    decision = evaluate_reuse_gate(
        source_id,
        repository_root=ROOT,
        catalog=catalog,
        huggingface_index={DATASET: paths},
        github_index={},
        requested=ReuseDisposition.LINK,
    )
    matches = tuple(
        candidate
        for candidate in decision.candidates
        if candidate.surface == "hugging_face"
        and candidate.kind is ReuseCandidateKind.PAYLOAD
        and DATASET in candidate.locator
    )
    if len(matches) != 1 or matches[0].revision != REVISION:
        raise ValueError("international reuse decision is not revision-bound")
    return decision, cast("str", matches[0].revision)


def _receipt(
    *,
    source: MedicineDataSource,
    relative: str,
    rights: str,
    payload: bytes,
    qualified_at: datetime,
    reuse: ReuseGateDecision,
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    uri = (
        f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/"
        f"{relative}"
    )
    temporal = temporal_identity_from_source(
        retrieved_at=qualified_at,
        source_id=source.source_id,
        payload_sha256=evidence.sha256,
        original_uri=uri,
    )
    transform_id = "international-public-hf-link-v1"
    return SourceReceipt(
        receipt_id=f"international-{temporal.acquisition_id}",
        source=SourceIdentity(
            catalog_id="gma-source-catalog-v5",
            source_id=source.source_id,
            jurisdiction=source.jurisdictions[0],
            authority=source.authority,
            dataset_title=source.title,
            catalog_version="5",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(uri),
            retrieved_at=qualified_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        temporal=temporal,
        reuse=reuse,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(RIGHTS_REFERENCES[rights]),
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.NON_SENSITIVE,
            personal_data=PersonalDataState.NONE,
            publication=PublicationDisposition.PERMITTED,
            reason_codes=("exact_public_manifest_approved",),
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id=transform_id,
            transformation_sha256=sha256(transform_id.encode()).hexdigest(),
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def _source_record_pair_count(bronze: Path, clean_room: Path) -> int:
    original = {
        path.relative_to(bronze): _digest(path)
        for path in bronze.rglob("source_records.parquet")
    }
    recovered = {
        path.relative_to(clean_room): _digest(path)
        for path in clean_room.rglob("source_records.parquet")
    }
    if recovered != original:
        raise RuntimeError("international source-record recovery drifted")
    return len(original)


def qualify(  # ruff: ignore[too-many-locals]
    input_dir: Path,
    output_dir: Path,
    *,
    publication_receipt_path: Path = PUBLICATION_RECEIPT,
) -> dict[str, object]:
    """Verify, land, and recover the exact source-native public files."""
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    files = _verify_public_revision(input_dir, publication_receipt_path)
    catalog = tuple(load_source_catalog())
    by_source = {source.source_id: source for source in catalog}
    qualified_at = datetime.now(UTC)
    paths = tuple(str(item["path"]) for item in files)
    bronze = output_dir / "bronze"
    items: list[dict[str, object]] = []
    derived_items: list[dict[str, object]] = []
    revisions: set[str] = set()
    source_record_count = 0
    for item in files:
        source_id = str(item["source_id"])
        relative = str(item["path"])
        path = input_dir / relative
        payload = path.read_bytes()
        if source_id in DERIVED_ONLY_SOURCE_IDS:
            derived_items.append({
                "source_id": source_id,
                "path": relative,
                "sha256": _digest(path),
                "byte_count": len(payload),
                "live_landing_performed": False,
            })
            continue
        reuse, revision = _archive_candidate(source_id, paths, catalog)
        revisions.add(revision)
        source_media_hint = path.suffix.lstrip(".") or "bin"
        media_hint = _landing_media_hint(path)
        batch = _source_record_factory(source_id, payload, media_hint)
        landing = land_bronze_payload(
            payload,
            _receipt(
                source=by_source[source_id],
                relative=relative,
                rights=str(item["rights"]),
                payload=payload,
                qualified_at=qualified_at,
                reuse=reuse,
            ),
            bronze_root=bronze,
            media_hint=media_hint,
            source_records=batch,
        )
        admitted = isinstance(landing, BronzeLanding)
        rows = 0 if batch is None or not admitted else batch.table.num_rows
        source_record_count += rows
        document = (
            None
            if batch is not None or not admitted
            else build_document_manifest(payload, media_hint=source_media_hint)
        )
        items.append({
            "source_id": source_id,
            "path": relative,
            "payload_sha256": landing.receipt.payload.sha256,
            "payload_byte_count": landing.receipt.payload.byte_count,
            "acquisition_id": require_temporal(
                landing.receipt.temporal
            ).acquisition_id,
            "admission": landing.admission.state,
            "source_record_count": rows,
            "source_media_hint": source_media_hint,
            "landing_media_hint": media_hint,
            "document_manifest": (
                None if document is None else document.model_dump(mode="json")
            ),
        })
    clean_room = output_dir / "clean-room"
    copy_evidentiary_truth(bronze, clean_room)
    recovery = reconstruct_bronze(
        clean_room,
        fail_closed_on_incomplete=False,
        source_record_factory=_source_record_factory,
    )
    recovered_products = _source_record_pair_count(bronze, clean_room)
    if revisions != {REVISION}:
        raise ValueError("international reuse revisions are inconsistent")
    source_states: dict[str, set[str]] = {}
    for item in items:
        source_states.setdefault(str(item["source_id"]), set()).add(
            str(item["admission"])
        )
    fully_accepted = sorted(
        source_id
        for source_id, states in source_states.items()
        if states == {"accepted"}
    )
    partially_quarantined = sorted(
        source_id
        for source_id, states in source_states.items()
        if "quarantined" in states
    )
    result: dict[str, object] = {
        "schema_id": (
            "global-medicines-atlas.international-public-bronze-qualification"
        ),
        "schema_version": 1,
        "qualified_at": qualified_at.isoformat(),
        "evidence_class": "live_public_archive_reuse",
        "public_dataset": DATASET,
        "immutable_revision": REVISION,
        "public_manifest_sha256": _digest(input_dir / "manifest.json"),
        "public_manifest_files_verified": len(files),
        "source_native_file_count": len(items),
        "source_native_payload_byte_count": sum(
            cast("int", item["payload_byte_count"]) for item in items
        ),
        "source_native_source_ids": sorted({
            str(item["source_id"]) for item in items
        }),
        "fully_accepted_source_ids": fully_accepted,
        "partially_quarantined_source_ids": partially_quarantined,
        "quarantine_reason": (
            "Legacy French delimiter files that do not decode as UTF-8 remain "
            "immutable B2 raw evidence; downstream processing and source-record "
            "projection are fail closed pending a reviewed source-specific parser."
        ),
        "accepted_admission_count": sum(
            item["admission"] == "accepted" for item in items
        ),
        "quarantined_admission_count": sum(
            item["admission"] == "quarantined" for item in items
        ),
        "recovered_acquisition_count": len(recovery.landings),
        "incomplete_quarantined_recovery_count": recovery.incomplete_count,
        "source_record_count": source_record_count,
        "source_record_projection_count": recovered_products,
        "source_record_parquet_pairs_byte_identical": recovered_products,
        "document_manifest_count": sum(
            item["document_manifest"] is not None for item in items
        ),
        "derived_only_source_ids": sorted(DERIVED_ONLY_SOURCE_IDS),
        "derived_only_files_verified": len(derived_items),
        "derived_only_files_landed_as_live": 0,
        "reuse_disposition": "link",
        "reuse_revision": revisions.pop(),
        "items": items,
        "derived_items": derived_items,
        "coverage_complete": False,
        "source_bytes_committed": False,
        "external_publication_performed": False,
        "canonical_medicine_identity_claimed": False,
        "regulatory_approval_claimed": False,
        "funding_or_formulary_equivalence_claimed": False,
        "cross_country_comparability_claimed": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def qualification_summary(result: dict[str, object]) -> dict[str, object]:
    """Remove per-file detail while preserving aggregate qualification facts."""
    return {
        key: value
        for key, value in result.items()
        if key not in {"items", "derived_items"}
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    result = qualify(args.input_dir, args.output_dir)
    if args.summary_output is not None:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(
            json.dumps(qualification_summary(result), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
