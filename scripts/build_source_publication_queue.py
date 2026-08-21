"""Build the rights-aware source acquisition and publication queue."""

from __future__ import annotations

import argparse
import json
from operator import itemgetter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "quality/qualifications/source-rights-review-ledger.json"
DEFAULT_OUTPUT = (
    ROOT / "quality/qualifications/source-publication-queue.json"
)
ACQUISITION_EVIDENCE = {
    "us-live-bronze": (
        ROOT / "quality/qualifications/us-live-bronze-corpus-20260820.json"
    ),
    "union-register": (
        ROOT / "quality/qualifications/union-register-live-corpus-20260821.json"
    ),
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _acquired_sources() -> dict[str, dict[str, str]]:
    us = _load(ACQUISITION_EVIDENCE["us-live-bronze"])
    acquired = {
        item["source_id"]: {
            "evidence": str(
                ACQUISITION_EVIDENCE["us-live-bronze"].relative_to(ROOT)
            ),
            "admission_state": str(item["admission_state"]),
        }
        for item in us["authorized_source_results"]
    }
    union = _load(ACQUISITION_EVIDENCE["union-register"])
    if union["acquisition_succeeded_count"]:
        acquired["eu-union-register"] = {
            "evidence": str(
                ACQUISITION_EVIDENCE["union-register"].relative_to(ROOT)
            ),
            "admission_state": (
                "accepted"
                if union["accepted_admission_count"]
                else "quarantined"
            ),
        }
    return acquired


def build() -> dict[str, Any]:
    """Return publication work for every rights-policy candidate."""

    ledger = _load(LEDGER)
    acquired = _acquired_sources()
    candidates = [
        entry
        for entry in ledger["entries"]
        if entry["policy_family_id"] != "unresolved-source-specific-terms"
    ]
    entries: list[dict[str, Any]] = []
    for review in candidates:
        source_id = review["source_id"]
        acquisition = acquired.get(source_id)
        entries.append({
            "source_id": source_id,
            "policy_family_id": review["policy_family_id"],
            "candidate_packaging_shape": (
                "derived_projection_only"
                if review["publish_source_bytes"] == "prohibited"
                else "source_bytes_candidate"
            ),
            "acquisition_state": (
                "evidenced" if acquisition else "pending"
            ),
            "admission_state": (
                acquisition["admission_state"]
                if acquisition
                else "not_acquired"
            ),
            "acquisition_evidence": (
                acquisition["evidence"] if acquisition else None
            ),
            "next_action": (
                "prepare_exact_manifest_for_human_review"
                if acquisition
                else "acquire_with_source_family_adapter"
            ),
        })
    entries.sort(key=itemgetter("source_id"))
    return {
        "schema_id": "global-medicines-atlas.source-publication-queue",
        "schema_version": 1,
        "generated_at": ledger["generated_at"],
        "publication_gate": ledger["publication_gate"],
        "public_eligible_count": sum(
            bool(item["public_source_eligible"])
            or bool(item["public_derived_eligible"])
            for item in candidates
        ),
        "candidate_count": len(entries),
        "acquisition_evidenced_count": sum(
            item["acquisition_state"] == "evidenced" for item in entries
        ),
        "acquisition_pending_count": sum(
            item["acquisition_state"] == "pending" for item in entries
        ),
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
            raise SystemExit("source publication queue is stale")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
