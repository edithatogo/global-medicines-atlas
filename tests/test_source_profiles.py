"""Tests for generic, non-parser acquisition profiles."""

from __future__ import annotations

import pytest

from global_medicines_atlas.source_profiles import (
    PROFILES,
    acquisition_profile,
)


def test_profiles_are_unique_bounded_and_non_secret() -> None:
    assert len(PROFILES) >= 8
    assert len({profile.profile_id for profile in PROFILES}) == len(PROFILES)
    assert all(profile.minimum_interval_seconds >= 0 for profile in PROFILES)
    assert all(
        "secret=" not in profile.model_dump_json().lower()
        for profile in PROFILES
    )


def test_profile_resolution_is_exact() -> None:
    assert acquisition_profile("public-rest").profile_id == "public-rest"
    with pytest.raises(LookupError, match="resolve once"):
        acquisition_profile("missing")
