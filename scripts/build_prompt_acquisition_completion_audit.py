"""Build the evidence-gated completion audit for acquisition prompts 1-36."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from global_medicines_atlas.source_expansion import (
    ExpansionTrack,
    expansion_tracks,
)

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "quality/qualifications/bronze-source-landing-queue.json"
MEASURED = ROOT / "quality/qualifications/stable-v1-measured-coverage.json"
US_LIVE_QUALIFICATION = (
    ROOT / "quality/qualifications/us-live-bronze-corpus-20260820.json"
)
US_RECORD_QUALIFICATION = (
    ROOT / "quality/qualifications/us-live-bronze-records-20260820.json"
)
NDC_RECORD_QUALIFICATION = (
    ROOT / "quality/qualifications/ndc-directory-live-corpus-20260821.json"
)
REMS_RECORD_QUALIFICATION = (
    ROOT / "quality/qualifications/fda-rems-live-corpus-20260821.json"
)
DEFAULT_OUTPUT = (
    ROOT / "quality/qualifications/prompt-acquisition-completion-audit.json"
)
RECONCILIATION_PROMPT_ID = 36
PROMPT_AUDIT_RECORD_SOURCE_IDS = frozenset({"us-fda-nsde"})
NDC_PROMPT_AUDIT_SOURCE_IDS = frozenset({
    "us-fda-ndc-directory",
    "us-openfda-ndc",
})
REMS_PROMPT_AUDIT_SOURCE_IDS = frozenset({"us-fda-rems"})
REMS_EXPORT_COUNT = 4
HTTP_NOT_FOUND = 404

NEXT_ACTIONS = {
    "credentialed_and_excluded": (
        "retain metadata-only until credentials, licence, and access authority are approved"
    ),
    "landed_and_evidenced": (
        "replace governed fixture evidence with a receipt-backed live source acquisition"
    ),
    "manual_only_documented_acquisition": (
        "execute the documented reproducible acquisition after source-specific rights confirmation"
    ),
    "not_yet_implemented": "implement and test the declared acquisition adapter",
    "rights_blocked": "obtain a maintainer-approved source-specific rights decision",
    "superseded_by_reused_source": (
        "verify the reused source has current live evidence for this source identity"
    ),
    "temporarily_unavailable": (
        "record a dated availability observation and retry without treating absence as negative evidence"
    ),
    "derived_reconciliation_output": (
        "regenerate the versioned source index after every scoped live acquisition is reconciled"
    ),
}


def _blocker_categories(states: set[str]) -> list[str]:
    categories: list[str] = []
    if "rights_blocked" in states:
        categories.append("source_specific_rights_decision_required")
    if "manual_only_documented_acquisition" in states:
        categories.append("documented_manual_acquisition_required")
    if "credentialed_and_excluded" in states:
        categories.append("credential_or_licence_boundary")
    if "landed_and_evidenced" in states:
        categories.append("fixture_only_is_not_live")
    if "temporarily_unavailable" in states:
        categories.append("temporarily_unavailable")
    if "not_yet_implemented" in states:
        categories.append("adapter_implementation_required")
    if "superseded_by_reused_source" in states:
        categories.append("reused_source_live_evidence_required")
    if "derived_reconciliation_output" in states:
        categories.append("dependent_on_live_acquisition_program")
    return categories


def _prompt_entry(
    track: ExpansionTrack,
    queue_by_source: dict[str, str],
    measured_by_source: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_ids = list(track.source_ids)
    states = {
        source_id: queue_by_source.get(
            source_id,
            "derived_reconciliation_output",
        )
        for source_id in source_ids
    }
    live = [
        source_id
        for source_id in source_ids
        if source_id in measured_by_source
        and measured_by_source[source_id]["live_qualified"]
    ]
    fixtures = [
        source_id
        for source_id in source_ids
        if source_id in measured_by_source
        and measured_by_source[source_id]["fixture_qualified"]
    ]
    missing = [source_id for source_id in source_ids if source_id not in live]
    live_complete = not missing
    completion_state = (
        "live_acquisition_complete"
        if live_complete
        else "live_acquisition_incomplete"
    )
    if track.track_id == RECONCILIATION_PROMPT_ID and not live_complete:
        completion_state = (
            "reconciliation_generated_but_live_program_incomplete"
        )
    incomplete_states = {states[source_id] for source_id in missing}
    return {
        "prompt_id": track.track_id,
        "title": track.title,
        "family": track.family.value,
        "invariant": track.invariant,
        "source_count": len(source_ids),
        "source_ids": source_ids,
        "queue_states": states,
        "queue_state_counts": dict(sorted(Counter(states.values()).items())),
        "fixture_qualified_source_ids": fixtures,
        "live_qualified_source_ids": live,
        "sources_without_live_evidence": missing,
        "live_complete": live_complete,
        "completion_state": completion_state,
        "blocker_categories": _blocker_categories(incomplete_states),
        "next_actions": [
            NEXT_ACTIONS[state] for state in sorted(incomplete_states)
        ],
    }


def _qualified_us_live_sources() -> set[str]:
    qualification = json.loads(
        US_LIVE_QUALIFICATION.read_text(encoding="utf-8")
    )
    if qualification["evidence_class"] != "live_bounded_internal":
        raise ValueError("U.S. live qualification has the wrong evidence class")
    if (
        qualification["coverage_complete"]
        or qualification["external_publication_performed"]
        or qualification["public_release_authorized"]
    ):
        raise ValueError(
            "U.S. live qualification crossed its internal-only boundary"
        )
    if (
        qualification["acquisition_succeeded_count"]
        != qualification["source_count"]
    ):
        raise ValueError(
            "U.S. live qualification contains acquisition failures"
        )
    return {
        item["source_id"]
        for item in qualification["authorized_source_results"]
        if item["rights_state"] == "permitted"
        and item["admission_state"] == "accepted"
        and item["parquet_projected"] is True
    }


def _qualified_us_record_sources() -> set[str]:
    qualification = json.loads(
        US_RECORD_QUALIFICATION.read_text(encoding="utf-8")
    )
    if qualification["evidence_class"] != "live_bounded_internal":
        raise ValueError(
            "U.S. record qualification has the wrong evidence class"
        )
    if (
        qualification["coverage_complete"]
        or qualification["external_publication_performed"]
        or qualification["public_release_authorized"]
    ):
        raise ValueError(
            "U.S. record qualification crossed its internal-only boundary"
        )
    projected = {
        item["source_id"]
        for item in qualification["record_products"]
        if item["row_count"] > 0
    }
    qualified = set(qualification["prompt_audit_qualified_source_ids"])
    if qualified != set(PROMPT_AUDIT_RECORD_SOURCE_IDS):
        raise ValueError(
            "U.S. record prompt qualification exceeds reviewed source scope"
        )
    if not qualified.issubset(projected):
        raise ValueError(
            "prompt-qualified source lacks a nonempty record product"
        )
    expected_products = qualification["source_record_projection_count"]
    if (
        qualification["recovered_source_record_projection_count"]
        != expected_products
        or qualification["source_record_parquet_pairs_byte_identical"]
        != expected_products
    ):
        raise ValueError(
            "U.S. record products lack byte-identical clean-room recovery"
        )
    return qualified


def _qualified_ndc_record_sources() -> set[str]:
    qualification = json.loads(
        NDC_RECORD_QUALIFICATION.read_text(encoding="utf-8")
    )
    if qualification["evidence_class"] != "live_bounded_internal":
        raise ValueError("NDC qualification has the wrong evidence class")
    if (
        not qualification["current_bulk_surface_complete"]
        or qualification["historical_snapshot_coverage_claimed"]
        or qualification["external_publication_performed"]
        or qualification["public_release_authorized"]
    ):
        raise ValueError("NDC qualification crossed its reviewed scope")
    if (
        qualification["acquisition_succeeded_count"]
        != qualification["release_count"]
        or qualification["acquisition_failed_count"] != 0
        or qualification["accepted_admission_count"]
        != qualification["release_count"]
    ):
        raise ValueError("NDC qualification contains incomplete acquisition")
    expected = qualification["source_record_projection_count"]
    if (
        expected != qualification["release_count"]
        or qualification["recovered_source_record_projection_count"] != expected
        or qualification["source_record_parquet_pairs_byte_identical"]
        != expected
        or qualification["source_record_rows"] <= 0
        or not qualification["archive_checksum_verified"]
    ):
        raise ValueError("NDC record products lack recovery evidence")
    qualified = set(qualification["prompt_audit_qualified_source_ids"])
    if qualified != set(NDC_PROMPT_AUDIT_SOURCE_IDS):
        raise ValueError("NDC qualification exceeds reviewed source scope")
    return qualified


def _qualified_rems_record_sources() -> set[str]:
    qualification = json.loads(
        REMS_RECORD_QUALIFICATION.read_text(encoding="utf-8")
    )
    if qualification["evidence_class"] != "live_internal_documents":
        raise ValueError("REMS qualification has the wrong evidence class")
    if (
        not qualification["prompt_complete"]
        or qualification["external_publication_performed"]
        or qualification["public_release_authorized"]
        or qualification["public_redistribution_rights_approved"]
    ):
        raise ValueError("REMS qualification crossed its reviewed scope")
    unavailable = qualification["current_documents_explicitly_unavailable"]
    coverage_checks = (
        qualification["current_detail_inventory_complete"],
        qualification["current_document_inventory_complete"],
        qualification[
            "explicit_unavailability_satisfies_public_surface_coverage"
        ],
        qualification["current_documents_acquired"] + unavailable
        == qualification["current_document_inventory_count"],
        unavailable == len(qualification["unavailable_documents"]),
    )
    if not all(coverage_checks) or any(
        item["observed_http_status"] != HTTP_NOT_FOUND
        or item["failure_code"] != "http_status"
        for item in qualification["unavailable_documents"]
    ):
        raise ValueError("REMS public document coverage is incomplete")
    expected = qualification["official_csv_surface_count"]
    recovery_checks = (
        expected == REMS_EXPORT_COUNT,
        qualification["source_record_projection_count"] == expected,
        qualification["recovered_source_record_projection_count"] == expected,
        qualification["source_record_parquet_pairs_byte_identical"] == expected,
        qualification["source_record_rows"] > 0,
        qualification["archive_checksum_verified"],
    )
    if not all(recovery_checks):
        raise ValueError("REMS record products lack recovery evidence")
    qualified = set(qualification["prompt_audit_qualified_source_ids"])
    if qualified != set(REMS_PROMPT_AUDIT_SOURCE_IDS):
        raise ValueError("REMS qualification exceeds reviewed source scope")
    return qualified


def build() -> dict[str, Any]:
    """Join locked prompt scope to queue and measured evidence."""

    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    measured = json.loads(MEASURED.read_text(encoding="utf-8"))["body"]
    queue_by_source = {
        item["source_id"]: item["state"] for item in queue["items"]
    }
    measured_by_source = {
        item["source_id"]: item for item in measured["sources"]
    }
    qualified_us_live = (
        _qualified_us_live_sources()
        | _qualified_us_record_sources()
        | _qualified_ndc_record_sources()
        | _qualified_rems_record_sources()
    )
    for source_id in qualified_us_live:
        existing = measured_by_source.get(source_id, {})
        measured_by_source[source_id] = existing | {"live_qualified": True}
    prompts: list[dict[str, Any]] = []
    prompt_sources: set[str] = set()
    for track in expansion_tracks():
        prompt_sources.update(track.source_ids)
        prompts.append(
            _prompt_entry(track, queue_by_source, measured_by_source)
        )
    live_complete_count = sum(item["live_complete"] for item in prompts)
    return {
        "schema_id": (
            "global-medicines-atlas.prompt-acquisition-completion-audit"
        ),
        "schema_version": 1,
        "generated_at": queue["catalog_reviewed_at"],
        "prompt_count": len(prompts),
        "unique_prompt_source_count": len(prompt_sources),
        "catalog_source_count": measured["totals"]["catalog_sources"],
        "fixture_qualified_source_count": measured["totals"][
            "fixture_qualified_sources"
        ],
        "live_qualified_source_count": len({
            source_id
            for source_id, item in measured_by_source.items()
            if item.get("live_qualified")
        }),
        "live_complete_prompt_count": live_complete_count,
        "program_completion": (
            "complete"
            if live_complete_count == len(prompts)
            else "incomplete_live_acquisition"
        ),
        "queue_state_counts": queue["state_counts"],
        "evidence_policy": (
            "catalogue, fixture, and archive evidence do not prove live acquisition; "
            "each prompt completes only when every scoped source is live-qualified or "
            "an explicit unavailable/excluded disposition satisfies that prompt"
        ),
        "prompts": prompts,
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
            raise SystemExit("prompt acquisition completion audit is stale")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
