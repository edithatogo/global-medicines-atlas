"""Bounded official MBS release staging; public availability is a later gate."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from time import sleep as system_sleep
from typing import Literal

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field, HttpUrl, model_validator

from .acquisition import AcquisitionPolicy, Receipt, acquire_source
from .adapters.au_mbs import MbsSourceBatch, parse_mbs_source_xml
from .bronze_admission import (
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
)
from .mbs_compatibility import select_p7_records
from .models import FrozenModel
from .receipts import (
    EvidenceClass,
    RightsState,
    SourceReceipt,
    require_temporal,
    temporal_identity_from_source,
)
from .reuse_gate import ReuseGateDecision
from .source_catalog import MedicineDataSource, load_source_catalog
from .source_health import (
    ProbeState,
    SourceHealthObservation,
    build_source_health_receipt,
    source_health_receipt_json,
)

APPROVED_MBS_URL = "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/650f3eec0dfb990fca25692100069854/81efb2067580a870ca258e28007f588c/$FILE/MBS-XML-20260801.XML"


class MbsReleaseContract(FrozenModel):
    """One enumerated release, never permission for arbitrary future URLs."""

    source_id: Literal["au-mbs"] = "au-mbs"
    dataset: Literal["edithatogo/australian-mbs-source-archive"]
    effective_date: date
    source_page: HttpUrl
    source_url: HttpUrl
    publication_authorized: bool = False
    authorization_reference: Literal[
        "https://github.com/edithatogo/global-medicines-atlas/issues/339#issuecomment-5467052330"
    ]

    @model_validator(mode="after")
    def exact_official_surface(self) -> MbsReleaseContract:
        suffix = self.effective_date.strftime("%Y%m%d")
        prefix = (
            "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/"
        )
        if (
            self.effective_date != date(2026, 8, 1)
            or str(self.source_page) != f"{prefix}Content/Downloads-{suffix}"
            or str(self.source_url) != APPROVED_MBS_URL
        ):
            raise ValueError(
                "MBS contract must bind the exact official release surface"
            )
        return self


class MbsArchiveObject(FrozenModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=0)
    role: str


class MbsReleaseManifest(FrozenModel):
    schema_id: Literal["global-medicines-atlas.mbs-release"] = (
        "global-medicines-atlas.mbs-release"
    )
    source_id: Literal["au-mbs"] = "au-mbs"
    contract: MbsReleaseContract
    evidence_class: EvidenceClass
    admission_state: Literal["accepted", "quarantined", "unavailable"]
    record_count: int = Field(ge=0)
    p7_record_count: int = Field(ge=0)
    data_acquired: Literal[False] = False
    objects: tuple[MbsArchiveObject, ...]


@dataclass(frozen=True)
class MbsReleaseStage:
    path: Path
    manifest_path: str
    manifest: MbsReleaseManifest


def require_mbs_hosted_authority(contract: MbsReleaseContract) -> None:
    """Fail closed before local live acquisition or publication attempts."""
    contract = MbsReleaseContract.model_validate(contract.model_dump())
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY")
        != "edithatogo/global-medicines-atlas"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
    ):
        raise ValueError(
            "MBS live acquisition/publication requires GitHub Actions on main"
        )
    if not contract.publication_authorized:
        raise ValueError("exact MBS release publication is not authorized")


def mbs_source_parquet(
    batch: MbsSourceBatch, *, only_p7: bool = False
) -> bytes:
    """Preserve ordered native fields, including absent versus blank fields."""
    records = select_p7_records(batch) if only_p7 else batch.records
    fields_type = pa.list_(
        pa.struct([
            pa.field("name", pa.string()),
            pa.field("value", pa.string()),
        ])
    )
    schema = pa.schema(
        [
            pa.field("source_record_id", pa.string()),
            pa.field("source_ordinal", pa.int64()),
            pa.field("fields", fields_type),
        ],
        metadata={
            "source_id": "au-mbs",
            "schema_era": batch.schema_era or "unknown",
            "provenance": batch.provenance.model_dump_json(),
            "selection": "Group=P7" if only_p7 else "all",
        },
    )
    arrays = [
        pa.array(
            [record.source_record_id for record in records], type=pa.string()
        ),
        pa.array(
            [record.source_ordinal for record in records], type=pa.int64()
        ),
        pa.array(
            [
                [field.model_dump() for field in record.fields]
                for record in records
            ],
            type=fields_type,
        ),
    ]
    output = BytesIO()
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        pa.Table.from_arrays(arrays, schema=schema),
        output,
        compression="zstd",
        version="2.6",
        use_dictionary=False,
    )
    return output.getvalue()


def _object(
    stage: Path, path: str, payload: bytes, role: str
) -> MbsArchiveObject:
    target = stage / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return MbsArchiveObject(
        path=path,
        sha256=sha256(payload).hexdigest(),
        bytes=len(payload),
        role=role,
    )


def _release_receipt(
    receipt: SourceReceipt, contract: MbsReleaseContract
) -> SourceReceipt:
    value = receipt.model_dump()
    value["source"]["catalog_version"] = str(contract.effective_date)
    if receipt.evidence_class is EvidenceClass.LIVE:
        value["rights_state"] = RightsState.PERMITTED
        value["rights_reference"] = str(contract.authorization_reference)
    # The version participates in the acquisition identity.
    value["temporal"] = temporal_identity_from_source(
        retrieved_at=receipt.retrieval.retrieved_at,
        source_id="au-mbs",
        payload_sha256=receipt.payload.sha256,
        source_version=str(contract.effective_date),
        original_uri=str(contract.source_url),
    )
    return SourceReceipt.model_validate(value)


def _acquire_attempts(
    source: MedicineDataSource,
    repository_root: Path,
    *,
    reuse_decision: ReuseGateDecision,
    transport: httpx.BaseTransport | None,
    clock: Callable[[], datetime],
    sleep: Callable[[float], None],
    evidence_class: EvidenceClass,
) -> tuple[Receipt, ...]:
    policy = AcquisitionPolicy(
        timeout_seconds=60,
        max_bytes=9_000_000,
        max_attempts=3,
        max_concurrency_per_host=1,
        max_redirects=0,
        allowed_hosts=("www.mbsonline.gov.au",),
        allowed_content_types=(
            "text/xml",
            "application/xml",
            "application/octet-stream",
            "text/plain",
            "text/html",
        ),
    )
    attempts: list[Receipt] = []
    for attempt in range(3):
        if attempt:
            sleep(2)
        receipt = acquire_source(
            "au-mbs",
            Path("build/mbs-release/source.xml"),
            repository_root=repository_root,
            catalog=(source,),
            policy=policy,
            transport=transport,
            resolver=(lambda _: ("8.8.8.8",))
            if transport is not None
            else None,
            evidence_class=evidence_class,
            clock=clock,
            reuse_decision=reuse_decision,
        )
        attempts.append(
            receipt.model_copy(update={"evidence_class": evidence_class})
            if transport is not None
            else receipt
        )
        if isinstance(receipt, SourceReceipt) or not receipt.retryable:
            break
    return tuple(attempts)


def stage_mbs_release(  # ruff: ignore[too-many-locals]
    contract: MbsReleaseContract,
    repository_root: Path,
    *,
    reuse_decision: ReuseGateDecision,
    transport: httpx.BaseTransport | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = system_sleep,
) -> MbsReleaseStage:
    """Keep failures and quarantine bytes; never upload or claim acquired data."""
    if transport is None:
        require_mbs_hosted_authority(contract)
    elif not isinstance(transport, httpx.MockTransport):
        raise TypeError("local MBS staging requires MockTransport")
    evidence_class = (
        EvidenceClass.SYNTHETIC if transport is not None else EvidenceClass.LIVE
    )
    source = next(
        item
        for item in load_source_catalog()
        if item.source_id == contract.source_id
    )
    source = source.model_copy(update={"download_url": contract.source_url})
    stage = repository_root / "build" / "mbs-release"
    stage.mkdir(parents=True, exist_ok=False)
    run_id = sha256(
        f"{contract.source_url}:{clock().isoformat()}".encode()
    ).hexdigest()
    prefix = f"bronze/mbs/releases/{contract.effective_date}/{run_id}"
    objects: list[MbsArchiveObject] = []
    attempts = _acquire_attempts(
        source,
        repository_root,
        reuse_decision=reuse_decision,
        transport=transport,
        clock=clock,
        sleep=sleep,
        evidence_class=evidence_class,
    )
    for attempt, receipt in enumerate(attempts, start=1):
        objects.append(
            _object(
                stage,
                f"{prefix}/attempt-{attempt}.json",
                receipt.canonical_json(),
                "attempt",
            )
        )
    receipt = attempts[-1]
    state: Literal["accepted", "quarantined", "unavailable"] = "unavailable"
    record_count = p7_count = 0
    if isinstance(receipt, SourceReceipt):
        receipt = _release_receipt(receipt, contract)
        payload = (stage / "source.xml").read_bytes()
        raw_path = f"raw/mbs/releases/{contract.effective_date}/{receipt.payload.sha256}.xml"
        raw_target = stage / raw_path
        raw_target.parent.mkdir(parents=True, exist_ok=True)
        (stage / "source.xml").rename(raw_target)
        objects.extend([
            MbsArchiveObject(
                path=raw_path,
                sha256=receipt.payload.sha256,
                bytes=len(payload),
                role="raw",
            ),
            _object(
                stage,
                f"{prefix}/source-receipt.json",
                receipt.canonical_json(),
                "source_receipt",
            ),
        ])
        try:
            batch = parse_mbs_source_xml(payload, receipt)
        except ValueError:
            batch = None
        state = "accepted" if batch is not None else "quarantined"
        if batch is not None:
            record_count = batch.record_count
            p7_count = len(select_p7_records(batch))
            objects.extend([
                _object(
                    stage,
                    f"{prefix}/source.parquet",
                    mbs_source_parquet(batch),
                    "source_parquet",
                ),
                _object(
                    stage,
                    f"{prefix}/p7.parquet",
                    mbs_source_parquet(batch, only_p7=True),
                    "p7_parquet",
                ),
            ])
        temporal = require_temporal(receipt.temporal)
        decision = create_admission_decision(
            acquisition_id=temporal.acquisition_id,
            content_id=receipt.payload.sha256,
            state=BronzeAdmissionState(state),
            reason_codes=("mbs_xml_profile_passed",)
            if batch is not None
            else ("mbs_xml_profile_mismatch",),
            validation_results=(
                ValidationResult(
                    check_id="official-mbs-xml",
                    passed=batch is not None,
                    message=f"records:{record_count}; p7_records:{p7_count}",
                ),
            ),
            actor="global-medicines-atlas:mbs-release-v1",
            decided_at=clock(),
        )
        objects.append(
            _object(
                stage,
                f"{prefix}/admission.json",
                (decision.model_dump_json() + "\n").encode(),
                "admission",
            )
        )
    if evidence_class is EvidenceClass.LIVE:
        health = build_source_health_receipt(
            SourceHealthObservation(
                source_id="au-mbs",
                checked_at=receipt.retrieval.retrieved_at,
                state=ProbeState.AVAILABLE
                if state == "accepted"
                else ProbeState.UNAVAILABLE,
                detail="MBS release admitted"
                if state == "accepted"
                else f"MbsRelease{state.title()}: no usable release",
            )
        )
        objects.append(
            _object(
                stage,
                f"{prefix}/source-health.json",
                source_health_receipt_json(health).encode(),
                "source_health",
            )
        )
    manifest = MbsReleaseManifest(
        contract=contract,
        evidence_class=evidence_class,
        admission_state=state,
        record_count=record_count,
        p7_record_count=p7_count,
        objects=tuple(objects),
    )
    manifest_path = f"{prefix}/manifest.json"
    _object(
        stage,
        manifest_path,
        (manifest.model_dump_json(indent=2) + "\n").encode(),
        "manifest",
    )
    return MbsReleaseStage(stage, manifest_path, manifest)
