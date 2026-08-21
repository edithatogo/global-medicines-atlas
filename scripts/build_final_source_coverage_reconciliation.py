"""Build Prompt 36's measured, fail-closed source-coverage reconciliation."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"
MEASURED = ROOT / "quality/qualifications/stable-v1-measured-coverage.json"
PROMPTS = (
    ROOT / "quality/qualifications/prompt-acquisition-completion-audit.json"
)
INDEX = ROOT / "src/global_medicines_atlas/data/source_coverage_index_v1.json"
DEFAULT_OUTPUT = (
    ROOT
    / "quality/qualifications/final-source-coverage-reconciliation-20260821.json"
)

FACETS = (
    "regulatory_registration",
    "essential_or_formulary_status",
    "reimbursement_or_funding",
    "pricing_or_procurement",
    "pharmacovigilance",
    "recalls",
    "shortages",
    "clinical_trials",
    "utilisation",
    "terminology",
)


def _facets(
    source: dict[str, Any],
    *,
    utilisation_source_ids: set[str],
    pv_source_ids: set[str],
) -> set[str]:
    domains = set(source["information_domains"])
    identity = f"{source['source_id']} {source['title']}".lower()
    facets: set[str] = set()
    if "regulatory_status" in domains:
        facets.add("regulatory_registration")
    if "formulary_status" in domains:
        facets.add("essential_or_formulary_status")
    if "funding_status" in domains:
        facets.add("reimbursement_or_funding")
    if domains & {"pricing", "procurement"}:
        facets.add("pricing_or_procurement")
    if "safety" in domains or source["source_id"] in pv_source_ids:
        facets.add("pharmacovigilance")
    if any(token in identity for token in ("recall", "enforcement")):
        facets.add("recalls")
    if "shortage" in identity:
        facets.add("shortages")
    if "clinical_trials" in domains:
        facets.add("clinical_trials")
    if source["source_id"] in utilisation_source_ids:
        facets.add("utilisation")
    if "terminology" in domains:
        facets.add("terminology")
    return facets


def build_reconciliation() -> dict[str, Any]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["sources"]
    measured = json.loads(MEASURED.read_text(encoding="utf-8"))["body"]
    prompt_audit = json.loads(PROMPTS.read_text(encoding="utf-8"))
    source_index = json.loads(INDEX.read_text(encoding="utf-8"))
    maturity = {item["source_id"]: item for item in measured["sources"]}
    utilisation_source_ids = {
        source_id
        for prompt in prompt_audit["prompts"]
        if prompt["family"] == "utilisation"
        for source_id in prompt["source_ids"]
    }
    pv_source_ids = {
        source_id
        for prompt in prompt_audit["prompts"]
        if prompt["family"] == "pharmacovigilance"
        for source_id in prompt["source_ids"]
    }

    facet_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    jurisdiction_sources: dict[str, set[str]] = defaultdict(set)
    regulator_sources: dict[str, set[str]] = defaultdict(set)
    for source in catalog:
        for jurisdiction in source["jurisdictions"]:
            jurisdiction_sources[jurisdiction].add(source["source_id"])
        regulator_sources[source["authority"]].add(source["source_id"])
        for facet in _facets(
            source,
            utilisation_source_ids=utilisation_source_ids,
            pv_source_ids=pv_source_ids,
        ):
            facet_sources[facet].append(source)

    def maturity_counts(source_ids: set[str]) -> dict[str, int]:
        return {
            "catalogued": len(source_ids),
            "fixture_qualified": sum(
                maturity[source_id]["fixture_qualified"]
                for source_id in source_ids
            ),
            "live_qualified": sum(
                maturity[source_id]["live_qualified"]
                for source_id in source_ids
            ),
        }

    facet_matrix: list[dict[str, Any]] = []
    for facet in FACETS:
        sources = facet_sources[facet]
        source_ids = {source["source_id"] for source in sources}
        facet_matrix.append({
            "facet": facet,
            **maturity_counts(source_ids),
            "jurisdictions": sorted({
                j for source in sources for j in source["jurisdictions"]
            }),
            "sources_without_live_evidence": sorted(
                source_id
                for source_id in source_ids
                if not maturity[source_id]["live_qualified"]
            ),
        })

    prompt_states = Counter(
        entry["completion_state"] for entry in prompt_audit["prompts"]
    )
    return {
        "schema_id": "global-medicines-atlas.final-source-coverage-reconciliation",
        "schema_version": 1,
        "as_of": "2026-08-21",
        "evidence_policy": "catalog declarations; executable committed fixtures; durable live receipts",
        "catalog_source_count": len(catalog),
        "facet_matrix": facet_matrix,
        "jurisdiction_matrix": [
            {"jurisdiction": key, **maturity_counts(value)}
            for key, value in sorted(jurisdiction_sources.items())
        ],
        "regulator_matrix": [
            {"regulator": key, **maturity_counts(value)}
            for key, value in sorted(regulator_sources.items())
        ],
        "prompt_completion_states": dict(sorted(prompt_states.items())),
        "live_complete_prompt_ids": [
            entry["prompt_id"]
            for entry in prompt_audit["prompts"]
            if entry["live_complete"]
        ],
        "high_value_gap_candidates": source_index["high_value_gaps"],
        "new_track_recommendation": "Do not open a new track until an existing high-value gap receives source-specific authority or a newly discovered source materially changes coverage.",
        "coverage_complete": False,
        "missing_coverage_is_negative_evidence": False,
        "fixture_or_metadata_counts_as_live": False,
        "external_publication_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build_reconciliation()
    args.output.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)


if __name__ == "__main__":
    main()
