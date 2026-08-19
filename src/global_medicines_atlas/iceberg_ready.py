"""Iceberg-ready table identities over source-faithful Parquet.

Parquet files remain Parquet. This module records stable identifiers,
partition specs, and schemas so those files can later be registered in an
Iceberg REST catalogue. Python 3.14 core does not import or require Iceberg.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

import httpx
from pydantic import Field

from .models import FrozenModel

_SLUG = re.compile(r"[^a-z0-9]+")


class IcebergReadyTableSpec(FrozenModel):
    """Metadata needed to register a Parquet dataset as an Iceberg table."""

    identifier: str = Field(min_length=3)
    location: str = Field(min_length=1)
    partition_fields: tuple[str, ...]
    schema_fields: tuple[tuple[str, str], ...]
    format_version: int = 2
    namespace: str = "bronze"

    @property
    def table_name(self) -> str:
        """Unqualified table name after the namespace."""

        _, _, name = self.identifier.partition(".")
        return name or self.identifier


def table_identifier_for(*, jurisdiction: str, source_id: str) -> str:
    """Stable Iceberg table identity for one bronze source partition."""

    slug = _SLUG.sub("_", f"{jurisdiction}_{source_id}".lower()).strip("_")
    return f"bronze.{slug}"


def iceberg_rest_create_body(spec: IcebergReadyTableSpec) -> dict[str, object]:
    """Iceberg REST create-table document; does not load pyiceberg."""

    fields: list[dict[str, object]] = []
    for index, (name, field_type) in enumerate(spec.schema_fields, start=1):
        fields.append({
            "id": index,
            "name": name,
            "required": name
            in {"source_id", "payload_sha256", "acquisition_id"},
            "type": field_type,
        })
    partitions = [
        {
            "source-id": index + 1,
            "field-id": 1000 + index,
            "name": name,
            "transform": "identity",
        }
        for index, name in enumerate(spec.partition_fields)
    ]
    return {
        "name": spec.table_name,
        "schema": {"type": "struct", "fields": fields, "schema-id": 0},
        "partition-spec": {"spec-id": 0, "fields": partitions},
        "write-order": None,
        "properties": {
            "format-version": str(spec.format_version),
            "location": spec.location,
            "gma.evidentiary-truth": "payload-and-receipt",
        },
    }


def register_iceberg_table(
    spec: IcebergReadyTableSpec,
    *,
    rest_uri: str,
    transport: httpx.BaseTransport | None = None,
    headers: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """POST Iceberg-ready metadata to an optional REST catalogue."""

    namespace = spec.namespace
    url = f"{rest_uri.rstrip('/')}/v1/namespaces/{namespace}/tables"
    with httpx.Client(transport=transport, timeout=10.0) as client:
        response = client.post(
            url,
            json=iceberg_rest_create_body(spec),
            headers=dict(headers or {}),
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("Iceberg REST catalogue returned a non-object")
    return cast("dict[str, object]", payload)


def optional_pyiceberg_available() -> bool:
    """Core must keep Iceberg optional; never import it at module load."""

    try:
        __import__("pyiceberg")
    except ImportError:
        return False
    return True
