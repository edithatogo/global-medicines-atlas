"""Current M-112 rights preflight preserves exact scope and release gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261020.json"
)


def _json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def test_preflight_binds_current_inputs_and_preserves_historical_snapshot() -> (
    None
):
    report = _json(PREFLIGHT)
    for path, expected_digest in report["inputs"].items():
        assert (
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            == expected_digest
        )
    historical = report["historical_preflight"]
    assert historical["superseded"] is True
    assert historical["preserved_unchanged"] is True
    assert historical["path"].endswith("preflight-20261019.json")
    assert report["frozen_inventory"]["object_count"] == 1759
    assert report["frozen_inventory"]["membership_changed"] is False
    assert report["effective_m112_rights"]["resolved_object_count"] == 32
    assert report["effective_m112_rights"]["unresolved_object_count"] == 1727


def test_scoped_rights_do_not_cross_object_or_release_boundaries() -> None:
    report = _json(PREFLIGHT)
    july = report["july_2025_mbs_silver"]
    assert len(july["objects"]) == 6
    assert july["public_release_authorized"] is True
    assert july["public_release_performed"] is False
    assert july["permission_instrument_existence_and_applicability"] == (
        "maintainer_attested_not_independently_reviewed_or_located_at_maintainer_direction"
    )
    august = report["august_2026_mbs_bronze_projections"]
    assert len(august["objects"]) == 4
    assert august["rights_state"] == (
        "maintainer_attested_exact_public_release_permission_for_bronze_projection"
    )
    assert august["public_release_rights_attested"] is True
    assert august["public_release_performed_by_this_action"] is False
    assert august["m108_assessment_derived_output_authority"] == "absent"
    assert all(obj["lineage_complete"] for obj in august["objects"])
    assert all(
        obj["rights_state"] == august["rights_state"]
        for obj in august["objects"]
    )
    cms = report["cms_hcpcs_reference"]
    assert cms["rights_state"] == "permitted"
    assert cms["reviewer_status"] == "approved"
    assert cms["acquisition_time_rights_state_preserved"] == "unknown"
    assert cms["external_publication_authorized"] is False
    assert cms["derived_table_rights_concluded"] is False
    assert report["pbs_utilisation_raw_objects"][
        "full_object_release_requires_exclusion_review"
    ]
    gates = report["release_and_admission_boundaries"]
    assert gates["all_1759_deferrals_preserved"] is True
    assert gates["v4_admissions"] == 0
    assert gates["consumer_canaries"] == 0
    assert gates["external_publications_performed"] is False
