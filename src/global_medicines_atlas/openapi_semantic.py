"""Deterministic, dependency-light OpenAPI compatibility contracts."""

# ruff: file-ignore[too-many-branches, too-many-locals, manual-list-comprehension]

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

READ_METHODS = frozenset({"get", "head", "options"})
MUTATION_METHODS = frozenset({"post", "put", "patch", "delete", "trace"})
_SCHEMA_KEYS = frozenset({
    "type",
    "format",
    "enum",
    "const",
    "required",
    "properties",
    "items",
    "anyOf",
    "oneOf",
    "allOf",
    "additionalProperties",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "pattern",
    "$ref",
})


class OpenAPIContractError(ValueError):
    """The public OpenAPI document violates the read-only contract."""


@dataclass(frozen=True)
class SemanticChange:
    """One deterministic compatibility finding."""

    location: str
    reason: str


def _object(value: object, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OpenAPIContractError(f"{location} must be an object")
    return cast("dict[str, Any]", value)


def _schema(value: object) -> dict[str, Any]:
    source = _object(value, "schema")
    return {
        key: _normalize_schema_item(source[key])
        for key in sorted(_SCHEMA_KEYS & source.keys())
    }


def _normalize_schema_item(value: object) -> object:
    if isinstance(value, dict):
        values = cast("dict[object, object]", value)
        return {
            str(key): _normalize_schema_item(item)
            for key, item in sorted(
                values.items(), key=lambda pair: str(pair[0])
            )
        }
    if isinstance(value, list):
        values_list = cast("list[object]", value)
        return [_normalize_schema_item(item) for item in values_list]
    return deepcopy(value)


def semantic_snapshot(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project a full OpenAPI document into a stable public contract."""
    paths = _object(document.get("paths"), "paths")
    projected: dict[str, dict[str, Any]] = {}
    for path, path_value in sorted(paths.items()):
        item = _object(path_value, f"paths.{path}")
        forbidden = sorted(MUTATION_METHODS & item.keys())
        if forbidden:
            raise OpenAPIContractError(
                f"mutation operations are forbidden on {path}: {forbidden}"
            )
        operations: dict[str, Any] = {}
        for method in sorted(READ_METHODS & item.keys()):
            operation = _object(item[method], f"{method.upper()} {path}")
            if "requestBody" in operation:
                raise OpenAPIContractError(
                    f"request bodies are forbidden on {method.upper()} {path}"
                )
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise OpenAPIContractError(
                    f"operationId is required on {method.upper()} {path}"
                )
            parameters: list[dict[str, Any]] = []
            for raw_parameter in operation.get("parameters", []):
                parameter = _object(raw_parameter, "parameter")
                parameter_contract: dict[str, Any] = {
                    "in": parameter.get("in"),
                    "name": parameter.get("name"),
                    "required": parameter.get("required", False),
                    "schema": _schema(parameter.get("schema", {})),
                }
                parameters.append(parameter_contract)
            parameters.sort(
                key=lambda value: (str(value["in"]), str(value["name"]))
            )
            responses = _object(operation.get("responses"), "responses")
            response_contract: dict[str, Any] = {}
            for status, raw_response in sorted(responses.items()):
                response = _object(raw_response, f"response {status}")
                content = _object(
                    response.get("content", {}), "response content"
                )
                response_contract[str(status)] = {
                    media: _schema(_object(body, media).get("schema", {}))
                    for media, body in sorted(content.items())
                }
            operations[method] = {
                "operationId": operation_id,
                "parameters": parameters,
                "responses": response_contract,
            }
        if operations:
            projected[path] = operations
    components = _object(document.get("components", {}), "components")
    component_schemas = _object(
        components.get("schemas", {}), "components.schemas"
    )
    return {
        "contract": "global-medicines-atlas.openapi-readonly",
        "version": 1,
        "components": {
            name: _schema(schema)
            for name, schema in sorted(component_schemas.items())
        },
        "paths": projected,
    }


def _parameter_map(
    operation: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(value["in"]), str(value["name"])): value
        for value in cast(
            "list[dict[str, Any]]", operation.get("parameters", [])
        )
    }


def _schema_changes(
    baseline: Mapping[str, Any], current: Mapping[str, Any], location: str
) -> list[SemanticChange]:
    changes: list[SemanticChange] = []
    for key in ("type", "format", "const", "pattern", "$ref"):
        if key in baseline and baseline.get(key) != current.get(key):
            changes.append(SemanticChange(location, f"{key} changed"))
    if "enum" in baseline and not set(baseline["enum"]) <= set(
        current.get("enum", [])
    ):
        changes.append(SemanticChange(location, "enum values removed"))
    for key in ("minimum", "exclusiveMinimum", "minLength", "minItems"):
        if key in baseline and (
            key not in current or current[key] > baseline[key]
        ):
            changes.append(SemanticChange(location, f"{key} narrowed"))
    for key in ("maximum", "exclusiveMaximum", "maxLength", "maxItems"):
        if key in baseline and (
            key not in current or current[key] < baseline[key]
        ):
            changes.append(SemanticChange(location, f"{key} narrowed"))
    old_required = set(baseline.get("required", []))
    new_required = set(current.get("required", []))
    if not old_required <= new_required:
        changes.append(
            SemanticChange(location, "required response fields removed")
        )
    old_properties = cast("Mapping[str, Any]", baseline.get("properties", {}))
    new_properties = cast("Mapping[str, Any]", current.get("properties", {}))
    for name in sorted(old_properties.keys() - new_properties.keys()):
        changes.append(
            SemanticChange(f"{location}.{name}", "response field removed")
        )
    for name in sorted(old_properties.keys() & new_properties.keys()):
        changes.extend(
            _schema_changes(
                old_properties[name], new_properties[name], f"{location}.{name}"
            )
        )
    if "items" in baseline:
        if "items" not in current:
            changes.append(
                SemanticChange(location, "array item schema removed")
            )
        else:
            changes.extend(
                _schema_changes(
                    baseline["items"], current["items"], f"{location}[]"
                )
            )
    for key in ("anyOf", "oneOf", "allOf"):
        if key in baseline and baseline.get(key) != current.get(key):
            changes.append(SemanticChange(location, f"{key} changed"))
    return changes


def semantic_diff(
    baseline: Mapping[str, Any], current_document: Mapping[str, Any]
) -> tuple[SemanticChange, ...]:
    """Return incompatible changes between a snapshot and a current document."""
    current = semantic_snapshot(current_document)
    old_components = _object(
        baseline.get("components", {}), "baseline components"
    )
    new_components = _object(
        current.get("components", {}), "current components"
    )
    old_paths = _object(baseline.get("paths"), "baseline paths")
    new_paths = _object(current.get("paths"), "current paths")
    changes: list[SemanticChange] = []
    for name in sorted(old_components.keys() - new_components.keys()):
        changes.append(
            SemanticChange(f"component {name}", "response schema removed")
        )
    for name in sorted(old_components.keys() & new_components.keys()):
        changes.extend(
            _schema_changes(
                _object(old_components[name], f"component {name}"),
                _object(new_components[name], f"component {name}"),
                f"component {name}",
            )
        )
    for path in sorted(old_paths.keys() - new_paths.keys()):
        changes.append(SemanticChange(path, "path removed"))
    for path in sorted(old_paths.keys() & new_paths.keys()):
        old_ops = _object(old_paths[path], path)
        new_ops = _object(new_paths[path], path)
        for method in sorted(old_ops.keys() - new_ops.keys()):
            changes.append(
                SemanticChange(f"{method.upper()} {path}", "operation removed")
            )
        for method in sorted(old_ops.keys() & new_ops.keys()):
            old = _object(old_ops[method], "baseline operation")
            new = _object(new_ops[method], "current operation")
            location = f"{method.upper()} {path}"
            if old.get("operationId") != new.get("operationId"):
                changes.append(
                    SemanticChange(location, "operation identity changed")
                )
            old_parameters = _parameter_map(old)
            new_parameters = _parameter_map(new)
            for identity in sorted(
                old_parameters.keys() - new_parameters.keys()
            ):
                changes.append(
                    SemanticChange(location, f"parameter removed: {identity}")
                )
            for identity in sorted(
                new_parameters.keys() - old_parameters.keys()
            ):
                if new_parameters[identity].get("required"):
                    changes.append(
                        SemanticChange(
                            location, f"required parameter added: {identity}"
                        )
                    )
            for identity in sorted(
                old_parameters.keys() & new_parameters.keys()
            ):
                before, after = (
                    old_parameters[identity],
                    new_parameters[identity],
                )
                if not before.get("required") and after.get("required"):
                    changes.append(
                        SemanticChange(
                            location, f"parameter became required: {identity}"
                        )
                    )
                changes.extend(
                    _schema_changes(
                        before["schema"],
                        after["schema"],
                        f"{location} parameter {identity}",
                    )
                )
            old_responses = _object(old.get("responses"), "baseline responses")
            new_responses = _object(new.get("responses"), "current responses")
            for status in sorted(old_responses.keys() - new_responses.keys()):
                changes.append(
                    SemanticChange(location, f"response removed: {status}")
                )
            for status in sorted(old_responses.keys() & new_responses.keys()):
                old_content = _object(
                    old_responses[status], "baseline response"
                )
                new_content = _object(new_responses[status], "current response")
                for media in sorted(old_content.keys() - new_content.keys()):
                    changes.append(
                        SemanticChange(
                            location,
                            f"response media removed: {status} {media}",
                        )
                    )
                for media in sorted(old_content.keys() & new_content.keys()):
                    changes.extend(
                        _schema_changes(
                            old_content[media],
                            new_content[media],
                            f"{location} response {status} {media}",
                        )
                    )
    return tuple(changes)


def assert_semantically_compatible(
    baseline: Mapping[str, Any], current: Mapping[str, Any]
) -> None:
    """Raise with a deterministic report when compatibility is broken."""
    changes = semantic_diff(baseline, current)
    if changes:
        report = "; ".join(
            f"{change.location}: {change.reason}" for change in changes
        )
        raise OpenAPIContractError(report)


__all__ = [
    "OpenAPIContractError",
    "SemanticChange",
    "assert_semantically_compatible",
    "semantic_diff",
    "semantic_snapshot",
]
