#!/usr/bin/env python3
"""Acquire, Bronze-project, recover, and archive the approved public GIP corpus."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
import tempfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import httpx
from pydantic import AnyUrl

from global_medicines_atlas.bronze_landing import (
    BronzeLanding,
    land_bronze_payload,
)
from global_medicines_atlas.bronze_recovery import reconstruct_bronze
from global_medicines_atlas.gip_acquisition import (
    GIPAuthorization,
    GIPRelease,
    gip_source_record_batch,
    parse_gip_inventory,
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
from global_medicines_atlas.reuse_gate import acquire_new_decision
from global_medicines_atlas.us_live_bronze import copy_evidentiary_truth

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT / "quality/qualifications/gip-acquisition-authorization.json"
)
SOURCE_ID = "nl-gipdatabank"
ARCHIVE_NAME = "gip-public-28-releases-20260826.tar.gz"
_SAFE_FILENAME = re.compile(r"[^a-z0-9]+")


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _filename(release: GIPRelease) -> str:
    stem = _SAFE_FILENAME.sub("-", release.title.casefold()).strip("-")
    return f"{stem}.csv"


def _receipt(
    release: GIPRelease, payload: bytes, *, retrieved_at: datetime
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    published_at = datetime.combine(
        release.version_date, datetime.min.time(), tzinfo=UTC
    )
    temporal = temporal_identity_from_source(
        retrieved_at=retrieved_at,
        source_id=SOURCE_ID,
        payload_sha256=evidence.sha256,
        source_published_at=published_at,
        source_version=release.title,
        original_uri="https://www.zorgcijfersdatabank.nl/algemeen/open-data-gip",
    )
    transform = sha256(b"nl-gip-public-acquisition-v1").hexdigest()
    return SourceReceipt(
        receipt_id=f"gip-{temporal.acquisition_id}",
        source=SourceIdentity(
            catalog_id="gma-source-catalog-v5",
            source_id=SOURCE_ID,
            jurisdiction="NLD",
            authority="Zorginstituut Nederland",
            dataset_title="GIPdatabank medicines utilisation",
            catalog_version="5",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(
                "https://www.zorgcijfersdatabank.nl/algemeen/open-data-gip"
            ),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        temporal=temporal,
        reuse=acquire_new_decision(SOURCE_ID),
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(
            "https://www.zorgcijfersdatabank.nl/algemeen/copyright"
        ),
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.NON_SENSITIVE,
            personal_data=PersonalDataState.NONE,
            publication=PublicationDisposition.PERMITTED,
            reason_codes=("maintainer_approved_cc0_aggregate",),
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="nl-gip-public-acquisition-v1",
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
        raise RuntimeError("GIP source-record recovery was not byte-identical")
    return len(original)


def acquire(  # ruff: ignore[too-many-locals,too-many-statements]
    output_dir: Path, *, transport: httpx.BaseTransport | None = None
) -> dict[str, object]:
    """Acquire the exact authorized inventory without persisting rotating keys."""
    authorization = GIPAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    authorization.require_payload_authority()
    output_dir = output_dir.resolve()
    payload_dir = output_dir / "payloads"
    bronze = output_dir / "bronze"
    acquired_at = datetime.now(UTC)
    files: list[dict[str, object]] = []
    payload_byte_count = 0
    source_record_count = 0
    with httpx.Client(
        transport=transport, follow_redirects=True, timeout=120
    ) as client:
        landing = client.get(str(authorization.landing_url))
        landing.raise_for_status()
        inventory = parse_gip_inventory(
            landing.content, authorization=authorization
        )
        for release in inventory.releases:
            response = client.get(str(release.download_url))
            response.raise_for_status()
            media = response.headers.get("content-type", "").split(";", 1)[0]
            if media != "text/csv":
                raise ValueError("GIP release did not return text/csv")
            payload = response.content
            batch = gip_source_record_batch(SOURCE_ID, payload, "csv")
            if batch is None:
                raise TypeError("GIP source-record parser was not selected")
            payload_byte_count += len(payload)
            source_record_count += batch.table.num_rows
            filename = _filename(release)
            payload_path = payload_dir / filename
            payload_path.parent.mkdir(parents=True, exist_ok=True)
            payload_path.write_bytes(payload)
            receipt = _receipt(release, payload, retrieved_at=acquired_at)
            landing_result = land_bronze_payload(
                payload,
                receipt,
                bronze_root=bronze,
                media_hint="csv",
                source_records=batch,
            )
            if not isinstance(landing_result, BronzeLanding):
                raise TypeError(f"GIP admission failed for {release.title}")
            if landing_result.source_records_path is None:
                raise RuntimeError("GIP source-record projection is missing")
            files.append({
                "title": release.title,
                "family": release.family,
                "shape": release.shape,
                "period": release.period,
                "version_date": release.version_date.isoformat(),
                "filename": filename,
                "payload_sha256": receipt.payload.sha256,
                "payload_byte_count": receipt.payload.byte_count,
                "transport_url_sha256": sha256(
                    str(release.download_url).encode()
                ).hexdigest(),
                "acquisition_id": require_temporal(
                    landing_result.receipt.temporal
                ).acquisition_id,
                "admission": landing_result.admission.state,
                "source_record_count": batch.table.num_rows,
                "source_records_sha256": _digest(
                    landing_result.source_records_path
                ),
            })
    clean_room = output_dir / "clean-room"
    copy_evidentiary_truth(bronze, clean_room)
    recovery = reconstruct_bronze(
        clean_room,
        fail_closed_on_incomplete=True,
        source_record_factory=gip_source_record_batch,
    )
    recovered_products = _verify_source_record_recovery(bronze, clean_room)
    manifest: dict[str, object] = {
        "schema_id": "global-medicines-atlas.gip-public-acquisition",
        "schema_version": 1,
        "acquired_at": acquired_at.isoformat(),
        "source_id": SOURCE_ID,
        "decision_status": authorization.decision_status,
        "rights_state": "permitted",
        "public_release_authorized": authorization.public_release_authorized,
        "external_publication_authorized": (
            authorization.external_publication_authorized
        ),
        "release_count": len(files),
        "accepted_admission_count": len(files),
        "payload_byte_count": payload_byte_count,
        "source_record_count": source_record_count,
        "source_record_projection_count": len(files),
        "recovered_acquisition_count": len(recovery.landings),
        "recovered_source_record_projection_count": recovered_products,
        "source_record_parquet_pairs_byte_identical": recovered_products,
        "files": files,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "gip-public-acquisition-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    archive_path = output_dir / ARCHIVE_NAME
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(payload_dir, arcname="payloads")
        archive.add(bronze, arcname="bronze")
        archive.add(manifest_path, arcname=manifest_path.name)
    expected = {
        f"payloads/{item['filename']}": item["payload_sha256"] for item in files
    }
    with tempfile.TemporaryDirectory(prefix="gip-restore-") as temporary:
        restored_root = Path(temporary)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(restored_root, filter="data")
        restored = {
            name: _digest(restored_root / name) for name in sorted(expected)
        }
    if restored != expected:
        raise RuntimeError("GIP archive clean-room payload restore failed")
    manifest.update({
        "archive_path": str(archive_path),
        "archive_sha256": _digest(archive_path),
        "archive_byte_count": archive_path.stat().st_size,
        "archive_restore_verified": True,
        "archive_restored_payload_count": len(restored),
    })
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(acquire(args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
