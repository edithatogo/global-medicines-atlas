#!/usr/bin/env python3
"""Acquire and verify the privately retained historic NICE-utilisation corpus."""

from __future__ import annotations

import argparse
import json
import tarfile
import tempfile
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path

import httpx
from pydantic import AnyUrl

from global_medicines_atlas.bronze_landing import (
    BronzeLanding,
    land_bronze_payload,
)
from global_medicines_atlas.nice_utilisation_acquisition import (
    NICE_UTILISATION_ARTIFACTS,
    NICEUtilisationArtifact,
    NICEUtilisationAuthorization,
    inspect_nice_utilisation_payload,
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

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
)
SOURCE_ID = "gb-nice-medicines-utilisation"


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _payload_path(input_dir: Path, release: str, filename: str) -> Path:
    return input_dir / release / filename


def _retrieve(input_dir: Path) -> None:
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for artifact in NICE_UTILISATION_ARTIFACTS:
            path = _payload_path(
                input_dir, artifact.release_label, artifact.filename
            )
            if path.exists():
                continue
            response = client.get(str(artifact.url))
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)


def _receipt(
    *,
    artifact: NICEUtilisationArtifact,
    payload: bytes,
    retrieved_at: datetime,
    publication_date: date,
) -> SourceReceipt:
    payload_evidence = PayloadEvidence.from_bytes(payload)
    identity = temporal_identity_from_source(
        retrieved_at=retrieved_at,
        source_id=SOURCE_ID,
        payload_sha256=payload_evidence.sha256,
        source_published_at=datetime.combine(
            publication_date, datetime.min.time(), tzinfo=UTC
        ),
        source_version=artifact.release_label,
        original_uri=str(artifact.url),
    )
    transformation_identity = sha256(
        b"nice-utilisation-private-acquisition-manifest-v1"
    ).hexdigest()
    return SourceReceipt(
        receipt_id=f"nice-utilisation-{identity.acquisition_id}",
        source=SourceIdentity(
            catalog_id="gma-source-catalog-v5",
            source_id=SOURCE_ID,
            jurisdiction="GBR",
            authority="NHS England",
            dataset_title="Use of NICE appraised medicines in the NHS in England",
            catalog_version="5",
        ),
        retrieval=RetrievalEvidence(
            uri=artifact.url,
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=payload_evidence,
        temporal=identity,
        reuse=acquire_new_decision(SOURCE_ID),
        rights_state=RightsState.RESTRICTED,
        rights_reference=AnyUrl(
            "https://www.england.nhs.uk/terms-and-conditions-2/"
        ),
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.NON_SENSITIVE,
            personal_data=PersonalDataState.NONE,
            publication=PublicationDisposition.PROHIBITED,
            reason_codes=("third_party_licensing_not_cleared",),
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="nice-utilisation-acquisition-v1",
            transformation_sha256=transformation_identity,
            output_sha256=payload_evidence.sha256,
            output_byte_count=payload_evidence.byte_count,
        ),
    )


def acquire(  # ruff: ignore[too-many-locals]
    input_dir: Path, output_dir: Path, *, download: bool
) -> dict[str, object]:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    authorization = NICEUtilisationAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    authorization.require_payload_authority()
    if download:
        _retrieve(input_dir)
    release_by_label = {item.label: item for item in authorization.releases}
    bronze_root = output_dir / "bronze"
    acquired_at = datetime.now(UTC)
    files: list[dict[str, object]] = []
    for artifact in NICE_UTILISATION_ARTIFACTS:
        path = _payload_path(
            input_dir, artifact.release_label, artifact.filename
        )
        payload = path.read_bytes()
        media = inspect_nice_utilisation_payload(artifact.filename, payload)
        receipt = _receipt(
            artifact=artifact,
            payload=payload,
            retrieved_at=acquired_at,
            publication_date=release_by_label[
                artifact.release_label
            ].publication_date,
        )
        landing = land_bronze_payload(
            payload,
            receipt,
            bronze_root=bronze_root,
            media_hint=media,
        )
        if not isinstance(landing, BronzeLanding):
            raise TypeError(
                f"admission rejected {artifact.filename}: "
                f"{landing.admission.reason_codes}"
            )
        files.append({
            "release": artifact.release_label,
            "role": artifact.role,
            "filename": artifact.filename,
            "uri": str(artifact.url),
            "sha256": receipt.payload.sha256,
            "byte_count": len(payload),
            "acquisition_id": require_temporal(
                landing.receipt.temporal
            ).acquisition_id,
            "admission": landing.admission.state,
            "manifest_sha256": _digest(landing.parquet_path),
            "publication_authorized": False,
        })
    manifest: dict[str, object] = {
        "schema_id": "global-medicines-atlas.nice-utilisation-private-acquisition",
        "schema_version": 1,
        "acquired_at": acquired_at.isoformat(),
        "source_id": SOURCE_ID,
        "rights_state": "restricted",
        "publication_authorized": False,
        "external_publication_authorized": False,
        "file_count": len(files),
        "payload_byte_count": sum(
            path.stat().st_size for path in input_dir.glob("*/*")
        ),
        "files": files,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "private-acquisition-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    archive_path = output_dir / "nice-utilisation-private-20260821.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(input_dir, arcname="payloads")
        archive.add(bronze_root, arcname="bronze")
        archive.add(manifest_path, arcname=manifest_path.name)
    expected_payloads = {
        f"payloads/{item.release_label}/{item.filename}"
        for item in NICE_UTILISATION_ARTIFACTS
    }
    with tempfile.TemporaryDirectory(prefix="nice-utilisation-restore-") as tmp:
        restore_root = Path(tmp)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(restore_root, filter="data")
        restored = {
            f"payloads/{item.release_label}/{item.filename}": _digest(
                restore_root / "payloads" / item.release_label / item.filename
            )
            for item in NICE_UTILISATION_ARTIFACTS
        }
    expected_digests = {
        f"payloads/{item['release']}/{item['filename']}": item["sha256"]
        for item in files
    }
    if set(restored) != expected_payloads or restored != expected_digests:
        raise RuntimeError(
            "private archive clean-room restore verification failed"
        )
    manifest.update({
        "archive_path": str(archive_path),
        "archive_sha256": _digest(archive_path),
        "archive_byte_count": archive_path.stat().st_size,
        "restore_verified": True,
        "restore_verified_payload_count": len(expected_payloads),
    })
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    result = acquire(args.input_dir, args.output_dir, download=args.download)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
