"""Build the stable-v1 maturity projection from the canonical source catalog."""

from __future__ import annotations

import json
from collections import defaultdict
from operator import itemgetter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = (
    ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"
)
OUTPUT_PATH = ROOT / "quality/qualifications/stable-v1-source-maturity.json"
LEVEL_ORDER = {f"M{level}": level for level in range(6)}


def _maturity(source: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    basis = ["catalog row exists"]
    gaps = [
        "live source receipt",
        "independent reproduction",
        "support readiness",
        "release approval",
    ]
    level = "M0"
    if source["qualification_state"] == "documentation_verified":
        level = "M1"
        basis.append("documentation qualification reference exists")
    if source.get("implemented_ingestion"):
        level = "M2"
        basis.append("catalog declares implemented ingestion")
    return level, basis, gaps


def build_projection(catalog: dict[str, Any]) -> dict[str, Any]:
    """Return a conservative, deterministic projection over catalog source IDs."""
    rows: list[dict[str, Any]] = []
    jurisdiction_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sorted(catalog["sources"], key=itemgetter("source_id")):
        level, basis, gaps = _maturity(source)
        row = {
            "source_id": source["source_id"],
            "jurisdictions": sorted(source["jurisdictions"]),
            "dimension": source["dimension"],
            "maturity_level": level,
            "documentation_readiness": source["qualification_state"],
            "assignment_basis": basis,
            "blocking_gaps": gaps,
        }
        rows.append(row)
        for jurisdiction in row["jurisdictions"]:
            jurisdiction_rows[jurisdiction].append(row)

    jurisdictions: list[dict[str, Any]] = []
    for jurisdiction, sources in sorted(jurisdiction_rows.items()):
        levels = [LEVEL_ORDER[source["maturity_level"]] for source in sources]
        jurisdictions.append({
            "jurisdiction": jurisdiction,
            "source_count": len(sources),
            "regulatory_source_count": sum(
                source["dimension"] == "regulatory" for source in sources
            ),
            "funding_or_formulary_source_count": sum(
                source["dimension"] in {"funding", "formulary"}
                for source in sources
            ),
            "highest_maturity_level": f"M{max(levels)}",
            "documentation_ready_source_count": sum(
                source["documentation_readiness"] == "documentation_verified"
                for source in sources
            ),
            "stable_ready": False,
        })
    return {
        "schema_id": "global-medicines-atlas.stable-v1-source-maturity",
        "schema_version": 1,
        "catalog": (
            "src/global_medicines_atlas/data/medicine_source_catalog.json"
        ),
        "catalog_schema_version": catalog["schema_version"],
        "assignment_policy": {
            "M0": "Catalogued source declaration only.",
            "M1": "Documentation contract and qualification reference evidenced.",
            "M2": "Local implementation and fixture evidence declared.",
            "M3": "End-to-end provenance receipt required; not inferred here.",
            "M4": "Live source, drift, and performance evidence required; not inferred here.",
            "M5": "Independent reproduction, support readiness, and release approval required; not inferred here.",
        },
        "sources": rows,
        "jurisdictions": jurisdictions,
        "matrix_state": "verified_projection",
    }


def main() -> None:
    """Write the deterministic governed projection."""
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    projection = build_projection(catalog)
    OUTPUT_PATH.write_text(
        json.dumps(projection, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
