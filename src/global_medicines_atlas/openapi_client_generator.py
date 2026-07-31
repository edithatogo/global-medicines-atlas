"""Generate a small typed, read-only Python client from an OpenAPI snapshot."""

from __future__ import annotations

import json
import keyword
import re
from collections.abc import Mapping
from typing import Any, cast


def _identifier(value: str) -> str:
    identifier = re.sub(r"\W+", "_", value).strip("_")
    if (
        not identifier
        or identifier[0].isdigit()
        or keyword.iskeyword(identifier)
    ):
        identifier = f"operation_{identifier}"
    return identifier


def generate_client(snapshot: Mapping[str, Any]) -> str:
    """Render deterministic source for snapshot read operations."""
    paths = cast("dict[str, dict[str, dict[str, Any]]]", snapshot["paths"])
    methods: list[str] = []
    for path, operations in sorted(paths.items()):
        for method, operation in sorted(operations.items()):
            operation_id = _identifier(str(operation["operationId"]))
            parameters = cast("list[dict[str, Any]]", operation["parameters"])
            path_parameters = [
                item for item in parameters if item["in"] == "path"
            ]
            query_parameters = [
                item for item in parameters if item["in"] == "query"
            ]
            arguments = [
                f"{_identifier(str(item['name']))}: str"
                for item in path_parameters
            ]
            arguments.extend(
                f"{_identifier(str(item['name']))}: str | int"
                + ("" if item["required"] else " | None = None")
                for item in query_parameters
            )
            signature = (
                "self,\n        *,\n        " + ",\n        ".join(arguments)
                if arguments
                else "self"
            )
            rendered_path = path
            for item in path_parameters:
                name = str(item["name"])
                rendered_path = rendered_path.replace(
                    f"{{{name}}}", f"{{{_identifier(name)}}}"
                )
            query_entries = "\n".join(
                f"            {json.dumps(str(item['name']))}: "
                f"{_identifier(str(item['name']))},"
                for item in query_parameters
            )
            path_literal = json.dumps(rendered_path)
            path_expression = (
                f"f{path_literal}" if path_parameters else path_literal
            )
            query_expression = (
                f"{{\n{query_entries}\n        }}" if query_entries else "{}"
            )
            methods.append(
                f"    def {operation_id}(\n"
                f"        {signature},\n"
                f"    ) -> JsonValue:\n"
                f"        path = {path_expression}\n"
                f"        query = _query({query_expression})\n"
                f"        return self._transport.request("
                f"{json.dumps(method.upper())}, path, query)\n"
            )
    body = "\n".join(methods)
    return f'''"""Generated read-only client. Regenerate; do not edit."""\n\nfrom __future__ import annotations\n\nfrom collections.abc import Mapping\nfrom typing import Protocol\n\ntype JsonScalar = str | int | float | bool | None\ntype JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]\n\n\nclass ReadOnlyTransport(Protocol):\n    """Transport boundary used by generated client methods."""\n\n    def request(\n        self, method: str, path: str, query: Mapping[str, str]\n    ) -> JsonValue: ...\n\n\ndef _query(values: Mapping[str, str | int | None]) -> dict[str, str]:\n    return {{\n        key: str(value) for key, value in values.items() if value is not None\n    }}\n\n\nclass GlobalMedicinesAtlasClient:\n    """Typed methods generated from committed read-only operations."""\n\n    def __init__(self, transport: ReadOnlyTransport) -> None:\n        self._transport = transport\n\n{body}\n\n__all__ = ["GlobalMedicinesAtlasClient", "JsonValue", "ReadOnlyTransport"]\n'''


__all__ = ["generate_client"]
