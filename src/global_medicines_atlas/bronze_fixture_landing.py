"""Land repository-owned source-shaped fixtures into governed Bronze.

These fixtures exercise acquisition, immutable payload storage, receipts,
source-faithful Parquet, and lineage without claiming live-source coverage.
They are repository-owned synthetic evidence and never substitute for a live
source-specific rights receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from pydantic import AnyUrl, Field

from .bronze_admission import BronzeAdmissionState
from .bronze_landing import BronzeLanding, land_bronze_payload
from .models import FrozenModel
from .receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    DeterministicReceipt,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)
from .reuse_gate import (
    ReuseCandidate,
    ReuseCandidateKind,
    ReuseDisposition,
    ReuseGateDecision,
    evaluate_reuse_gate,
)
from .source_catalog import (
    AccessMode,
    AuthenticationMode,
    MedicineDataSource,
    load_source_catalog,
)

FIXTURE_VERSION = "bronze-current-scope-fixtures-v1"
FIXTURE_RIGHTS_REFERENCE = AnyUrl(
    "https://github.com/edithatogo/global-medicines-atlas/blob/main/"
    "DATA_LICENSE.md"
)
CURRENT_SCOPE_FIXTURE_SOURCE_IDS: tuple[str, ...] = (
    "au-artg",
    "au-pbs-historical-xml",
    "ca-dpd",
    "ca-noc",
    "eu-ema-medicines",
    "eu-union-register",
    "gb-mhra-products",
    "gb-nice-ta",
    "global-who-eml",
    "jp-mhlw-nhi-price",
    "jp-pmda-approvals",
    "nz-medsafe-products",
    "nz-pharmac-schedule-xml",
    "us-cms-partd-formulary",
    "us-drugsfda",
    "us-fda-faers",
)


@dataclass(frozen=True, slots=True)
class GovernedFixtureSpec:
    """One repository-owned source-shaped payload used for Bronze landing."""

    source_id: str
    relative_path: str
    payload_path: Path
    media_hint: str


class FixtureLandingRecord(FrozenModel):
    """Portable paths and identities for one landed fixture acquisition."""

    source_id: str = Field(min_length=1)
    fixture_path: str = Field(min_length=1)
    payload_path: str = Field(min_length=1)
    parquet_path: str = Field(min_length=1)
    receipt_path: str = Field(min_length=1)
    lineage_path: str = Field(min_length=1)
    admission_path: str = Field(min_length=1)
    admission_state: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class BronzeFixtureLandingManifest(DeterministicReceipt):
    """Deterministic proof of fixture-only Bronze landing."""

    schema_id: str = "global-medicines-atlas.bronze-fixture-landing"
    schema_version: int = 1
    fixture_version: str = FIXTURE_VERSION
    evidence_class: str = "synthetic_fixture_only"
    live_source_coverage_claimed: bool = False
    retrieved_at: datetime
    source_ids: tuple[str, ...]
    missing_source_ids: tuple[str, ...]
    landings: tuple[FixtureLandingRecord, ...]


_FIXTURE_DECLARATIONS: tuple[tuple[str, str, str], ...] = (
    ("au-artg", "tests/fixtures/adapters/au_artg.csv", "csv"),
    (
        "au-pbs-historical-xml",
        "tests/fixtures/adapters/au_pbs.xml",
        "xml",
    ),
    ("ca-dpd", "tests/fixtures/native/ca/dpd_api.json", "json"),
    ("ca-dpd", "tests/fixtures/native/ca/dpd_bulk.csv", "csv"),
    ("ca-noc", "tests/fixtures/native/ca/noc_extract.csv", "csv"),
    (
        "eu-ema-medicines",
        "tests/fixtures/native/eu/ema_medicines.csv",
        "csv",
    ),
    (
        "eu-union-register",
        "tests/fixtures/native/eu/union_register.xml",
        "xml",
    ),
    (
        "gb-mhra-products",
        "tests/fixtures/native/gb/mhra_products.csv",
        "csv",
    ),
    (
        "gb-nice-ta",
        "tests/fixtures/native/gb/nice_appraisals.xml",
        "xml",
    ),
    (
        "global-who-eml",
        "tests/fixtures/source_expansion/who-eml.csv",
        "csv",
    ),
    (
        "jp-mhlw-nhi-price",
        "tests/fixtures/native/jp/mhlw_nhi_prices.csv",
        "csv",
    ),
    (
        "jp-pmda-approvals",
        "tests/fixtures/native/jp/pmda_approvals.csv",
        "csv",
    ),
    (
        "nz-medsafe-products",
        "tests/fixtures/adapters/nz_medsafe_registry.csv",
        "csv",
    ),
    (
        "nz-pharmac-schedule-xml",
        "tests/fixtures/adapters/nz_pharmac_schedule.xml",
        "xml",
    ),
    (
        "us-cms-partd-formulary",
        "tests/fixtures/us/cms_partd_formulary.csv",
        "csv",
    ),
    (
        "us-drugsfda",
        "tests/fixtures/us/drugsfda_api.json",
        "json",
    ),
    (
        "us-fda-faers",
        "tests/fixtures/source_expansion/faers.json",
        "json",
    ),
)


def _safe_fixture_path(root: Path, relative_path: str) -> Path:
    fixture_root = (root / "tests" / "fixtures").resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(fixture_root):
        raise ValueError("fixture path must remain under tests/fixtures")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def governed_fixture_specs(root: Path) -> tuple[GovernedFixtureSpec, ...]:
    """Resolve the explicit current-scope fixture inventory."""

    specs = tuple(
        GovernedFixtureSpec(
            source_id=source_id,
            relative_path=relative_path,
            payload_path=_safe_fixture_path(root, relative_path),
            media_hint=media_hint,
        )
        for source_id, relative_path, media_hint in _FIXTURE_DECLARATIONS
    )
    actual = {spec.source_id for spec in specs}
    expected = set(CURRENT_SCOPE_FIXTURE_SOURCE_IDS)
    if actual != expected:
        raise ValueError("fixture declarations do not match current scope")
    return specs


def fixture_qualification_patches() -> dict[str, dict[str, object]]:
    """Return catalog claims supported by the executable fixture runner."""

    paths_by_source: dict[str, list[str]] = {
        source_id: [] for source_id in CURRENT_SCOPE_FIXTURE_SOURCE_IDS
    }
    for source_id, relative_path, _media_hint in _FIXTURE_DECLARATIONS:
        paths_by_source[source_id].append(relative_path)
    shared = (
        "src/global_medicines_atlas/bronze_fixture_landing.py",
        "tests/test_bronze_fixture_landing.py",
    )
    return {
        source_id: {
            "readiness": "implemented",
            "integration_layer": (
                "parser" if source_id == "us-drugsfda" else "fixture"
            ),
            "implemented_ingestion": True,
            "discovery_status": "declaration_verified",
            "qualification_state": "fixture_verified",
            "qualification_references": [
                *shared,
                *sorted(paths_by_source[source_id]),
            ],
            "last_verified_at": "2026-08-20",
        }
        for source_id in CURRENT_SCOPE_FIXTURE_SOURCE_IDS
    }


def apply_fixture_qualification_to_catalog(
    document: dict[str, Any],
) -> dict[str, Any]:
    """Apply fixture-only integration evidence without live promotion."""

    raw_sources: object = document.get("sources")
    if not isinstance(raw_sources, list):
        raise TypeError("catalog sources must be a list")
    source_rows = cast("list[object]", raw_sources)
    patches = fixture_qualification_patches()
    seen: set[str] = set()
    for raw in source_rows:
        if not isinstance(raw, dict):
            raise TypeError("catalog source rows must be objects")
        row = cast("dict[str, Any]", raw)
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or source_id not in patches:
            continue
        row.update(patches[source_id])
        row.pop("current_receipt_id", None)
        seen.add(source_id)
    missing = sorted(set(patches) - seen)
    if missing:
        raise KeyError(f"fixture sources missing from catalog: {missing}")
    document["reviewed_at"] = "2026-08-20"
    return document


def validate_fixture_source(source: MedicineDataSource) -> None:
    """Reject credentialed or licensed sources from fixture landing."""

    if source.authentication is not AuthenticationMode.NONE:
        raise ValueError("fixture landing is limited to no-credential sources")
    if source.access_mode is AccessMode.LICENSED_FEED:
        raise ValueError("fixture landing is limited to no-credential sources")


def _fixture_reuse_decision(
    root: Path,
    spec: GovernedFixtureSpec,
    *,
    catalog: tuple[MedicineDataSource, ...],
) -> ReuseGateDecision:
    searched = evaluate_reuse_gate(
        spec.source_id,
        repository_root=root,
        catalog=catalog,
    )
    local = ReuseCandidate(
        surface="local_clones",
        locator=spec.relative_path,
        source_id=spec.source_id,
        kind=ReuseCandidateKind.PAYLOAD,
        digest=sha256(spec.payload_path.read_bytes()).hexdigest(),
    )
    candidates = (*searched.candidates, local)
    return ReuseGateDecision(
        source_id=spec.source_id,
        disposition=ReuseDisposition.REUSE,
        searched_surfaces=searched.searched_surfaces,
        candidates=candidates,
        rationale=(
            "reuse repository-owned governed fixture after searching local "
            "clones, GitHub, Hugging Face, and the source registry"
        ),
        catalogue_revision=searched.catalogue_revision,
    )


def _fixture_receipt(
    source: MedicineDataSource,
    spec: GovernedFixtureSpec,
    payload: bytes,
    *,
    retrieved_at: datetime,
    reuse: ReuseGateDecision,
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    transformation_id = f"{spec.source_id}-{FIXTURE_VERSION}"
    jurisdiction = (
        "GLB"
        if source.jurisdictions[0] == "GLOBAL"
        else source.jurisdictions[0]
    )
    return SourceReceipt(
        receipt_id=f"fixture:{spec.source_id}:{evidence.sha256}",
        source=SourceIdentity(
            catalog_id=source.source_id,
            source_id=source.source_id,
            jurisdiction=jurisdiction,
            authority=source.authority,
            dataset_title=f"Synthetic source-shaped fixture: {source.title}",
            catalog_version=FIXTURE_VERSION,
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(
                "https://github.com/edithatogo/global-medicines-atlas/blob/"
                f"main/{spec.relative_path}"
            ),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        reuse=reuse,
        rights_state=RightsState.PERMITTED,
        rights_reference=FIXTURE_RIGHTS_REFERENCE,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id=transformation_id,
            transformation_sha256=sha256(
                transformation_id.encode("utf-8")
            ).hexdigest(),
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def land_governed_fixtures(
    root: Path,
    *,
    bronze_root: Path,
    retrieved_at: datetime,
) -> BronzeFixtureLandingManifest:
    """Land every current-scope governed fixture without live claims."""

    catalog = tuple(load_source_catalog())
    by_id = {source.source_id: source for source in catalog}
    records: list[FixtureLandingRecord] = []
    for spec in governed_fixture_specs(root):
        source = by_id.get(spec.source_id)
        if source is None:
            raise KeyError(
                f"fixture source is absent from catalog: {spec.source_id}"
            )
        validate_fixture_source(source)
        payload = spec.payload_path.read_bytes()
        reuse = _fixture_reuse_decision(root, spec, catalog=catalog)
        receipt = _fixture_receipt(
            source,
            spec,
            payload,
            retrieved_at=retrieved_at,
            reuse=reuse,
        )
        landing = land_bronze_payload(
            payload,
            receipt,
            bronze_root=bronze_root,
            media_hint=spec.media_hint,
            transformation_completed_at=retrieved_at,
        )
        if not isinstance(landing, BronzeLanding):
            raise TypeError("governed fixture was not admitted for projection")
        admission = landing.admission
        if admission.state is not BronzeAdmissionState.ACCEPTED:
            raise ValueError("governed fixture admission must be accepted")
        if admission.path is None:
            raise ValueError("fixture admission record lacks a durable path")
        temporal = landing.receipt.temporal
        if temporal is None:
            raise ValueError("landed fixture receipt lacks temporal identity")
        records.append(
            FixtureLandingRecord(
                source_id=spec.source_id,
                fixture_path=spec.relative_path,
                payload_path=_relative(landing.payload_path, bronze_root),
                parquet_path=_relative(landing.parquet_path, bronze_root),
                receipt_path=_relative(landing.receipt_path, bronze_root),
                lineage_path=_relative(landing.lineage_path, bronze_root),
                admission_path=_relative(admission.path, bronze_root),
                admission_state=admission.state.value,
                payload_sha256=landing.receipt.payload.sha256,
                acquisition_id=temporal.acquisition_id,
            )
        )
    source_ids = tuple(sorted({record.source_id for record in records}))
    missing = tuple(
        sorted(set(CURRENT_SCOPE_FIXTURE_SOURCE_IDS) - set(source_ids))
    )
    return BronzeFixtureLandingManifest(
        retrieved_at=retrieved_at,
        source_ids=source_ids,
        missing_source_ids=missing,
        landings=tuple(records),
    )
