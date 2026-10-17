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
CONSUMER_RECEIPT = ROOT / (
    "quality/qualifications/"
    "australian-mbs-gold-candidate-consumers-20261018.json"
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


def test_exact_main_candidate_consumer_receipt_preserves_lineage_and_limits() -> (
    None
):
    receipt_bytes = CONSUMER_RECEIPT.read_bytes()
    receipt = json.loads(receipt_bytes)

    assert hashlib.sha256(receipt_bytes).hexdigest() == (
        "8d1db8c5fa9376a9f786078114e7bb7682decb8709fde6bf7992113065d8488f"
    )
    assert receipt["hosted_workflow"] == {
        "commit": "1182ab71a44c9e72fce6031ec244848e6919f096",
        "repository": "edithatogo/global-medicines-atlas",
        "run_attempt": 1,
        "run_id": 39045806438,
        "run_url": (
            "https://github.com/edithatogo/global-medicines-atlas/"
            "actions/runs/39045806438"
        ),
        "workflow": (
            ".github/workflows/"
            "australian-mbs-gold-candidate-consumer-qualification.yml"
        ),
    }
    assert receipt["edge_count"] == 5989
    assert receipt["candidate_only"] is True
    assert receipt["review_state"] == "not_reviewed"
    assert receipt["public_publication_performed"] is False
    assert receipt["source_payload_bytes_retained"] is False
    assert receipt["page_offsets"] == [0, 1000, 2000, 3000, 4000, 5000]
    assert receipt["browser_page_offsets"] == receipt["page_offsets"]
    edge_digest = (
        "7a2ba8a0b31dca32101172bde49f6dc17d3ef6d873afb4760651f2a22c3a502d"
    )
    assert receipt["surface_edge_id_sha256"] == {
        "API": edge_digest,
        "Atlas": edge_digest,
        "Browser": edge_digest,
        "CLI": edge_digest,
    }

    lineage = receipt["candidate_v4_source_lineage"]
    assert lineage["candidate_only"] is True
    assert lineage["admission_sha256"] == (
        "a97289a9b0d4abc864b62606eb6d3356fccbedce5ea656235200353c507be7d4"
    )
    assert lineage["semantic_manifest_sha256"] == (
        "9ad5e2747949b8b7142819e981241c1f74105b3570d78025e654e780241c5882"
    )
    assert [table["name"] for table in lineage["tables"]] == [
        "benefits",
        "caps",
        "descriptions",
        "fees",
        "hierarchy",
        "services",
    ]
    assert all(table["row_count"] == 5989 for table in lineage["tables"])
    assert "items" not in receipt
    receipt_text = receipt_bytes.decode()
    assert '"edge_id":' not in receipt_text
    assert '"items":' not in receipt_text
