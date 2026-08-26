#!/usr/bin/env python3
"""Qualify all approved Open Medic releases from the pinned public archive."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast

from pydantic import AnyUrl

from global_medicines_atlas.additional_utilisation_acquisition import (
    AdditionalUtilisationAuthorization,
    AdditionalUtilisationSourceAuthorization,
)
from global_medicines_atlas.bronze_landing import (
    BronzeLanding,
    land_bronze_payload,
)
from global_medicines_atlas.bronze_recovery import reconstruct_bronze
from global_medicines_atlas.open_medic_acquisition import (
    EXPECTED_YEARS,
    open_medic_source_record_batch,
)
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
from global_medicines_atlas.us_live_bronze import copy_evidentiary_truth

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/additional-utilisation-acquisition-authorization.json"
)
PUBLICATION_RECEIPT = (
    ROOT / "quality/qualifications/open-medic-public-huggingface-20260821.json"
)
SOURCE_ID = "fr-open-medic"
DATASET = "edithatogo/global-medicines-atlas-open-medic-20260821"
REVISION = "d19f7a66e35c58c557615bffa456856b485b7edc"
RIGHTS = "Etalab-2.0"
MANIFEST_NAME = "open-medic-all-release-bronze-qualification.json"


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _authorization() -> AdditionalUtilisationSourceAuthorization:
    document = AdditionalUtilisationAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    matches = tuple(
        source for source in document.sources if source.source_id == SOURCE_ID
    )
    if len(matches) != 1:
        raise ValueError("Open Medic authorization identity drifted")
    authorization = matches[0]
    authorization.require_payload_authority()
    if (
        authorization.decision_status != "approved_public"
        or not authorization.public_release_authorized
        or not authorization.external_publication_authorized
    ):
        raise PermissionError("Open Medic public authority is incomplete")
    return authorization


def _verify_public_revision(
    input_dir: Path, publication_receipt_path: Path
) -> tuple[tuple[int, Path, dict[str, object]], ...]:
    publication = cast(
        "dict[str, object]",
        json.loads(publication_receipt_path.read_text(encoding="utf-8")),
    )
    if (
        publication.get("dataset") != DATASET
        or publication.get("immutable_revision") != REVISION
        or publication.get("rights_families") != [RIGHTS]
        or publication.get("repository_private") is not False
        or publication.get("repository_gated") is not False
    ):
        raise ValueError("Open Medic publication identity drifted")
    manifest_path = input_dir / "manifest.json"
    if _digest(manifest_path) != publication.get("manifest_sha256"):
        raise ValueError("Open Medic public manifest digest drifted")
    manifest = cast(
        "dict[str, object]",
        json.loads(manifest_path.read_text(encoding="utf-8")),
    )
    files = cast("list[dict[str, object]]", manifest.get("files"))
    if (
        manifest.get("schema_id")
        != "global-medicines-atlas.international-public-archive"
        or manifest.get("archived_source_count") != 1
        or manifest.get("pending_sources") != {}
        or len(files) != publication.get("file_count")
        or len(files) != len(EXPECTED_YEARS) * 2
    ):
        raise ValueError("Open Medic public archive inventory drifted")
    entries = {str(item["path"]): item for item in files}
    releases: list[tuple[int, Path, dict[str, object]]] = []
    for year in EXPECTED_YEARS:
        stem = f"data/{SOURCE_ID}/OPEN_MEDIC_{year}"
        payload_relative = f"{stem}.zip"
        receipt_relative = f"{stem}.receipt.json"
        if {payload_relative, receipt_relative} - entries.keys():
            raise ValueError(
                "Open Medic annual archive inventory is incomplete"
            )
        for relative in (receipt_relative, payload_relative):
            item = entries[relative]
            path = input_dir / relative
            if (
                item.get("source_id") != SOURCE_ID
                or item.get("rights") != RIGHTS
                or not path.is_file()
                or path.stat().st_size != item.get("byte_count")
                or _digest(path) != item.get("sha256")
            ):
                raise ValueError("Open Medic public archive file drifted")
        source_receipt = cast(
            "dict[str, object]",
            json.loads(
                (input_dir / receipt_relative).read_text(encoding="utf-8")
            ),
        )
        payload_path = input_dir / payload_relative
        expected_receipt_fields = {
            "schema_id": "global-medicines-atlas.open-medic-acquisition",
            "source_id": SOURCE_ID,
            "year": year,
            "rights": RIGHTS,
            "admission_state": "accepted",
            "sha256": _digest(payload_path),
            "byte_count": payload_path.stat().st_size,
        }
        if any(
            source_receipt.get(key) != value
            for key, value in expected_receipt_fields.items()
        ):
            raise ValueError("Open Medic source receipt drifted")
        releases.append((year, payload_path, source_receipt))
    if set(entries) != {
        relative
        for year in EXPECTED_YEARS
        for relative in (
            f"data/{SOURCE_ID}/OPEN_MEDIC_{year}.receipt.json",
            f"data/{SOURCE_ID}/OPEN_MEDIC_{year}.zip",
        )
    }:
        raise ValueError("Open Medic public archive contains unexpected files")
    return tuple(releases)


def _source_receipt(
    *,
    year: int,
    payload: bytes,
    source_receipt: dict[str, object],
    retrieved_at: datetime,
    reuse: ReuseGateDecision,
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    temporal = temporal_identity_from_source(
        retrieved_at=retrieved_at,
        source_id=SOURCE_ID,
        payload_sha256=evidence.sha256,
        source_version=str(year),
        original_uri=str(source_receipt["resource_url"]),
    )
    transform = sha256(b"fr-open-medic-hf-link-v1").hexdigest()
    archive_uri = (
        f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/"
        f"data/{SOURCE_ID}/OPEN_MEDIC_{year}.zip"
    )
    return SourceReceipt(
        receipt_id=f"open-medic-{temporal.acquisition_id}",
        source=SourceIdentity(
            catalog_id="gma-source-catalog-v5",
            source_id=SOURCE_ID,
            jurisdiction="FRA",
            authority="Assurance Maladie",
            dataset_title="Open Medic interregime medicines expenditure",
            catalog_version="5",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(archive_uri),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        temporal=temporal,
        reuse=reuse,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(
            "https://www.etalab.gouv.fr/licence-ouverte-open-licence/"
        ),
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.NON_SENSITIVE,
            personal_data=PersonalDataState.NONE,
            publication=PublicationDisposition.PERMITTED,
            reason_codes=("maintainer_approved_etalab_aggregate",),
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="fr-open-medic-hf-link-v1",
            transformation_sha256=transform,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def _verify_source_record_recovery(bronze: Path, clean_room: Path) -> int:
    original = {
        path.relative_to(bronze): _digest(path)
        for path in bronze.rglob("source_records.parquet")
    }
    recovered = {
        path.relative_to(clean_room): _digest(path)
        for path in clean_room.rglob("source_records.parquet")
    }
    if not original or recovered != original:
        raise RuntimeError(
            "Open Medic source-record recovery was not byte-identical"
        )
    return len(original)


def qualify(  # ruff: ignore[too-many-locals]
    input_dir: Path,
    output_dir: Path,
    *,
    publication_receipt_path: Path = PUBLICATION_RECEIPT,
) -> dict[str, object]:
    """Land and reconstruct the exact twelve-release public archive."""
    _authorization()
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    releases = _verify_public_revision(input_dir, publication_receipt_path)
    qualified_at = datetime.now(UTC)
    huggingface_paths = tuple(
        str(path.relative_to(input_dir)) for _, path, _ in releases
    )
    reuse = evaluate_reuse_gate(
        SOURCE_ID,
        repository_root=ROOT,
        huggingface_index={DATASET: huggingface_paths},
        github_index={},
        requested=ReuseDisposition.LINK,
    )
    archive_candidates = tuple(
        candidate
        for candidate in reuse.candidates
        if candidate.surface == "hugging_face"
        and candidate.kind is ReuseCandidateKind.PAYLOAD
        and DATASET in candidate.locator
    )
    if (
        len(archive_candidates) != 1
        or archive_candidates[0].revision != REVISION
    ):
        raise ValueError(
            "Open Medic reuse decision is not bound to the pinned revision"
        )
    bronze = output_dir / "bronze"
    items: list[dict[str, object]] = []
    source_record_count = 0
    payload_byte_count = 0
    for year, payload_path, archived_receipt in releases:
        payload = payload_path.read_bytes()
        batch = open_medic_source_record_batch(SOURCE_ID, payload, "zip")
        if batch is None:
            raise TypeError("Open Medic source-record parser was not selected")
        receipt = _source_receipt(
            year=year,
            payload=payload,
            source_receipt=archived_receipt,
            retrieved_at=qualified_at,
            reuse=reuse,
        )
        landing = land_bronze_payload(
            payload,
            receipt,
            bronze_root=bronze,
            media_hint="zip",
            source_records=batch,
        )
        if not isinstance(landing, BronzeLanding):
            raise TypeError(f"Open Medic admission failed for {year}")
        if landing.source_records_path is None:
            raise RuntimeError("Open Medic source-record projection is missing")
        rows = batch.table.num_rows
        source_record_count += rows
        payload_byte_count += len(payload)
        items.append({
            "year": year,
            "payload_sha256": receipt.payload.sha256,
            "payload_byte_count": receipt.payload.byte_count,
            "acquisition_id": require_temporal(
                landing.receipt.temporal
            ).acquisition_id,
            "admission": landing.admission.state,
            "source_record_count": rows,
            "source_records_sha256": _digest(landing.source_records_path),
        })
    clean_room = output_dir / "clean-room"
    copy_evidentiary_truth(bronze, clean_room)
    recovery = reconstruct_bronze(
        clean_room,
        fail_closed_on_incomplete=True,
        source_record_factory=open_medic_source_record_batch,
    )
    recovered_products = _verify_source_record_recovery(bronze, clean_room)
    result: dict[str, object] = {
        "schema_id": (
            "global-medicines-atlas.open-medic-all-release-bronze-qualification"
        ),
        "schema_version": 1,
        "qualified_at": qualified_at.isoformat(),
        "source_id": SOURCE_ID,
        "prompt_id": 34,
        "evidence_class": "live_public_archive_reuse",
        "source_live_qualified": True,
        "prompt_complete": False,
        "prompt_audit_qualified_source_ids": [SOURCE_ID],
        "public_dataset": DATASET,
        "immutable_revision": REVISION,
        "public_manifest_sha256": _digest(input_dir / "manifest.json"),
        "public_manifest_files_verified": len(EXPECTED_YEARS) * 2,
        "existing_public_archive_verified": True,
        "release_count": len(items),
        "accepted_admission_count": len(items),
        "payload_byte_count": payload_byte_count,
        "source_record_count": source_record_count,
        "source_record_projection_count": len(items),
        "recovered_acquisition_count": len(recovery.landings),
        "recovered_source_record_projection_count": recovered_products,
        "source_record_parquet_pairs_byte_identical": recovered_products,
        "reuse_disposition": reuse.disposition,
        "reuse_revision": archive_candidates[0].revision,
        "items": items,
        "rights": RIGHTS,
        "source_bytes_committed": False,
        "external_publication_performed": False,
        "canonical_medicine_identity_claimed": False,
        "regulatory_approval_claimed": False,
        "cross_country_comparability_claimed": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(qualify(args.input_dir, args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
