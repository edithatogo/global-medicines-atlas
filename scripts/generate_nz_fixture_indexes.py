"""Reproduce nzmedicines fixture indexes without mutating vendor."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

JsonObject = dict[str, Any]
INDEX_FILENAMES = (
    Path("document-references/index.txt"),
    Path("substance/substance.txt"),
)


def _object(value: object, *, context: str) -> JsonObject:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in cast("dict[object, object]", value)
    ):
        raise ValueError(f"{context} must be a JSON object")
    return cast("JsonObject", value)


def _objects(value: object, *, context: str) -> list[JsonObject]:
    if not isinstance(value, list):
        raise TypeError(f"{context} must be a JSON array")
    return [
        _object(item, context=f"{context}[{position}]")
        for position, item in enumerate(cast("list[object]", value))
    ]


def _string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} must be a non-empty string")
    return value


def _extensions(resource: Mapping[str, Any]) -> list[JsonObject]:
    value = resource.get("extension", [])
    return _objects(value, context="resource.extension")


def _children(extension: Mapping[str, Any]) -> dict[str, JsonObject]:
    rows = _objects(
        extension.get("extension", []), context="extension.extension"
    )
    result: dict[str, JsonObject] = {}
    for row in rows:
        url = _string(row.get("url"), context="nested extension url")
        if url in result:
            raise ValueError(f"duplicate nested extension: {url}")
        result[url] = row
    return result


def _coding(value: object, *, context: str) -> list[JsonObject]:
    concept = _object(value, context=context)
    return _objects(concept.get("coding"), context=f"{context}.coding")


def _first_code(value: object, *, context: str) -> str:
    rows = _coding(value, context=context)
    if not rows:
        raise ValueError(f"{context}.coding must not be empty")
    return _string(rows[0].get("code"), context=f"{context}.coding[0].code")


def _type_of(resource: Mapping[str, Any]) -> str:
    for extension in _extensions(resource):
        if str(extension.get("url", "")).endswith("nzf-nzmt-type"):
            return _first_code(
                extension.get("valueCodeableConcept"),
                context="nzf-nzmt-type",
            )
    raise ValueError(f"Medication/{resource.get('id', '?')} has no NZMT type")


def _name_of(resource: Mapping[str, Any]) -> str:
    resource_id = _string(resource.get("id"), context="resource.id")
    code = _object(
        resource.get("code"), context=f"Medication/{resource_id}.code"
    )
    rows = _objects(
        code.get("coding"), context=f"Medication/{resource_id}.code.coding"
    )
    if not rows:
        raise ValueError(
            f"Medication/{resource_id}.code.coding must not be empty"
        )
    display = rows[0].get("display")
    return display if isinstance(display, str) and display else resource_id


def _extension(resource: Mapping[str, Any], suffix: str) -> JsonObject | None:
    return next(
        (
            extension
            for extension in _extensions(resource)
            if str(extension.get("url", "")).endswith(suffix)
        ),
        None,
    )


def _concept_code(extension: Mapping[str, Any], *, context: str) -> str:
    return _first_code(extension.get("valueCodeableConcept"), context=context)


def _related(resource: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for extension in _extensions(resource):
        if not str(extension.get("url", "")).endswith("nzf-related-medication"):
            continue
        children = _children(extension)
        try:
            target_id = _concept_code(children["code"], context="related code")
            target_type = _concept_code(
                children["type"], context="related type"
            )
        except KeyError as error:
            raise ValueError(
                "related medication requires code and type"
            ) from error
        if target_id not in result[target_type]:
            result[target_type].append(target_id)
    return dict(result)


def _boolean_extension(resource: Mapping[str, Any], suffix: str) -> bool | None:
    extension = _extension(resource, suffix)
    if extension is None:
        return None
    value = extension.get("valueBoolean")
    if not isinstance(value, bool):
        raise TypeError(f"{suffix} must contain valueBoolean")
    return value


def _atc(resource: Mapping[str, Any]) -> str | None:
    extension = _extension(resource, "nzf-atc")
    return (
        _concept_code(extension, context="nzf-atc")
        if extension is not None
        else None
    )


def _snomed(resource: Mapping[str, Any]) -> str | None:
    code = _object(resource.get("code"), context="Medication.code")
    for coding in _objects(
        code.get("coding"), context="Medication.code.coding"
    ):
        if "snomed" in str(coding.get("system", "")).lower():
            return _string(coding.get("code"), context="SNOMED code")
    return None


def _synonyms(resource: Mapping[str, Any]) -> list[str]:
    values: set[str] = set()
    for extension in _extensions(resource):
        if not str(extension.get("url", "")).endswith("nzf-description"):
            continue
        children = _children(extension)
        type_row = children.get("type")
        term_row = children.get("term")
        if type_row is None or term_row is None:
            raise ValueError("nzf-description requires type and term")
        type_concept = _object(
            type_row.get("valueCodeableConcept"), context="description type"
        )
        if type_concept.get("text") != "Synonym":
            continue
        term = _object(
            term_row.get("valueCodeableConcept"), context="description term"
        ).get("text")
        values.add(_string(term, context="description term text"))
    return sorted(values)


def _legal_classification(resource: Mapping[str, Any]) -> str | None:
    extension = _extension(resource, "nzf-legalclass")
    if extension is None:
        return None
    children = _children(extension)
    classification = children.get("classification") or children.get("code")
    if classification is None:
        return None
    concept = _object(
        classification.get("valueCodeableConcept"),
        context="legal classification",
    )
    text = concept.get("text")
    return text if isinstance(text, str) and text else None


def _monographs(resource: Mapping[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for extension in _extensions(resource):
        if not str(extension.get("url", "")).endswith("nzf-link"):
            continue
        reference = _object(
            extension.get("valueReference"), context="nzf-link.valueReference"
        )
        identifier = _object(
            reference.get("identifier"), context="nzf-link.identifier"
        )
        value = _string(
            identifier.get("value"), context="nzf-link identifier value"
        )
        target = _string(
            reference.get("reference"), context="nzf-link reference"
        )
        lowered = target.casefold()
        audience = "child" if "child" in lowered else "adult"
        if audience in values and values[audience] != value:
            raise ValueError(f"duplicate {audience} monograph")
        values[audience] = value
    return dict(sorted(values.items()))


def _extra_codes(resource: Mapping[str, Any]) -> dict[str, Any]:
    code = _object(resource.get("code"), context="Medication.code")
    gtins: set[str] = set()
    primary: str | None = None
    other: set[str] = set()
    for coding in _objects(
        code.get("coding"), context="Medication.code.coding"
    ):
        system = str(coding.get("system", ""))
        value = coding.get("code")
        if not isinstance(value, str) or not value:
            continue
        if "gs1" in system:
            gtins.add(value)
        elif "pharmac-subsidy-code" in system:
            extensions = _objects(
                coding.get("extension", []), context="coding.extension"
            )
            is_primary = any(
                row.get("valueBoolean") is True for row in extensions
            )
            if is_primary:
                if primary is not None and primary != value:
                    raise ValueError("multiple primary pharmacodes")
                primary = value
            else:
                other.add(value)
    result: dict[str, Any] = {}
    if gtins:
        result["gtins"] = sorted(gtins)
    if primary is not None:
        result["primaryPharmacode"] = primary
    if other:
        result["otherPharmacode"] = sorted(other)
    return result


def _funding_types(resource: Mapping[str, Any]) -> list[str]:
    for extension in _extensions(resource):
        url = str(extension.get("url", ""))
        if not url.endswith("nzf-funding") or "rule" in url:
            continue
        type_row = _children(extension).get("type")
        if type_row is not None:
            return [_concept_code(type_row, context="funding type")]
    return []


def _load_resources(
    paths: Iterable[Path],
) -> tuple[dict[str, JsonObject], dict[str, str]]:
    resources: dict[str, JsonObject] = {}
    source_files: dict[str, str] = {}
    for path in sorted(paths, key=lambda item: item.name.casefold()):
        try:
            bundle = _object(
                json.loads(path.read_text(encoding="utf-8")),
                context=str(path),
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError(f"malformed JSON in {path.name}") from error
        if (
            bundle.get("resourceType") != "Bundle"
            or bundle.get("type") != "collection"
        ):
            raise ValueError(f"{path.name} must be a collection Bundle")
        for entry in _objects(
            bundle.get("entry"), context=f"{path.name}.entry"
        ):
            resource = _object(
                entry.get("resource"), context=f"{path.name} resource"
            )
            if resource.get("resourceType") != "Medication":
                raise ValueError(
                    f"{path.name} contains a non-Medication resource"
                )
            resource_id = _string(resource.get("id"), context="Medication.id")
            if resource_id in resources:
                raise ValueError(
                    f"duplicate Medication resource id: {resource_id}"
                )
            resources[resource_id] = resource
            source_files[resource_id] = path.name
    if not resources:
        raise ValueError("at least one Medication resource is required")
    return resources, source_files


def build_medication_index(  # ruff: ignore[too-many-locals]
    paths: Iterable[Path],
) -> bytes:
    """Build the historical medication relationship index deterministically."""
    path_rows = tuple(paths)
    resources, source_files = _load_resources(path_rows)
    types = {
        resource_id: _type_of(resource)
        for resource_id, resource in resources.items()
    }
    related = {
        resource_id: _related(resource)
        for resource_id, resource in resources.items()
    }
    by_type: dict[str, list[str]] = defaultdict(list)
    for resource_id, resource_type in types.items():
        by_type[resource_type].append(resource_id)
    for values in by_type.values():
        values.sort(key=lambda item: (_name_of(resources[item]), item))
    if len(by_type.get("mp", [])) != 1:
        raise ValueError("a medication folder must contain exactly one MP")
    mp_id = by_type["mp"][0]
    mp_resource = resources[mp_id]

    def simple(resource_id: str, relation: str) -> JsonObject:
        return {
            "id": resource_id,
            "name": _name_of(resources[resource_id]),
            relation: related[resource_id].get(
                "mpp" if relation == "relatedMpps" else "mpuu", []
            ),
        }

    mpuus: list[JsonObject] = []
    for resource_id in by_type.get("mpuu", []):
        row: JsonObject = {
            "id": resource_id,
            "name": _name_of(resources[resource_id]),
            "isPrescribeByBrand": _boolean_extension(
                resources[resource_id], "nzf-prescribe-by-brand"
            ),
            "relatedMpps": related[resource_id].get("mpp", []),
        }
        mpuus.append(row)
    mpps = [
        simple(resource_id, "relatedMpuu")
        for resource_id in by_type.get("mpp", [])
    ]

    brands: list[JsonObject] = []
    lookup_order = [mp_id, *by_type.get("mpuu", [])]
    lookup_order.extend(
        target
        for resource_id in by_type.get("mpuu", [])
        for target in related[resource_id].get("mpp", [])
    )
    for tp_id in by_type.get("tp", []):
        tpuus = [
            resource_id
            for resource_id in by_type.get("tpuu", [])
            if tp_id in related[resource_id].get("tp", [])
        ]
        products = [
            resource_id
            for resource_id in by_type.get("ctpp", [])
            if tp_id in related[resource_id].get("tp", [])
        ]
        tpp_ids = {
            target
            for resource_id in tpuus
            for target in related[resource_id].get("tpp", [])
        }
        lookup_order.extend([tp_id, *tpuus])
        lookup_order.extend(
            sorted(tpp_ids, key=lambda item: (_name_of(resources[item]), item))
        )
        lookup_order.extend(products)
        product_rows: list[JsonObject] = []
        for resource_id in products:
            links = related[resource_id]
            ctpp = {
                "id": resource_id,
                "name": _name_of(resources[resource_id]),
                **_extra_codes(resources[resource_id]),
            }
            funding = _funding_types(resources[resource_id])
            if funding:
                ctpp["fundingTypes"] = funding
            product_rows.append({
                "ctpp": ctpp,
                "tpp": links.get("tpp", [None])[0],
                "tpuu": links.get("tpuu", [None])[0],
                "mpp": links.get("mpp", [None])[0],
                "mpuu": links.get("mpuu", [None])[0],
            })
        brands.append({
            "tp": {
                "id": tp_id,
                "name": _name_of(resources[tp_id]),
                "sourceFile": source_files[tp_id],
            },
            "tpuus": [
                {
                    "id": resource_id,
                    "name": _name_of(resources[resource_id]),
                    "relatedMpuu": related[resource_id].get(
                        "mpuu",
                        [],
                    ),
                    "relatedTpp": related[resource_id].get(
                        "tpp",
                        [],
                    ),
                }
                for resource_id in tpuus
            ],
            "products": product_rows,
        })

    mp: JsonObject = {
        "id": mp_id,
        "name": _name_of(mp_resource),
        "atc": _atc(mp_resource),
        "snomed": _snomed(mp_resource),
        "synonyms": _synonyms(mp_resource),
        "substanceLegalClassification": _legal_classification(mp_resource),
        "isPrescribeByBrand": (
            _boolean_extension(mp_resource, "nzf-prescribe-by-brand") or False
        ),
        "monographs": _monographs(mp_resource),
    }
    index = {
        "_description": (
            "Auto-generated relationship index for "
            f"{_name_of(mp_resource)} ({mp_id}). Regenerated by GitHub Actions "
            "on every push to main. Do not edit manually."
        ),
        "_sourceFiles": [
            source_files[mp_id],
            *[
                source_files[resource_id]
                for resource_id in by_type.get("tp", [])
            ],
        ],
        "mp": mp,
        "generics": {"mpuus": mpuus, "mpps": mpps},
        "brands": brands,
        "_lookup": {
            resource_id: {
                "type": types[resource_id],
                "name": _name_of(resources[resource_id]),
            }
            for resource_id in dict.fromkeys(lookup_order)
        },
    }
    return (
        json
        .dumps(index, indent=2, ensure_ascii=False)
        .replace("\n", "\r\n")
        .encode()
    )


def build_indexes(vendor_root: Path) -> dict[Path, bytes]:
    """Return all generated index bytes, keyed by vendor-relative path."""
    medication_root = vendor_root / "medications"
    outputs = dict.fromkeys(INDEX_FILENAMES, b"\r\n")
    for folder in sorted(
        (path for path in medication_root.iterdir() if path.is_dir()),
        key=lambda item: item.name.casefold(),
    ):
        inputs = tuple(
            path
            for path in folder.glob("*.json")
            if not path.name.startswith("_")
        )
        if inputs:
            outputs[Path("medications") / folder.name / "_index.json"] = (
                build_medication_index(inputs)
            )
    return outputs


def verify_indexes(vendor_root: Path) -> tuple[Path, ...]:
    """Return indexes whose committed bytes differ from deterministic output."""
    outputs = build_indexes(vendor_root)
    return tuple(
        relative
        for relative, expected in outputs.items()
        if not (vendor_root / relative).is_file()
        or (vendor_root / relative).read_bytes() != expected
    )


def _is_below(path: Path, root: Path) -> bool:
    return path != root and root in path.parents


def _safe_destination(
    *,
    output_root: Path,
    output_resolved: Path,
    vendor_resolved: Path,
    relative: Path,
) -> Path:
    destination = output_root / relative
    current = output_root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise ValueError(
                f"generated destination contains a symlink: {current}"
            )
        current.mkdir(exist_ok=True)
        resolved = current.resolve()
        if not _is_below(resolved, output_resolved):
            raise ValueError("generated destination escapes the output root")
        if resolved == vendor_resolved or _is_below(
            resolved,
            vendor_resolved,
        ):
            raise ValueError(
                "generated destination enters the immutable vendor snapshot"
            )
    if destination.is_symlink():
        raise ValueError(
            f"generated destination contains a symlink: {destination}"
        )
    resolved_destination = destination.resolve()
    if not _is_below(resolved_destination, output_resolved):
        raise ValueError("generated destination escapes the output root")
    if resolved_destination == vendor_resolved or _is_below(
        resolved_destination,
        vendor_resolved,
    ):
        raise ValueError(
            "generated destination enters the immutable vendor snapshot"
        )
    return destination


def write_indexes(vendor_root: Path, output_root: Path) -> tuple[Path, ...]:
    """Write generated indexes only to a separate, non-vendor output tree."""
    vendor_resolved = vendor_root.resolve()
    if output_root.is_symlink():
        raise ValueError("output root must not be a symlink")
    output_resolved = output_root.resolve()
    if output_resolved == vendor_resolved or _is_below(
        output_resolved,
        vendor_resolved,
    ):
        raise ValueError("output must be outside the immutable vendor snapshot")
    output_root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for relative, payload in build_indexes(vendor_root).items():
        output = _safe_destination(
            output_root=output_root,
            output_resolved=output_resolved,
            vendor_resolved=vendor_resolved,
            relative=relative,
        )
        output.write_bytes(payload)
        paths.append(output)
    return tuple(paths)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vendor-root",
        type=Path,
        default=Path("vendor/nzmedicines"),
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Verify committed indexes or generate them into a separate output tree."""
    arguments = _parser().parse_args(argv)
    if arguments.output is not None:
        paths = write_indexes(arguments.vendor_root, arguments.output)
        for path in paths:
            print(path)
        return 0
    drift = verify_indexes(arguments.vendor_root)
    if drift:
        for path in drift:
            print(f"index drift: {path}")
        return 1
    if arguments.check:
        print(f"verified {len(build_indexes(arguments.vendor_root))} indexes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
