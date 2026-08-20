"""Bounded, internal-only acquisition and Bronze exercise for U.S. sources."""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

import json
import shutil
import tarfile
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import AnyUrl, Field, model_validator

if TYPE_CHECKING:
    import httpx

from .acquisition import AcquisitionPolicy, Receipt, acquire_source
from .bronze_admission import BronzeAdmissionState
from .bronze_landing import (
    PAYLOAD_DIR,
    RECEIPT_DIR,
    BronzeAcquisition,
    BronzeLanding,
    SourceRecordBatch,
    land_bronze_payload,
)
from .bronze_recovery import reconstruct_bronze
from .models import FrozenModel
from .receipts import EvidenceClass, FailureReceipt, RightsState, SourceReceipt
from .reuse_gate import ReuseGateDecision, evaluate_reuse_gate
from .rights_policy import (
    AccessRestriction,
    AcquisitionRightsPolicy,
    Permission,
    ReviewStatus,
    coarse_rights_state,
)
from .source_catalog import AccessMode, MedicineDataSource, load_source_catalog
from .us_source_records import us_source_record_batch

PRIVATE_ARCHIVE_FILENAME = "us-live-bronze-corpus.private.tar"
PRIVATE_MANIFEST_FILENAME = "us-live-bronze-corpus.manifest.json"
PRIVATE_CHECKSUM_FILENAME = "SHA256SUMS"
_OPENFDA_TERMS = "https://open.fda.gov/terms/"
_FDA_POLICY = "https://www.fda.gov/about-fda/about-website/website-policies"
_AUTHORIZED_SOURCE_IDS = frozenset({
    "us-openfda-drugsfda",
    "us-openfda-enforcement",
    "us-openfda-faers",
    "us-openfda-ndc",
    "us-openfda-nsde",
    "us-drugsfda",
    "us-fda-drug-shortages",
    "us-fda-faers",
    "us-fda-ndc-directory",
    "us-fda-nsde",
    "us-fda-orange-book",
    "us-fda-recalls-notices",
    "us-fda-rems",
})
_CATALOGUE_ONLY_SOURCE_IDS = frozenset({
    "us-cms-mdrp",
    "us-cms-nadac",
    "us-cms-partd-formulary",
    "us-cms-partd-spending",
    "us-dailymed-spl",
    "us-gsrs-unii",
    "us-rxnorm-api",
})


class AuthorizedUSSource(FrozenModel):
    """One exact, bounded endpoint approved for internal acquisition."""

    source_id: str = Field(min_length=1)
    endpoint: AnyUrl
    media_hint: Literal["json", "zip", "html"]
    rights_profile: Literal[
        "scoped_cc0_metadata_only",
        "government_public_domain_policy_review",
    ]
    max_bytes: int = Field(ge=1, le=512 * 1024 * 1024)


class USLiveAcquisitionAuthorization(FrozenModel):
    """Maintainer decision boundary for the approved internal cohort."""

    schema_id: Literal[
        "global-medicines-atlas.us-live-acquisition-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date
    decision_basis: str = Field(min_length=1)
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    coverage_complete: bool
    scope_note: str = Field(min_length=1)
    authorized_sources: tuple[AuthorizedUSSource, ...]
    catalogue_only_sources: tuple[str, ...]
    field_exclusions: tuple[str, ...]

    @model_validator(mode="after")
    def exact_internal_only_scope(self) -> USLiveAcquisitionAuthorization:
        if not self.internal_retention_authorized:
            raise ValueError("internal retention must be authorized")
        if (
            self.public_release_authorized
            or self.external_publication_authorized
        ):
            raise ValueError("authorization must remain internal-only")
        if self.coverage_complete:
            raise ValueError(
                "bounded acquisition cannot claim complete coverage"
            )
        acquired = [item.source_id for item in self.authorized_sources]
        if len(acquired) != len(set(acquired)):
            raise ValueError("authorized source IDs must be unique")
        if frozenset(acquired) != _AUTHORIZED_SOURCE_IDS:
            raise ValueError("authorization must match the approved 13 sources")
        if frozenset(self.catalogue_only_sources) != _CATALOGUE_ONLY_SOURCE_IDS:
            raise ValueError("authorization must preserve the seven terms gaps")
        exclusions = " ".join(self.field_exclusions).casefold()
        if "third-party" not in exclusions or "gmdn" not in exclusions:
            raise ValueError(
                "authorization must exclude third-party and GMDN material"
            )
        return self


class USLiveCorpusItem(FrozenModel):
    """Redacted outcome for one authorized source; contains no source fields."""

    source_id: str
    status: Literal["succeeded", "failed"]
    acquisition_id: str | None = None
    payload_sha256: str | None = None
    payload_byte_count: int | None = None
    rights_state: str
    admission_state: str | None = None
    parquet_projected: bool = False
    source_records_projected: bool = False
    source_record_count: int | None = Field(default=None, ge=0)
    source_record_failure_code: str | None = None
    reuse_disposition: str
    failure_code: str | None = None


class USLiveCorpusManifest(FrozenModel):
    """Private archive receipt for one fault-isolated live-source exercise."""

    schema_id: Literal["global-medicines-atlas.us-live-bronze-corpus"] = (
        "global-medicines-atlas.us-live-bronze-corpus"
    )
    schema_version: Literal[2] = 2
    exercised_at: datetime
    evidence_class: Literal["live_bounded_internal"] = "live_bounded_internal"
    external_publication_performed: Literal[False] = False
    coverage_complete: Literal[False] = False
    source_count: int
    acquisition_succeeded_count: int
    acquisition_failed_count: int
    accepted_admission_count: int
    quarantined_admission_count: int
    recovered_acquisition_count: int
    source_record_projection_count: int
    recovered_source_record_projection_count: int
    items: tuple[USLiveCorpusItem, ...]
    archive_filename: Literal["us-live-bronze-corpus.private.tar"] = (
        PRIVATE_ARCHIVE_FILENAME
    )
    archive_sha256: str
    archive_byte_count: int


ReuseSearcher = Callable[[str], ReuseGateDecision]
Clock = Callable[[], datetime]


def _recoverable_source_record_batch(
    source_id: str,
    payload: bytes,
    media_hint: str,
) -> SourceRecordBatch | None:
    try:
        return us_source_record_batch(source_id, payload, media_hint)
    except TypeError, ValueError, pa.ArrowException:
        return None


def _catalog_source(
    source_id: str,
    catalog: tuple[MedicineDataSource, ...],
) -> MedicineDataSource:
    matches = tuple(item for item in catalog if item.source_id == source_id)
    if len(matches) != 1:
        raise ValueError(f"catalog source must resolve once: {source_id}")
    return matches[0]


def _endpoint_source(
    item: AuthorizedUSSource,
    catalog: tuple[MedicineDataSource, ...],
) -> MedicineDataSource:
    source = _catalog_source(item.source_id, catalog)
    if item.media_hint == "json":
        updates = {
            "access_mode": AccessMode.API,
            "api_url": str(item.endpoint),
            "download_url": None,
        }
    else:
        updates = {
            "access_mode": AccessMode.DOWNLOAD,
            "api_url": None,
            "download_url": str(item.endpoint),
        }
    return MedicineDataSource.model_validate(
        source.model_dump(mode="python") | updates
    )


def _rights_policy(
    item: AuthorizedUSSource,
    receipt: SourceReceipt,
    observed_at: datetime,
) -> AcquisitionRightsPolicy:
    temporal = receipt.temporal
    if temporal is None:
        raise ValueError("live acquisition requires temporal identity")
    is_cc0 = item.rights_profile == "scoped_cc0_metadata_only"
    return AcquisitionRightsPolicy(
        acquisition_id=temporal.acquisition_id,
        source_id=item.source_id,
        licence_evidence_uri=AnyUrl(_OPENFDA_TERMS if is_cc0 else _FDA_POLICY),
        licence_expression=(
            "CC0-scoped metadata only; exclude marked third-party content, "
            "GMDN, separately licensed terminology, and FDA marks."
            if is_cc0
            else "Conditional internal retention of government-authored source "
            "material; exclude third-party content, separately licensed "
            "terminology, marks, and inferred claims from projections."
        ),
        retain_evidence=(
            Permission.PERMITTED if is_cc0 else Permission.CONDITIONAL
        ),
        publish_bytes=Permission.PROHIBITED,
        redistribute=Permission.PROHIBITED,
        transform=(Permission.PERMITTED if is_cc0 else Permission.CONDITIONAL),
        attribution_requirement="Record FDA source URL and retrieval date.",
        access_restriction=AccessRestriction.NONE,
        review_status=ReviewStatus.REVIEWED,
        observed_at=observed_at,
        reviewed_at=observed_at,
        maintainer_licence_approved=True,
        maintainer_publication_approved=False,
    )


def _bind_rights(
    item: AuthorizedUSSource,
    receipt: SourceReceipt,
    observed_at: datetime,
) -> SourceReceipt:
    policy = _rights_policy(item, receipt, observed_at)
    state = RightsState(coarse_rights_state(policy))
    return SourceReceipt.model_validate(
        receipt.model_dump(mode="python")
        | {
            "rights_state": state,
            "rights_reference": str(policy.licence_evidence_uri),
            "rights_policy": policy,
        }
    )


def _reject_excluded_openfda_material(
    item: AuthorizedUSSource,
    payload: bytes,
) -> None:
    if (
        item.rights_profile == "scoped_cc0_metadata_only"
        and b"gmdn" in payload.lower()
    ):
        raise ValueError(
            f"{item.source_id} contained excluded GMDN material; corpus aborted"
        )


def _copy_evidentiary_truth(source: Path, destination: Path) -> None:
    for folder in (PAYLOAD_DIR, RECEIPT_DIR):
        origin = source / folder
        if origin.is_dir():
            shutil.copytree(origin, destination / folder)


def _add_tar_entry(archive: tarfile.TarFile, path: Path, root: Path) -> None:
    relative = path.relative_to(root).as_posix()
    info = tarfile.TarInfo(f"corpus/{relative}")
    info.uid = info.gid = info.mtime = 0
    info.uname = info.gname = ""
    if path.is_dir():
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        archive.addfile(info)
        return
    payload = path.read_bytes()
    info.size = len(payload)
    info.mode = 0o600
    archive.addfile(info, BytesIO(payload))


def _write_private_archive(corpus: Path, destination: Path) -> tuple[str, int]:
    with tarfile.open(
        destination, mode="w", format=tarfile.PAX_FORMAT
    ) as archive:
        for path in sorted(
            corpus.rglob("*"),
            key=lambda item: item.relative_to(corpus).as_posix(),
        ):
            if path.is_symlink():
                raise ValueError(
                    "private corpus archive cannot contain symlinks"
                )
            _add_tar_entry(archive, path, corpus)
    payload = destination.read_bytes()
    return sha256(payload).hexdigest(), len(payload)


def _failure_item(
    receipt: FailureReceipt,
    decision: ReuseGateDecision,
) -> USLiveCorpusItem:
    return USLiveCorpusItem(
        source_id=receipt.source.source_id,
        status="failed",
        rights_state=receipt.rights_state.value,
        reuse_disposition=decision.disposition.value,
        failure_code=receipt.failure_code,
    )


def _success_item(
    receipt: SourceReceipt,
    landing: BronzeAcquisition | BronzeLanding,
    decision: ReuseGateDecision,
    *,
    source_record_failure_code: str | None = None,
) -> USLiveCorpusItem:
    temporal = receipt.temporal
    if temporal is None:
        raise ValueError("live acquisition requires temporal identity")
    admission = landing.admission
    source_records_path = (
        landing.source_records_path
        if isinstance(landing, BronzeLanding)
        else None
    )
    source_record_count = (
        pq.read_metadata(source_records_path).num_rows
        if isinstance(landing, BronzeLanding)
        and source_records_path is not None
        else None
    )
    return USLiveCorpusItem(
        source_id=receipt.source.source_id,
        status="succeeded",
        acquisition_id=temporal.acquisition_id,
        payload_sha256=receipt.payload.sha256,
        payload_byte_count=receipt.payload.byte_count,
        rights_state=receipt.rights_state.value,
        admission_state=admission.state.value,
        parquet_projected=isinstance(landing, BronzeLanding),
        source_records_projected=source_records_path is not None,
        source_record_count=source_record_count,
        source_record_failure_code=source_record_failure_code,
        reuse_disposition=decision.disposition.value,
    )


def exercise_us_live_bronze_corpus(  # ruff: ignore[too-many-locals, too-many-statements]
    *,
    repository_root: Path,
    output_dir: Path,
    authorization_path: Path,
    catalog: Iterable[MedicineDataSource] | None = None,
    transport: httpx.BaseTransport | None = None,
    reuse_searcher: ReuseSearcher | None = None,
    clock: Clock = lambda: datetime.now(UTC),
) -> USLiveCorpusManifest:
    """Acquire, admit, recover, and privately archive the approved cohort."""

    authorization = USLiveAcquisitionAuthorization.model_validate_json(
        authorization_path.read_bytes()
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus = output_dir / "corpus"
    bronze = corpus / "bronze"
    downloads = corpus / "downloads"
    evidence = corpus / "evidence"
    evidence.mkdir(parents=True)
    shutil.copy2(authorization_path, evidence / authorization_path.name)
    sources = tuple(load_source_catalog() if catalog is None else catalog)

    def default_reuse_searcher(source_id: str) -> ReuseGateDecision:
        return evaluate_reuse_gate(
            source_id,
            repository_root=repository_root,
            catalog=sources,
        )

    searcher: ReuseSearcher = reuse_searcher or default_reuse_searcher
    exercised_at = clock()
    if exercised_at.tzinfo is None:
        raise ValueError("acquisition clock must be timezone-aware")
    results: list[USLiveCorpusItem] = []
    for item in authorization.authorized_sources:
        source = _endpoint_source(item, sources)
        decision = searcher(item.source_id)
        destination = downloads / f"{item.source_id}.{item.media_hint}"
        receipt: Receipt = acquire_source(
            item.source_id,
            destination,
            repository_root=repository_root,
            catalog=(source,),
            policy=AcquisitionPolicy(
                timeout_seconds=90,
                max_bytes=item.max_bytes,
                max_redirects=5,
                allowed_content_types=(
                    "application/json",
                    "application/octet-stream",
                    "application/zip",
                    "application/x-zip-compressed",
                    "binary/octet-stream",
                    "text/html",
                    "text/plain",
                ),
            ),
            transport=transport,
            evidence_class=EvidenceClass.LIVE,
            clock=lambda: exercised_at,
            reuse_decision=decision,
        )
        if isinstance(receipt, FailureReceipt):
            results.append(_failure_item(receipt, decision))
            continue
        payload = destination.read_bytes()
        _reject_excluded_openfda_material(item, payload)
        bound = _bind_rights(item, receipt, exercised_at)
        source_record_failure_code = None
        try:
            source_records = us_source_record_batch(
                item.source_id,
                payload,
                item.media_hint,
            )
        except TypeError, ValueError, pa.ArrowException:
            source_records = None
            source_record_failure_code = "source_record_projection_failed"
        landing = land_bronze_payload(
            payload,
            bound,
            bronze_root=bronze,
            media_hint=item.media_hint,
            admission_decided_at=exercised_at,
            transformation_completed_at=exercised_at,
            source_records=source_records,
        )
        results.append(
            _success_item(
                bound,
                landing,
                decision,
                source_record_failure_code=source_record_failure_code,
            )
        )

    result_bytes = (
        json.dumps(
            [item.model_dump(mode="json") for item in results],
            indent=2,
            sort_keys=True,
        ).encode()
        + b"\n"
    )
    (evidence / "redacted-acquisition-results.json").write_bytes(result_bytes)
    clean_room = corpus / "clean-room"
    _copy_evidentiary_truth(bronze, clean_room)
    recovery = reconstruct_bronze(
        clean_room,
        fail_closed_on_incomplete=False,
        source_record_factory=_recoverable_source_record_batch,
    )
    archive_path = output_dir / PRIVATE_ARCHIVE_FILENAME
    archive_digest, archive_size = _write_private_archive(corpus, archive_path)
    succeeded = tuple(item for item in results if item.status == "succeeded")
    accepted = tuple(
        item
        for item in succeeded
        if item.admission_state == BronzeAdmissionState.ACCEPTED.value
    )
    quarantined = tuple(
        item
        for item in succeeded
        if item.admission_state == BronzeAdmissionState.QUARANTINED.value
    )
    projected = tuple(
        item for item in succeeded if item.source_records_projected
    )
    recovered_source_records = len(
        tuple((clean_room / "parquet").rglob("source_records.parquet"))
    )
    manifest = USLiveCorpusManifest(
        exercised_at=exercised_at,
        source_count=len(results),
        acquisition_succeeded_count=len(succeeded),
        acquisition_failed_count=len(results) - len(succeeded),
        accepted_admission_count=len(accepted),
        quarantined_admission_count=len(quarantined),
        recovered_acquisition_count=len(recovery.landings),
        source_record_projection_count=len(projected),
        recovered_source_record_projection_count=recovered_source_records,
        items=tuple(results),
        archive_sha256=archive_digest,
        archive_byte_count=archive_size,
    )
    (output_dir / PRIVATE_MANIFEST_FILENAME).write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / PRIVATE_CHECKSUM_FILENAME).write_text(
        f"{archive_digest}  {PRIVATE_ARCHIVE_FILENAME}\n",
        encoding="utf-8",
    )
    return manifest
