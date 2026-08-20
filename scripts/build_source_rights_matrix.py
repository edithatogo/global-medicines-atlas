"""Build the fail-closed source-rights disposition matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"
DEFAULT_OUTPUT = ROOT / "quality/qualifications/source-rights-disposition.json"


def build() -> dict[str, object]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    sources = catalog["sources"]
    entries = [
        {
            "source_id": source["source_id"],
            "jurisdictions": source["jurisdictions"],
            "authority": source["authority"],
            "dimension": source["dimension"],
            "catalogue_rights_status": source["rights_status"],
            "recommended_disposition": "catalogue_only",
            "internal_acquisition": "conditional_on_lawful_access_and_retention_review",
            "public_derived_release": "not_approved",
            "approved_surfaces": ["repository_metadata"],
            "required_evidence": [
                "current_terms_or_written_permission",
                "field_level_redistribution_decision",
                "attribution_and_notice_requirements",
                "retrieval_and_schema_receipt",
                "withdrawal_and_correction_route",
            ],
            "blocker": "source-specific rights receipt required",
        }
        for source in sources
    ]
    return {
        "schema_id": "global-medicines-atlas.source-rights-disposition",
        "schema_version": 1,
        "generated_at": catalog["reviewed_at"],
        "decision_id": "conductor/decisions/0008-source-derived-dataset-licensing-batch.md",
        "source_count": len(entries),
        "batch_recommendation": "catalogue_only_for_all_unresolved_sources",
        "public_derived_release": "source_specific_receipt_required",
        "internal_acquisition": "conditional_and_non_public",
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(build(), indent=2) + "\n"
    if args.check:
        if (
            not args.output.exists()
            or args.output.read_text(encoding="utf-8") != expected
        ):
            raise SystemExit(
                "source-rights disposition is stale; regenerate it"
            )
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
