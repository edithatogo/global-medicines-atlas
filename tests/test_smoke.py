"""Fast installation and critical-path smoke tests."""

from global_medicines_atlas.countries import builtin_registry
from global_medicines_atlas.source_catalog import load_source_catalog


def test_package_import_and_first_cohort_are_available() -> None:
    registry = builtin_registry()

    assert {"NZL", "AUS", "USA", "GBR", "CAN", "JPN", "EU"} <= set(
        registry.jurisdictions()
    )
    assert len(load_source_catalog()) >= 20
