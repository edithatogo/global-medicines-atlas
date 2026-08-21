#!/usr/bin/env python3
"""Acquire, land, and package the maintainer-approved public GSRS/UNII releases."""

from __future__ import annotations

import argparse
import json
import subprocess
import tarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen

from pydantic import AnyHttpUrl, AnyUrl

from global_medicines_atlas.bronze_landing import (
    BronzeLanding,
    land_bronze_payload,
)
from global_medicines_atlas.gsrs_acquisition import (
    GSRSAuthorization,
    GSRSRelease,
    parse_gsrs_release_inventory,
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
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION_PATH = (
    ROOT / "quality/qualifications/gsrs-unii-acquisition-authorization.json"
)
SOURCE_ID = "us-gsrs-unii"
ARCHIVE_INDEX = AnyHttpUrl("https://precision.fda.gov/uniisearch/archive")
LICENSING_URL = AnyUrl("https://gsrs.ncats.nih.gov/licensing")


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _fetch(url: str) -> bytes:
    with urlopen(url, timeout=180) as response:  # ruff: ignore[suspicious-url-open-usage]
        return response.read()


def _download_to(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--retry",
            "2",
            "--retry-delay",
            "2",
            "--max-time",
            "90",
            "--output",
            str(path),
            url,
        ],
        check=True,
    )


def _receipt(
    release: GSRSRelease, payload: bytes, retrieved_at: datetime
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    temporal = temporal_identity_from_source(
        retrieved_at=retrieved_at,
        source_id=SOURCE_ID,
        payload_sha256=evidence.sha256,
        source_published_at=datetime.combine(
            release.release_date, datetime.min.time(), tzinfo=UTC
        ),
        source_version=release.release_date.isoformat(),
    )
    transform_id = sha256(b"gma-gsrs-unii-source-native-v1").hexdigest()
    return SourceReceipt(
        receipt_id=f"gsrs-unii-{temporal.acquisition_id}",
        source=SourceIdentity(
            catalog_id="gma-source-catalog-v5",
            source_id=SOURCE_ID,
            jurisdiction="USA",
            authority="FDA / NCATS GSRS",
            dataset_title="GSRS and UNII paired dated releases",
            catalog_version="5",
        ),
        retrieval=RetrievalEvidence(
            uri=release.data_url,
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        temporal=temporal,
        reuse=acquire_new_decision(SOURCE_ID),
        rights_state=RightsState.PERMITTED,
        rights_reference=LICENSING_URL,
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.NON_SENSITIVE,
            personal_data=PersonalDataState.NONE,
            publication=PublicationDisposition.PROHIBITED,
            reason_codes=("official_cc0_public_domain_statement",),
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="gsrs-unii-source-native-v1",
            transformation_sha256=transform_id,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def acquire(  # ruff: ignore[too-many-locals]
    output_dir: Path, workers: int = 6
) -> dict[str, object]:
    authorization = GSRSAuthorization.model_validate_json(
        AUTHORIZATION_PATH.read_bytes()
    )
    authorization.require_payload_authority()
    if (
        not authorization.public_release_authorized
        or not authorization.external_publication_authorized
    ):
        raise PermissionError(
            "GSRS public publication authority is not approved"
        )
    index_payload = _fetch(str(ARCHIVE_INDEX))
    inventory = parse_gsrs_release_inventory(
        index_payload, base_url=ARCHIVE_INDEX, authorization=authorization
    )
    output_dir = output_dir.resolve()
    payload_root = output_dir / "payloads"
    bronze_root = output_dir / "bronze"
    payload_root.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC)
    jobs = {
        (release.release_date.isoformat(), "data"): release.data_url
        for release in inventory.releases
    }
    jobs.update({
        (release.release_date.isoformat(), "names"): release.names_url
        for release in inventory.releases
    })
    download_paths = {
        key: payload_root / key[0] / f"{key[1]}_{key[0]}.zip" for key in jobs
    }
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_download_to, str(url), download_paths[key]): key
            for key, url in jobs.items()
            if not download_paths[key].exists()
        }
        for future in as_completed(futures):
            future.result()
    rows: list[dict[str, object]] = []
    for release in inventory.releases:
        for kind, url in (
            ("data", release.data_url),
            ("names", release.names_url),
        ):
            key = (release.release_date.isoformat(), kind)
            payload = download_paths[key].read_bytes()
            filename = f"{kind}_{release.release_date.isoformat()}.zip"
            path = payload_root / release.release_date.isoformat() / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            receipt = _receipt(release, payload, retrieved_at)
            landing = land_bronze_payload(
                payload,
                receipt,
                bronze_root=bronze_root,
                media_hint="zip",
            )
            if not isinstance(landing, BronzeLanding):
                raise TypeError(f"GSRS admission rejected {filename}")
            rows.append({
                "release_date": release.release_date.isoformat(),
                "kind": kind,
                "source_uri": str(url),
                "filename": filename,
                "sha256": receipt.payload.sha256,
                "byte_count": len(payload),
                "acquisition_id": receipt.temporal.acquisition_id,
                "bronze_manifest_sha256": _digest(landing.parquet_path),
                "rights": "cc0_public_domain",
                "publication_authorized": True,
            })
    public_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_id": "global-medicines-atlas.gsrs-unii-public-release",
        "schema_version": 1,
        "source_id": SOURCE_ID,
        "license": "CC0-1.0",
        "source_license_evidence": str(LICENSING_URL),
        "release_count": inventory.release_count,
        "paired_payload_count": len(rows),
        "public_release_authorized": True,
        "external_publication_authorized": True,
        "records": rows,
        "evidence_limit": "UNII and GSRS records are terminology and substance evidence; they do not establish regulatory approval, clinical equivalence, safety, efficacy, funding, availability, or canonical medicine identity.",
    }
    manifest_path = output_dir / "gsrs-unii-private-retention-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    archive_path = output_dir / "gsrs-unii.private.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(payload_root, arcname="payloads")
        archive.add(bronze_root, arcname="bronze")
        archive.add(manifest_path, arcname=manifest_path.name)
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": _digest(manifest_path),
        "release_count": inventory.release_count,
        "paired_payload_count": len(rows),
        "payload_bytes": sum(int(row["byte_count"]) for row in rows),
        "archive_path": str(archive_path),
        "archive_sha256": _digest(archive_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    print(
        json.dumps(
            acquire(args.output_dir, workers=args.workers), sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
