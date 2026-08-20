"""Build the source-level rights review ledger from policy families."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from global_medicines_atlas.source_rights_review import (
    SourceRightsReview,
    validate_catalogue_reviews,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src/global_medicines_atlas/data"
CATALOG = DATA / "medicine_source_catalog.json"
FAMILIES = DATA / "source_rights_policy_families.json"
DECISIONS = DATA / "source_rights_source_decisions.json"
DEFAULT_OUTPUT = (
    ROOT / "quality/qualifications/source-rights-review-ledger.json"
)
REVIEWED_AT = "2026-08-21T00:00:00Z"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _unresolved(source_id: str) -> SourceRightsReview:
    return SourceRightsReview.model_validate({
        "source_id": source_id,
        "policy_family_id": "unresolved-source-specific-terms",
        "evidence": [],
        "redistribute": "unknown",
        "transform": "unknown",
        "publish_source_bytes": "unknown",
        "sensitivity": "unknown",
        "disposition": "catalogue_only",
        "maintainer_licence_approved": False,
        "maintainer_publication_approved": False,
        "reviewed_at": REVIEWED_AT,
        "review_trigger": "capture current official reuse terms",
        "blocker": "affirmative official reuse evidence not yet recorded",
    })


def _review(
    source_id: str,
    family_id: str,
    family: dict[str, Any],
) -> SourceRightsReview:
    return SourceRightsReview.model_validate({
        "source_id": source_id,
        "policy_family_id": family_id,
        **family,
        "disposition": "catalogue_only",
        "maintainer_licence_approved": False,
        "maintainer_publication_approved": False,
        "reviewed_at": REVIEWED_AT,
        "blocker": (
            "official reuse evidence is a candidate only; maintainer "
            "licensing conclusion and exact-manifest publication approval "
            "remain pending"
        ),
    })


def build() -> dict[str, Any]:
    """Return the deterministic complete source-rights ledger."""

    catalog = _load(CATALOG)
    families = _load(FAMILIES)["families"]
    decision_file = _load(DECISIONS)
    decisions = decision_file["policy_family_assignments"]
    source_ids = tuple(source["source_id"] for source in catalog["sources"])
    unknown = sorted(set(decisions) - set(source_ids))
    if unknown:
        raise ValueError(
            f"rights decisions reference unknown sources: {unknown}"
        )
    unknown_families = sorted(set(decisions.values()) - set(families))
    if unknown_families:
        raise ValueError(
            "rights decisions reference unknown policy families: "
            f"{unknown_families}"
        )
    reviews = tuple(
        _review(source_id, decisions[source_id], families[decisions[source_id]])
        if source_id in decisions
        else _unresolved(source_id)
        for source_id in source_ids
    )
    validate_catalogue_reviews(
        source_ids,
        reviews,
        as_of=datetime(2026, 8, 21, tzinfo=UTC),
    )
    entries = [
        review.model_dump(mode="json")
        for review in sorted(reviews, key=lambda item: item.source_id)
    ]
    return {
        "schema_id": "global-medicines-atlas.source-rights-review-ledger",
        "schema_version": 1,
        "generated_at": REVIEWED_AT,
        "catalogue_source_count": len(source_ids),
        "review_count": len(entries),
        "publication_gate": decision_file["publication_gate"],
        "candidate_policy_assignment_count": len(decisions),
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
            raise SystemExit("source-rights review ledger is stale")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
