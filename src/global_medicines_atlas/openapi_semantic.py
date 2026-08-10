"""Deterministic, dependency-light OpenAPI compatibility contracts."""

# ruff: file-ignore[too-many-branches, too-many-locals, manual-list-comprehension]

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, cast

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
_SECURITY_SCHEME_KEYS = frozenset({
    "type",
    "description",
    "name",
    "in",
    "scheme",
    "bearerFormat",
    "openIdConnectUrl",
    "flows",
})
type SchemaVariance = Literal["request", "response"]


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


def _security_requirements(
    value: object,
    location: str,
) -> list[dict[str, list[str]]]:
    if not isinstance(value, list):
        raise OpenAPIContractError(f"{location} must be an array")
    requirements: list[dict[str, list[str]]] = []
    for index, raw_requirement in enumerate(cast("list[object]", value)):
        requirement = _object(
            raw_requirement,
            f"{location}[{index}]",
        )
        normalized: dict[str, list[str]] = {}
        for scheme, raw_scopes in sorted(requirement.items()):
            if not scheme:
                raise OpenAPIContractError(
                    f"{location}[{index}] has an invalid scheme name"
                )
            if not isinstance(raw_scopes, list):
                raise OpenAPIContractError(
                    f"{location}[{index}].{scheme} scopes must be strings"
                )
            scopes = cast("list[object]", raw_scopes)
            if not all(isinstance(scope, str) for scope in scopes):
                raise OpenAPIContractError(
                    f"{location}[{index}].{scheme} scopes must be strings"
                )
            normalized[scheme] = sorted(cast("list[str]", scopes))
        requirements.append(normalized)
    requirements.sort(
        key=lambda requirement: tuple(
            (scheme, tuple(scopes)) for scheme, scopes in requirement.items()
        )
    )
    return requirements


def _security_scheme(value: object, location: str) -> dict[str, object]:
    source = _object(value, location)
    return {
        key: _normalize_schema_item(source[key])
        for key in sorted(_SECURITY_SCHEME_KEYS & source.keys())
    }


def semantic_snapshot(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project a full OpenAPI document into a stable public contract."""
    paths = _object(document.get("paths"), "paths")
    root_security = _security_requirements(
        document.get("security", []),
        "security",
    )
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
                "security": _security_requirements(
                    operation.get("security", root_security),
                    f"{method.upper()} {path} security",
                ),
            }
        if operations:
            projected[path] = operations
    components = _object(document.get("components", {}), "components")
    component_schemas = _object(
        components.get("schemas", {}), "components.schemas"
    )
    security_schemes = _object(
        components.get("securitySchemes", {}),
        "components.securitySchemes",
    )
    return {
        "contract": "global-medicines-atlas.openapi-readonly",
        "version": 1,
        "components": {
            name: _schema(schema)
            for name, schema in sorted(component_schemas.items())
        },
        "securitySchemes": {
            name: _security_scheme(
                scheme,
                f"components.securitySchemes.{name}",
            )
            for name, scheme in sorted(security_schemes.items())
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


def _enum_changes(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    location: str,
    variance: SchemaVariance,
) -> list[SemanticChange]:
    old_enum = baseline.get("enum")
    new_enum = current.get("enum")
    reason: str | None = None
    old_values = {repr(value) for value in cast("list[object]", old_enum or [])}
    new_values = {repr(value) for value in cast("list[object]", new_enum or [])}
    if variance == "request":
        if old_enum is None:
            if new_enum is not None:
                reason = "request enum narrowed"
        elif new_enum is not None and not old_values <= new_values:
            reason = "request enum values removed"
    elif old_enum is not None and (
        new_enum is None or not new_values <= old_values
    ):
        reason = "response enum values added"
    return [] if reason is None else [SemanticChange(location, reason)]


def _bounded_change(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    location: str,
    key: str,
    variance: SchemaVariance,
    *,
    lower_bound: bool,
) -> SemanticChange | None:
    old = baseline.get(key)
    new = current.get(key)
    if old is None and new is None:
        return None
    if variance == "request":
        narrowed = old is None or (
            new is not None and ((new > old) if lower_bound else (new < old))
        )
    else:
        narrowed = new is not None and (
            old is None or ((new >= old) if lower_bound else (new <= old))
        )
        narrowed = not narrowed
    if narrowed:
        direction = "narrowed" if variance == "request" else "widened"
        return SemanticChange(location, f"{key} {variance} range {direction}")
    return None


def _schema_changes(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    location: str,
    variance: SchemaVariance,
) -> list[SemanticChange]:
    changes: list[SemanticChange] = []
    for key in ("type", "format", "const", "$ref"):
        if key in baseline and baseline.get(key) != current.get(key):
            changes.append(SemanticChange(location, f"{key} changed"))
    changes.extend(_enum_changes(baseline, current, location, variance))
    for key in ("minimum", "exclusiveMinimum", "minLength", "minItems"):
        change = _bounded_change(
            baseline,
            current,
            location,
            key,
            variance,
            lower_bound=True,
        )
        if change is not None:
            changes.append(change)
    for key in ("maximum", "exclusiveMaximum", "maxLength", "maxItems"):
        change = _bounded_change(
            baseline,
            current,
            location,
            key,
            variance,
            lower_bound=False,
        )
        if change is not None:
            changes.append(change)
    old_pattern = baseline.get("pattern")
    new_pattern = current.get("pattern")
    if variance == "request":
        if new_pattern is not None and old_pattern != new_pattern:
            changes.append(SemanticChange(location, "request pattern narrowed"))
    elif old_pattern is not None and old_pattern != new_pattern:
        changes.append(SemanticChange(location, "response pattern widened"))
    old_required = set(baseline.get("required", []))
    new_required = set(current.get("required", []))
    if variance == "request" and not new_required <= old_required:
        changes.append(
            SemanticChange(location, "required request fields added")
        )
    elif variance == "response" and not old_required <= new_required:
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
                old_properties[name],
                new_properties[name],
                f"{location}.{name}",
                variance,
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
                    baseline["items"],
                    current["items"],
                    f"{location}[]",
                    variance,
                )
            )
    for key in ("anyOf", "oneOf", "allOf"):
        if key in baseline and baseline.get(key) != current.get(key):
            changes.append(SemanticChange(location, f"{key} changed"))
    return changes


def _component_changes(
    old_components: Mapping[str, Any], new_components: Mapping[str, Any]
) -> list[SemanticChange]:
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
                "response",
            )
        )
    return changes


def _security_scheme_changes(
    old_security_schemes: Mapping[str, Any],
    new_security_schemes: Mapping[str, Any],
) -> list[SemanticChange]:
    changes: list[SemanticChange] = []
    for name in sorted(
        old_security_schemes.keys() - new_security_schemes.keys()
    ):
        changes.append(
            SemanticChange(f"security scheme {name}", "scheme removed")
        )
    for name in sorted(
        old_security_schemes.keys() & new_security_schemes.keys()
    ):
        if old_security_schemes[name] != new_security_schemes[name]:
            changes.append(
                SemanticChange(f"security scheme {name}", "scheme changed")
            )
    return changes


def _parameter_changes(
    old: Mapping[str, Any], new: Mapping[str, Any], location: str
) -> list[SemanticChange]:
    changes: list[SemanticChange] = []
    old_parameters = _parameter_map(old)
    new_parameters = _parameter_map(new)
    for identity in sorted(old_parameters.keys() - new_parameters.keys()):
        changes.append(
            SemanticChange(location, f"parameter removed: {identity}")
        )
    for identity in sorted(new_parameters.keys() - old_parameters.keys()):
        if new_parameters[identity].get("required"):
            changes.append(
                SemanticChange(
                    location, f"required parameter added: {identity}"
                )
            )
    for identity in sorted(old_parameters.keys() & new_parameters.keys()):
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
                "request",
            )
        )
    return changes


def _response_changes(
    old_responses: Mapping[str, Any],
    new_responses: Mapping[str, Any],
    location: str,
) -> list[SemanticChange]:
    changes: list[SemanticChange] = []
    for status in sorted(old_responses.keys() - new_responses.keys()):
        changes.append(SemanticChange(location, f"response removed: {status}"))
    for status in sorted(old_responses.keys() & new_responses.keys()):
        old_content = _object(old_responses[status], "baseline response")
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
                    "response",
                )
            )
    return changes


def _operation_changes(
    old: Mapping[str, Any], new: Mapping[str, Any], location: str
) -> list[SemanticChange]:
    changes: list[SemanticChange] = []
    if old.get("operationId") != new.get("operationId"):
        changes.append(SemanticChange(location, "operation identity changed"))
    if old.get("security", []) != new.get("security", []):
        changes.append(
            SemanticChange(
                location,
                "security requirements changed",
            )
        )
    changes.extend(_parameter_changes(old, new, location))
    old_responses = _object(old.get("responses"), "baseline responses")
    new_responses = _object(new.get("responses"), "current responses")
    changes.extend(_response_changes(old_responses, new_responses, location))
    return changes


def _path_changes(
    old_paths: Mapping[str, Any], new_paths: Mapping[str, Any]
) -> list[SemanticChange]:
    changes: list[SemanticChange] = []
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
            changes.extend(_operation_changes(old, new, location))
    return changes


def semantic_diff(
    baseline: Mapping[str, Any], current_document: Mapping[str, Any]
) -> tuple[SemanticChange, ...]:
    """Return incompatible changes between a snapshot and a current document."""
    if (
        baseline.get("contract") != ("global-medicines-atlas.openapi-readonly")
        or baseline.get("version") != 1
    ):
        raise OpenAPIContractError("baseline contract identity is invalid")
    current = semantic_snapshot(current_document)
    old_components = _object(
        baseline.get("components", {}), "baseline components"
    )
    new_components = _object(
        current.get("components", {}), "current components"
    )
    old_security_schemes = _object(
        baseline.get("securitySchemes", {}),
        "baseline security schemes",
    )
    new_security_schemes = _object(
        current.get("securitySchemes", {}),
        "current security schemes",
    )
    old_paths = _object(baseline.get("paths"), "baseline paths")
    new_paths = _object(current.get("paths"), "current paths")

    changes: list[SemanticChange] = []
    changes.extend(_component_changes(old_components, new_components))
    changes.extend(
        _security_scheme_changes(old_security_schemes, new_security_schemes)
    )
    changes.extend(_path_changes(old_paths, new_paths))

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
