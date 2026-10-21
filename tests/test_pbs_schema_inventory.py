"""PBS schema profiling emits only paths/counts, retaining namespace and coverage."""

import hashlib
import json
from pathlib import Path

import pytest
from test_pbs_value_package import inputs

from global_medicines_atlas import pbs_schema_inventory as module
from global_medicines_atlas.receipts import PayloadEvidence


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


def test_source_specific_limits_require_exact_archive_and_member_identity():

    _, _, _, binding = inputs()
    assert (
        module.schema_inventory_limits(binding)["inventory_bytes"]
        == 1024 * 1024
    )
    pinned = binding.model_copy(
        update={
            "source": binding.source.model_copy(
                update={"catalog_version": "2026-04-01"}
            ),
            "archive_payload": PayloadEvidence(
                sha256="f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20",
                byte_count=1,
            ),
            "member_payload": PayloadEvidence(
                sha256="73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43",
                byte_count=1,
            ),
            "member_path": "sch-2026-04-01-r1.xml",
        }
    )
    limits = module.schema_inventory_limits(pinned)
    assert limits["inventory_bytes"] == 32 * 1024**2
    assert limits["expected_native_fields"] == 18208758
    for dimension, replacement in [
        ("source", pinned.source.model_copy(update={"source_id": "other"})),
        (
            "source",
            pinned.source.model_copy(update={"catalog_version": "2026-05-01"}),
        ),
        ("archive_payload", PayloadEvidence(sha256="0" * 64, byte_count=1)),
        ("member_payload", PayloadEvidence(sha256="0" * 64, byte_count=1)),
    ]:
        changed_identity = pinned.model_copy(update={dimension: replacement})
        assert (
            module.schema_inventory_limits(changed_identity)["profile"]
            == "pbs-schema-paths-v1"
        )
    changed = pinned.model_copy(update={"member_path": "other.xml"})
    assert (
        module.schema_inventory_limits(changed)["inventory_bytes"]
        == 1024 * 1024
    )


@pytest.mark.parametrize(
    "dimension", ["source", "archive_payload", "member_payload"]
)
def test_scoped_profile_rejects_other_identity_components(dimension):
    _, _, _, binding = inputs()
    # The synthetic source must retain the default bounded profile regardless
    # of an unrelated identity component being changed.
    replacement = (
        binding.source.model_copy(update={"source_id": "other-source"})
        if dimension == "source"
        else PayloadEvidence(sha256="0" * 64, byte_count=1)
    )
    changed = binding.model_copy(update={dimension: replacement})
    assert (
        module.schema_inventory_limits(changed)["profile"]
        == "pbs-schema-paths-v1"
    )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"total_path_bytes": 1}, "total path byte"),
        ({"expected_native_fields": 1}, "denominator differs"),
    ],
)
def test_scoped_limits_still_reject_incomplete_or_excessive_inventory(
    monkeypatch, override, message
):
    binding = inputs()[3]
    limits = module.schema_inventory_limits(binding) | override
    monkeypatch.setattr(module, "schema_inventory_limits", lambda _: limits)
    with pytest.raises(ValueError, match=message):
        module.profile_schema_paths(*inputs())


def test_bounded_recovery_records_original_limit_without_truncation(
    monkeypatch,
):
    arguments = inputs()
    limits = module.schema_inventory_limits(arguments[3])
    monkeypatch.setattr(module, "schema_inventory_limits", lambda _: limits)
    monkeypatch.setattr(module, "MAX_SCHEMA_PATHS", 1)
    monkeypatch.setattr(module, "MAX_SCHEMA_PATH_BYTES", 1)
    monkeypatch.setattr(module, "MAX_INVENTORY_BYTES", 1)
    report = module.profile_schema_paths(*arguments)
    assert report["original_v1_limits_exceeded"] == [
        "inventory_bytes",
        "path_bytes",
        "path_count",
    ]
    assert len(report["paths"]) > 1
    assert (
        sum(path["native_fields"] for path in report["paths"])
        == report["native_fields"]
    )
