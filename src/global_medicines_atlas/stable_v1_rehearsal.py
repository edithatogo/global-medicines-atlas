"""Deterministic aggregate rehearsal for the stable-v1 representative boundary."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, Self, cast

import orjson
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import Field, model_validator

from .canonical_v2 import (
    Package,
    Price,
    Product,
    ScopedAssertion,
    StructuralEntity,
    StructuralProjection,
    migrate_record_v1_to_v2,
    rollback_record_v2_to_v1,
)
from .models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    FrozenModel,
    Identifier,
    MedicineConcept,
    Provenance,
    StatusAssertion,
)
from .recovery_rehearsal import (
    RecoveryRehearsalReceipt,
    rehearse_governed_recovery,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rehearse_stable_v1.py"
AGGREGATE_SCHEMA = (
    ROOT / "schemas" / "stable_v1_aggregate_rehearsal.schema.json"
)
_BOUND_INPUT_PATHS = (
    "schemas/canonical-medicine-v2.json",
    "schemas/stable-v1-rehearsal-v1.json",
    "schemas/stable_v1_aggregate_rehearsal.schema.json",
    "scripts/rehearse_stable_v1.py",
    "src/global_medicines_atlas/canonical_v2.py",
    "src/global_medicines_atlas/models.py",
    "src/global_medicines_atlas/recovery.py",
    "src/global_medicines_atlas/recovery_rehearsal.py",
    "src/global_medicines_atlas/stable_v1_rehearsal.py",
    "uv.lock",
)
_FIXTURE_IDENTITY_KEYS = {
    "canonical_v1_fixture",
    "structural_projection_fixture",
}
_SHA256_HEX_LENGTH = 64
Digest = str


class _SchemaValidator(Protocol):
    def validate(self, instance: object) -> None: ...


class StableV1RehearsalError(RuntimeError):
    """The aggregate rehearsal could not prove every bounded assertion."""


class CleanProcessReceipt(FrozenModel):
    """Identity reproduced across a fresh local Python process."""

    boundary: Literal["independent_local_fixture_process"]
    canonical_v1_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_v2_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    identity_reproduced: Literal[True]
    current_checkout_used: Literal[True] = True
    artifact_only_release_reproduction: Literal[False] = False
    external_network_isolation_verified: Literal[False] = False


class CanonicalRehearsalReceipt(FrozenModel):
    """Content identities and semantic invariants for migration and rollback."""

    canonical_v1_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_v2_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    rolled_back_v1_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    migration_deterministic: Literal[True]
    rollback_exact: Literal[True]
    regulatory_funding_separation_verified: Literal[True]


class StableV1RehearsalReceipt(FrozenModel):
    """Content-bound aggregate receipt with deliberately bounded claims."""

    schema_id: Literal["global-medicines-atlas.stable-v1-rehearsal"] = (
        "global-medicines-atlas.stable-v1-rehearsal"
    )
    schema_version: Literal[2] = 2
    evidence_class: Literal["deterministic_representative_fixtures"] = (
        "deterministic_representative_fixtures"
    )
    input_sha256: dict[str, Digest]
    fixture_sha256: dict[str, Digest]
    qualification_input_tree_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    clean_room: CleanProcessReceipt
    canonical: CanonicalRehearsalReceipt
    recovery: RecoveryRehearsalReceipt
    passed: Literal[True]
    production_disaster_recovery_qualified: Literal[False] = False
    external_publication_verified: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=1)
    content_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def aggregate_claims_are_consistent(self) -> Self:
        if self.recovery.production_disaster_recovery_qualified:
            raise ValueError("fixture rehearsal cannot qualify production DR")
        if set(self.input_sha256) != set(_BOUND_INPUT_PATHS):
            raise ValueError("aggregate receipt input set is incomplete")
        if set(self.fixture_sha256) != _FIXTURE_IDENTITY_KEYS:
            raise ValueError("aggregate receipt fixture set is incomplete")
        if not all(
            _is_digest(item)
            for item in (
                *self.input_sha256.values(),
                *self.fixture_sha256.values(),
            )
        ):
            raise ValueError(
                "aggregate receipt contains an invalid input identity"
            )
        return self


def _canonical_bytes(value: object) -> bytes:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_digest(value: str) -> bool:
    return len(value) == _SHA256_HEX_LENGTH and all(
        item in "0123456789abcdef" for item in value
    )


def _fixture() -> tuple[CanonicalMedicineRecord, StructuralProjection]:
    regulatory = Provenance(
        source_id="nz-medsafe",
        source_uri="https://example.invalid/regulatory",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_sha256="a" * 64,
        source_path="fixture/regulatory/1",
        transformation="stable-v1-representative-fixture",
    )
    funding = regulatory.model_copy(
        update={
            "source_id": "nz-pharmac",
            "source_uri": "https://example.invalid/funding",
            "source_path": "fixture/funding/1",
        }
    )
    record = CanonicalMedicineRecord(
        concept=MedicineConcept(
            concept_id="nz:stable-v1-fixture",
            jurisdiction="NZL",
            level="product",
            preferred_name="Stable v1 fixture medicine",
            identifiers=(Identifier(system="urn:gma:fixture", value="1"),),
        ),
        assertions=(
            StatusAssertion(
                assertion_id="regulatory:1",
                concept_id="nz:stable-v1-fixture",
                jurisdiction="NZL",
                kind=AssertionKind.REGULATORY,
                authority="Medsafe",
                status_code="approved",
                evidence_status=EvidenceStatus.CONFIRMED,
                provenance=regulatory,
            ),
            StatusAssertion(
                assertion_id="funding:1",
                concept_id="nz:stable-v1-fixture",
                jurisdiction="NZL",
                kind=AssertionKind.FUNDING,
                authority="Pharmac",
                status_code="funded",
                evidence_status=EvidenceStatus.CONFIRMED,
                restrictions=("representative restriction",),
                provenance=funding,
            ),
        ),
        provenance=(regulatory, funding),
    )
    native = (record.concept.concept_id,)
    substance = StructuralEntity(
        id="substance:fixture",
        label="Fixture substance",
        native_identifiers={"urn:gma:substance": "1"},
        provenance=(regulatory,),
        source_native_ids=native,
    )
    product = Product(
        id="product:fixture",
        label="Stable v1 fixture medicine",
        native_identifiers={"urn:gma:fixture": "1"},
        provenance=(regulatory,),
        source_native_ids=native,
        substance_ids=(substance.id,),
        dose_form="tablet",
        strength="10 mg",
    )
    package = Package(
        id="package:fixture",
        label="Fixture pack",
        native_identifiers={"urn:gma:package": "1"},
        provenance=(funding,),
        source_native_ids=native,
        product_id=product.id,
        quantity="30 tablets",
    )
    projection = StructuralProjection(
        substances=(substance,),
        products=(product,),
        packages=(package,),
        indications=(
            ScopedAssertion(
                id="indication:fixture",
                subject_id=product.id,
                jurisdiction="NZL",
                scope="representative indication",
                evidence_id="regulatory:1",
                assertion_kind=AssertionKind.REGULATORY,
                provenance=regulatory,
                source_native_ids=native,
            ),
        ),
        prices=(
            Price(
                id="price:fixture",
                package_id=package.id,
                jurisdiction="NZL",
                amount="12.34",
                currency="NZD",
                price_type="schedule",
                evidence_id="funding:1",
                provenance=funding,
                source_native_ids=native,
            ),
        ),
        restrictions=(
            ScopedAssertion(
                id="restriction:fixture",
                subject_id=package.id,
                jurisdiction="NZL",
                scope="representative restriction",
                evidence_id="funding:1",
                assertion_kind=AssertionKind.FUNDING,
                provenance=funding,
                source_native_ids=native,
            ),
        ),
    )
    return record, projection


def representative_identities() -> dict[str, str]:
    """Return deterministic fixture identities for clean-process comparison."""
    record, projection = _fixture()
    migrated = migrate_record_v1_to_v2(record, projection)
    return {
        "canonical_v1_sha256": _digest(record.model_dump(mode="json")),
        "canonical_v2_sha256": _digest(migrated.model_dump(mode="json")),
    }


def _fixture_identities() -> dict[str, str]:
    record, projection = _fixture()
    return {
        "canonical_v1_fixture": _digest(record.model_dump(mode="json")),
        "structural_projection_fixture": _digest(
            projection.model_dump(mode="json")
        ),
    }


def _run_clean_process() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}
    }
    environment.update({
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": str(ROOT / "src"),
    })
    with tempfile.TemporaryDirectory(
        prefix="gma-stable-v1-clean-process-"
    ) as raw:
        completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [sys.executable, str(SCRIPT), "--fixture-child"],
            cwd=raw,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
    if completed.returncode != 0:
        raise StableV1RehearsalError("clean-process reproduction failed")
    try:
        value: object = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise StableV1RehearsalError(
            "clean-process reproduction returned invalid JSON"
        ) from error
    if not isinstance(value, dict):
        raise StableV1RehearsalError(
            "clean-process reproduction returned an invalid identity set"
        )
    typed = cast("dict[object, object]", value)
    if set(typed) != {
        "canonical_v1_sha256",
        "canonical_v2_sha256",
    }:
        raise StableV1RehearsalError(
            "clean-process reproduction returned an invalid identity set"
        )
    if not all(isinstance(item, str) for item in typed.values()):
        raise StableV1RehearsalError(
            "clean-process reproduction returned invalid identities"
        )
    return {str(key): cast("str", item) for key, item in typed.items()}


def _input_identities() -> dict[str, str]:
    return {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in _BOUND_INPUT_PATHS
    }


def _qualification_input_tree_digest(
    input_sha256: dict[str, str], fixture_sha256: dict[str, str]
) -> str:
    return _digest({"files": input_sha256, "fixtures": fixture_sha256})


def _receipt_digest(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("content_sha256", None)
    return _digest(unsigned)


def _validate_aggregate_schema(payload: dict[str, object]) -> None:
    schema = json.loads(AGGREGATE_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = cast("_SchemaValidator", Draft202012Validator(schema))
    validator.validate(payload)


def verify_receipt_content(receipt: StableV1RehearsalReceipt) -> bool:
    """Verify self-identity and every input against the current checkout."""

    payload = receipt.model_dump(mode="json")
    if receipt.content_sha256 != _receipt_digest(payload):
        return False
    try:
        _validate_aggregate_schema(payload)
        current_inputs = _input_identities()
        current_fixtures = _fixture_identities()
    except (
        OSError,
        json.JSONDecodeError,
        SchemaError,
        SchemaValidationError,
    ):
        return False
    current_tree = _qualification_input_tree_digest(
        current_inputs, current_fixtures
    )
    identities = representative_identities()
    return all((
        receipt.input_sha256 == current_inputs,
        receipt.fixture_sha256 == current_fixtures,
        receipt.qualification_input_tree_sha256 == current_tree,
        receipt.canonical.canonical_v1_sha256
        == identities["canonical_v1_sha256"],
        receipt.canonical.canonical_v2_sha256
        == identities["canonical_v2_sha256"],
    ))


def run_stable_v1_rehearsal(output: Path) -> StableV1RehearsalReceipt:
    """Execute all bounded rehearsals and atomically persist their receipt."""
    identities = representative_identities()
    input_sha256 = _input_identities()
    fixture_sha256 = _fixture_identities()
    qualification_input_tree_sha256 = _qualification_input_tree_digest(
        input_sha256, fixture_sha256
    )
    child = _run_clean_process()
    if child != identities:
        raise StableV1RehearsalError(
            "clean-process reproduction identity mismatch"
        )

    record, projection = _fixture()
    migrated = migrate_record_v1_to_v2(record, projection)
    restored = rollback_record_v2_to_v1(migrated)
    kinds = {
        item.assertion_kind
        for item in (
            *migrated.indications,
            *migrated.prices,
            *migrated.restrictions,
        )
    }
    if (
        migrated != migrate_record_v1_to_v2(record, projection)
        or restored != record
        or kinds
        != {
            AssertionKind.REGULATORY,
            AssertionKind.FUNDING,
        }
    ):
        raise StableV1RehearsalError("canonical migration invariants failed")

    with tempfile.TemporaryDirectory(prefix="gma-stable-v1-recovery-") as raw:
        recovery = rehearse_governed_recovery(Path(raw) / "recovery.json")
    if not all((
        recovery.backup_verified,
        recovery.restore_verified,
        recovery.rollback_verified,
        recovery.failed_restore_quarantined,
    )):
        raise StableV1RehearsalError("governed recovery rehearsal failed")

    clean_room = CleanProcessReceipt.model_validate({
        "boundary": "independent_local_fixture_process",
        **child,
        "identity_reproduced": True,
        "current_checkout_used": True,
        "artifact_only_release_reproduction": False,
        "external_network_isolation_verified": False,
    })
    canonical = CanonicalRehearsalReceipt.model_validate({
        **identities,
        "rolled_back_v1_sha256": _digest(restored.model_dump(mode="json")),
        "migration_deterministic": True,
        "rollback_exact": True,
        "regulatory_funding_separation_verified": True,
    })
    receipt = StableV1RehearsalReceipt(
        input_sha256=input_sha256,
        fixture_sha256=fixture_sha256,
        qualification_input_tree_sha256=qualification_input_tree_sha256,
        clean_room=clean_room,
        canonical=canonical,
        recovery=recovery,
        passed=True,
        limitations=(
            "The clean process uses the current checkout and interpreter; it is not artifact-only release reproduction.",
            "Recovery covers synthetic local fixtures, not production storage, RPO, RTO, or crash consistency.",
            "No external publication is executed or verified.",
        ),
        content_sha256="0" * 64,
    )
    receipt = receipt.model_copy(
        update={
            "content_sha256": _receipt_digest(receipt.model_dump(mode="json"))
        }
    )
    if not verify_receipt_content(receipt):
        raise StableV1RehearsalError("aggregate receipt identity mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_bytes(
        orjson.dumps(
            receipt.model_dump(mode="json"),
            option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
        )
        + b"\n"
    )
    temporary.replace(output)
    return receipt
