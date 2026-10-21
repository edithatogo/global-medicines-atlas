"""Observed PBS domain profiles preserve exact path and source boundaries."""

import json
from dataclasses import replace
from pathlib import Path

import pyarrow as pa
import pytest
from test_pbs_value_package import inputs

from global_medicines_atlas.pbs_historical_silver import (
    iter_pbs_historical_silver_batches,
)
from global_medicines_atlas.pbs_observed_domain import (
    INVENTORY,
    iter_observed_historical_domain_batches,
    load_observed_profile,
)

ROOT = Path(__file__).resolve().parents[1]


def test_profile_accounts_for_every_retained_native_field():
    profile = load_observed_profile(ROOT)
    assert profile.native_fields == 18208758
    assert sum(profile.field_counts.values()) == 18208758
    assert profile.field_counts["prices"] > 0
    assert profile.field_counts["products"] > 0
    assert profile.field_counts["restrictions"] > 0
    assert profile.field_counts["historical_records"] > 0


def test_profile_cannot_relabel_another_member_or_unknown_path():
    profile = load_observed_profile(ROOT)
    with pytest.raises(ValueError, match="member identity"):
        profile.mapping("0" * 64, "/unknown/text", "/unknown/1")
    mapping = profile.mapping(
        profile.member_sha256, "/unknown/text", "/unknown/1"
    )
    assert mapping["mapping_target"] == "unmapped"
    assert mapping["item_occurrence_id"] is None


def test_every_observed_element_maps_consistently_without_invented_item_ids():
    profile = load_observed_profile(ROOT)
    inventory = json.loads((ROOT / INVENTORY).read_bytes())
    for row in inventory["paths"]:
        path = row["schema_path"]
        entity = (
            path.split("/attributes/", 1)[0]
            if "/attributes/" in path
            else path.rsplit("/", 1)[0]
        )
        record = "/" + "/".join(part + "/1" for part in entity.split("/")[1:])
        mapping = profile.mapping(profile.member_sha256, path, record)
        assert mapping["mapping_target"] == profile.roles[entity]
        if "}pharmaceutical-item/" not in record:
            assert mapping["item_occurrence_id"] is None


def test_occurrence_path_must_agree_with_observed_schema_path():
    profile = load_observed_profile(ROOT)
    path = next(iter(profile.roles))
    with pytest.raises(ValueError, match="occurrence paths"):
        profile.mapping(profile.member_sha256, path + "/text", "/unrelated/1")


def test_synthetic_profile_preserves_every_native_field_and_binding():
    archive, member, parent, binding = inputs()
    profile = replace(
        load_observed_profile(ROOT), member_sha256=binding.member_payload.sha256
    )
    native = pa.Table.from_batches(
        list(
            iter_pbs_historical_silver_batches(archive, member, parent, binding)
        )
    )
    actual = pa.Table.from_batches(
        list(
            iter_observed_historical_domain_batches(
                archive, member, parent, binding, profile, rows_per_batch=2
            )
        )
    )
    assert actual.select(native.column_names).to_pylist() == native.to_pylist()
    assert actual.schema.metadata[b"domain_semantics_qualified"] == b"false"
    assert (
        actual.schema.metadata[b"mapping_profile"]
        == b"pbs-observed-april-2026-structural-v1"
    )


def test_actual_profile_rejects_other_source_before_projection():
    with pytest.raises(ValueError, match="member identity"):
        list(
            iter_observed_historical_domain_batches(
                *inputs(), load_observed_profile(ROOT)
            )
        )
