"""Bounded, hosted-only Socialstyrelsen aggregate API acquisition."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote

from pydantic import AnyHttpUrl, Field, model_validator

from .bronze_landing import BronzeLanding, land_bronze_payload
from .bronze_recovery import reconstruct_bronze
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
from .reuse_gate import ReuseGateDecision, require_reuse_decision
from .rights_policy import (
    AccessRestriction,
    AcquisitionRightsPolicy,
    Permission,
    ReviewStatus,
)
from .us_live_bronze import copy_evidentiary_truth, write_private_corpus_archive

SOURCE_ID = "se-socialstyrelsen-utilisation"
PRIVATE_DATASET = "edithatogo/global-medicines-atlas-socialstyrelsen-private"
PRIVATE_ARCHIVE = "socialstyrelsen-2025-national-aggregate.private.tar"
MANIFEST = "socialstyrelsen-private-acquisition-manifest.json"
CHECKSUM = "SHA256SUMS"
API_ROOT = "https://sdb.socialstyrelsen.se/api/v1/sv/lakemedel"
_ALLOWED_SOURCE_HOSTS = frozenset({"sdb.socialstyrelsen.se"})
_MAX_CELLS = 70_000
_MAX_ATC_CODES = 100
_MAX_RESPONSE_BYTES = 25_000_000
_ATC = ("TOTALT",)
_REGION = ("0",)
_AGES = tuple(str(value) for value in range(1, 19))
_SEX = ("3",)
_YEAR = ("2025",)
_MEASURES = (1, 2, 3, 4, 9)


class SwedenQuery(FrozenModel):
    """A source-generated aggregate request inside the approved narrow scope."""

    year: tuple[str, ...] = _YEAR
    measure_ids: tuple[int, ...] = _MEASURES
    atc_codes: tuple[str, ...] = _ATC
    regions: tuple[str, ...] = _REGION
    ages: tuple[str, ...] = _AGES
    sexes: tuple[str, ...] = _SEX
    maximum_cells: int = Field(default=90, ge=1, le=_MAX_CELLS)

    @model_validator(mode="after")
    def approved_scope(self) -> SwedenQuery:
        if self.year != _YEAR:
            raise ValueError("Sweden query year must match approved 2025 scope")
        if self.measure_ids != _MEASURES:
            raise ValueError(
                "Sweden query must preserve all five approved measures"
            )
        if self.atc_codes != _ATC or len(self.atc_codes) > _MAX_ATC_CODES:
            raise ValueError("Sweden query ATC scope is not approved")
        if self.regions != _REGION or self.ages != _AGES or self.sexes != _SEX:
            raise ValueError("Sweden query dimensions exceed approved scope")
        if self.cell_count > self.maximum_cells:
            raise ValueError("Sweden query exceeds its declared cell bound")
        return self

    @property
    def cell_count(self) -> int:
        return (
            len(self.measure_ids)
            * len(self.atc_codes)
            * len(self.regions)
            * len(self.ages)
            * len(self.sexes)
            * len(self.year)
        )

    def source_urls(self) -> tuple[str, ...]:
        """Return one exact API URL per measure, without making requests."""
        return tuple(
            f"{API_ROOT}/resultat/matt/{measure}/variabel/{quote(atc_codes, safe=',')}/"
            f"region/{quote(regions, safe=',')}/alder/{quote(ages, safe=',')}/"
            f"kon/{quote(sexes, safe=',')}/ar/{quote(years, safe=',')}?per_sida=5000"
            for measure in self.measure_ids
            for atc_codes, regions, ages, sexes, years in (
                (
                    ",".join(self.atc_codes),
                    ",".join(self.regions),
                    ",".join(self.ages),
                    ",".join(self.sexes),
                    ",".join(self.year),
                ),
            )
        )

    def source_parameters(self) -> dict[str, object]:
        """Return the retrieval contract written to the evidence corpus."""
        return {
            "year": list(self.year),
            "measure_ids": list(self.measure_ids),
            "atc_codes": list(self.atc_codes),
            "regions": list(self.regions),
            "ages": list(self.ages),
            "sexes": list(self.sexes),
            "cell_count_upper_bound": self.cell_count,
            "maximum_cells_per_query": _MAX_CELLS,
            "maximum_atc_codes_per_query": _MAX_ATC_CODES,
            "response_format": "JSON",
        }


class SwedenPrivateManifest(FrozenModel):
    """Non-public receipt for one bounded privately retained API acquisition."""

    acquired_at: datetime
    source_id: str
    source_urls: tuple[AnyHttpUrl, ...]
    query: dict[str, object]
    acquisition_id: str
    payload_sha256: tuple[str, ...]
    payload_byte_count: tuple[int, ...]
    archive_sha256: str
    archive_byte_count: int
    private_dataset: str
    attribution: str
    public_release_authorized: bool
    external_publication_authorized: bool
    clean_room_recovered_payload_count: int


def require_sweden_authorization(authorization_path: Path) -> None:
    """Require the dated Sweden approval and keep publication independently off."""
    authorization = load_nordic_authorization(authorization_path)
    sweden = authorization.sources[2]
    sweden.require_payload_authority()
    if (
        sweden.decision_date is None
        or sweden.decision_date.isoformat() != "2026-09-29"
    ):
        raise PermissionError("Sweden acquisition approval date is not current")


def validate_sweden_response(payload: bytes) -> None:
    """Require one bounded source JSON response without logging its values."""
    if not payload:
        raise ValueError("Socialstyrelsen response is empty")
    if len(payload) > _MAX_RESPONSE_BYTES:
        raise ValueError("Socialstyrelsen response exceeds the 25 MB bound")
    value = json.loads(payload)
    if not isinstance(value, (dict, list)):
        raise TypeError(
            "Socialstyrelsen response is not a JSON result document"
        )


def _receipt(
    payload: bytes,
    *,
    observed_at: datetime,
    uri: str,
    measure_id: int,
    reuse: ReuseGateDecision,
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    temporal = temporal_identity_from_source(
        retrieved_at=observed_at,
        source_id=SOURCE_ID,
        payload_sha256=evidence.sha256,
        source_version=f"annual-2025-measure-{measure_id}",
        original_uri=uri,
    )
    return SourceReceipt(
        receipt_id=f"socialstyrelsen-{temporal.acquisition_id}",
        source=SourceIdentity(
            catalog_id="gma-source-catalog-v5",
            source_id=SOURCE_ID,
            jurisdiction="SWE",
            authority="Socialstyrelsen",
            dataset_title="Swedish medicines statistics aggregate API results",
            catalog_version="5",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyHttpUrl(uri),
            retrieved_at=observed_at,
            acquisition_method=AcquisitionMethod.API,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        temporal=temporal,
        reuse=require_reuse_decision(reuse, SOURCE_ID, now=observed_at),
        rights_state=RightsState.UNKNOWN,
        rights_reference=AnyHttpUrl(
            "https://www.socialstyrelsen.se/statistik-och-data/oppna-data/statistikdatabaser/"
        ),
        rights_policy=AcquisitionRightsPolicy(
            acquisition_id=temporal.acquisition_id,
            source_id=SOURCE_ID,
            licence_evidence_uri=AnyHttpUrl(
                "https://www.socialstyrelsen.se/statistik-och-data/oppna-data/statistikdatabaser/"
            ),
            licence_expression=(
                "CC0 1.0 declared by Socialstyrelsen; project rights review open"
            ),
            retain_evidence=Permission.PERMITTED,
            publish_bytes=Permission.PROHIBITED,
            redistribute=Permission.PROHIBITED,
            transform=Permission.UNKNOWN,
            attribution_requirement=(
                "Attribute Socialstyrelsen and record the retrieval date."
            ),
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
            transformation_id="socialstyrelsen-source-native-api-json-v1",
            transformation_sha256=sha256(
                b"socialstyrelsen-source-native-api-json-v1"
            ).hexdigest(),
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def exercise_sweden_private_acquisition(
    *,
    payloads: tuple[bytes, ...],
    output_dir: Path,
    authorization_path: Path,
    reuse_decision: ReuseGateDecision | None,
    observed_at: datetime | None = None,
    query: SwedenQuery | None = None,
) -> SwedenPrivateManifest:
    """Land exact API response bytes, recover them, and prepare a private archive."""
    selected = query or SwedenQuery()
    urls = selected.source_urls()
    if len(payloads) != len(urls):
        raise ValueError("Sweden response count must match the approved query")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Sweden output directory must be empty")
    require_sweden_authorization(authorization_path)
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("Sweden acquisition time must be timezone-aware")
    reuse = require_reuse_decision(reuse_decision, SOURCE_ID, now=timestamp)
    for payload in payloads:
        validate_sweden_response(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus = output_dir / "corpus"
    _write_sweden_evidence(corpus, authorization_path, selected)
    landings, digests, byte_counts = _land_sweden_responses(
        payloads=payloads,
        urls=urls,
        selected=selected,
        timestamp=timestamp,
        reuse=reuse,
        bronze_root=corpus / "bronze",
    )
    clean_room = corpus / "clean-room"
    copy_evidentiary_truth(corpus / "bronze", clean_room)
    recovery = reconstruct_bronze(clean_room, fail_closed_on_incomplete=True)
    if len(recovery.landings) != len(payloads):
        raise ValueError(
            "Sweden clean-room recovery count does not match query"
        )
    archive_path = output_dir / PRIVATE_ARCHIVE
    archive_sha256, archive_byte_count = write_private_corpus_archive(
        corpus, archive_path
    )
    temporal = require_temporal(landings[0].receipt.temporal)
    manifest = SwedenPrivateManifest(
        acquired_at=timestamp,
        source_id=SOURCE_ID,
        source_urls=tuple(AnyHttpUrl(url) for url in urls),
        query=selected.source_parameters(),
        acquisition_id=temporal.acquisition_id,
        payload_sha256=tuple(digests),
        payload_byte_count=tuple(byte_counts),
        archive_sha256=archive_sha256,
        archive_byte_count=archive_byte_count,
        private_dataset=PRIVATE_DATASET,
        attribution="Source: Socialstyrelsen statistics database; accessed on the recorded retrieval date.",
        public_release_authorized=False,
        external_publication_authorized=False,
        clean_room_recovered_payload_count=len(payloads),
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


def _write_sweden_evidence(
    corpus: Path,
    authorization_path: Path,
    selected: SwedenQuery,
) -> None:
    """Copy the authority and exact bounded source parameters into evidence."""
    evidence = corpus / "evidence"
    evidence.mkdir(parents=True)
    shutil.copy2(authorization_path, evidence / authorization_path.name)
    (evidence / "query.json").write_text(
        json.dumps(selected.source_parameters(), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _land_sweden_responses(
    *,
    payloads: tuple[bytes, ...],
    urls: tuple[str, ...],
    selected: SwedenQuery,
    timestamp: datetime,
    reuse: ReuseGateDecision,
    bronze_root: Path,
) -> tuple[list[BronzeLanding], list[str], list[int]]:
    """Admit one result per measure and return value-free receipt metadata."""
    landings: list[BronzeLanding] = []
    digests: list[str] = []
    byte_counts: list[int] = []
    for measure_id, uri, payload in zip(
        selected.measure_ids, urls, payloads, strict=True
    ):
        receipt = _receipt(
            payload,
            observed_at=timestamp,
            uri=uri,
            measure_id=measure_id,
            reuse=reuse,
        )
        landing = land_bronze_payload(
            payload,
            receipt,
            bronze_root=bronze_root,
            media_hint="json",
            reuse=receipt.reuse,
            admission_decided_at=timestamp,
            transformation_completed_at=timestamp,
        )
        if not isinstance(landing, BronzeLanding):
            raise TypeError("Sweden API response was not admitted to Bronze")
        landings.append(landing)
        digests.append(receipt.payload.sha256)
        byte_counts.append(receipt.payload.byte_count)
    return landings, digests, byte_counts
