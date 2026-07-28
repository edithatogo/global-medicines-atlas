"""Read-only adapters for preserved nzmedicines FHIR fixtures.

The preserved upstream snapshot is evidence and test input. This module emits
small provenance-bearing records without treating FHIR projections as the
canonical medicines data model.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.logging import get_logger

UPSTREAM_REPOSITORY = "https://github.com/edithatogo/nzmedicines"
UPSTREAM_COMMIT = "6a8ecfae67f15d635750d11d5f446b93d76c1865"
LOGGER = get_logger("nz.fhir", component="nz-fhir-adapter", jurisdiction="NZL")


@dataclass(frozen=True, slots=True)
class FhirResourceRecord:
    """A source-native FHIR fixture with immutable upstream provenance."""

    resource_type: str
    resource_id: str
    resource: Mapping[str, Any]
    source_path: str
    source_sha256: str
    source_repository: str = UPSTREAM_REPOSITORY
    source_commit: str = UPSTREAM_COMMIT


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
    paths: Iterable[Path], *, source_root: Path
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
                raise ValueError(f"{source_path}: FHIR resourceType is required")
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
            )


def load_upstream_fixture_records(project_root: Path) -> tuple[FhirResourceRecord, ...]:
    """Load preserved upstream JSON fixtures from the immutable vendor snapshot."""
    source_root = project_root / "vendor" / "nzmedicines"
    paths = (
        path
        for path in source_root.rglob("*.json")
        if path.name != "nzmedicines.import.json"
    )
    return tuple(iter_fhir_resources(paths, source_root=source_root))
