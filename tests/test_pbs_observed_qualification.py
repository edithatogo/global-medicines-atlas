"""Observed PBS qualification checks all native fields and structural counters."""

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pyarrow as pa
import pytest
from test_pbs_value_package import inputs

from global_medicines_atlas import pbs_observed_domain as domain
from global_medicines_atlas.pbs_historical_silver import (
    iter_pbs_historical_silver_batches,
)
from global_medicines_atlas.pbs_observed_qualification import (
    qualify_observed_values,
)

ROOT = Path(__file__).resolve().parents[1]


def test_all_fields_restore_and_role_counts_match_independent_inventory(
    monkeypatch,
):
    archive, member, parent, binding = inputs()
    profile = domain.load_observed_profile(ROOT)
    native = pa.Table.from_batches(
        list(
            iter_pbs_historical_silver_batches(archive, member, parent, binding)
        )
    ).to_pylist()
    counts = Counter(
        profile.roles.get(domain._entity_path(row["schema_path"]), "unmapped")
        for row in native
    )
    selected = replace(
        profile,
        member_sha256=binding.member_payload.sha256,
        native_fields=len(native),
        field_counts=counts,
    )
    monkeypatch.setattr(domain, "MEMBER_SHA256", binding.member_payload.sha256)
    report = qualify_observed_values(archive, member, parent, binding, selected)
    assert report["native_fields"] == len(native)
    assert report["role_field_counts"] == dict(counts)
    assert report["domain_semantics_qualified"] is False
    assert report["new_admissions"] == 0


def test_wrong_native_denominator_is_rejected():
    archive, member, parent, binding = inputs()
    profile = domain.load_observed_profile(ROOT)
    with pytest.raises(ValueError, match="native denominator"):
        qualify_observed_values(archive, member, parent, binding, profile)


def test_source_matched_profile_cannot_hide_role_coverage_gap(monkeypatch):
    archive, member, parent, binding = inputs()
    profile = domain.load_observed_profile(ROOT)
    native = pa.Table.from_batches(
        list(
            iter_pbs_historical_silver_batches(archive, member, parent, binding)
        )
    ).to_pylist()
    selected = replace(
        profile,
        member_sha256=binding.member_payload.sha256,
        native_fields=len(native),
        field_counts={"unmapped": len(native) + 1},
    )
    monkeypatch.setattr(domain, "MEMBER_SHA256", binding.member_payload.sha256)
    with pytest.raises(ValueError, match="role coverage"):
        qualify_observed_values(archive, member, parent, binding, selected)
