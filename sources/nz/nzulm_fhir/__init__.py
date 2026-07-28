"""NZULM/NZMT FHIR projection and fixture support."""

from .adapter import (
    FhirResourceRecord,
    iter_fhir_resources,
    load_upstream_fixture_records,
)

__all__ = [
    "FhirResourceRecord",
    "iter_fhir_resources",
    "load_upstream_fixture_records",
]
