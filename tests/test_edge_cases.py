"""Boundary and failure-mode tests kept separate from happy-path suites."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.countries import (
    AdapterRegistry,
    DeclarativeCountryAdapter,
)
from global_medicines_atlas.source_catalog import MedicineDataSource
from sources.nz.nzulm_fhir import iter_fhir_resources


def test_empty_fhir_document_yields_no_inferred_resources(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "empty.json"
    payload.write_text("{}", encoding="utf-8")

    assert tuple(iter_fhir_resources([payload], source_root=tmp_path)) == ()


def test_unknown_country_adapter_fails_closed() -> None:
    with pytest.raises(KeyError):
        AdapterRegistry().get("ZZZ")


def test_declarative_adapter_without_regulatory_source_is_rejected() -> None:
    adapter = DeclarativeCountryAdapter(jurisdiction="ZZZ", sources=())

    with pytest.raises(ValueError, match="regulatory"):
        AdapterRegistry().register(adapter)


def test_api_source_requires_an_access_surface() -> None:
    with pytest.raises(ValidationError):
        MedicineDataSource.model_validate({
            "source_id": "edge.invalid",
            "jurisdiction": "ZZZ",
            "authority": "Example",
            "dataset": "Example",
            "dimension": "regulatory",
            "access_mode": "api",
            "readiness": "candidate",
            "evidence_limit": "Test-only invalid source.",
        })
