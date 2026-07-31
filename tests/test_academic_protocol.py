"""Phase 1 contract tests for the academic protocol package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from scripts.build_academic_protocol import build_protocol_markdown

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/academic-protocol-v1.json"
CONTRACT = ROOT / "research/protocol/academic-protocol-v1.json"
DOCUMENT = ROOT / "docs/research/academic-protocol.md"
CATALOG = ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_protocol_contract_validates_and_is_complete() -> None:
    schema = _load(SCHEMA)
    Draft202012Validator.check_schema(schema)
    protocol = _load(CONTRACT)
    Draft202012Validator(schema).validate(protocol)

    assert len(protocol["objectives"]) >= 3
    assert {item["outcome"] for item in protocol["estimands"]} == {
        "regulatory_status",
        "funding_status",
    }
    assert protocol["scope"]["clinical_decision_support"] is False
    assert protocol["scope"]["individual_patient_inference"] is False
    assert protocol["scope"]["claims_exhaustive_global_coverage"] is False


def test_source_census_is_bound_to_the_governed_catalog() -> None:
    protocol = _load(CONTRACT)
    catalog = _load(CATALOG)
    census = protocol["source_selection"]["census"]

    assert census["authority"] == (
        "src/global_medicines_atlas/data/medicine_source_catalog.json"
    )
    assert census["catalog_schema_version"] == catalog["schema_version"]
    assert census["jurisdictions"] == sorted(
        item["jurisdiction"] for item in catalog["jurisdictions"]
    )
    assert census["source_ids"] == sorted(
        item["source_id"] for item in catalog["sources"]
    )
    assert (
        protocol["source_selection"]["rights_rules"][
            "restricted_payload_default"
        ]
        == "metadata_and_retrieval_code_only"
    )


@pytest.mark.parametrize(
    "field",
    ["entity", "indication", "population", "temporal", "mapping"],
)
def test_comparison_semantics_cover_every_m090_dimension(field: str) -> None:
    semantics = _load(CONTRACT)["comparison_semantics"]
    assert semantics[field]["required"] is True
    assert semantics[field]["unknown_state"] == "insufficient_evidence"


def test_protocol_uses_exact_m090_validity_vocabulary() -> None:
    protocol = _load(CONTRACT)
    assert protocol["comparison_semantics"]["validity_states"] == [
        "valid",
        "valid_with_caveats",
        "inappropriate_comparison",
        "insufficient_evidence",
    ]
    assert protocol["comparison_semantics"]["clinical_equivalence"] is False
    assert protocol["comparison_semantics"]["substitutability"] is False
    assert protocol["comparison_semantics"]["equal_benefit"] is False


def test_phase_one_traceability_is_explicit_and_resolvable() -> None:
    traceability = _load(CONTRACT)["traceability"]
    assert set(traceability["requirements"]) == {
        "M-002",
        "M-003",
        "M-004",
        "M-035",
        "M-078",
        "M-081",
        "M-088",
        "M-090",
        "M-091",
    }
    assert traceability["github_issue"] == (
        "https://github.com/edithatogo/global-medicines-atlas/issues/67"
    )
    for relative in traceability["repository_paths"]:
        assert (ROOT / relative).is_file(), relative

    design = (ROOT / "conductor/design.md").read_text(encoding="utf-8")
    assert all(
        f"## {heading}" in design for heading in traceability["design_sections"]
    )


def test_rendered_protocol_is_committed_and_deterministic() -> None:
    expected = build_protocol_markdown(_load(CONTRACT))
    assert DOCUMENT.read_text(encoding="utf-8") == expected
    assert expected.startswith("# Global Medicines Atlas academic protocol\n")
    assert (
        "Generated offline from `research/protocol/academic-protocol-v1.json`"
        in expected
    )
