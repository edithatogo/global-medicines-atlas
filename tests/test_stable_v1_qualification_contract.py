"""Stable-v1 qualification contracts fail closed and reuse project authorities."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from scripts.build_stable_v1_source_maturity import build_projection

ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION_SCHEMA = ROOT / "schemas/stable-v1-qualification-v1.json"
QUALIFICATION = ROOT / "quality/qualifications/stable-v1-contract.json"
CANONICAL_SCHEMA = ROOT / "schemas/canonical-medicine-v2.json"
COMPARISON_SCHEMA = ROOT / "schemas/comparison-validity-v1.json"
REHEARSAL_SCHEMA = ROOT / "schemas/stable-v1-rehearsal-v1.json"
REHEARSAL_PLAN = ROOT / "quality/qualifications/stable-v1-rehearsal-plan.json"
SUPPORT_SCHEMA = ROOT / "schemas/stable-v1-support-readiness-v1.json"
SUPPORT = ROOT / "quality/qualifications/stable-v1-support-readiness.json"
SOURCE_MATURITY_SCHEMA = ROOT / "schemas/stable-v1-source-maturity-v1.json"
SOURCE_MATURITY = ROOT / "quality/qualifications/stable-v1-source-maturity.json"
CONSUMER_SCHEMA = ROOT / "schemas/stable-v1-consumer-compatibility-v1.json"
CONSUMER = ROOT / "quality/qualifications/stable-v1-consumer-compatibility.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(path: Path) -> Draft202012Validator:
    schema = _load(path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _must_requirement_ids() -> set[str]:
    text = (ROOT / "conductor/requirements.md").read_text(encoding="utf-8")
    must_section = text.split("## Should Have", maxsplit=1)[0]
    return set(re.findall(r"\*\*(M-\d{3})", must_section))


def test_contract_schemas_are_valid_draft_2020_12() -> None:
    for path in (
        QUALIFICATION_SCHEMA,
        CANONICAL_SCHEMA,
        COMPARISON_SCHEMA,
        REHEARSAL_SCHEMA,
        SUPPORT_SCHEMA,
        SOURCE_MATURITY_SCHEMA,
        CONSUMER_SCHEMA,
    ):
        _validator(path)


def test_consumer_compatibility_contract_is_complete_and_fail_closed() -> None:
    contract = _load(CONSUMER)
    _validator(CONSUMER_SCHEMA).validate(contract)
    assert set(contract["platforms"]) == {"linux", "macos", "windows"}
    assert contract["runners"] == {
        "linux": "ubuntu-24.04",
        "macos": "macos-15",
        "windows": "windows-2025",
    }
    assert set(contract["artifacts"]) == {"wheel", "sdist"}
    assert {
        "metadata",
        "reinstall",
        "openapi_compatibility",
        "core_fallback",
    } <= set(contract["probes"])
    assert contract["state"] == "contracted"


def test_projection_validates_and_traces_every_must_requirement() -> None:
    projection = _load(QUALIFICATION)
    _validator(QUALIFICATION_SCHEMA).validate(projection)

    projected = [item["requirement_id"] for item in projection["requirements"]]
    assert len(projected) == len(set(projected))
    assert set(projected) == _must_requirement_ids()


def test_projection_reuses_authoritative_models_and_catalog() -> None:
    projection = _load(QUALIFICATION)
    authorities = projection["authorities"]
    assert authorities == {
        "requirements": "conductor/requirements.md",
        "maturity_model": "conductor/maturity-model.json",
        "source_catalog": (
            "src/global_medicines_atlas/data/medicine_source_catalog.json"
        ),
        "publication_contract": (
            "src/global_medicines_atlas/publication_contracts.py"
        ),
    }

    maturity = _load(ROOT / authorities["maturity_model"])
    projected_dimensions = {
        item["dimension"] for item in projection["maturity_dimensions"]
    }
    assert projected_dimensions == set(maturity["blocking_dimensions"])

    catalog = _load(ROOT / authorities["source_catalog"])
    assert projection["source_maturity"]["catalog_source_count"] == len(
        catalog["sources"]
    )
    assert projection["source_maturity"]["matrix"] == (
        "quality/qualifications/stable-v1-source-maturity.json"
    )


def test_all_local_evidence_paths_exist() -> None:
    projection = _load(QUALIFICATION)
    evidence_paths: set[str] = set()
    for requirement in projection["requirements"]:
        evidence_paths.update(requirement["evidence"])
    for dimension in projection["maturity_dimensions"]:
        evidence_paths.update(dimension["evidence"])
    evidence_paths.update(projection["support"]["evidence"])
    evidence_paths.add(projection["source_maturity"]["matrix"])
    for risk in projection["residual_risks"]:
        evidence_paths.update(risk["evidence"])
    for gate in projection["release_gates"]:
        evidence_paths.update(gate["evidence"])

    missing = sorted(
        path for path in evidence_paths if not (ROOT / path).is_file()
    )
    assert not missing


def test_publication_identities_are_unique_and_non_overlapping() -> None:
    identities = _load(QUALIFICATION)["publication_identities"]
    assert {item["system"] for item in identities} == {
        "github",
        "hugging_face",
        "zenodo",
        "osf",
    }
    roles = [item["object_role"] for item in identities]
    assert len(roles) == len(set(roles))
    unresolved = [item for item in identities if item["identifier"] is None]
    assert unresolved
    assert all(item["state"] == "blocked" for item in unresolved)


def test_qualification_fails_closed_with_unresolved_gates() -> None:
    projection = _load(QUALIFICATION)
    assert projection["qualification_state"] == "blocked"
    unresolved = {
        gate["gate_id"]
        for gate in projection["release_gates"]
        if gate["state"] != "passed"
    }
    assert set(projection["unresolved_gate_ids"]) == unresolved

    invalid = copy.deepcopy(projection)
    invalid["qualification_state"] = "qualified"
    with pytest.raises(ValidationError):
        _validator(QUALIFICATION_SCHEMA).validate(invalid)

    invalid["unresolved_gate_ids"] = []
    with pytest.raises(ValidationError):
        _validator(QUALIFICATION_SCHEMA).validate(invalid)


def test_structural_medicine_v2_is_not_temporal_migration_v2() -> None:
    schema = _load(CANONICAL_SCHEMA)
    assert schema["properties"]["schema_id"]["const"] == (
        "global-medicines-atlas.canonical-medicine"
    )
    assert schema["properties"]["schema_version"]["const"] == 2
    assert "temporal assertion migration" in schema["description"]
    assert {
        "substances",
        "products",
        "packages",
        "indications",
        "prices",
        "restrictions",
    }.issubset(schema["required"])


def test_inappropriate_comparison_requires_material_mismatch() -> None:
    comparison = {
        "schema_id": "global-medicines-atlas.comparison-validity",
        "schema_version": 1,
        "left_subject_id": "left",
        "right_subject_id": "right",
        "outcome": "inappropriate_comparison",
        "dimensions": {
            name: {
                "state": "unknown",
                "left_value": None,
                "right_value": None,
                "evidence_ids": [],
            }
            for name in (
                "granularity",
                "indication",
                "population",
                "mapping",
                "normalization",
            )
        },
        "material_mismatches": [],
        "explanation": "Evidence is not comparable.",
    }
    with pytest.raises(ValidationError):
        _validator(COMPARISON_SCHEMA).validate(comparison)

    comparison["material_mismatches"] = ["granularity"]
    _validator(COMPARISON_SCHEMA).validate(comparison)


def test_rehearsal_plan_defines_every_blocking_stable_rehearsal() -> None:
    plan = _load(REHEARSAL_PLAN)
    _validator(REHEARSAL_SCHEMA).validate(plan)
    rehearsals = plan["rehearsals"]
    assert {item["kind"] for item in rehearsals} == {
        "clean_room_reproduction",
        "canonical_schema_migration",
        "canonical_schema_rollback",
        "governed_recovery",
    }
    assert len({item["rehearsal_id"] for item in rehearsals}) == len(rehearsals)
    assert all(item["blocking"] for item in rehearsals)
    assert all(item["state"] != "passed" for item in rehearsals)
    assert all(item["blocker"] for item in rehearsals)


def test_support_readiness_fails_closed_and_matches_residual_risks() -> None:
    support = _load(SUPPORT)
    _validator(SUPPORT_SCHEMA).validate(support)
    projection_risks = {
        item["risk_id"]: (item["disposition"], item["blocking"])
        for item in _load(QUALIFICATION)["residual_risks"]
    }
    support_risks = {
        item["risk_id"]: (item["disposition"], item["blocking"])
        for item in support["residual_risks"]
    }
    assert support_risks == projection_risks
    assert support["readiness_state"] == "blocked"
    assert any(
        item["blocking"] and item["disposition"] == "unresolved"
        for item in support["residual_risks"]
    )


def test_source_maturity_matrix_is_complete_conservative_projection() -> None:
    matrix = _load(SOURCE_MATURITY)
    _validator(SOURCE_MATURITY_SCHEMA).validate(matrix)
    catalog = _load(ROOT / matrix["catalog"])
    source_rows = {item["source_id"]: item for item in matrix["sources"]}
    catalog_rows = {item["source_id"]: item for item in catalog["sources"]}
    assert set(source_rows) == set(catalog_rows)
    assert len(source_rows) == len(matrix["sources"])
    assert matrix["catalog_schema_version"] == catalog["schema_version"]
    assert matrix["matrix_state"] == "verified_projection"
    assert all(
        int(item["maturity_level"][1:]) <= 2 for item in matrix["sources"]
    )
    assert all(item["blocking_gaps"] for item in matrix["sources"])
    assert all(not item["stable_ready"] for item in matrix["jurisdictions"])


def test_source_maturity_projection_is_deterministically_regenerated() -> None:
    catalog = _load(
        ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"
    )
    assert build_projection(catalog) == _load(SOURCE_MATURITY)
