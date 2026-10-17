"""Guard the bounded maintainer review of the exact MBS v3 edge set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).parents[1]
REVIEW = ROOT / (
    "quality/qualifications/"
    "australian-mbs-gold-same-record-review-20261018.json"
)
ASSESSMENT = ROOT / (
    "quality/qualifications/"
    "australian-m110-mbs-july-2025-real-gold-assessment-20261018.json"
)
QUALIFICATION = ROOT / (
    "quality/qualifications/"
    "australian-mbs-gold-real-silver-qualification-20261017.json"
)
PREVIOUS_ASSESSMENT = ROOT / (
    "quality/qualifications/"
    "australian-m110-mbs-july-2025-real-gold-assessment-20261017.json"
)
CONSUMER_RECEIPT = ROOT / (
    "quality/qualifications/"
    "australian-mbs-gold-candidate-consumers-20261018.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt_digest(receipt: dict[str, object]) -> str:
    payload = {
        key: value for key, value in receipt.items() if key != "receipt_sha256"
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def test_review_receipt_binds_exact_candidate_edge_set_and_limits() -> None:
    receipt = json.loads(REVIEW.read_bytes())
    qualification = json.loads(QUALIFICATION.read_bytes())
    consumers = json.loads(CONSUMER_RECEIPT.read_bytes())

    assert (
        receipt["schema_id"]
        == "global-medicines-atlas.mbs-gold-edge-review-disposition"
    )
    assert receipt["schema_version"] == 1
    assert receipt["decision_by"] == "maintainer"
    assert (
        receipt["decision"]
        == "Accept the exact same-record edge set as reviewed"
    )
    assert receipt["disposition"] == "accepted_candidate_only"
    assert (
        receipt["scope"]["qualification_path"]
        == QUALIFICATION.relative_to(ROOT).as_posix()
    )
    assert receipt["scope"]["qualification_sha256"] == _sha256(QUALIFICATION)
    assert (
        receipt["scope"]["candidate_graph_sha256"]
        == qualification["graph"]["graph_sha256"]
    )
    assert receipt["reviewed_edge_set"] == {
        "edge_count": 5989,
        "edge_id_sha256": consumers["surface_edge_id_sha256"]["API"],
        "edge_kind": "source_record_has_benefit",
        "semantic_dimension": "service_benefit",
        "mapping_method": "source-explicit",
        "assertion_basis": "same_source_record",
        "all_edges_same_record_bound": True,
        "negative_controls_passed": True,
        "pre_review_graph_state": "not_reviewed",
        "reviewed_state": "reviewed_candidate",
    }
    assert consumers["edge_count"] == 5989
    assert all(value is False for value in receipt["boundaries"].values())
    assert receipt["receipt_sha256"] == _receipt_digest(receipt)


def test_review_receipt_conforms_to_strict_schema() -> None:
    schema = json.loads(
        (
            ROOT / "schemas/australian-mbs-gold-edge-review-disposition-v1.json"
        ).read_bytes()
    )
    jsonschema.Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
        json.loads(REVIEW.read_bytes())
    )


def test_current_assessment_records_review_without_expanding_m110_scope() -> (
    None
):
    assessment = json.loads(ASSESSMENT.read_bytes())
    receipt = json.loads(REVIEW.read_bytes())
    qualification = json.loads(QUALIFICATION.read_bytes())

    assert assessment["supersedes_assessment"] == {
        "path": PREVIOUS_ASSESSMENT.relative_to(ROOT).as_posix(),
        "sha256": _sha256(PREVIOUS_ASSESSMENT),
        "reason": "The exact July 2025 MBS v3 same-record Gold edge set received a maintainer review disposition.",
    }
    assert assessment["evidence"]["gold_edge_review"] == {
        "path": REVIEW.relative_to(ROOT).as_posix(),
        "sha256": receipt["receipt_sha256"],
    }
    assert assessment["gate_assessment"]["gold_graph_review"] == (
        "pass_maintainer_reviewed_exact_same_record_mbs_v3_candidate_edges"
    )
    assert assessment["status"] == (
        "exact_mbs_v3_same_record_edges_reviewed_candidate_only"
    )
    assert assessment["gate_assessment"]["gold_graph_qualification"] == (
        "pass_real_silver_candidate_graph_qualified_and_exact_same_record_edges_reviewed_candidate_only"
    )
    assert qualification["graph"]["review_state"] == "not_reviewed"
    assert assessment["gate_assessment"]["m110_overall"] == (
        "open_other_source_eras_pbs_product_admission_and_federation"
    )
    assert assessment["boundaries"]["m110_overall_accepted"] is False
    assert assessment["boundaries"]["m112_federation_accepted"] is False
    assert assessment["boundaries"]["product_admission_performed"] is False
