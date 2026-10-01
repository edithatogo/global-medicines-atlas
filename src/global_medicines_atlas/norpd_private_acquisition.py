"""Hosted-only retention of one official historic NorPD aggregate report."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import AnyHttpUrl

from .bronze_landing import BronzeLanding, land_bronze_payload
from .bronze_recovery import reconstruct_bronze
from .models import FrozenModel
from .nordic_utilisation_acquisition import load_nordic_authorization
from .receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    DataSensitivity,
    EvidenceClass,
    HttpRetrievalEvidence,
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
from .reuse_gate import ReuseGateDecision, require_reuse_decision
from .rights_policy import (
    AccessRestriction,
    AcquisitionRightsPolicy,
    Permission,
    ReviewStatus,
)
from .us_live_bronze import copy_evidentiary_truth, write_private_corpus_archive

SOURCE_ID = "no-norpd-utilisation"
REPORT_URL = "https://www.fhi.no/contentassets/4df2902e8492453bb22c219bf69d8f71/191303_legemiddelstatistikk2019.pdf"
REPORT_PAGE = "https://www.fhi.no/en/publ/2019/norpd-20142018/"
PRIVATE_DATASET = "edithatogo/global-medicines-atlas-norpd-private"
PRIVATE_ARCHIVE = "norpd-2014-2018.private.tar"
MANIFEST = "norpd-private-acquisition-manifest.json"
CHECKSUM = "SHA256SUMS"
MAX_REPORT_BYTES = 100_000_000
HTTP_SUCCESS = 200


class NorpdPrivateManifest(FrozenModel):
    """Value-free record for the privately retained official report."""

    acquired_at: datetime
    source_id: str
    report_url: AnyHttpUrl
    report_page: AnyHttpUrl
    report_period: str
    attribution: str
    acquisition_id: str
    payload_sha256: str
    payload_byte_count: int
    archive_sha256: str
    archive_byte_count: int
    private_dataset: str
    public_release_authorized: bool
    external_publication_authorized: bool
    clean_room_recovered_payload_count: int


def require_norpd_authorization(authorization_path: Path) -> None:
    """Require Norway's dated, exact internal decision and no publication."""
    norway = load_nordic_authorization(authorization_path).sources[1]
    if norway.source_id != SOURCE_ID:
        raise ValueError("NorPD authorization source identity drifted")
    norway.require_payload_authority()
    if (
        norway.decision_date is None
        or norway.decision_date.isoformat() != "2026-10-01"
        or norway.public_release_authorized
        or norway.external_publication_authorized
    ):
        raise PermissionError(
            "NorPD approval is not the bounded internal decision"
        )


def validate_norpd_report(payload: bytes) -> None:
    """Check bounded PDF signature and trailer without parsing report data."""
    if not payload.startswith(b"%PDF-"):
        raise ValueError("NorPD report is not a PDF document")
    if not payload.rstrip().endswith(b"%%EOF"):
        raise ValueError("NorPD report is missing the PDF end marker")
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError("NorPD report exceeds the 100 MB bound")


def _receipt(
    payload: bytes,
    *,
    observed_at: datetime,
    reuse: ReuseGateDecision,
    http_evidence: HttpRetrievalEvidence,
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    temporal = temporal_identity_from_source(
        retrieved_at=observed_at,
        source_id=SOURCE_ID,
        payload_sha256=evidence.sha256,
        source_version="NorPD-2014-2018-NIPH-report-2019",
        original_uri=REPORT_URL,
    )
    return SourceReceipt(
        receipt_id=f"norpd-{temporal.acquisition_id}",
        source=SourceIdentity(
            catalog_id="gma-source-catalog-v5",
            source_id=SOURCE_ID,
            jurisdiction="NOR",
            authority="Norwegian Institute of Public Health",
            dataset_title="Norwegian Prescription Database 2014-2018",
            catalog_version="5",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyHttpUrl(REPORT_URL),
            retrieved_at=observed_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
            http=http_evidence,
        ),
        payload=evidence,
        temporal=temporal,
        reuse=require_reuse_decision(reuse, SOURCE_ID, now=observed_at),
        rights_state=RightsState.UNKNOWN,
        rights_reference=AnyHttpUrl("https://norpd.no/default.aspx"),
        rights_policy=AcquisitionRightsPolicy(
            acquisition_id=temporal.acquisition_id,
            source_id=SOURCE_ID,
            licence_evidence_uri=AnyHttpUrl(REPORT_PAGE),
            licence_expression="Unknown; maintainer decision authorizes this bounded internal historic report retention only.",
            retain_evidence=Permission.PERMITTED,
            publish_bytes=Permission.PROHIBITED,
            redistribute=Permission.PROHIBITED,
            transform=Permission.UNKNOWN,
            attribution_requirement="Norwegian Prescription Database (NorPD), Norwegian Institute of Public Health (NIPH).",
            access_restriction=AccessRestriction.NONE,
            review_status=ReviewStatus.IN_REVIEW,
            observed_at=observed_at,
            maintainer_licence_approved=False,
            maintainer_publication_approved=False,
        ),
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.NON_SENSITIVE,
            personal_data=PersonalDataState.NONE,
            publication=PublicationDisposition.PROHIBITED,
            reason_codes=("maintainer_internal_retention_only",),
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="norpd-official-pdf-byte-preservation-v1",
            transformation_sha256=sha256(
                b"norpd-official-pdf-byte-preservation-v1"
            ).hexdigest(),
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def exercise_norpd_private_acquisition(
    *,
    payload: bytes,
    output_dir: Path,
    authorization_path: Path,
    reuse_decision: ReuseGateDecision | None,
    http_evidence: HttpRetrievalEvidence,
    observed_at: datetime | None = None,
) -> NorpdPrivateManifest:
    """Admit the official 2014-2018 PDF, restore it, and prepare private archive."""
    if output_dir.exists():
        raise FileExistsError("NorPD output directory must not already exist")
    require_norpd_authorization(authorization_path)
    validate_norpd_report(payload)
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("NorPD acquisition time must be timezone-aware")
    reuse = require_reuse_decision(reuse_decision, SOURCE_ID, now=timestamp)
    output_dir.mkdir(parents=True, exist_ok=False)
    corpus = output_dir / "corpus"
    evidence_dir = corpus / "evidence"
    evidence_dir.mkdir(parents=True)
    shutil.copy2(authorization_path, evidence_dir / authorization_path.name)
    (evidence_dir / "report-scope.json").write_text(
        json.dumps(
            {
                "report_url": REPORT_URL,
                "report_page": REPORT_PAGE,
                "period": "2014-2018",
                "latest_source_coverage_asserted": 2020,
                "attribution": "Norwegian Prescription Database (NorPD), Norwegian Institute of Public Health (NIPH).",
                "public_release_authorized": False,
                "external_publication_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if http_evidence.observed_byte_length != len(payload):
        raise ValueError("NorPD HTTP byte count does not match the payload")
    if http_evidence.http_status != HTTP_SUCCESS:
        raise ValueError("NorPD HTTP status is not successful")
    if http_evidence.content_type != "application/pdf":
        raise ValueError("NorPD HTTP response media type is not PDF")
    receipt = _receipt(
        payload,
        observed_at=timestamp,
        reuse=reuse,
        http_evidence=http_evidence,
    )
    landing = land_bronze_payload(
        payload,
        receipt,
        bronze_root=corpus / "bronze",
        media_hint="pdf",
        reuse=receipt.reuse,
        admission_decided_at=timestamp,
        transformation_completed_at=timestamp,
    )
    if not isinstance(landing, BronzeLanding):
        raise TypeError("NorPD report was not admitted to Bronze")
    clean_room = corpus / "clean-room"
    copy_evidentiary_truth(corpus / "bronze", clean_room)
    recovery = reconstruct_bronze(clean_room, fail_closed_on_incomplete=True)
    if len(recovery.landings) != 1:
        raise ValueError("NorPD clean-room recovery count drifted")
    archive_path = output_dir / PRIVATE_ARCHIVE
    archive_digest, archive_size = write_private_corpus_archive(
        corpus, archive_path
    )
    manifest = NorpdPrivateManifest(
        acquired_at=timestamp,
        source_id=SOURCE_ID,
        report_url=AnyHttpUrl(REPORT_URL),
        report_page=AnyHttpUrl(REPORT_PAGE),
        report_period="2014-2018",
        attribution="Norwegian Prescription Database (NorPD), Norwegian Institute of Public Health (NIPH); report published 2019.",
        acquisition_id=require_temporal(receipt.temporal).acquisition_id,
        payload_sha256=receipt.payload.sha256,
        payload_byte_count=receipt.payload.byte_count,
        archive_sha256=archive_digest,
        archive_byte_count=archive_size,
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
        f"{archive_digest}  {PRIVATE_ARCHIVE}\n", encoding="utf-8"
    )
    return manifest
