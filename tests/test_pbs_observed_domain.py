"""Observed PBS domain profiles preserve exact path and source boundaries."""

import json
from dataclasses import replace
from pathlib import Path

import pyarrow as pa
import pytest
from test_au_pbs_v3 import (
    _zip,  # ruff: ignore[import-private-name] -- synthetic archive only
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic lineage only
)
from test_pbs_historical_silver import PATH, SOURCE
from test_pbs_value_package import inputs

from global_medicines_atlas import pbs_observed_domain as module
from global_medicines_atlas.pbs_historical_silver import (
    iter_pbs_historical_silver_batches,
)
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
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


def test_synthetic_profile_preserves_every_native_field_and_binding(
    monkeypatch,
):
    archive, member, parent, binding = inputs()
    profile = replace(
        load_observed_profile(ROOT), member_sha256=binding.member_payload.sha256
    )
    monkeypatch.setattr(module, "MEMBER_SHA256", binding.member_payload.sha256)
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


def test_observed_entity_values_keep_native_amount_and_ancestors(monkeypatch):
    profile = load_observed_profile(ROOT)
    path = min(
        (path for path, role in profile.roles.items() if role == "prices"),
        key=len,
    )
    tags = [
        name.replace("~1", "/").replace("~0", "~").split("}")[-1]
        for name in path.split("/")[1:]
    ]
    body = "001.1234567891"
    for tag in reversed(tags):
        body = f"<pbs:{tag}>{body}</pbs:{tag}>"
    member = body.replace(
        "<pbs:root>", '<pbs:root xmlns:pbs="http://schema.pbs.gov.au/">'
    ).encode()
    archive, parent, binding = synthetic_binding(member)
    selected = replace(profile, member_sha256=binding.member_payload.sha256)
    monkeypatch.setattr(module, "MEMBER_SHA256", binding.member_payload.sha256)
    batches = list(
        module.iter_observed_historical_value_batches(
            archive, member, parent, binding, selected, rows_per_batch=2
        )
    )
    rows = pa.Table.from_batches(batches).to_pylist()
    amount = next(row for row in rows if row["mapping_target"] == "prices")
    assert amount["native_text"] == "001.1234567891"
    assert amount["candidate_decimal"] is None
    assert amount["candidate_conversion_status"] == "unrepresentable"
    assert amount["native_currency_state"] == "missing_field"
    assert amount["interpretation_state"] == "native_unresolved"
    assert amount["parent_entity_id"] is not None
    native = pa.Table.from_batches(
        list(
            iter_pbs_historical_silver_batches(archive, member, parent, binding)
        )
    ).to_pylist()
    flattened = [
        {name: value for name, value in field.items() if name in native[0]}
        for row in rows
        for field in row["native_fields"]
    ]
    assert flattened == native


def synthetic_binding(member):
    archive = _zip([(PATH, member)])
    parent = _receipt(archive, SOURCE)
    return archive, parent, build_pbs_xml_member_binding(archive, parent)
