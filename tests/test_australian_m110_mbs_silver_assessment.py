"""Guard the boundary of the exact-era M-110 MBS input assessment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
ASSESSMENT = (
    ROOT
    / "quality/qualifications/australian-m110-mbs-july-2025-silver-assessment-20261017.json"
)
PARITY = (
    ROOT
    / "quality/qualifications/mbs-source-silver-tables-parity-2025-07-v3.json"
)
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/australian-health-legacy-publication-authorization.json"
)
EVIDENCE = (
    ROOT
    / "conductor/tracks/australian_benefits_silver_gold_20260829/evidence.jsonl"
)


def test_assessment_binds_exact_candidate_without_promoting_it() -> None:
    assessment = json.loads(ASSESSMENT.read_text())
    parity = json.loads(PARITY.read_text())
    authorization = json.loads(AUTHORIZATION.read_text())

    assert (
        assessment["schema_id"]
        == "global-medicines-atlas.australian-m110-mbs-silver-assessment"
    )
    assert (
        assessment["scope"]["source_sha256"] == parity["source_object_sha256"]
    )
    assert (
        assessment["scope"]["manifest_sha256"]
        == parity["silver_manifest_sha256"]
    )
    assert (
        assessment["scope"]["public_revision"]
        == "3d2d528439bddf6f42e8e700c88917f0960a9f38"
    )
    tables = {table["name"]: table for table in assessment["scope"]["tables"]}
    assert set(tables) == {table["table"] for table in parity["tables"]}
    assert all(
        tables[table["table"]]["sha256"] == table["silver_object_sha256"]
        and tables[table["table"]]["bytes"] == table["silver_object_bytes"]
        and tables[table["table"]]["rows"] == table["row_count"]
        for table in parity["tables"]
    )
    assert authorization["dataset"] == assessment["scope"]["public_dataset"]
    assert authorization["external_publication_authorized"] is True
    assert (
        authorization["maintainer_asserted_redistribution_permission"] is True
    )
    assert assessment["gate_assessment"][
        "source_era_field_semantics"
    ].startswith("pass_")
    assert assessment["gate_assessment"][
        "source_era_date_semantics"
    ].startswith("pass_")
    assert (
        assessment["evidence"]["profile_status_scope"]
        == "schema_compatibility_only"
    )
    assert assessment["evidence"]["hosted_artifact_id"] == "12066023734"
    assert assessment["evidence"]["hosted_artifact_body_sha256"] == (
        "de159badf4af83e0963f7a57518910e009e79b864717059b3e4389de9efcf606"
    )
    assert assessment["evidence"]["candidate_report_sha256"] == (
        "a61681c48e4627f9076dc972e05f1ef61d2edbbd70715ccda26c0d860361cfa3"
    )
    assert (
        assessment["evidence"]["field_semantics_crosswalk_sha256"]
        == hashlib.sha256(
            (
                ROOT / "docs/qualification/mbs-xml-v3-field-semantics.md"
            ).read_bytes()
        ).hexdigest()
    )
    assert (
        assessment["evidence"]["date_profile_receipt_sha256"]
        == hashlib.sha256(
            (
                ROOT
                / "quality/qualifications/mbs-xml-v3-date-profile-qualification-20260929.json"
            ).read_bytes()
        ).hexdigest()
    )
    assert assessment["evidence"]["profile_status"] == "declared_only"
    assert assessment["evidence"]["publication_performed"] is False
    assert assessment["evidence"]["source_bytes_retained"] is False
    assert parity["rights_conclusion"] is False
    assert parity["production_admission"] is False
    assert parity["production_promotion"] is False
    assert (
        assessment["status"]
        == "candidate_only_field_width_fix_pending_current_main_revalidation"
    )


def test_evidence_ledger_binds_assessment_digest() -> None:
    assessment_bytes = ASSESSMENT.read_bytes()
    assessment_sha256 = hashlib.sha256(assessment_bytes).hexdigest()
    records = [json.loads(line) for line in EVIDENCE.read_text().splitlines()]
    record = next(
        item
        for item in reversed(records)
        if item.get("kind") == "m110_mbs_july_2025_silver_candidate_revalidated"
    )

    assert record["qualification"] == str(ASSESSMENT.relative_to(ROOT))
    assert record["qualification_sha256"] == assessment_sha256
    assert record["exact_commit"] == "7fe32a8830d9576ebcc4b431031d59e6809ef379"
    assert record["production_admission"] is False
    assert record["m110_acceptance"] is False
