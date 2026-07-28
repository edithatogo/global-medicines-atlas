"""New Zealand FHIR fixture projection into canonical medicine contracts."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, cast

from sources.nz.nzulm_fhir import FhirResourceRecord

from .models import CanonicalMedicineRecord, Identifier, MedicineConcept, Provenance

NZMT_SYSTEM = "http://nzmt.org.nz"
NZMT_TYPE_EXTENSION = "http://hl7.org.nz/fhir/StructureDefinition/nzf-nzmt-type"
RELATED_EXTENSION = "http://hl7.org.nz/fhir/StructureDefinition/nzf-related-medication"


def _string_mapping(value: object) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    candidate = cast("Mapping[object, object]", value)
    if not all(isinstance(key, str) for key in candidate):
        return None
    return cast("Mapping[str, Any]", value)


def _first_coding(value: object) -> Mapping[str, Any] | None:
    mapping = _string_mapping(value)
    if mapping is None:
        return None
    coding = mapping.get("coding")
    if not isinstance(coding, list):
        return None
    return next(
        (
            item
            for item_value in cast("list[object]", coding)
            if (item := _string_mapping(item_value)) is not None
        ),
        None,
    )


def _extension_code(extension: Mapping[str, Any]) -> str | None:
    coding = _first_coding(extension.get("valueCodeableConcept"))
    code = coding.get("code") if coding else None
    return code if isinstance(code, str) and code else None


def _nested_extension(
    extension: Mapping[str, Any], url: str
) -> Mapping[str, Any] | None:
    children = extension.get("extension")
    if not isinstance(children, list):
        return None
    return next(
        (
            child
            for child_value in cast("list[object]", children)
            if (child := _string_mapping(child_value)) is not None
            and child.get("url") == url
        ),
        None,
    )


def _display(resource: Mapping[str, Any], resource_id: str) -> str:
    coding = _first_coding(resource.get("code"))
    if coding:
        for key in ("display", "code"):
            value = coding.get(key)
            if isinstance(value, str) and value:
                return value
    code_value = resource.get("code")
    code_mapping = _string_mapping(code_value)
    if code_mapping is not None:
        text = code_mapping.get("text")
        if isinstance(text, str) and text:
            return text
    return resource_id


def project_nz_fhir_record(record: FhirResourceRecord) -> CanonicalMedicineRecord:
    """Project a Medication fixture without inferring approval or funding."""
    if record.resource_type != "Medication":
        raise ValueError(f"Expected Medication, got {record.resource_type}")
    resource = record.resource
    extensions = resource.get("extension")
    extension_rows: list[Mapping[str, Any]] = (
        [
            item
            for item_value in cast("list[object]", extensions)
            if (item := _string_mapping(item_value)) is not None
        ]
        if isinstance(extensions, list)
        else []
    )
    level = next(
        (
            code
            for extension in extension_rows
            if extension.get("url") == NZMT_TYPE_EXTENSION
            if (code := _extension_code(extension))
        ),
        "unknown",
    )
    related: list[str] = []
    for extension in extension_rows:
        if extension.get("url") != RELATED_EXTENSION:
            continue
        code_extension = _nested_extension(extension, "code")
        if code_extension is None:
            continue
        coding = _first_coding(code_extension.get("valueCodeableConcept"))
        value = coding.get("code") if coding else None
        if isinstance(value, str) and value:
            related.append(f"nzmt:{value}")
    provenance = Provenance(
        source_id="nzmedicines-fixtures",
        source_uri=record.source_repository,
        source_path=record.source_path,
        source_sha256=record.source_sha256,
        source_version=record.source_commit,
        transformation="nz-fhir-medication-to-canonical-v1",
    )
    concept_id = f"nzmt:{record.resource_id}"
    return CanonicalMedicineRecord(
        concept=MedicineConcept(
            concept_id=concept_id,
            jurisdiction="NZ",
            level=level,
            preferred_name=_display(resource, record.resource_id),
            identifiers=(
                Identifier(
                    system=NZMT_SYSTEM,
                    value=record.resource_id,
                    identifier_type=level,
                ),
            ),
            related_concept_ids=tuple(dict.fromkeys(related)),
        ),
        assertions=(),
        provenance=(provenance,),
    )


def project_nz_fhir_records(
    records: Iterable[FhirResourceRecord],
) -> tuple[CanonicalMedicineRecord, ...]:
    projected = [
        project_nz_fhir_record(record)
        for record in records
        if record.resource_type == "Medication"
    ]
    return tuple(sorted(projected, key=lambda item: item.concept.concept_id))


def write_canonical_index(
    records: Iterable[CanonicalMedicineRecord], output: Path
) -> None:
    payload = [
        record.model_dump(mode="json")
        for record in sorted(records, key=lambda item: item.concept.concept_id)
    ]
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
