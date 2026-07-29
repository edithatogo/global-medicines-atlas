# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = (
    ROOT / "release-inputs" / "v0.7-fixture-production-qualification.json"
)
SCHEMA_PATH = ROOT / "release-inputs" / "v0.7-qualification-matrix.schema.json"
DOC_PATH = (
    ROOT / "docs" / "publication" / "v0.7-fixture-production-qualification.md"
)

REQUIREMENTS = {
    "M-004",
    "M-005",
    "M-052",
    "M-061",
    "M-062",
    "M-074",
    "M-080",
    "M-083",
    "S-004",
}
ISSUES = {32, 33, 34, 35}


def _load_json(path: Path) -> dict[str, Any]:
    value = cast("object", json.loads(path.read_text(encoding="utf-8")))
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


def _gates(matrix: dict[str, Any], scope: str) -> dict[str, str]:
    gate_set = matrix[f"{scope}_qualification"]
    assert isinstance(gate_set, dict)
    gates = gate_set["gates"]
    assert isinstance(gates, list)
    return {
        str(gate["gate_id"]): str(gate["status"])
        for gate in gates
        if isinstance(gate, dict)
    }


def test_v07_matrix_validates_against_draft_2020_12_schema() -> None:
    schema = _load_json(SCHEMA_PATH)
    matrix = _load_json(MATRIX_PATH)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(matrix)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("swapped-scopes", id="swapped-fixture-production-scopes"),
        pytest.param("production-passed", id="production-cannot-pass"),
        pytest.param("duplicate-gate-id", id="gate-identities-are-unique"),
        pytest.param("all-public", id="states-cannot-be-conflated-as-public"),
    ],
)
def test_schema_rejects_conflated_qualification_states(mutation: str) -> None:
    schema = _load_json(SCHEMA_PATH)
    matrix = deepcopy(_load_json(MATRIX_PATH))

    if mutation == "swapped-scopes":
        matrix["fixture_qualification"]["scope"] = "production"
        matrix["production_qualification"]["scope"] = "fixture"
    elif mutation == "production-passed":
        matrix["production_qualification"]["overall_status"] = "passed"
        for gate in matrix["production_qualification"]["gates"]:
            gate["status"] = "passed"
    elif mutation == "duplicate-gate-id":
        gates = matrix["fixture_qualification"]["gates"]
        gates[1]["gate_id"] = gates[0]["gate_id"]
    elif mutation == "all-public":
        for state in matrix["publication_states"]:
            state["state"] = "public"
            state["status"] = "passed_fixture"
    else:  # pragma: no cover - parametrization is closed above
        raise AssertionError(f"unknown mutation: {mutation}")

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(matrix)


def test_traceability_is_exact_and_documented() -> None:
    matrix = _load_json(MATRIX_PATH)
    traceability = matrix["traceability"]
    assert isinstance(traceability, dict)
    assert set(traceability["requirements"]) == REQUIREMENTS
    assert set(traceability["github_issues"]) == ISSUES

    requirements_text = (ROOT / "conductor" / "requirements.md").read_text(
        encoding="utf-8"
    )
    active_plan = (
        ROOT
        / "conductor"
        / "tracks"
        / "governed_publication_20260729"
        / "plan.md"
    )
    archived_plan = (
        ROOT
        / "conductor"
        / "archive"
        / "governed_publication_20260729"
        / "plan.md"
    )
    track_text = (
        active_plan if active_plan.exists() else archived_plan
    ).read_text(encoding="utf-8")
    evidence_doc = DOC_PATH.read_text(encoding="utf-8")
    for requirement in REQUIREMENTS:
        assert f"**{requirement}:**" in requirements_text
        assert requirement in evidence_doc
    for issue in ISSUES:
        assert f"/issues/{issue}" in track_text
        assert f"/issues/{issue}" in evidence_doc


def test_fixture_and_production_gates_cannot_be_conflated() -> None:
    matrix = _load_json(MATRIX_PATH)
    assert matrix["release"] == {
        "target": "0.7.0",
        "classification": "fixture-qualified-production-blocked",
        "publication_performed": False,
    }
    assert matrix["fixture_qualification"]["overall_status"] == "passed"
    assert matrix["production_qualification"]["overall_status"] == "blocked"

    fixture = _gates(matrix, "fixture")
    production = _gates(matrix, "production")
    assert fixture == {
        "rights": "passed",
        "privacy": "passed",
        "provenance": "passed",
        "software-licence": "not_applicable",
        "maintainer-release-approval": "not_applicable",
    }
    assert set(production.values()) == {"blocked"}


def test_no_uploaded_or_public_state_is_claimed() -> None:
    matrix = _load_json(MATRIX_PATH)
    states = {
        item["state"]: item["status"] for item in matrix["publication_states"]
    }
    assert states == {
        "prepared": "passed_fixture",
        "uploaded": "not_performed",
        "public": "not_performed",
    }
    assert matrix["release"]["publication_performed"] is False


def test_every_non_fixture_source_fails_closed_for_production_payloads() -> (
    None
):
    matrix = _load_json(MATRIX_PATH)
    rights = matrix["source_rights"]
    fixture = next(
        item for item in rights if item["source_id"] == "synthetic-fixture"
    )
    assert fixture["redistribution_status"] == "permitted_fixture_only"
    assert fixture["production_disposition"] == "exclude_payload"

    production_sources = [
        item for item in rights if item["source_id"] != "synthetic-fixture"
    ]
    assert production_sources
    assert all(
        item["redistribution_status"] in {"restricted", "unresolved"}
        for item in production_sources
    )
    assert all(
        item["production_disposition"]
        in {
            "exclude_payload",
            "metadata_only_pending_review",
            "blocked_pending_rights_review",
        }
        for item in production_sources
    )


def test_evidence_document_preserves_release_and_licence_gates() -> None:
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    assert "no publication was" in text
    assert "software-licence decision" in text
    assert "maintainer approval" in text
    assert "production gates are blocked" in text
    assert "fixture gates are passed" in text
