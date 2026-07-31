"""Fail-closed measured source and jurisdiction coverage qualification.

The authoritative source catalog defines the denominator.  Committed fixtures
and executable adapters can raise an individual source to fixture maturity;
only a durable live receipt can raise it to live maturity.  This module never
uses the network and never treats missing evidence as negative medicine status.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from importlib import import_module
from pathlib import Path
from typing import Literal, Self, cast

import orjson
from pydantic import AnyUrl, Field, model_validator

from .adapters.au_artg import project_artg_csv
from .adapters.au_pbs import project_pbs_xml
from .adapters.canada import (
    project_dpd_api,
    project_dpd_bulk,
    project_noc_extract,
)
from .adapters.european_union import (
    project_ema_medicine_csv,
    project_union_register_xml,
)
from .adapters.japan import (
    project_mhlw_nhi_price_csv,
    project_pmda_approval_csv,
)
from .adapters.nz_medsafe import project_medsafe_registry_csv
from .adapters.nz_pharmac import project_pharmac_schedule_xml
from .adapters.united_kingdom import (
    project_mhra_products_csv,
    project_nice_appraisals_xml,
)
from .adapters.us_cms_partd import project_cms_partd_csv
from .adapters.us_drugsfda import project_drugsfda_api
from .countries import Capability, SourceDimension, builtin_source_capabilities
from .models import AssertionKind, CanonicalMedicineRecord, FrozenModel
from .receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)
from .source_catalog import MedicineDataSource, load_source_catalog
from .terminology import bootstrap_rxnorm_resolver

SCHEMA_ID = "global-medicines-atlas.stable-v1-measured-coverage"
CATALOG_PATH = "src/global_medicines_atlas/data/medicine_source_catalog.json"
SCHEMA_PATH = "schemas/stable-v1-measured-coverage-v1.json"
_ZERO_DIGEST = "0" * 64
_FIXTURE_TIME = datetime(2026, 7, 29, tzinfo=UTC)


def _canonical_bytes(value: object) -> bytes:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS)


def _digest_value(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_nzulm_records(root: Path) -> tuple[object, ...]:
    module = import_module("sources.nz.nzulm_fhir")
    loader = cast(
        "Callable[[Path], tuple[object, ...]]",
        module.load_upstream_fixture_records,
    )
    return loader(root)


class EvidenceMaturity(StrEnum):
    """Ordered evidence layers used in the qualification receipt."""

    CATALOGUE = "catalogue"
    FIXTURE = "fixture"
    LIVE = "live"


_MATURITY_ORDER = {
    EvidenceMaturity.CATALOGUE: 0,
    EvidenceMaturity.FIXTURE: 1,
    EvidenceMaturity.LIVE: 2,
}


class ArtifactEvidence(FrozenModel):
    """Content identity for one repository-local qualification input."""

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)


class DimensionCounts(FrozenModel):
    """Counts kept separate across all medicine evidence dimensions."""

    regulatory: int = Field(ge=0)
    funding: int = Field(ge=0)
    formulary: int = Field(ge=0)
    terminology: int = Field(ge=0)


class SourceCoverage(FrozenModel):
    """Measured evidence for one authoritative catalog source."""

    source_id: str = Field(min_length=1)
    jurisdictions: tuple[str, ...] = Field(min_length=1)
    catalog_dimension: SourceDimension
    catalog_information_domains: tuple[str, ...] = Field(min_length=1)
    catalog_record_entities: tuple[str, ...] = Field(min_length=1)
    catalog_available_fields: tuple[str, ...] = Field(min_length=1)
    catalogued: Literal[True] = True
    fixture_qualified: bool
    live_qualified: bool
    highest_maturity: EvidenceMaturity
    measured_fixture_dimensions: tuple[SourceDimension, ...] = ()
    catalog_fixture_dimension_agreement: bool | None = None
    measured_fixture_records: int = Field(default=0, ge=0)
    fixture_artifacts: tuple[ArtifactEvidence, ...] = ()
    implementation_artifacts: tuple[ArtifactEvidence, ...] = ()
    implementations: tuple[str, ...] = ()
    live_receipt_id: str | None = Field(default=None, min_length=1)
    unsupported_claims: tuple[str, ...] = (
        "current/live source coverage",
        "exhaustive jurisdiction coverage",
        "medicine-level negative status from absence",
    )

    @model_validator(mode="after")
    def evidence_layers_are_coherent(self) -> Self:
        for values, label in (
            (self.jurisdictions, "jurisdictions"),
            (self.catalog_information_domains, "information domains"),
            (self.catalog_record_entities, "record entities"),
            (self.catalog_available_fields, "available fields"),
            (self.measured_fixture_dimensions, "fixture dimensions"),
            (self.implementations, "implementations"),
        ):
            if tuple(sorted(values)) != values or len(set(values)) != len(
                values
            ):
                raise ValueError(f"{label} must be sorted and unique")
        for artifacts, label in (
            (self.fixture_artifacts, "fixture artifacts"),
            (self.implementation_artifacts, "implementation artifacts"),
        ):
            paths = tuple(item.path for item in artifacts)
            if tuple(sorted(paths)) != paths or len(set(paths)) != len(paths):
                raise ValueError(f"{label} must be sorted and unique")
        expected_maturity = (
            EvidenceMaturity.LIVE
            if self.live_qualified
            else EvidenceMaturity.FIXTURE
            if self.fixture_qualified
            else EvidenceMaturity.CATALOGUE
        )
        if self.highest_maturity != expected_maturity:
            raise ValueError("highest maturity disagrees with evidence layers")
        if self.fixture_qualified:
            if (
                not self.fixture_artifacts
                or not self.implementation_artifacts
                or not self.implementations
                or not self.measured_fixture_dimensions
                or self.measured_fixture_records <= 0
            ):
                raise ValueError(
                    "fixture qualification requires measured evidence"
                )
            agreement = self.measured_fixture_dimensions == (
                self.catalog_dimension,
            )
            if self.catalog_fixture_dimension_agreement != agreement:
                raise ValueError(
                    "catalog/fixture dimension agreement is misreported"
                )
        elif any((
            self.fixture_artifacts,
            self.implementation_artifacts,
            self.implementations,
            self.measured_fixture_dimensions,
            self.measured_fixture_records,
        )):
            raise ValueError(
                "catalogue-only source cannot carry fixture evidence"
            )
        elif self.catalog_fixture_dimension_agreement is not None:
            raise ValueError(
                "catalogue-only source cannot claim fixture dimension agreement"
            )
        if self.live_qualified != (self.live_receipt_id is not None):
            raise ValueError(
                "live qualification requires exactly one receipt identity"
            )
        if self.live_qualified and not self.fixture_qualified:
            raise ValueError(
                "live qualification requires fixture qualification"
            )
        return self


class JurisdictionCoverage(FrozenModel):
    """Catalog denominator and measured evidence totals for one jurisdiction."""

    jurisdiction: str = Field(min_length=2, max_length=6)
    catalog_source_count: int = Field(gt=0)
    fixture_source_count: int = Field(ge=0)
    live_source_count: int = Field(ge=0)
    catalog_dimensions: DimensionCounts
    fixture_dimensions: DimensionCounts
    live_dimensions: DimensionCounts
    highest_maturity: EvidenceMaturity
    regulatory_and_funding_both_catalogued: bool
    regulatory_and_funding_both_fixture_qualified: bool


class CoverageTotals(FrozenModel):
    """Receipt-wide denominators and maturity counts."""

    catalog_jurisdictions: int = Field(gt=0)
    represented_jurisdictions: int = Field(gt=0)
    catalog_sources: int = Field(gt=0)
    fixture_qualified_sources: int = Field(ge=0)
    live_qualified_sources: int = Field(ge=0)
    catalog_dimensions: DimensionCounts
    fixture_dimensions: DimensionCounts
    live_dimensions: DimensionCounts


class MeasuredCoverageBody(FrozenModel):
    """Deterministic coverage body before content binding."""

    schema_id: Literal["global-medicines-atlas.stable-v1-measured-coverage"] = (
        SCHEMA_ID
    )
    schema_version: Literal[1] = 1
    catalog: ArtifactEvidence
    catalog_jurisdiction_denominator: tuple[str, ...] = Field(min_length=1)
    qualification_inputs: tuple[ArtifactEvidence, ...] = Field(min_length=3)
    sources: tuple[SourceCoverage, ...] = Field(min_length=1)
    jurisdictions: tuple[JurisdictionCoverage, ...] = Field(min_length=1)
    totals: CoverageTotals
    evidence_policy: Literal[
        "catalogue declarations; executable committed fixtures; durable live receipts"
    ] = "catalogue declarations; executable committed fixtures; durable live receipts"
    regulatory_funding_separate: Literal[True] = True
    unsupported_coverage_fails_closed: Literal[True] = True
    external_network_used: Literal[False] = False
    external_publication_performed: Literal[False] = False
    exhaustive_global_coverage: Literal[False] = False
    current_live_coverage_claimed: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def totals_are_coherent(self) -> Self:
        if tuple(
            sorted(self.catalog_jurisdiction_denominator)
        ) != self.catalog_jurisdiction_denominator or len(
            set(self.catalog_jurisdiction_denominator)
        ) != len(self.catalog_jurisdiction_denominator):
            raise ValueError(
                "catalog jurisdiction denominator must be sorted and unique"
            )
        if (
            tuple(sorted(self.sources, key=lambda row: row.source_id))
            != self.sources
        ):
            raise ValueError("sources must be sorted")
        if (
            tuple(sorted(self.jurisdictions, key=lambda row: row.jurisdiction))
            != self.jurisdictions
        ):
            raise ValueError("jurisdictions must be sorted")
        expected = _coverage_totals(
            self.sources,
            len(self.catalog_jurisdiction_denominator),
        )
        if self.totals != expected:
            raise ValueError("coverage totals disagree with source evidence")
        return self


class ContentBoundMeasuredCoverageReceipt(FrozenModel):
    """Coverage body protected by a deterministic SHA-256 digest."""

    body: MeasuredCoverageBody
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_digest_matches(self) -> Self:
        if self.receipt_sha256 != _digest_value(
            self.body.model_dump(mode="json")
        ):
            raise ValueError("measured coverage receipt digest mismatch")
        return self


@dataclass(frozen=True, slots=True)
class _ProbeSpec:
    catalog_source_id: str
    adapter_source_id: str
    jurisdiction: str
    fixture_paths: tuple[str, ...]
    implementation_paths: tuple[str, ...]
    implementations: tuple[str, ...]
    acquisition_method: AcquisitionMethod = AcquisitionMethod.LOCAL_FIXTURE


_PROBES = (
    _ProbeSpec(
        "au-artg",
        "au-artg",
        "AUS",
        ("tests/fixtures/adapters/au_artg.csv",),
        ("src/global_medicines_atlas/adapters/au_artg.py",),
        ("adapters.au_artg:project_artg_csv",),
    ),
    _ProbeSpec(
        "au-pbs-historical-xml",
        "au-pbs",
        "AUS",
        ("tests/fixtures/adapters/au_pbs.xml",),
        ("src/global_medicines_atlas/adapters/au_pbs.py",),
        ("adapters.au_pbs:project_pbs_xml",),
    ),
    _ProbeSpec(
        "ca-dpd",
        "ca-dpd",
        "CAN",
        (
            "tests/fixtures/native/ca/dpd_api.json",
            "tests/fixtures/native/ca/dpd_bulk.csv",
        ),
        ("src/global_medicines_atlas/adapters/canada.py",),
        (
            "adapters.canada:project_dpd_api",
            "adapters.canada:project_dpd_bulk",
        ),
    ),
    _ProbeSpec(
        "ca-noc",
        "ca-noc",
        "CAN",
        ("tests/fixtures/native/ca/noc_extract.csv",),
        ("src/global_medicines_atlas/adapters/canada.py",),
        ("adapters.canada:project_noc_extract",),
    ),
    _ProbeSpec(
        "eu-ema-medicines",
        "eu-ema",
        "EU",
        ("tests/fixtures/native/eu/ema_medicines.csv",),
        ("src/global_medicines_atlas/adapters/european_union.py",),
        ("adapters.european_union:project_ema_medicine_csv",),
    ),
    _ProbeSpec(
        "eu-union-register",
        "eu-union-register",
        "EU",
        ("tests/fixtures/native/eu/union_register.xml",),
        ("src/global_medicines_atlas/adapters/european_union.py",),
        ("adapters.european_union:project_union_register_xml",),
    ),
    _ProbeSpec(
        "gb-mhra-products",
        "uk-mhra",
        "GBR",
        ("tests/fixtures/native/gb/mhra_products.csv",),
        ("src/global_medicines_atlas/adapters/united_kingdom.py",),
        ("adapters.united_kingdom:project_mhra_products_csv",),
    ),
    _ProbeSpec(
        "gb-nice-ta",
        "uk-nice",
        "GBR",
        ("tests/fixtures/native/gb/nice_appraisals.xml",),
        ("src/global_medicines_atlas/adapters/united_kingdom.py",),
        ("adapters.united_kingdom:project_nice_appraisals_xml",),
    ),
    _ProbeSpec(
        "jp-mhlw-nhi-price",
        "jp-mhlw-nhi",
        "JPN",
        ("tests/fixtures/native/jp/mhlw_nhi_prices.csv",),
        ("src/global_medicines_atlas/adapters/japan.py",),
        ("adapters.japan:project_mhlw_nhi_price_csv",),
    ),
    _ProbeSpec(
        "jp-pmda-approvals",
        "jp-pmda",
        "JPN",
        ("tests/fixtures/native/jp/pmda_approvals.csv",),
        ("src/global_medicines_atlas/adapters/japan.py",),
        ("adapters.japan:project_pmda_approval_csv",),
    ),
    _ProbeSpec(
        "nz-medsafe-products",
        "nz-medsafe",
        "NZL",
        ("tests/fixtures/adapters/nz_medsafe_registry.csv",),
        ("src/global_medicines_atlas/adapters/nz_medsafe.py",),
        ("adapters.nz_medsafe:project_medsafe_registry_csv",),
    ),
    _ProbeSpec(
        "nz-pharmac-schedule-xml",
        "nz-pharmac",
        "NZL",
        ("tests/fixtures/adapters/nz_pharmac_schedule.xml",),
        ("src/global_medicines_atlas/adapters/nz_pharmac.py",),
        ("adapters.nz_pharmac:project_pharmac_schedule_xml",),
    ),
    _ProbeSpec(
        "us-cms-partd-formulary",
        "us-cms-partd-formulary",
        "USA",
        ("tests/fixtures/us/cms_partd_formulary.csv",),
        ("src/global_medicines_atlas/adapters/us_cms_partd.py",),
        ("adapters.us_cms_partd:project_cms_partd_csv",),
        AcquisitionMethod.DOWNLOAD,
    ),
    _ProbeSpec(
        "us-drugsfda",
        "us-drugsfda",
        "USA",
        ("tests/fixtures/us/drugsfda_api.json",),
        ("src/global_medicines_atlas/adapters/us_drugsfda.py",),
        ("adapters.us_drugsfda:project_drugsfda_api",),
        AcquisitionMethod.API,
    ),
    _ProbeSpec(
        "global-rxnorm",
        "global-rxnorm",
        "GLOBAL",
        ("src/global_medicines_atlas/data/rxnorm_bootstrap.json",),
        ("src/global_medicines_atlas/terminology.py",),
        (
            "terminology:LocalRxNormResolver",
            "terminology:bootstrap_rxnorm_resolver",
        ),
    ),
    _ProbeSpec(
        "nz-nzulm-bulk",
        "nz-nzulm-bulk",
        "NZL",
        ("vendor/nzmedicines",),
        ("sources/nz/nzulm_fhir/adapter.py",),
        ("sources.nz.nzulm_fhir.adapter:load_upstream_fixture_records",),
    ),
)

_RecordProjector = Callable[
    [bytes, SourceReceipt], tuple[CanonicalMedicineRecord, ...]
]
_SIMPLE_PROJECTORS: dict[str, _RecordProjector] = {
    "au-artg": project_artg_csv,
    "au-pbs-historical-xml": project_pbs_xml,
    "ca-noc": project_noc_extract,
    "eu-ema-medicines": project_ema_medicine_csv,
    "eu-union-register": project_union_register_xml,
    "gb-mhra-products": project_mhra_products_csv,
    "gb-nice-ta": project_nice_appraisals_xml,
    "jp-mhlw-nhi-price": project_mhlw_nhi_price_csv,
    "jp-pmda-approvals": project_pmda_approval_csv,
    "nz-medsafe-products": project_medsafe_registry_csv,
    "nz-pharmac-schedule-xml": project_pharmac_schedule_xml,
}


def _artifact(root: Path, relative_path: str) -> ArtifactEvidence:
    path = root / relative_path
    if not path.is_file():
        raise ValueError(f"qualification input is not a file: {relative_path}")
    payload = path.read_bytes()
    return ArtifactEvidence(
        path=relative_path,
        sha256=_digest_bytes(payload),
        byte_count=len(payload),
    )


def _fixture_artifacts(
    root: Path, spec: _ProbeSpec
) -> tuple[ArtifactEvidence, ...]:
    paths: list[str] = []
    for relative_path in spec.fixture_paths:
        path = root / relative_path
        if path.is_dir():
            paths.extend(
                item.relative_to(root).as_posix()
                for item in path.rglob("*.json")
                if item.name != "nzmedicines.import.json"
            )
        else:
            paths.append(relative_path)
    if not paths:
        raise ValueError(f"no fixture artifacts for {spec.catalog_source_id}")
    return tuple(_artifact(root, path) for path in sorted(set(paths)))


def _receipt(
    payload: bytes,
    spec: _ProbeSpec,
    *,
    method: AcquisitionMethod | None = None,
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id=f"stable-v1-fixture:{spec.catalog_source_id}:{evidence.sha256}",
        source=SourceIdentity(
            catalog_id=spec.catalog_source_id,
            source_id=spec.adapter_source_id,
            jurisdiction=spec.jurisdiction,
            authority="Committed synthetic qualification fixture",
            dataset_title=f"Fixture evidence for {spec.catalog_source_id}",
            catalog_version="stable-v1-fixture-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(f"https://fixtures.invalid/{spec.catalog_source_id}"),
            retrieved_at=_FIXTURE_TIME,
            acquisition_method=method or spec.acquisition_method,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id=f"{spec.catalog_source_id}-qualification-v1",
            transformation_sha256=_ZERO_DIGEST,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def _record_dimensions(
    records: tuple[CanonicalMedicineRecord, ...],
) -> tuple[SourceDimension, ...]:
    kinds = {
        assertion.kind for record in records for assertion in record.assertions
    }
    dimensions = {
        SourceDimension(kind.value)
        for kind in kinds
        if kind
        in {
            AssertionKind.REGULATORY,
            AssertionKind.FUNDING,
            AssertionKind.FORMULARY,
        }
    }
    return tuple(sorted(dimensions))


def _measure_probe(
    root: Path,
    spec: _ProbeSpec,
) -> tuple[int, tuple[SourceDimension, ...]]:
    payloads = [
        (root / path).read_bytes()
        for path in spec.fixture_paths
        if (root / path).is_file()
    ]
    source_id = spec.catalog_source_id
    records: tuple[CanonicalMedicineRecord, ...]
    projector = _SIMPLE_PROJECTORS.get(source_id)
    if projector is not None:
        method = AcquisitionMethod.DOWNLOAD if source_id == "ca-noc" else None
        records = projector(
            payloads[0],
            _receipt(payloads[0], spec, method=method),
        )
    elif source_id == "ca-dpd":
        records = (
            *project_dpd_api(
                payloads[0],
                _receipt(payloads[0], spec, method=AcquisitionMethod.API),
            ),
            *project_dpd_bulk(
                payloads[1],
                _receipt(payloads[1], spec, method=AcquisitionMethod.DOWNLOAD),
            ),
        )
    elif source_id == "us-cms-partd-formulary":
        projection = project_cms_partd_csv(
            payloads[0].decode("utf-8"),
            receipt=_receipt(payloads[0], spec),
        )
        records = projection.records
    elif source_id == "us-drugsfda":
        records = project_drugsfda_api(
            payloads[0], receipt=_receipt(payloads[0], spec)
        )
    elif source_id == "global-rxnorm":
        document = cast(
            "dict[str, object]",
            json.loads(payloads[0]),
        )
        concepts = cast("dict[str, object]", document["concepts"])
        resolver = bootstrap_rxnorm_resolver()
        if any(not resolver.resolve(alias) for alias in sorted(concepts)):
            raise ValueError("RxNorm fixture contains an unresolved alias")
        return len(concepts), (SourceDimension.TERMINOLOGY,)
    elif source_id == "nz-nzulm-bulk":
        resources = _load_nzulm_records(root)
        if not resources:
            raise ValueError("NZULM/NZMT fixture adapter returned no resources")
        return len(resources), (SourceDimension.TERMINOLOGY,)
    else:
        raise ValueError(f"unsupported fixture probe: {source_id}")
    if not records:
        raise ValueError(f"fixture adapter returned no records: {source_id}")
    dimensions = _record_dimensions(records)
    if not dimensions:
        raise ValueError(
            f"fixture adapter returned no status dimension: {source_id}"
        )
    return len(records), dimensions


def _dimension_counts(dimensions: list[SourceDimension]) -> DimensionCounts:
    counts = Counter(dimensions)
    return DimensionCounts(
        regulatory=counts[SourceDimension.REGULATORY],
        funding=counts[SourceDimension.FUNDING],
        formulary=counts[SourceDimension.FORMULARY],
        terminology=counts[SourceDimension.TERMINOLOGY],
    )


def _source_row(
    root: Path,
    source: MedicineDataSource,
    spec: _ProbeSpec | None,
) -> SourceCoverage:
    if spec is None:
        return SourceCoverage(
            source_id=source.source_id,
            jurisdictions=tuple(sorted(source.jurisdictions)),
            catalog_dimension=source.dimension,
            catalog_information_domains=tuple(
                sorted(item.value for item in source.information_domains)
            ),
            catalog_record_entities=tuple(
                sorted(item.value for item in source.record_entities)
            ),
            catalog_available_fields=tuple(
                sorted(item.value for item in source.available_fields)
            ),
            fixture_qualified=False,
            live_qualified=False,
            highest_maturity=EvidenceMaturity.CATALOGUE,
        )
    measured_records, dimensions = _measure_probe(root, spec)
    return SourceCoverage(
        source_id=source.source_id,
        jurisdictions=tuple(sorted(source.jurisdictions)),
        catalog_dimension=source.dimension,
        catalog_information_domains=tuple(
            sorted(item.value for item in source.information_domains)
        ),
        catalog_record_entities=tuple(
            sorted(item.value for item in source.record_entities)
        ),
        catalog_available_fields=tuple(
            sorted(item.value for item in source.available_fields)
        ),
        fixture_qualified=True,
        live_qualified=False,
        highest_maturity=EvidenceMaturity.FIXTURE,
        measured_fixture_dimensions=dimensions,
        catalog_fixture_dimension_agreement=(dimensions == (source.dimension,)),
        measured_fixture_records=measured_records,
        fixture_artifacts=_fixture_artifacts(root, spec),
        implementation_artifacts=tuple(
            _artifact(root, path)
            for path in sorted(set(spec.implementation_paths))
        ),
        implementations=tuple(sorted(spec.implementations)),
    )


def _jurisdiction_rows(
    sources: tuple[SourceCoverage, ...],
) -> tuple[JurisdictionCoverage, ...]:
    grouped: dict[str, list[SourceCoverage]] = defaultdict(list)
    for source in sources:
        for jurisdiction in source.jurisdictions:
            grouped[jurisdiction].append(source)
    rows: list[JurisdictionCoverage] = []
    for jurisdiction, members in sorted(grouped.items()):
        catalog_dimensions = [row.catalog_dimension for row in members]
        fixture_dimensions = [
            dimension
            for row in members
            for dimension in row.measured_fixture_dimensions
        ]
        live_dimensions = [
            row.catalog_dimension for row in members if row.live_qualified
        ]
        highest = max(
            (row.highest_maturity for row in members),
            key=_MATURITY_ORDER.__getitem__,
        )
        rows.append(
            JurisdictionCoverage(
                jurisdiction=jurisdiction,
                catalog_source_count=len(members),
                fixture_source_count=sum(
                    row.fixture_qualified for row in members
                ),
                live_source_count=sum(row.live_qualified for row in members),
                catalog_dimensions=_dimension_counts(catalog_dimensions),
                fixture_dimensions=_dimension_counts(fixture_dimensions),
                live_dimensions=_dimension_counts(live_dimensions),
                highest_maturity=highest,
                regulatory_and_funding_both_catalogued=(
                    SourceDimension.REGULATORY in catalog_dimensions
                    and SourceDimension.FUNDING in catalog_dimensions
                ),
                regulatory_and_funding_both_fixture_qualified=(
                    SourceDimension.REGULATORY in fixture_dimensions
                    and SourceDimension.FUNDING in fixture_dimensions
                ),
            )
        )
    return tuple(rows)


def _coverage_totals(
    sources: tuple[SourceCoverage, ...],
    catalog_jurisdiction_count: int,
) -> CoverageTotals:
    return CoverageTotals(
        catalog_jurisdictions=catalog_jurisdiction_count,
        represented_jurisdictions=len({
            j for source in sources for j in source.jurisdictions
        }),
        catalog_sources=len(sources),
        fixture_qualified_sources=sum(
            source.fixture_qualified for source in sources
        ),
        live_qualified_sources=sum(source.live_qualified for source in sources),
        catalog_dimensions=_dimension_counts([
            source.catalog_dimension for source in sources
        ]),
        fixture_dimensions=_dimension_counts([
            dimension
            for source in sources
            for dimension in source.measured_fixture_dimensions
        ]),
        live_dimensions=_dimension_counts([
            source.catalog_dimension
            for source in sources
            if source.live_qualified
        ]),
    )


def _catalog_context(
    root: Path,
) -> tuple[tuple[MedicineDataSource, ...], tuple[str, ...]]:
    catalog = tuple(
        sorted(load_source_catalog(), key=lambda item: item.source_id)
    )
    document = cast(
        "dict[str, object]",
        json.loads((root / CATALOG_PATH).read_bytes()),
    )
    raw_jurisdictions = cast(
        "list[dict[str, object]]", document["jurisdictions"]
    )
    jurisdictions = tuple(
        sorted(cast("str", item["jurisdiction"]) for item in raw_jurisdictions)
    )
    return catalog, jurisdictions


def _validate_probe_contract(
    catalog: tuple[MedicineDataSource, ...],
    specs: dict[str, _ProbeSpec],
) -> None:
    catalog_ids = {source.source_id for source in catalog}
    if len(specs) != len(_PROBES):
        raise ValueError("fixture probe source identifiers must be unique")
    unknown_specs = sorted(set(specs) - catalog_ids)
    if unknown_specs:
        raise ValueError(
            f"fixture probes use unknown catalog sources: {unknown_specs}"
        )
    capabilities = builtin_source_capabilities()
    capabilities.validate_catalog(catalog)
    capability_ids = {declaration.source_id for declaration in capabilities}
    uncovered_capabilities = sorted(capability_ids - set(specs))
    if uncovered_capabilities:
        raise ValueError(
            "executable source capabilities lack fixture probes: "
            f"{uncovered_capabilities}"
        )
    live_capabilities = {
        declaration.source_id
        for declaration in capabilities
        if Capability.LIVE_RECEIPT in declaration.capabilities
    }
    if live_capabilities:
        raise ValueError(
            "live capability requires durable receipt integration before "
            f"qualification: {sorted(live_capabilities)}"
        )


def build_measured_coverage_receipt(
    root: Path,
) -> ContentBoundMeasuredCoverageReceipt:
    """Execute local probes and return a deterministic content-bound receipt."""
    root = root.resolve()
    catalog, catalog_jurisdictions = _catalog_context(root)
    specs = {spec.catalog_source_id: spec for spec in _PROBES}
    _validate_probe_contract(catalog, specs)

    rows = tuple(
        _source_row(root, source, specs.get(source.source_id))
        for source in catalog
    )
    jurisdictions = _jurisdiction_rows(rows)
    catalog_artifact = _artifact(root, CATALOG_PATH)
    qualification_inputs = tuple(
        sorted(
            (
                catalog_artifact,
                _artifact(root, "src/global_medicines_atlas/countries.py"),
                _artifact(
                    root,
                    "src/global_medicines_atlas/stable_v1_measured_coverage.py",
                ),
                _artifact(
                    root,
                    "scripts/qualify_stable_v1_measured_coverage.py",
                ),
                _artifact(root, SCHEMA_PATH),
            ),
            key=lambda item: item.path,
        )
    )
    body = MeasuredCoverageBody(
        catalog=catalog_artifact,
        catalog_jurisdiction_denominator=catalog_jurisdictions,
        qualification_inputs=qualification_inputs,
        sources=rows,
        jurisdictions=jurisdictions,
        totals=_coverage_totals(
            rows,
            len(catalog_jurisdictions),
        ),
        limitations=(
            "Catalogue rows describe declared resource scope, not current medicine-level coverage.",
            "Fixture qualification measures committed representative payloads, not live source currency or completeness.",
            "No source has a durable live receipt in this offline qualification.",
            "Absence from a source is unknown or not covered and never evidence of unapproval or non-funding.",
            "Regulatory, funding, formulary and terminology dimensions remain separate.",
        ),
    )
    return ContentBoundMeasuredCoverageReceipt(
        body=body,
        receipt_sha256=_digest_value(body.model_dump(mode="json")),
    )


def verify_measured_coverage_receipt(
    receipt: ContentBoundMeasuredCoverageReceipt,
    root: Path,
) -> None:
    """Fail closed unless the receipt exactly matches current local evidence."""
    expected = build_measured_coverage_receipt(root)
    if receipt != expected:
        raise ValueError(
            "measured coverage receipt does not match current evidence"
        )


def require_coverage(
    receipt: ContentBoundMeasuredCoverageReceipt,
    *,
    source_ids: tuple[str, ...],
    maturity: Literal["catalogue", "fixture", "live"],
    dimensions: tuple[SourceDimension, ...] = (),
) -> None:
    """Reject unsupported coverage requests instead of weakening the claim."""
    rows = {source.source_id: source for source in receipt.body.sources}
    unknown = sorted(set(source_ids) - set(rows))
    if unknown:
        raise ValueError(f"unknown source coverage requested: {unknown}")
    required_maturity = EvidenceMaturity(maturity)
    required_level = _MATURITY_ORDER[required_maturity]
    for source_id in sorted(set(source_ids)):
        row = rows[source_id]
        if _MATURITY_ORDER[row.highest_maturity] < required_level:
            raise ValueError(
                f"{source_id} has {row.highest_maturity} maturity, not {maturity}"
            )
        available: set[SourceDimension] = (
            {row.catalog_dimension}
            if maturity == EvidenceMaturity.CATALOGUE
            else set(row.measured_fixture_dimensions)
            if maturity == EvidenceMaturity.FIXTURE
            else {row.catalog_dimension}
            if row.live_qualified
            else set()
        )
        missing = sorted(set(dimensions) - available)
        if missing:
            raise ValueError(
                f"{source_id} lacks {maturity} dimensions: "
                f"{[item.value for item in missing]}"
            )


def write_measured_coverage_receipt(
    receipt: ContentBoundMeasuredCoverageReceipt,
    destination: Path,
) -> None:
    """Atomically write canonical JSON and re-validate the model."""
    payload = _canonical_bytes(receipt.model_dump(mode="json")) + b"\n"
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(payload)
    parsed = ContentBoundMeasuredCoverageReceipt.model_validate_json(payload)
    if parsed != receipt:
        raise ValueError("serialized measured coverage receipt changed meaning")
    temporary.replace(destination)
