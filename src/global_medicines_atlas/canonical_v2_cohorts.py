"""Measured canonical schema-v2 migration over governed adapter fixtures.

The qualification is deliberately narrower than adapter availability. A record
is migrated only when its committed source fixture exposes the structural
fields required by schema v2. Missing ingredient or hierarchy data is recorded
as a blocker rather than inferred from a medicine name.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Any, Literal, Self, cast

import orjson
from pydantic import AnyUrl, Field, model_validator

from sources.nz.nzulm_fhir import (
    FhirResourceRecord,
    load_synthetic_fixture_records,
)

from .adapters.au_pbs import project_pbs_xml
from .adapters.european_union import project_ema_medicine_csv
from .adapters.japan import project_pmda_approval_csv
from .adapters.us_drugsfda import project_drugsfda_api
from .canonical_v2 import (
    Package,
    Product,
    StructuralEntity,
    StructuralProjection,
    migrate_record_v1_to_v2,
    rollback_record_v2_to_v1,
)
from .models import AssertionKind, CanonicalMedicineRecord, FrozenModel
from .nz import project_nz_fhir_records
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

RECEIPT_SCHEMA_ID = "global-medicines-atlas.canonical-v2-cohort-receipt"
MIGRATION_CONTRACT = "canonical-medicine-v1-to-structural-v2"
FIXTURE_RETRIEVED_AT = datetime(2026, 7, 29, tzinfo=UTC)


def _canonical_bytes(value: object) -> bytes:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS)


def _digest(value: object) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


class AssertionCounts(FrozenModel):
    """Dimension-specific assertion counts; no combined status is exposed."""

    regulatory: int = Field(ge=0)
    funding: int = Field(ge=0)
    formulary: int = Field(ge=0)

    @property
    def total(self) -> int:
        return self.regulatory + self.funding + self.formulary

    def __add__(self, other: AssertionCounts) -> AssertionCounts:
        return AssertionCounts(
            regulatory=self.regulatory + other.regulatory,
            funding=self.funding + other.funding,
            formulary=self.formulary + other.formulary,
        )


class FixtureArtifact(FrozenModel):
    """Content identity of one committed input fixture."""

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RecordQualification(FrozenModel):
    """Migration and rollback result for one adapter-produced v1 record."""

    record_id: str = Field(min_length=1)
    result: Literal["passed", "blocked_missing_explicit_structure"]
    v1_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    v2_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    rollback_v1_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    assertions: AssertionCounts
    block_reason: str | None = None

    @model_validator(mode="after")
    def result_is_coherent(self) -> Self:
        if self.result == "passed":
            if self.v2_sha256 is None or self.rollback_v1_sha256 is None:
                raise ValueError(
                    "passed migration requires v2 and rollback digests"
                )
            if self.rollback_v1_sha256 != self.v1_sha256:
                raise ValueError(
                    "passed migration requires an exact v2-to-v1 rollback"
                )
            if self.block_reason is not None:
                raise ValueError("passed migration cannot carry a block reason")
        elif (
            self.v2_sha256 is not None
            or self.rollback_v1_sha256 is not None
            or not self.block_reason
        ):
            raise ValueError("blocked migration must carry only a block reason")
        return self


class CohortQualification(FrozenModel):
    """Measured result for one adapter/source fixture cohort."""

    cohort_id: str = Field(min_length=1)
    jurisdiction: str = Field(pattern=r"^[A-Z]{2,3}$")
    source_ids: tuple[str, ...] = Field(min_length=1)
    evidence_class: Literal[
        "preserved_upstream_fixture",
        "synthetic_local_fixture",
    ]
    fixtures: tuple[FixtureArtifact, ...] = Field(min_length=1)
    explicit_fields_used: tuple[str, ...] = ()
    records: tuple[RecordQualification, ...] = Field(min_length=1)
    measured_records: int = Field(gt=0)
    migrated_records: int = Field(ge=0)
    blocked_records: int = Field(ge=0)
    assertions: AssertionCounts
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def measurements_are_coherent(self) -> Self:
        if tuple(sorted(self.source_ids)) != self.source_ids:
            raise ValueError("source identifiers must be sorted")
        if (
            tuple(sorted(self.fixtures, key=lambda item: item.path))
            != self.fixtures
        ):
            raise ValueError("fixture artifacts must be sorted")
        if (
            tuple(sorted(self.records, key=lambda item: item.record_id))
            != self.records
        ):
            raise ValueError("record results must be sorted")
        migrated = sum(item.result == "passed" for item in self.records)
        blocked = len(self.records) - migrated
        assertions = _sum_assertions(item.assertions for item in self.records)
        if self.measured_records != len(self.records):
            raise ValueError("measured record count disagrees with results")
        if self.migrated_records != migrated or self.blocked_records != blocked:
            raise ValueError("cohort disposition counts disagree with results")
        if self.assertions != assertions:
            raise ValueError("cohort assertion counts disagree with records")
        return self


class CanonicalV2CohortReceipt(FrozenModel):
    """Deterministic fixture qualification without a global-coverage claim."""

    schema_id: Literal["global-medicines-atlas.canonical-v2-cohort-receipt"] = (
        RECEIPT_SCHEMA_ID
    )
    schema_version: Literal[1] = 1
    migration_contract: Literal["canonical-medicine-v1-to-structural-v2"] = (
        MIGRATION_CONTRACT
    )
    cohorts: tuple[CohortQualification, ...] = Field(min_length=1)
    measured_records: int = Field(gt=0)
    migrated_records: int = Field(ge=0)
    blocked_records: int = Field(ge=0)
    assertions: AssertionCounts
    all_migrated_round_trips_exact: bool
    complete_global_coverage: Literal[False] = False
    production_data_qualified: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def totals_are_coherent(self) -> Self:
        if (
            tuple(sorted(self.cohorts, key=lambda item: item.cohort_id))
            != self.cohorts
        ):
            raise ValueError("cohorts must be sorted")
        measured = sum(item.measured_records for item in self.cohorts)
        migrated = sum(item.migrated_records for item in self.cohorts)
        blocked = sum(item.blocked_records for item in self.cohorts)
        assertions = _sum_assertions(item.assertions for item in self.cohorts)
        if (
            self.measured_records,
            self.migrated_records,
            self.blocked_records,
        ) != (
            measured,
            migrated,
            blocked,
        ):
            raise ValueError("receipt totals disagree with cohort measurements")
        if self.assertions != assertions:
            raise ValueError("receipt assertion counts disagree with cohorts")
        exact = all(
            record.rollback_v1_sha256 == record.v1_sha256
            for cohort in self.cohorts
            for record in cohort.records
            if record.result == "passed"
        )
        if self.all_migrated_round_trips_exact != exact:
            raise ValueError(
                "round-trip summary disagrees with record evidence"
            )
        return self


class ContentBoundCohortReceipt(FrozenModel):
    """Receipt plus the digest of its canonical receipt payload."""

    receipt: CanonicalV2CohortReceipt
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def digest_matches_receipt(self) -> Self:
        if self.receipt_sha256 != _digest(self.receipt.model_dump(mode="json")):
            raise ValueError("canonical v2 cohort receipt digest mismatch")
        return self


@dataclass(frozen=True, slots=True)
class MigrationCase:
    """One v1 record and either an explicit projection or a blocker."""

    record: CanonicalMedicineRecord
    projection: StructuralProjection | None
    block_reason: str | None = None

    def __post_init__(self) -> None:
        if (self.projection is None) == (self.block_reason is None):
            raise ValueError(
                "case requires exactly one projection or block reason"
            )


@dataclass(frozen=True, slots=True)
class AdapterCohort:
    """Inputs needed to measure one committed fixture cohort."""

    cohort_id: str
    jurisdiction: str
    source_ids: tuple[str, ...]
    evidence_class: Literal[
        "preserved_upstream_fixture",
        "synthetic_local_fixture",
    ]
    fixtures: tuple[FixtureArtifact, ...]
    explicit_fields_used: tuple[str, ...]
    cases: tuple[MigrationCase, ...]
    limitations: tuple[str, ...]


def _assertion_counts(record: CanonicalMedicineRecord) -> AssertionCounts:
    kinds = [item.kind for item in record.assertions]
    return AssertionCounts(
        regulatory=kinds.count(AssertionKind.REGULATORY),
        funding=kinds.count(AssertionKind.FUNDING),
        formulary=kinds.count(AssertionKind.FORMULARY),
    )


def _sum_assertions(values: Iterable[AssertionCounts]) -> AssertionCounts:
    total = AssertionCounts(regulatory=0, funding=0, formulary=0)
    for value in values:
        total += value
    return total


def qualify_adapter_cohort(cohort: AdapterCohort) -> CohortQualification:
    """Run deterministic migration and exact rollback for eligible records."""
    results: list[RecordQualification] = []
    seen: set[str] = set()
    for case in sorted(
        cohort.cases, key=lambda item: item.record.concept.concept_id
    ):
        record = case.record
        record_id = record.concept.concept_id
        if record_id in seen:
            raise ValueError(f"duplicate cohort record identity: {record_id}")
        seen.add(record_id)
        v1_payload = record.model_dump(mode="json")
        v1_sha256 = _digest(v1_payload)
        assertions = _assertion_counts(record)
        if case.projection is None:
            results.append(
                RecordQualification(
                    record_id=record_id,
                    result="blocked_missing_explicit_structure",
                    v1_sha256=v1_sha256,
                    assertions=assertions,
                    block_reason=case.block_reason,
                )
            )
            continue
        migrated = migrate_record_v1_to_v2(record, case.projection)
        rollback = rollback_record_v2_to_v1(migrated)
        if rollback != record:
            raise ValueError(f"non-exact canonical rollback for {record_id}")
        results.append(
            RecordQualification(
                record_id=record_id,
                result="passed",
                v1_sha256=v1_sha256,
                v2_sha256=_digest(migrated.model_dump(mode="json")),
                rollback_v1_sha256=_digest(rollback.model_dump(mode="json")),
                assertions=assertions,
            )
        )
    migrated_count = sum(item.result == "passed" for item in results)
    return CohortQualification(
        cohort_id=cohort.cohort_id,
        jurisdiction=cohort.jurisdiction,
        source_ids=tuple(sorted(cohort.source_ids)),
        evidence_class=cohort.evidence_class,
        fixtures=tuple(sorted(cohort.fixtures, key=_fixture_path)),
        explicit_fields_used=cohort.explicit_fields_used,
        records=tuple(results),
        measured_records=len(results),
        migrated_records=migrated_count,
        blocked_records=len(results) - migrated_count,
        assertions=_sum_assertions(item.assertions for item in results),
        limitations=cohort.limitations,
    )


def qualify_representative_cohorts(
    cohorts: Iterable[AdapterCohort],
) -> ContentBoundCohortReceipt:
    """Qualify cohorts and bind the deterministic aggregate receipt."""
    measured = tuple(
        sorted(
            (qualify_adapter_cohort(cohort) for cohort in cohorts),
            key=lambda item: item.cohort_id,
        )
    )
    if len({item.cohort_id for item in measured}) != len(measured):
        raise ValueError("cohort identifiers must be unique")
    receipt = CanonicalV2CohortReceipt(
        cohorts=measured,
        measured_records=sum(item.measured_records for item in measured),
        migrated_records=sum(item.migrated_records for item in measured),
        blocked_records=sum(item.blocked_records for item in measured),
        assertions=_sum_assertions(item.assertions for item in measured),
        all_migrated_round_trips_exact=True,
        limitations=(
            "Committed fixtures are representative and do not establish complete source or jurisdiction coverage.",
            "Synthetic local fixtures do not qualify live regulatory, funding, formulary, price, or publication evidence.",
            "Records lacking explicit source structure remain blocked; medicine names are never parsed to manufacture schema-v2 fields.",
        ),
    )
    return ContentBoundCohortReceipt(
        receipt=receipt,
        receipt_sha256=_digest(receipt.model_dump(mode="json")),
    )


def receipt_bytes(receipt: ContentBoundCohortReceipt) -> bytes:
    """Serialize a receipt deterministically with a single trailing newline."""
    return orjson.dumps(
        receipt.model_dump(mode="json"),
        option=orjson.OPT_INDENT_2
        | orjson.OPT_SORT_KEYS
        | orjson.OPT_APPEND_NEWLINE,
    )


def write_receipt(
    receipt: ContentBoundCohortReceipt,
    output: Path,
) -> None:
    """Write deterministic qualification evidence."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(receipt_bytes(receipt))


def build_representative_adapter_cohorts(
    project_root: Path,
) -> tuple[AdapterCohort, ...]:
    """Load only committed, bounded fixtures from supported adapters."""
    return (
        _build_ema_cohort(project_root),
        _build_fda_cohort(project_root),
        _build_nzmt_cohort(project_root),
        _build_pbs_cohort(project_root),
        _build_pmda_cohort(project_root),
    )


def _fixture_artifact(project_root: Path, path: Path) -> FixtureArtifact:
    payload = _portable_fixture_bytes(path)
    return FixtureArtifact(
        path=path.relative_to(project_root).as_posix(),
        sha256=sha256(payload).hexdigest(),
    )


def _portable_fixture_bytes(path: Path) -> bytes:
    """Return text-fixture bytes independent of Git checkout EOL policy."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def _fixture_path(artifact: FixtureArtifact) -> str:
    return artifact.path


def _fixture_receipt(
    payload: bytes,
    *,
    source_id: str,
    jurisdiction: str,
    authority: str,
    method: AcquisitionMethod,
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id=f"canonical-v2-fixture:{source_id}",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction=jurisdiction,
            authority=authority,
            dataset_title=f"Representative fixture for {source_id}",
            catalog_version="fixture-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(f"https://fixtures.invalid/{source_id}"),
            retrieved_at=FIXTURE_RETRIEVED_AT,
            acquisition_method=method,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id=f"canonical-v2-cohort:{source_id}",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def _blocked_cases(
    records: Iterable[CanonicalMedicineRecord],
    reason: str,
) -> tuple[MigrationCase, ...]:
    return tuple(
        MigrationCase(record=record, projection=None, block_reason=reason)
        for record in records
    )


def _build_fda_cohort(project_root: Path) -> AdapterCohort:
    path = project_root / "tests/fixtures/us/drugsfda_api.json"
    payload = _portable_fixture_bytes(path)
    receipt = _fixture_receipt(
        payload,
        source_id="us-drugsfda",
        jurisdiction="USA",
        authority="US Food and Drug Administration",
        method=AcquisitionMethod.API,
    )
    records = project_drugsfda_api(payload, receipt=receipt)
    return AdapterCohort(
        cohort_id="fda-drugsfda-api-representative",
        jurisdiction="USA",
        source_ids=("us-drugsfda",),
        evidence_class="synthetic_local_fixture",
        fixtures=(_fixture_artifact(project_root, path),),
        explicit_fields_used=(
            "application_number",
            "product_number",
            "brand_name",
        ),
        cases=_blocked_cases(
            records,
            "The committed API fixture omits explicit active_ingredients; schema-v2 substance_ids cannot be populated without inference.",
        ),
        limitations=(
            "The fixture is synthetic and does not qualify live FDA coverage.",
            "The adapter supports active ingredients, but this committed sample does not contain them.",
        ),
    )


def _build_pbs_cohort(project_root: Path) -> AdapterCohort:
    path = project_root / "tests/fixtures/adapters/au_pbs.xml"
    payload = _portable_fixture_bytes(path)
    receipt = _fixture_receipt(
        payload,
        source_id="au-pbs",
        jurisdiction="AUS",
        authority="Department of Health, Disability and Ageing",
        method=AcquisitionMethod.LOCAL_FIXTURE,
    )
    records = project_pbs_xml(payload, receipt)
    return AdapterCohort(
        cohort_id="australia-pbs-representative",
        jurisdiction="AUS",
        source_ids=("au-pbs",),
        evidence_class="synthetic_local_fixture",
        fixtures=(_fixture_artifact(project_root, path),),
        explicit_fields_used=(
            "item-code",
            "product-name",
            "listing-status",
            "restriction",
        ),
        cases=_blocked_cases(
            records,
            "The committed PBS fixture has no explicit ingredient or product hierarchy required by schema v2.",
        ),
        limitations=(
            "The funding assertion remains separate from regulatory status.",
            "The fixture is synthetic and does not qualify PBS coverage or currency.",
        ),
    )


def _build_ema_cohort(project_root: Path) -> AdapterCohort:
    path = project_root / "tests/fixtures/native/eu/ema_medicines.csv"
    payload = _portable_fixture_bytes(path)
    receipt = _fixture_receipt(
        payload,
        source_id="eu-ema",
        jurisdiction="EU",
        authority="European Medicines Agency",
        method=AcquisitionMethod.LOCAL_FIXTURE,
    )
    records = project_ema_medicine_csv(payload, receipt)
    return AdapterCohort(
        cohort_id="eu-ema-representative",
        jurisdiction="EU",
        source_ids=("eu-ema",),
        evidence_class="synthetic_local_fixture",
        fixtures=(_fixture_artifact(project_root, path),),
        explicit_fields_used=(
            "ema_product_number",
            "medicine_name",
            "authorisation_status",
        ),
        cases=_blocked_cases(
            records,
            "The committed EMA fixture has no explicit substance structure required by schema-v2 products.",
        ),
        limitations=(
            "EMA authorisation is regulatory evidence and never implies national funding.",
            "The fixture is synthetic and does not qualify complete EMA coverage.",
        ),
    )


def _build_pmda_cohort(project_root: Path) -> AdapterCohort:
    path = project_root / "tests/fixtures/native/jp/pmda_approvals.csv"
    payload = _portable_fixture_bytes(path)
    receipt = _fixture_receipt(
        payload,
        source_id="jp-pmda",
        jurisdiction="JPN",
        authority="Pharmaceuticals and Medical Devices Agency",
        method=AcquisitionMethod.LOCAL_FIXTURE,
    )
    records = project_pmda_approval_csv(payload, receipt)
    rows = tuple(csv.DictReader(StringIO(payload.decode("utf-8-sig"))))
    generic_by_approval = {
        cast("str", row["承認番号"]): cast("str", row["一般名"]) for row in rows
    }
    cases = tuple(
        MigrationCase(
            record=record,
            projection=_product_projection(
                record,
                substance_label=generic_by_approval[
                    record.concept.identifiers[0].value
                ],
                substance_system="urn:global-medicines-atlas:jp-pmda:generic-name",
                substance_code=generic_by_approval[
                    record.concept.identifiers[0].value
                ],
            ),
        )
        for record in records
    )
    return AdapterCohort(
        cohort_id="japan-pmda-representative",
        jurisdiction="JPN",
        source_ids=("jp-pmda",),
        evidence_class="synthetic_local_fixture",
        fixtures=(_fixture_artifact(project_root, path),),
        explicit_fields_used=(
            "承認番号",
            "販売名",
            "一般名",
            "承認年月日",
            "承認区分",
        ),
        cases=cases,
        limitations=(
            "Japanese field semantics remain subject to the adapter's independent translation-review gate.",
            "The fixture is synthetic and does not qualify live PMDA coverage.",
        ),
    )


def _build_nzmt_cohort(project_root: Path) -> AdapterCohort:
    source_root = project_root / "tests/fixtures/nz"
    native = tuple(
        replace(
            item,
            source_sha256=sha256(
                _portable_fixture_bytes(source_root / item.source_path)
            ).hexdigest(),
        )
        for item in load_synthetic_fixture_records(project_root)
        if item.resource_type == "Medication"
    )
    records = project_nz_fhir_records(native)
    native_by_id = {item.resource_id: item for item in native}
    cases = tuple(
        MigrationCase(
            record=record,
            projection=_nzmt_projection(
                record, native_by_id[record.concept.identifiers[0].value]
            ),
        )
        for record in records
    )
    fixture_paths = {source_root / item.source_path for item in native}
    return AdapterCohort(
        cohort_id="new-zealand-nzmt-synthetic",
        jurisdiction="NZ",
        source_ids=("nzmt-synthetic-fixtures",),
        evidence_class="synthetic_local_fixture",
        fixtures=tuple(
            _fixture_artifact(project_root, path)
            for path in sorted(fixture_paths)
        ),
        explicit_fields_used=(
            "Medication.code",
            "Medication.extension[nzmt-type]",
            "Medication.ingredient.itemCodeableConcept",
            "Medication.ingredient.strength",
            "Medication.form",
            "Medication.amount",
        ),
        cases=cases,
        limitations=(
            "The first-party synthetic cohort tests FHIR structure only; it contains no NZULM distribution rows.",
            "The canonical-v1 NZ adapter intentionally emits no regulatory or funding assertions; source FHIR extensions are not promoted by this migration.",
            "Structural identifiers are record-local migration identities, not cross-record ingredient or product deduplication claims.",
            "FHIR projection qualification does not decide NZULM, NZMT, SNOMED CT, NZF, Medsafe, or Pharmac redistribution rights.",
        ),
    )


def _product_projection(
    record: CanonicalMedicineRecord,
    *,
    substance_label: str,
    substance_system: str,
    substance_code: str,
    dose_form: str | None = None,
    strength: str | None = None,
    quantity: str | None = None,
) -> StructuralProjection:
    native_id = record.concept.concept_id
    native = (native_id,)
    provenance = record.provenance
    identifiers = _identifier_map(record)
    substance_id = f"substance:{record.concept.concept_id}:{substance_code}"
    substance = StructuralEntity(
        id=substance_id,
        label=substance_label,
        native_identifiers={substance_system: substance_code},
        provenance=provenance,
        source_native_ids=native,
    )
    product = Product(
        id=f"product:{record.concept.concept_id}",
        label=record.concept.preferred_name,
        native_identifiers=identifiers,
        provenance=provenance,
        source_native_ids=native,
        substance_ids=(substance.id,),
        dose_form=dose_form,
        strength=strength,
    )
    packages = (
        (
            Package(
                id=f"package:{record.concept.concept_id}",
                label=record.concept.preferred_name,
                native_identifiers=identifiers,
                provenance=provenance,
                source_native_ids=native,
                product_id=product.id,
                quantity=quantity,
            ),
        )
        if quantity is not None
        else ()
    )
    return StructuralProjection(
        substances=(substance,),
        products=(product,),
        packages=packages,
    )


def _identifier_map(record: CanonicalMedicineRecord) -> dict[str, str]:
    identifiers = {
        item.system: item.value for item in record.concept.identifiers
    }
    if not identifiers:
        raise ValueError("schema-v2 projection requires a native identifier")
    return identifiers


def _nzmt_projection(
    record: CanonicalMedicineRecord,
    native: FhirResourceRecord,
) -> StructuralProjection:
    ingredients: object = native.resource.get("ingredient")
    if not isinstance(ingredients, list):
        raise TypeError(f"{native.resource_id}: ingredient list is required")
    ingredient_rows = cast("list[object]", ingredients)
    if len(ingredient_rows) != 1:
        raise ValueError(
            f"{native.resource_id}: representative NZMT fixture requires exactly one explicit ingredient"
        )
    ingredient = _string_mapping(ingredient_rows[0])
    if ingredient is None:
        raise ValueError(f"{native.resource_id}: malformed ingredient")
    coding = _first_coding(ingredient.get("itemCodeableConcept"))
    if coding is None:
        raise ValueError(f"{native.resource_id}: ingredient coding is required")
    system = _required_string(coding, "system", native.resource_id)
    code = _required_string(coding, "code", native.resource_id)
    label_value = coding.get("display")
    label = (
        label_value if isinstance(label_value, str) and label_value else code
    )
    strength = _ratio_text(ingredient.get("strength"), native.resource_id)
    dose_form = _coding_display(native.resource.get("form"), native.resource_id)
    quantity = _ratio_text(native.resource.get("amount"), native.resource_id)
    return _product_projection(
        record,
        substance_label=label,
        substance_system=system,
        substance_code=code,
        dose_form=dose_form,
        strength=strength,
        quantity=quantity,
    )


def _string_mapping(value: object) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    candidate = cast("Mapping[object, object]", value)
    if not all(isinstance(key, str) for key in candidate):
        return None
    return cast("Mapping[str, Any]", value)


def _first_coding(value: object) -> Mapping[str, Any] | None:
    mapping = _string_mapping(value)
    if mapping is None:
        return None
    coding = mapping.get("coding")
    if not isinstance(coding, list):
        return None
    return next(
        (
            item
            for raw in cast("list[object]", coding)
            if (item := _string_mapping(raw)) is not None
        ),
        None,
    )


def _required_string(
    value: Mapping[str, Any],
    key: str,
    resource_id: str,
) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate:
        raise ValueError(f"{resource_id}: {key} is required")
    return candidate


def _coding_display(value: object, resource_id: str) -> str | None:
    if value is None:
        return None
    coding = _first_coding(value)
    if coding is None:
        raise ValueError(f"{resource_id}: malformed coded value")
    display = coding.get("display")
    if isinstance(display, str) and display:
        return display
    code = coding.get("code")
    if isinstance(code, str) and code:
        return code
    raise ValueError(f"{resource_id}: coded value requires display or code")


def _ratio_text(value: object, resource_id: str) -> str | None:
    if value is None:
        return None
    ratio = _string_mapping(value)
    if ratio is None:
        raise ValueError(f"{resource_id}: malformed ratio")
    numerator = _quantity_text(ratio.get("numerator"), resource_id)
    denominator_value = ratio.get("denominator")
    if denominator_value is None:
        return numerator
    return f"{numerator}/{_quantity_text(denominator_value, resource_id)}"


def _quantity_text(value: object, resource_id: str) -> str:
    quantity = _string_mapping(value)
    if quantity is None:
        raise ValueError(f"{resource_id}: malformed quantity")
    amount = quantity.get("value")
    unit = quantity.get("unit")
    if not isinstance(amount, int | float) or isinstance(amount, bool):
        raise TypeError(f"{resource_id}: quantity value is required")
    if not isinstance(unit, str) or not unit:
        raise ValueError(f"{resource_id}: quantity unit is required")
    return f"{amount} {unit}"
