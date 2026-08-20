"""Build the fail-closed U.S. source-rights review packet."""

from __future__ import annotations

import argparse
import json
from operator import itemgetter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"
DEFAULT_OUTPUT = (
    ROOT / "quality/qualifications/us-source-rights-review-packet.json"
)
OBSERVED_AT = "2026-08-20"

OPENFDA = {
    "us-openfda-drugsfda",
    "us-openfda-enforcement",
    "us-openfda-faers",
    "us-openfda-ndc",
    "us-openfda-nsde",
}
CMS = {
    "us-cms-mdrp",
    "us-cms-nadac",
    "us-cms-partd-formulary",
    "us-cms-partd-spending",
}
NLM_OR_NCATS = {"us-dailymed-spl", "us-gsrs-unii", "us-rxnorm-api"}


def _evidence(url: str, finding: str, gap: str) -> dict[str, str]:
    return {
        "url": url,
        "observed_at": OBSERVED_AT,
        "finding": finding,
        "remaining_gap": gap,
    }


def _source_review(source: dict[str, Any]) -> dict[str, Any]:
    source_id = source["source_id"]
    common: dict[str, Any] = {
        "source_id": source_id,
        "authority": source["authority"],
        "source_reference": source["landing_page"],
        "catalogue_rights_status": source["rights_status"],
        "review_status": "candidate_unapproved",
        "maintainer_licence_approved": False,
        "maintainer_publication_approved": False,
        "live_acquisition": "not_authorized",
        "public_release": "not_approved",
        "raw_payload_redistribution": "not_approved",
        "required_next_decision": "maintainer_source_specific_licensing_decision",
    }
    if source_id in OPENFDA:
        return common | {
            "candidate_disposition": "scoped_cc0_metadata_only",
            "retain_source_bytes": "conditional",
            "terms_evidence": [
                _evidence(
                    "https://open.fda.gov/terms/",
                    "openFDA generally dedicates unmarked content and data to the public domain under CC0.",
                    "Every acquired field and linked material still requires review for marked third-party rights.",
                )
            ],
            "candidate_fields": [
                "source-native identifiers",
                "source-native product or event metadata explicitly covered by openFDA CC0 terms",
            ],
            "field_exclusions": [
                "all content marked third-party or non-CC0",
                "GMDN terms or descriptions and any other separately licensed terminology",
                "FDA names, logos, marks, and inferred approval, safety, efficacy, or reimbursement claims",
            ],
            "attribution_candidate": "Data provided by the U.S. Food and Drug Administration through openFDA.",
        }
    if source_id in CMS:
        return common | {
            "candidate_disposition": "terms_gap_catalogue_only",
            "retain_source_bytes": "unknown",
            "terms_evidence": [
                _evidence(
                    "https://data.cms.gov/api-docs",
                    "CMS documents public API access and retrieval mechanics.",
                    "The API documentation is not, by itself, a dataset-specific retention or redistribution grant.",
                ),
                _evidence(
                    "https://www.cms.gov/about-cms/information-systems/privacy/data-use-agreement-dua",
                    "CMS documents Data Use Agreements for disclosures involving protected or identifiable information.",
                    "Applicability to each public aggregate dataset and any dataset-specific agreement remains unresolved.",
                ),
            ],
            "candidate_fields": [],
            "field_exclusions": [
                "all source-derived fields pending dataset-specific terms review"
            ],
            "attribution_candidate": "unresolved",
        }
    if source_id in NLM_OR_NCATS:
        reference = (
            "https://gsrs.ncats.nih.gov/#/about"
            if source_id == "us-gsrs-unii"
            else "https://www.nlm.nih.gov/web_policies.html"
        )
        return common | {
            "candidate_disposition": "terms_gap_catalogue_only",
            "retain_source_bytes": "unknown",
            "terms_evidence": [
                _evidence(
                    reference,
                    "An official agency policy or service page identifies the responsible government surface.",
                    "Dataset-specific retention, transformation, terminology, attribution, and redistribution terms are not established by this evidence alone.",
                )
            ],
            "candidate_fields": [],
            "field_exclusions": [
                "all source-derived fields pending dataset-specific terms review"
            ],
            "attribution_candidate": "unresolved",
        }
    return common | {
        "candidate_disposition": "government_public_domain_policy_review",
        "retain_source_bytes": "conditional",
        "terms_evidence": [
            _evidence(
                "https://www.fda.gov/about-fda/about-website/website-policies",
                "FDA states that FDA.gov text and graphics are generally public domain unless otherwise noted.",
                "The exact endpoint, files, embedded third-party content, notices, and field-level transformations still require review.",
            )
        ],
        "candidate_fields": [
            "source-native identifiers and government-authored metadata where no contrary notice applies"
        ],
        "field_exclusions": [
            "third-party or separately licensed content",
            "FDA names, logos, marks, and inferred clinical, approval, or reimbursement claims",
        ],
        "attribution_candidate": "Credit the U.S. Food and Drug Administration, source URL, and retrieval date.",
    }


def build() -> dict[str, Any]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    sources = sorted(
        (
            source
            for source in catalog["sources"]
            if source["source_id"].startswith("us-")
        ),
        key=itemgetter("source_id"),
    )
    entries = [_source_review(source) for source in sources]
    return {
        "schema_id": "global-medicines-atlas.us-source-rights-review-packet",
        "schema_version": 1,
        "generated_at": OBSERVED_AT,
        "decision_id": "conductor/decisions/0008-source-derived-dataset-licensing-batch.md",
        "source_count": len(entries),
        "licensing_decision": "maintainer_approval_required",
        "live_acquisition": "not_authorized",
        "public_release": "not_approved",
        "scope_note": "Candidate evidence for bounded maintainer review; not a licence conclusion, acquisition authority, coverage claim, or publication approval.",
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
                "U.S. source-rights review packet is stale; regenerate it"
            )
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
