"""Read-only adapters for synthetic NZ medicines FHIR fixtures."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.logging import get_logger

SYNTHETIC_FIXTURE_URI = "local://tests/fixtures/nz/nzmt_synthetic_bundle.json"
SYNTHETIC_FIXTURE_VERSION = "gma-nzmt-synthetic-v1"
LOGGER = get_logger("nz.fhir", component="nz-fhir-adapter", jurisdiction="NZL")


@dataclass(frozen=True, slots=True)
class FhirResourceRecord:
    """A FHIR fixture with explicit source provenance."""

    resource_type: str
    resource_id: str
    resource: Mapping[str, Any]
    source_path: str
    source_sha256: str
    source_repository: str = SYNTHETIC_FIXTURE_URI
    source_commit: str = SYNTHETIC_FIXTURE_VERSION


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _string_mapping(value: object) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    candidate = cast("Mapping[object, object]", value)
    if not all(isinstance(key, str) for key in candidate):
        return None
    return cast("Mapping[str, Any]", value)


def _resource_dicts(document: object) -> Iterator[Mapping[str, Any]]:
    document_mapping = _string_mapping(document)
    if document_mapping is None:
        return
    resource_type = document_mapping.get("resourceType")
    if isinstance(resource_type, str):
        yield document_mapping
    entries = document_mapping.get("entry")
    if not isinstance(entries, list):
        return
    for entry_value in cast("list[object]", entries):
        entry = _string_mapping(entry_value)
        if entry is None:
            continue
        resource = entry.get("resource")
        resource_mapping = _string_mapping(resource)
        if resource_mapping is not None:
            yield resource_mapping


def iter_fhir_resources(
    paths: Iterable[Path],
    *,
    source_root: Path,
    source_repository: str = SYNTHETIC_FIXTURE_URI,
    source_version: str = SYNTHETIC_FIXTURE_VERSION,
) -> Iterator[FhirResourceRecord]:
    """Yield unique FHIR resources from source-native documents and bundles."""
    seen: set[tuple[str, str]] = set()
    for path in sorted(paths):
        document = json.loads(path.read_text(encoding="utf-8"))
        source_path = path.relative_to(source_root).as_posix()
        source_sha256 = _sha256(path)
        for resource in _resource_dicts(document):
            resource_type = resource.get("resourceType")
            resource_id = resource.get("id")
            if not isinstance(resource_type, str) or not resource_type.strip():
                raise ValueError(
                    f"{source_path}: FHIR resourceType is required"
                )
            if not isinstance(resource_id, str) or not resource_id.strip():
                raise ValueError(f"{source_path}: FHIR id is required")
            identity = (resource_type, resource_id)
            if identity in seen:
                raise ValueError(
                    f"{source_path}: duplicate FHIR identity {resource_type}/{resource_id}"
                )
            seen.add(identity)
            LOGGER.debug(
                "Loaded source-native FHIR resource",
                extra={"source_id": source_path},
            )
            yield FhirResourceRecord(
                resource_type=resource_type,
                resource_id=resource_id,
                resource=resource,
                source_path=source_path,
                source_sha256=source_sha256,
                source_repository=source_repository,
                source_commit=source_version,
            )


def load_synthetic_fixture_records(
    project_root: Path,
) -> tuple[FhirResourceRecord, ...]:
    """Load the minimal first-party synthetic NZMT-shaped fixture cohort."""
    source_root = project_root / "tests" / "fixtures" / "nz"
    paths = (source_root / "nzmt_synthetic_bundle.json",)
    return tuple(iter_fhir_resources(paths, source_root=source_root))
