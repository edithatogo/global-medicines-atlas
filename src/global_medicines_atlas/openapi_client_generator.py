"""Generate a small typed, read-only Python client from an OpenAPI snapshot."""

from __future__ import annotations

import json
import keyword
import re
from collections.abc import Mapping
from typing import Any, cast

_LINE_LENGTH = 80
_METHOD_INDENT = 8


class OpenAPIClientGenerationError(ValueError):
    """The semantic snapshot cannot be represented by the minimal client."""


def _identifier(value: str) -> str:
    identifier = re.sub(r"\W+", "_", value).strip("_")
    if (
        not identifier
        or identifier[0].isdigit()
        or keyword.iskeyword(identifier)
    ):
        identifier = f"operation_{identifier}"
    return identifier


def _schema_object(value: object, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OpenAPIClientGenerationError(f"{location} must be an object")
    return cast("dict[str, Any]", value)


def _without_null(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    alternatives = schema.get("anyOf")
    if not isinstance(alternatives, list):
        return schema
    concrete = [
        _schema_object(item, "anyOf item")
        for item in cast("list[object]", alternatives)
        if not _is_null_schema(item)
    ]
    if len(concrete) != 1:
        raise OpenAPIClientGenerationError(
            "query parameter anyOf must contain one concrete schema"
        )
    return concrete[0]


def _is_null_schema(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    schema = cast("dict[object, object]", value)
    return schema.get("type") == "null"


def _resolved_schema(
    schema: Mapping[str, Any],
    components: Mapping[str, Any],
) -> Mapping[str, Any]:
    concrete = _without_null(schema)
    reference = concrete.get("$ref")
    if reference is None:
        return concrete
    prefix = "#/components/schemas/"
    if not isinstance(reference, str) or not reference.startswith(prefix):
        raise OpenAPIClientGenerationError(
            f"unsupported query schema reference: {reference!r}"
        )
    name = reference.removeprefix(prefix)
    if name not in components:
        raise OpenAPIClientGenerationError(
            f"query schema reference is missing: {reference}"
        )
    return _resolved_schema(
        _schema_object(components[name], f"component {name}"),
        components,
    )


def _literal_type(values: list[object]) -> str:
    if not values or not all(
        isinstance(value, str | int | float | bool) for value in values
    ):
        raise OpenAPIClientGenerationError(
            "query enum values must be non-empty JSON scalars"
        )
    rendered = (
        json.dumps(value) if isinstance(value, str) else repr(value)
        for value in values
    )
    return "Literal[" + ", ".join(rendered) + "]"


def _query_type(
    raw_schema: object,
    components: Mapping[str, Any],
) -> str:
    schema = _resolved_schema(
        _schema_object(raw_schema, "query schema"),
        components,
    )
    raw_enum = schema.get("enum")
    if isinstance(raw_enum, list):
        return _literal_type(cast("list[object]", raw_enum))
    schema_type = schema.get("type")
    if not isinstance(schema_type, str):
        raise OpenAPIClientGenerationError(
            f"unsupported query schema type: {schema_type!r}"
        )
    primitive = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
    }.get(schema_type)
    if primitive is not None:
        return primitive
    if schema_type == "array":
        item_type = _query_type(schema.get("items", {}), components)
        return f"Sequence[{item_type}]"
    raise OpenAPIClientGenerationError(
        f"unsupported query schema type: {schema_type!r}"
    )


def _argument_source(
    item: Mapping[str, Any],
    components: Mapping[str, Any],
) -> str:
    name = _identifier(str(item["name"]))
    base = f"{name}: {_query_type(item['schema'], components)}"
    if item["required"]:
        return base
    optional = f"{base} | None = None"
    if len(optional) + _METHOD_INDENT <= _LINE_LENGTH:
        return optional
    return f"{base}\n        | None = None"


def _method_source(  # ruff: ignore[too-many-locals]
    *,
    path: str,
    method: str,
    operation: Mapping[str, Any],
    components: Mapping[str, Any],
) -> str:
    operation_id = _identifier(str(operation["operationId"]))
    parameters = cast("list[dict[str, Any]]", operation["parameters"])
    path_parameters = [item for item in parameters if item["in"] == "path"]
    query_parameters = [item for item in parameters if item["in"] == "query"]
    arguments: list[str] = []
    for item in path_parameters:
        if not item["required"]:
            raise OpenAPIClientGenerationError(
                f"path parameter {item['name']} must be required"
            )
        arguments.append(_argument_source(item, components))
    arguments.extend(
        _argument_source(item, components) for item in query_parameters
    )
    signature = (
        "self,\n        *,\n        " + ",\n        ".join(arguments)
        if arguments
        else "self"
    )
    rendered_path = path
    path_lines: list[str] = []
    encoded_placeholders: list[tuple[str, str]] = []
    for item in path_parameters:
        name = str(item["name"])
        identifier = _identifier(name)
        placeholder = f"{{{name}}}"
        if placeholder not in rendered_path:
            raise OpenAPIClientGenerationError(
                f"path parameter {name} has no placeholder in {path}"
            )
        encoded = f"encoded_{identifier}"
        path_lines.append(
            f'        {encoded} = quote(str({identifier}), safe="")'
        )
        sentinel = f"__GMA_ENCODED_PATH_{identifier.upper()}__"
        rendered_path = rendered_path.replace(placeholder, sentinel)
        encoded_placeholders.append((sentinel, f"{{{encoded}}}"))
    if "{" in rendered_path or "}" in rendered_path:
        raise OpenAPIClientGenerationError(
            f"unbound path placeholder in {rendered_path}"
        )
    for sentinel, encoded_placeholder in encoded_placeholders:
        rendered_path = rendered_path.replace(sentinel, encoded_placeholder)
    query_entries = "\n".join(
        f"            ({json.dumps(str(item['name']))}, "
        f"{_identifier(str(item['name']))}),"
        for item in query_parameters
    )
    path_literal = json.dumps(rendered_path)
    path_expression = f"f{path_literal}" if path_parameters else path_literal
    path_lines.append(f"        path = {path_expression}")
    if len(query_parameters) == 1:
        item = query_parameters[0]
        query_expression = (
            f"(({json.dumps(str(item['name']))}, "
            f"{_identifier(str(item['name']))}),)"
        )
    elif query_entries:
        query_expression = f"(\n{query_entries}\n        )"
    else:
        query_expression = "()"
    path_lines.extend((
        f"        query = _query({query_expression})",
        (
            "        return self._transport.request("
            f"{json.dumps(method.upper())}, path, query)"
        ),
    ))
    method_body = "\n".join(path_lines)
    return (
        f"    def {operation_id}(\n"
        f"        {signature},\n"
        "    ) -> JsonValue:\n"
        f"{method_body}\n"
    )


def generate_client(snapshot: Mapping[str, Any]) -> str:
    """Render deterministic source for snapshot read operations."""
    paths = cast("dict[str, dict[str, dict[str, Any]]]", snapshot["paths"])
    components = cast("dict[str, Any]", snapshot.get("components", {}))
    methods = [
        _method_source(
            path=path,
            method=method,
            operation=operation,
            components=components,
        )
        for path, operations in sorted(paths.items())
        for method, operation in sorted(operations.items())
    ]
    body = "\n".join(methods)
    return f'''"""Generated read-only client. Regenerate; do not edit."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, cast
from urllib.parse import quote

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type QueryScalar = str | int | float | bool
type QueryValue = QueryScalar | Sequence[QueryScalar] | None
type QueryPairs = tuple[tuple[str, str], ...]
_HTTP_SUCCESS_MIN = 200
_HTTP_SUCCESS_LIMIT = 300


class ReadOnlyTransport(Protocol):
    """Transport boundary used by generated client methods."""

    def request(
        self, method: str, path: str, query: Sequence[tuple[str, str]]
    ) -> JsonValue: ...


class ClientResponse(Protocol):
    """Minimal response shape shared by HTTPX and FastAPI TestClient."""

    status_code: int

    def json(self) -> object: ...


class RequestClient(Protocol):
    """Minimal synchronous HTTP client accepted by ClientTransport."""

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Sequence[tuple[str, str]],
    ) -> ClientResponse: ...


class ClientTransportError(RuntimeError):
    """A generated client request returned a non-success response."""


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        values = cast("list[object]", value)
        return [_json_value(item) for item in values]
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        result: dict[str, JsonValue] = {{}}
        for key, item in mapping.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            result[key] = _json_value(item)
        return result
    raise TypeError(f"unsupported JSON response value: {{type(value).__name__}}")


def _query_scalar(value: QueryScalar) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _query(values: Sequence[tuple[str, QueryValue]]) -> QueryPairs:
    pairs: list[tuple[str, str]] = []
    for key, value in values:
        if value is None:
            continue
        if isinstance(value, str | int | float | bool):
            pairs.append((key, _query_scalar(value)))
            continue
        pairs.extend((key, _query_scalar(item)) for item in value)
    return tuple(pairs)


class ClientTransport:
    """HTTPX/FastAPI-TestClient-compatible synchronous transport."""

    def __init__(self, client: RequestClient) -> None:
        self._client = client

    def request(
        self, method: str, path: str, query: Sequence[tuple[str, str]]
    ) -> JsonValue:
        response = self._client.request(method, path, params=query)
        if not _HTTP_SUCCESS_MIN <= response.status_code < _HTTP_SUCCESS_LIMIT:
            raise ClientTransportError(
                f"{{method}} {{path}} returned HTTP {{response.status_code}}"
            )
        return _json_value(response.json())


class GlobalMedicinesAtlasClient:
    """Typed methods generated from committed read-only operations."""

    def __init__(self, transport: ReadOnlyTransport) -> None:
        self._transport = transport

{body}

__all__ = [
    "ClientTransport",
    "ClientTransportError",
    "GlobalMedicinesAtlasClient",
    "JsonValue",
    "ReadOnlyTransport",
]
'''


__all__ = [
    "OpenAPIClientGenerationError",
    "generate_client",
]
