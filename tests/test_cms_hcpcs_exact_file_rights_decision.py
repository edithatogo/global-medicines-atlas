"""Exact CMS HCPCS rights disposition stays outside M-112 admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.bronze_admission import BronzeAdmissionRecord

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261019.json"
)
REVIEW = ROOT / "quality/qualifications/cms-hcpcs-rights-review-20261019.json"


def _json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def test_exact_cms_hcpcs_rights_decision_binds_the_existing_reference() -> None:
    cms = _json(PREFLIGHT)["cms_hcpcs_reference"]
    review = _json(REVIEW)
    decision = _json(ROOT / review["rights_review"]["decision_path"])

    assert review["scope"]["source_id"] == cms["source_id"]
    assert review["scope"]["source_version"] == cms["source_version"]
    assert (
        review["scope"]["payload_opened_or_code_composition_inspected"] is False
    )
    assert (
        review["scope"]["exact_external_file"]["sha256"]
        == cms["payload_sha256"]
    )
    assert review["scope"]["exact_external_file"]["byte_count"] == 2499217
    assert decision["source_id"] == cms["source_id"]
    assert decision["source_version"] == cms["source_version"]
    assert decision["scope"]["b1_acquisition_id"] == (
        cms["b1_acquisition_path"]
        .rsplit("/", maxsplit=1)[-1]
        .removesuffix(".json")
    )
    assert decision["scope"]["b2_state"] == "external_reference_only"
    assert decision["effective_state"]["rights_state"] == "permitted"
    assert decision["effective_state"]["reviewer_status"] == "approved"
    assert (
        decision["effective_state"]["external_publication_authorized"] is False
    )
    assert (
        decision["effective_state"]["processing_or_v4_admission_authorized"]
        is False
    )
    assert decision["effective_state"]["consumer_canaries_authorized"] is False
    material = {
        key: value for key, value in decision.items() if key != "decision_id"
    }
    expected_id = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert decision["decision_id"] == expected_id


def test_latest_cms_admission_reviews_rights_without_admitting_payload() -> (
    None
):
    cms = _json(PREFLIGHT)["cms_hcpcs_reference"]
    review = _json(REVIEW)
    original = _json(ROOT / cms["admission_path"])
    latest = BronzeAdmissionRecord.model_validate(
        _json(ROOT / review["rights_review"]["superseding_admission_path"])
    )
    b1 = _json(ROOT / cms["b1_acquisition_path"])
    b2 = _json(ROOT / cms["b2_manifest_path"])

    assert original["reviewer_status"] == "unreviewed"
    assert latest.supersedes_decision_id == original["decision_id"]
    assert latest.reviewer_status == "approved"
    assert latest.state.value == "landed"
    assert "not_admitted_to_processing" in latest.reason_codes
    assert b1["rights_state"] == "unknown"  # immutable acquisition-time state
    assert b2["rows"][0]["state"] == "external_reference_only"
    assert review["rights_review"]["external_publication_performed"] is False
