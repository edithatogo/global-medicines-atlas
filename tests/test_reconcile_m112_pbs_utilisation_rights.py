"""Exact-object PBS utilisation rights and lineage overlay checks."""

from __future__ import annotations

import pytest
from scripts import reconcile_m112_pbs_utilisation_rights as module
from scripts.reconcile_m112_pbs_utilisation_rights import build_report


def test_report_binds_only_the_six_exact_rights_and_lineage_objects() -> None:
    report = build_report()

    assert report["scope"] == {
        "frozen_denominator": 1759,
        "denominator_changed": False,
        "exact_objects": 6,
        "rights_attestation_bound": 6,
        "complete_b1_b2_lineage": 6,
        "v4_admitted": 0,
        "consumer_canaries": 0,
        "disposition": "deferred_not_admitted",
    }
    assert len(report["objects"]) == 6
    assert report["boundaries"]["source_payload_bytes_read"] is False
    assert report["boundaries"]["source_payload_values_inspected"] is False
    assert report["boundaries"]["new_sources_added"] is False
    assert report["boundaries"]["public_release_performed"] is False
    assert report["boundaries"]["v4_admission_performed"] is False
    assert report["boundaries"]["consumer_canary_performed"] is False

    for item in report["objects"]:
        assert item["rights_state"] == (
            "maintainer_attested_exact_public_release_permission_for_pbs_"
            "utilisation_raw_object"
        )
        assert item["rights_evidence"]["permission_instrument_review"] == (
            "maintainer_attested_not_independently_reviewed"
        )
        assert item["b1_b2_lineage_complete"] is True
        assert item["lineage_evidence"]["landed_admission_reviewer_status"] == (
            "unreviewed"
        )
        assert item["v4_admission"] is False
        assert item["consumer_canary"] is False
        assert item["disposition"] == "deferred_not_admitted"


def test_rights_identity_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read = module._read

    def read(path):  # type: ignore[no-untyped-def]
        value = original_read(path)
        if path == module.RIGHTS_RECONCILIATION:
            value["pbs_utilisation_raw_objects"]["objects"][0]["sha256"] = (
                "0" * 64
            )
        return value

    monkeypatch.setattr(module, "_read", read)
    with pytest.raises(
        ValueError, match="PBS utilisation rights identity differs"
    ):
        build_report()
