"""PBS schema profiling emits only paths/counts, retaining namespace and coverage."""

import hashlib
import json
from pathlib import Path

import pytest
from test_pbs_value_package import inputs

from global_medicines_atlas import pbs_schema_inventory as module


def test_schema_paths_cover_all_slots_and_withhold_native_values():
    archive, xml, parent, binding = inputs()
    profile = module.profile_schema_paths(archive, xml, parent, binding)
    assert (
        sum(row["native_fields"] for row in profile["paths"])
        == profile["native_fields"]
    )
    assert all(
        row["native_fields"] == row["null_fields"] + row["value_fields"]
        for row in profile["paths"]
    )
    assert any(
        row["schema_path"].endswith("}price/text") for row in profile["paths"]
    )
    assert profile["member_sha256"] == binding.member_payload.sha256
    assert profile["native_values_emitted"] is False
    assert profile["domain_semantics_qualified"] is False
    serialized = json.dumps(profile)
    assert "1.1234567891" not in serialized
    assert profile == module.profile_schema_paths(archive, xml, parent, binding)


@pytest.mark.parametrize(
    "limit",
    ["MAX_SCHEMA_PATHS", "MAX_SCHEMA_PATH_BYTES", "MAX_INVENTORY_BYTES"],
)
def test_inventory_limits_reject_complete_report_instead_of_truncating(
    monkeypatch, limit
):
    monkeypatch.setattr(module, limit, 1)
    with pytest.raises(ValueError, match="inventory"):
        module.profile_schema_paths(*inputs())


def test_profile_cannot_relabel_or_change_the_archive_member():
    archive, xml, parent, binding = inputs()
    with pytest.raises(ValueError, match="member"):
        module.profile_schema_paths(archive, xml + b"changed", parent, binding)


def test_retained_real_values_pass_does_not_claim_prices_or_domain_completion():

    path = (
        Path(__file__).resolve().parents[1]
        / "quality/qualifications/pbs-native-values-qualification-20261022-39648302023.json"
    )
    envelope = json.loads(path.read_bytes())
    report = envelope["report"]
    assert (
        hashlib.sha256(
            json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == envelope["report_sha256"]
    )
    assert report["status"] == "passed"
    qualification = report["qualification"]
    assert qualification["native_fields"] == 18208758
    assert qualification["domain_semantics_qualified"] is False
    values = qualification["projections"]["values"]
    assert values["value_status_counts"] == {"not_price": 7730684}
    assert values["unmapped_rows"] == 7713891
    assert values["native_fields"] == qualification["native_fields"]
