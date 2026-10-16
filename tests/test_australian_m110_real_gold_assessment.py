"""The real-data MBS Gold candidate remains scoped and review pending."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
QUALIFICATION = ROOT / (
    "quality/qualifications/"
    "australian-mbs-gold-real-silver-qualification-20261017.json"
)
ASSESSMENT = ROOT / (
    "quality/qualifications/"
    "australian-m110-mbs-july-2025-real-gold-assessment-20261017.json"
)
PRIOR_ASSESSMENT = ROOT / (
    "quality/qualifications/"
    "australian-m110-mbs-july-2025-silver-assessment-20261017-8c0090db.json"
)


def test_real_gold_candidate_binds_admission_and_stays_unaccepted() -> None:
    qualification_bytes = QUALIFICATION.read_bytes()
    qualification = json.loads(qualification_bytes)
    assessment = json.loads(ASSESSMENT.read_bytes())

    assert qualification["requirement_id"] == "M-110"
    assert qualification["status"] == (
        "real_admitted_silver_graph_candidate_qualified_for_review"
    )
    assert qualification["graph"]["candidate_schema_version"] == 3
    assert qualification["graph"]["source_record_count"] == 5989
    assert qualification["graph"]["node_count"] == 11978
    assert qualification["graph"]["edge_count"] == 5989
    assert qualification["graph"]["review_state"] == "not_reviewed"
    assert qualification["graph"]["all_edges_same_record_bound"] is True
    assert all(qualification["negative_controls"].values())
    assert all(value is False for value in qualification["boundaries"].values())

    fingerprint_paths = (
        "scripts/qualify_australian_mbs_gold_real_silver.py",
        "src/global_medicines_atlas/mbs_gold_graph.py",
        "schemas/australian-mbs-gold-real-silver-qualification-v1.json",
        "schemas/australian-mbs-silver-admission-v1.json",
        "schemas/australian-mbs-silver-semantic-manifest-v1.json",
    )
    assert qualification["implementation_fingerprints"] == [
        {
            "path": path,
            "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
        }
        for path in fingerprint_paths
    ]

    assert assessment["evidence"]["real_gold_graph_qualification_path"] == str(
        QUALIFICATION.relative_to(ROOT)
    )
    assert assessment["evidence"]["real_gold_graph_qualification_sha256"] == (
        hashlib.sha256(qualification_bytes).hexdigest()
    )
    assert (
        assessment["evidence"]["real_gold_graph_sha256"]
        == (qualification["graph"]["graph_sha256"])
    )
    assert assessment["gate_assessment"]["gold_graph_review"].startswith(
        "pending_"
    )
    assert assessment["status"] == (
        "real_mbs_gold_graph_candidate_qualified_review_and_consumer_acceptance_pending"
    )
    assert assessment["supersedes_assessment"]["sha256"] == (
        hashlib.sha256(PRIOR_ASSESSMENT.read_bytes()).hexdigest()
    )
