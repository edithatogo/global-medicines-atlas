"""Field-level uncertainty remains visible and constrains derived claims."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from global_medicines_atlas.mbs_patient_rates import (
    PatientDenominatorDefinition,
)
from global_medicines_atlas.silver_field_semantics import (
    SilverFieldSemantics,
    compatible_measure_values,
    qualified_date,
)


def field(**overrides):
    values = {
        "source_sha256": "a" * 64,
        "native_name": "Benefits ($)",
        "state": "native_unresolved",
        "reason": "Source calculation unresolved",
    }
    return SilverFieldSemantics(**(values | overrides))


def test_native_measure_identity_remains_source_specific():
    left, right = field(), field(source_sha256="b" * 64)
    assert left.measure_identity != right.measure_identity
    with pytest.raises(ValueError, match="interpreted"):
        compatible_measure_values([(left, Decimal(1)), (right, Decimal(1))])


def test_interpretation_requires_exact_evidence_and_definition():
    with pytest.raises(ValidationError, match="evidence"):
        field(state="interpreted")
    result = field(
        state="interpreted",
        evidence_sha256="c" * 64,
        semantic_definition="synthetic:measure",
        unit="synthetic-unit",
    )
    assert compatible_measure_values([(result, Decimal("1.00000000001"))]) == (
        Decimal("1.00000000001"),
    )


def test_heterogeneous_interpreted_measures_cannot_be_pooled():
    left = field(
        state="interpreted",
        evidence_sha256="c" * 64,
        semantic_definition="synthetic:one",
        unit="synthetic-unit",
    )
    right = left.model_copy(update={"semantic_definition": "synthetic:two"})
    with pytest.raises(ValueError, match="definition and unit"):
        compatible_measure_values([(left, Decimal(1)), (right, Decimal(2))])


def test_parsed_candidate_date_is_not_qualified_by_parsing():
    with pytest.raises(ValueError, match="interpreted"):
        qualified_date(
            field(native_name="FeeStartDate", value_kind="date"),
            date(2024, 7, 1),
        )
    known = field(
        native_name="FeeStartDate",
        state="interpreted",
        evidence_sha256="c" * 64,
        semantic_definition="synthetic:date",
        value_kind="date",
    )
    assert qualified_date(known, date(2024, 7, 1)) == date(2024, 7, 1)


def test_unavailable_is_distinct_from_native_unresolved():
    missing = field(state="unavailable", reason="No patient denominator")
    assert missing.state == "unavailable"
    assert field().state == "native_unresolved"


def test_measure_guards_reject_unknown_units_and_nonfinite_values():
    known = field(
        state="interpreted",
        evidence_sha256="c" * 64,
        semantic_definition="synthetic:measure",
    )
    with pytest.raises(ValueError, match="unit"):
        compatible_measure_values([(known, Decimal(1))])
    with pytest.raises(ValueError, match="finite"):
        compatible_measure_values([
            (known.model_copy(update={"unit": "count"}), Decimal("NaN"))
        ])
    assert compatible_measure_values([]) == ()


def test_missing_parsed_date_remains_unavailable():
    known = field(
        state="interpreted",
        evidence_sha256="c" * 64,
        semantic_definition="synthetic:date",
        value_kind="date",
    )
    with pytest.raises(ValueError, match="unavailable"):
        qualified_date(known, None)


def test_matching_reviewed_measure_definitions_preserve_both_values():
    left = field(
        state="interpreted",
        evidence_sha256="c" * 64,
        semantic_definition="synthetic:measure",
        unit="count",
    )
    right = left.model_copy(update={"source_sha256": "b" * 64})
    assert compatible_measure_values([
        (left, Decimal("1.000000000001")),
        (right, Decimal(2)),
    ]) == (Decimal("1.000000000001"), Decimal(2))


def test_field_kinds_cannot_be_used_for_other_capabilities():
    known = field(
        state="interpreted",
        evidence_sha256="c" * 64,
        semantic_definition="synthetic:category",
        unit="count",
    )
    with pytest.raises(ValueError, match="not a date"):
        qualified_date(known, date(2024, 1, 1))
    with pytest.raises(ValueError, match="not a numeric"):
        compatible_measure_values([
            (known.model_copy(update={"value_kind": "category"}), Decimal(1))
        ])


def test_versioned_json_contracts_match_models_and_gate_interpretation():
    root = Path(__file__).resolve().parents[1]
    for name, model in (
        ("silver-field-semantics-v1", SilverFieldSemantics),
        ("mbs-patient-denominator-definition-v1", PatientDenominatorDefinition),
    ):
        schema = json.loads((root / f"schemas/{name}.json").read_text())
        schema.pop("$schema")
        schema.pop("$id")
        assert schema == model.model_json_schema()
    schema = SilverFieldSemantics.model_json_schema()
    unsupported = field().model_dump() | {"state": "interpreted"}
    assert not Draft202012Validator(schema).is_valid(unsupported)
    assert Draft202012Validator(schema).is_valid(field().model_dump())
