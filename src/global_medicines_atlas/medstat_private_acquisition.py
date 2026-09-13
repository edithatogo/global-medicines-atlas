"""Hosted-only, privately retained acquisition for one bounded Medstat export."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote

from pydantic import AnyUrl

from .bronze_landing import BronzeLanding, land_bronze_payload
from .models import FrozenModel
from .nordic_utilisation_acquisition import load_nordic_authorization
from .receipts import (
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
from .reuse_gate import acquire_new_decision
from .us_live_bronze import copy_evidentiary_truth, write_private_corpus_archive

SOURCE_ID = "dk-medstat-utilisation"
PRIVATE_DATASET = "edithatogo/global-medicines-atlas-nordic-utilisation-private"
PRIVATE_ARCHIVE = "medstat-2025-national-turnover.private.tar"
MANIFEST = "medstat-private-acquisition-manifest.json"
CHECKSUM = "SHA256SUMS"
_EXPORT_ROOT = (
    "https://medstat.dk/da/viewDataTables/medicineAndMedicalGroups/"
    "exportToExcel/"
)


class MedstatQuery(FrozenModel):
    """The one bounded aggregate query approved for internal retention."""

    years: tuple[int, ...] = (2025,)
    region: tuple[str, ...] = ("0",)
    gender: tuple[str, ...] = ("A",)
    age_group: tuple[str, ...] = ("A",)
    search_variable: tuple[str, ...] = ("turnover",)
    atc_code: tuple[str, ...] = ("X",)
    sector: tuple[str, ...] = ("2",)

    def source_parameters(self) -> dict[str, list[str]]:
        """Return the exact names and values required by the Medstat route."""
        return {
            "year": [str(year) for year in self.years],
            "region": list(self.region),
            "gender": list(self.gender),
            "ageGroup": list(self.age_group),
            "searchVariable": list(self.search_variable),
            "atcCode": list(self.atc_code),
            "sector": list(self.sector),
        }

    def export_url(self) -> str:
        """Build the source-native Excel export URL without issuing a request."""
        payload = json.dumps(self.source_parameters(), separators=(",", ":"))
        return _EXPORT_ROOT + quote(payload, safe="")


class MedstatPrivateManifest(FrozenModel):
    """Non-public receipt for the archive retained in the private dataset."""

    acquired_at: datetime
    source_id: str
    export_url: AnyUrl
    query: dict[str, list[str]]
    acquisition_id: str
    payload_sha256: str
    payload_byte_count: int
    archive_sha256: str
    archive_byte_count: int
    private_dataset: str
    public_release_authorized: bool
    external_publication_authorized: bool
    clean_room_recovered_payload_count: int


def require_medstat_authorization(authorization_path: Path) -> None:
    """Reject every source and scope without this dated Denmark authority."""
    authorization = load_nordic_authorization(authorization_path)
    denmark = authorization.sources[0]
    if denmark.source_id != SOURCE_ID:
        raise ValueError("Denmark authorization source identity drifted")
    denmark.require_payload_authority()
    if (
        denmark.public_release_authorized
        or denmark.external_publication_authorized
    ):
        raise ValueError(
            "Medstat private acquisition cannot authorize publication"
        )


def _receipt(
    payload: bytes, *, observed_at: datetime, query: MedstatQuery
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    export_url = query.export_url()
    temporal = temporal_identity_from_source(
        retrieved_at=observed_at,
        source_id=SOURCE_ID,
        payload_sha256=evidence.sha256,
        source_version="annual-2025-national-total-turnover",
        original_uri=export_url,
    )
    return SourceReceipt(
        receipt_id=f"medstat-{temporal.acquisition_id}",
        source=SourceIdentity(
            catalog_id="gma-source-catalog-v5",
            source_id=SOURCE_ID,
            jurisdiction="DNK",
            authority="Danish Health Data Authority",
            dataset_title="Medstat.dk medicines statistics aggregate export",
            catalog_version="5",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(export_url),
            retrieved_at=observed_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        temporal=temporal,
        reuse=acquire_new_decision(SOURCE_ID),
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(
            "https://medstat.dk/apps/lms/public/dokumentation/"
            "Hvordan-du-maa-anvende-data.pdf"
        ),
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.NON_SENSITIVE,
            personal_data=PersonalDataState.NONE,
            publication=PublicationDisposition.PROHIBITED,
            reason_codes=("maintainer_internal_retention_only",),
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="medstat-source-native-export-v1",
            transformation_sha256=sha256(
                b"medstat-source-native-export-v1"
            ).hexdigest(),
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def exercise_medstat_private_acquisition(
    *,
    payload: bytes,
    output_dir: Path,
    authorization_path: Path,
    observed_at: datetime | None = None,
    query: MedstatQuery | None = None,
) -> MedstatPrivateManifest:
    """Land, recover, and privately archive one authorized Medstat export."""
    if not payload:
        raise ValueError("Medstat export is empty")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Medstat output directory must be empty")
    require_medstat_authorization(authorization_path)
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("Medstat acquisition time must be timezone-aware")
    selected = query or MedstatQuery()
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus = output_dir / "corpus"
    evidence = corpus / "evidence"
    evidence.mkdir(parents=True)
    shutil.copy2(authorization_path, evidence / authorization_path.name)
    (evidence / "query.json").write_text(
        json.dumps(selected.source_parameters(), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    receipt = _receipt(payload, observed_at=timestamp, query=selected)
    landing = land_bronze_payload(
        payload,
        receipt,
        bronze_root=corpus / "bronze",
        media_hint="xlsx",
        reuse=receipt.reuse,
        admission_decided_at=timestamp,
        transformation_completed_at=timestamp,
    )
    if not isinstance(landing, BronzeLanding):
        raise TypeError("Medstat export was not admitted to Bronze")
    clean_room = corpus / "clean-room"
    copy_evidentiary_truth(corpus / "bronze", clean_room)
    recovered_payloads = tuple((clean_room / "payloads").rglob("*"))
    if len([path for path in recovered_payloads if path.is_file()]) != 1:
        raise ValueError(
            "Medstat clean-room recovery did not preserve one payload"
        )
    archive_path = output_dir / PRIVATE_ARCHIVE
    archive_sha256, archive_byte_count = write_private_corpus_archive(
        corpus, archive_path
    )
    temporal = require_temporal(receipt.temporal)
    manifest = MedstatPrivateManifest(
        acquired_at=timestamp,
        source_id=SOURCE_ID,
        export_url=AnyUrl(selected.export_url()),
        query=selected.source_parameters(),
        acquisition_id=temporal.acquisition_id,
        payload_sha256=receipt.payload.sha256,
        payload_byte_count=receipt.payload.byte_count,
        archive_sha256=archive_sha256,
        archive_byte_count=archive_byte_count,
        private_dataset=PRIVATE_DATASET,
        public_release_authorized=False,
        external_publication_authorized=False,
        clean_room_recovered_payload_count=1,
    )
    (output_dir / MANIFEST).write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / CHECKSUM).write_text(
        f"{archive_sha256}  {PRIVATE_ARCHIVE}\n", encoding="utf-8"
    )
    return manifest
