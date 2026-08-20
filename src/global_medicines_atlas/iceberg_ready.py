"""Iceberg-ready table identities over source-faithful Parquet.

Parquet files remain Parquet and remain valid without Iceberg. This module
records stable identifiers, namespaces, schemas, partition specs, evolution
rules, and snapshot-to-acquisition bindings so those files can later be
registered in an Iceberg REST catalogue. Iceberg metadata is rebuildable
catalogue state, not evidentiary truth. Python 3.14 core does not import
Iceberg.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Mapping
from typing import Self, cast

import httpx
from pydantic import Field, model_validator

from .models import FrozenModel
from .receipts import SHA256_PATTERN

_SLUG = re.compile(r"[^a-z0-9]+")
_PARTITION_TRANSFORM = re.compile(
    r"^(?:identity|year|month|day|hour|bucket\[[1-9][0-9]*\]|"
    r"truncate\[[1-9][0-9]*\])$"
)
_CONSTANT_PARTITION_FIELDS = frozenset({"jurisdiction", "source_id"})
_MUTABLE_GOVERNANCE_PARTITION_FIELDS = frozenset({
    "admission_state",
    "review_state",
    "review_status",
    "rights_state",
    "rights_status",
})
_TEMPORAL_PARTITION_TYPES = frozenset({"date", "timestamp", "timestamptz"})
EVIDENTIARY_COLUMNS = frozenset({
    "source_id",
    "jurisdiction",
    "rights_state",
    "payload_sha256",
    "content_id",
    "receipt_digest",
    "acquisition_id",
})
ICEBERG_CAPABILITIES = {
    "row_lineage": (
        "Iceberg row/file lineage is optional telemetry; Atlas acquisition "
        "receipts remain authoritative"
    ),
    "branching": (
        "Iceberg branches are optional aliases, not acquisition identity"
    ),
    "tagging": (
        "Iceberg tags may label a snapshot; they do not replace acquisition_id"
    ),
    "metadata": (
        "Iceberg metadata is rebuildable catalogue state, not bronze truth"
    ),
}


class IcebergPartitionField(FrozenModel):
    """One Iceberg partition transform over an immutable source field."""

    source_field: str = Field(min_length=1)
    name: str = Field(min_length=1)
    transform: str = Field(pattern=_PARTITION_TRANSFORM.pattern)


class IcebergPartitionPolicy(FrozenModel):
    """Scale and recurrence evidence used to select physical partitions."""

    recurring: bool = False
    large_table_min_rows: int = Field(default=1_000_000, ge=1)
    source_release_field: str | None = Field(default=None, min_length=1)
    acquisition_time_field: str = Field(
        default="gma_acquired_at",
        min_length=1,
    )
    record_id_field: str | None = Field(default=None, min_length=1)
    record_id_buckets: int | None = Field(default=None, ge=2, le=1024)

    @model_validator(mode="after")
    def validate_bucket_configuration(self) -> Self:
        if (self.record_id_field is None) != (self.record_id_buckets is None):
            raise ValueError(
                "record_id_field and record_id_buckets must be configured together"
            )
        return self


def plan_iceberg_partitions(
    schema_fields: tuple[tuple[str, str], ...],
    *,
    row_count: int,
    policy: IcebergPartitionPolicy | None = None,
) -> tuple[IcebergPartitionField, ...]:
    """Plan partitions only for large recurring source products."""

    if row_count < 0:
        raise ValueError("row_count must not be negative")
    if policy is None or not policy.recurring:
        return ()
    if row_count < policy.large_table_min_rows:
        return ()
    field_types = dict(schema_fields)
    temporal_field = (
        policy.source_release_field or policy.acquisition_time_field
    )
    if temporal_field not in field_types:
        raise ValueError(
            f"partition time field {temporal_field} is not in schema"
        )
    if field_types[temporal_field] not in _TEMPORAL_PARTITION_TYPES:
        raise ValueError("monthly partition field must be temporal")
    planned = [
        IcebergPartitionField(
            source_field=temporal_field,
            name=f"{temporal_field}_month",
            transform="month",
        )
    ]
    if policy.record_id_field is not None:
        if policy.record_id_field not in field_types:
            raise ValueError(
                f"record identifier field {policy.record_id_field} is not in schema"
            )
        buckets = cast("int", policy.record_id_buckets)
        planned.append(
            IcebergPartitionField(
                source_field=policy.record_id_field,
                name=f"{policy.record_id_field}_bucket_{buckets}",
                transform=f"bucket[{buckets}]",
            )
        )
    return tuple(planned)


class IcebergReadyTableSpec(FrozenModel):
    """Metadata needed to register a Parquet dataset as an Iceberg table."""

    identifier: str = Field(min_length=3)
    location: str = Field(min_length=1)
    partition_fields: tuple[IcebergPartitionField, ...] = ()
    schema_fields: tuple[tuple[str, str], ...]
    format_version: int = 2
    namespace: str = "bronze"
    schema_id: int = 0
    last_column_id: int | None = None
    acquisition_id: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    content_id: str | None = Field(default=None, pattern=SHA256_PATTERN)
    parquet_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)

    @property
    def table_name(self) -> str:
        """Unqualified table name after the namespace."""

        _, _, name = self.identifier.partition(".")
        return name or self.identifier

    @property
    def assigned_last_column_id(self) -> int:
        """Highest assigned field id, at least the declared schema length."""

        declared = len(self.schema_fields)
        if self.last_column_id is None:
            return declared
        return self.last_column_id

    @model_validator(mode="after")
    def validate_column_ids(self) -> Self:
        declared = len(self.schema_fields)
        if declared < 1:
            raise ValueError("schema_fields must not be empty")
        last = self.assigned_last_column_id
        if last < declared:
            raise ValueError("last_column_id is below the schema width")
        names = {name for name, _typ in self.schema_fields}
        partition_names: set[str] = set()
        for part in self.partition_fields:
            source_field = part.source_field
            if source_field not in names:
                raise ValueError(
                    f"partition field {source_field} is not in schema"
                )
            lowered = source_field.lower()
            governance_status = lowered.endswith(("_state", "_status"))
            mutable_governance = governance_status and any(
                token in lowered for token in ("admission", "review", "rights")
            )
            if (
                source_field in _CONSTANT_PARTITION_FIELDS
                or (source_field in _MUTABLE_GOVERNANCE_PARTITION_FIELDS)
                or mutable_governance
            ):
                raise ValueError(
                    f"{source_field} cannot be a physical partition key"
                )
            if part.name in partition_names:
                raise ValueError(f"duplicate partition name {part.name}")
            partition_names.add(part.name)
        return self

    def field_ids(self) -> dict[str, int]:
        """Stable Iceberg field ids; 1-based in declaration order."""

        return {
            name: index
            for index, (name, _typ) in enumerate(self.schema_fields, start=1)
        }


class SnapshotAcquisitionBinding(FrozenModel):
    """Maps one Iceberg snapshot alias onto an Atlas acquisition."""

    snapshot_id: int = Field(ge=0)
    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    content_id: str = Field(pattern=SHA256_PATTERN)
    parquet_digest: str = Field(pattern=SHA256_PATTERN)
    iceberg_branch: str = "main"
    iceberg_tag: str | None = None


def table_identifier_for(*, jurisdiction: str, source_id: str) -> str:
    """Stable Iceberg table identity for one bronze source partition."""

    slug = _SLUG.sub("_", f"{jurisdiction}_{source_id}".lower()).strip("_")
    return f"bronze.{slug}"


def iceberg_capability_notes() -> dict[str, str]:
    """Current Iceberg features vs Atlas acquisition provenance."""

    return dict(ICEBERG_CAPABILITIES)


def catalogue_properties(
    spec: IcebergReadyTableSpec,
    binding: SnapshotAcquisitionBinding | None = None,
) -> dict[str, str]:
    """Iceberg table properties; never stores payload bytes."""

    properties = {
        "format-version": str(spec.format_version),
        "location": spec.location,
        "gma.evidentiary-truth": "payload-and-receipt",
        "gma.row-lineage-authority": "atlas-receipt",
        "gma.iceberg-branch-is-alias": "true",
        "gma.namespace": spec.namespace,
    }
    acquisition_id = spec.acquisition_id
    if binding is not None:
        acquisition_id = binding.acquisition_id
        properties["gma.snapshot-id"] = str(binding.snapshot_id)
        properties["gma.content-id"] = binding.content_id
        properties["gma.parquet-digest"] = binding.parquet_digest
        properties["gma.iceberg-branch"] = binding.iceberg_branch
        if binding.iceberg_tag is not None:
            properties["gma.iceberg-tag"] = binding.iceberg_tag
    elif spec.content_id is not None and spec.parquet_digest is not None:
        properties["gma.content-id"] = spec.content_id
        properties["gma.parquet-digest"] = spec.parquet_digest
    if acquisition_id is not None:
        properties["gma.acquisition-id"] = acquisition_id
    return properties


def evolve_table_spec(
    spec: IcebergReadyTableSpec,
    added: tuple[tuple[str, str], ...],
) -> IcebergReadyTableSpec:
    """Append-only schema evolution; evidentiary columns stay put."""

    existing = dict(spec.schema_fields)
    for name, _field_type in added:
        if name in existing:
            raise ValueError(f"cannot reuse field name {name}")
    last = spec.assigned_last_column_id + len(added)
    return spec.model_copy(
        update={
            "schema_fields": spec.schema_fields + added,
            "schema_id": spec.schema_id + 1,
            "last_column_id": last,
        }
    )


def assert_compatible_evolution(
    before: IcebergReadyTableSpec,
    after: IcebergReadyTableSpec,
) -> None:
    """Reject dropped columns, type changes, or reused field ids."""

    before_ids = before.field_ids()
    after_ids = after.field_ids()
    before_types = dict(before.schema_fields)
    after_types = dict(after.schema_fields)
    for name in EVIDENTIARY_COLUMNS:
        if name in before_types and name not in after_types:
            raise ValueError(f"cannot drop evidentiary field {name}")
    for name, field_id in before_ids.items():
        if name not in after_ids:
            raise ValueError(f"cannot drop field {name}")
        if after_ids[name] != field_id:
            raise ValueError(f"field id for {name} is immutable")
        if after_types[name] != before_types[name]:
            raise ValueError(f"cannot change type of {name}")


def iceberg_rest_create_body(
    spec: IcebergReadyTableSpec,
    binding: SnapshotAcquisitionBinding | None = None,
) -> dict[str, object]:
    """Iceberg REST create-table document; does not load pyiceberg."""

    fields: list[dict[str, object]] = []
    for index, (name, field_type) in enumerate(spec.schema_fields, start=1):
        fields.append({
            "id": index,
            "name": name,
            "required": name in EVIDENTIARY_COLUMNS,
            "type": field_type,
        })
    field_ids = spec.field_ids()
    partitions = [
        {
            "source-id": field_ids[partition.source_field],
            "field-id": 1000 + index,
            "name": partition.name,
            "transform": partition.transform,
        }
        for index, partition in enumerate(spec.partition_fields)
    ]
    return {
        "name": spec.table_name,
        "namespace": spec.namespace,
        "schema": {
            "type": "struct",
            "fields": fields,
            "schema-id": spec.schema_id,
            "last-column-id": spec.assigned_last_column_id,
        },
        "partition-spec": {"spec-id": 0, "fields": partitions},
        "write-order": None,
        "properties": catalogue_properties(spec, binding),
    }


def _as_object_map(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    typed = cast("dict[object, object]", value)
    mapped: dict[str, object] = {}
    for key, item in typed.items():
        mapped[str(key)] = item
    return mapped


def _as_object_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an array")
    return cast("list[object]", value)


def _schema_fields_from_body(
    schema: Mapping[str, object],
) -> list[tuple[str, str]]:
    raw_fields = _as_object_list(schema.get("fields"), "create-table fields")
    schema_fields: list[tuple[str, str]] = []
    for raw_item in raw_fields:
        item = _as_object_map(raw_item, "schema field")
        name = item.get("name")
        field_type = item.get("type")
        if not isinstance(name, str) or not isinstance(field_type, str):
            raise TypeError("schema field name and type must be strings")
        schema_fields.append((name, field_type))
    return schema_fields


def _partition_fields_from_body(
    body: Mapping[str, object],
    schema_fields: list[tuple[str, str]],
) -> tuple[IcebergPartitionField, ...]:
    partition = body.get("partition-spec")
    if not isinstance(partition, dict):
        return ()
    typed = _as_object_map(cast("object", partition), "partition-spec")
    raw_parts = typed.get("fields", [])
    if not isinstance(raw_parts, list):
        return ()
    partitions: list[IcebergPartitionField] = []
    for raw_part in cast("list[object]", raw_parts):
        if not isinstance(raw_part, dict):
            continue
        part = _as_object_map(cast("object", raw_part), "partition field")
        name = part.get("name")
        transform = part.get("transform")
        source_id = part.get("source-id")
        if (
            not isinstance(name, str)
            or not isinstance(transform, str)
            or not isinstance(source_id, int)
            or source_id < 1
            or source_id > len(schema_fields)
        ):
            raise TypeError(
                "partition fields must bind a source id and transform"
            )
        partitions.append(
            IcebergPartitionField(
                source_field=schema_fields[source_id - 1][0],
                name=name,
                transform=transform,
            )
        )
    return tuple(partitions)


def spec_from_create_body(body: Mapping[str, object]) -> IcebergReadyTableSpec:
    """Rebuild a table spec from an Iceberg REST create-table document."""

    schema = _as_object_map(body.get("schema"), "create-table schema")
    schema_fields = _schema_fields_from_body(schema)
    properties = _as_object_map(
        body.get("properties"),
        "create-table properties",
    )
    location = properties.get("location")
    raw_namespace = body.get(
        "namespace", properties.get("gma.namespace", "bronze")
    )
    if not isinstance(location, str):
        raise TypeError("location must be a string")
    if not isinstance(raw_namespace, str):
        raise TypeError("namespace must be a string")
    name = body.get("name")
    if not isinstance(name, str):
        raise TypeError("table name must be a string")
    last_column = schema.get("last-column-id", len(schema_fields))
    schema_id = schema.get("schema-id", 0)
    if not isinstance(last_column, int) or not isinstance(schema_id, int):
        raise TypeError("schema ids must be integers")
    acquisition = properties.get("gma.acquisition-id")
    content = properties.get("gma.content-id")
    parquet = properties.get("gma.parquet-digest")
    format_version = properties.get("format-version", "2")
    return IcebergReadyTableSpec(
        identifier=f"{raw_namespace}.{name}",
        location=location,
        partition_fields=_partition_fields_from_body(body, schema_fields),
        schema_fields=tuple(schema_fields),
        format_version=int(str(format_version)),
        namespace=raw_namespace,
        schema_id=schema_id,
        last_column_id=last_column,
        acquisition_id=acquisition if isinstance(acquisition, str) else None,
        content_id=content if isinstance(content, str) else None,
        parquet_digest=parquet if isinstance(parquet, str) else None,
    )


def register_iceberg_table(
    spec: IcebergReadyTableSpec,
    *,
    rest_uri: str,
    transport: httpx.BaseTransport | None = None,
    headers: Mapping[str, str] | None = None,
    binding: SnapshotAcquisitionBinding | None = None,
) -> dict[str, object]:
    """POST Iceberg-ready metadata to an optional REST catalogue."""

    namespace = spec.namespace
    url = f"{rest_uri.rstrip('/')}/v1/namespaces/{namespace}/tables"
    with httpx.Client(transport=transport, timeout=10.0) as client:
        response = client.post(
            url,
            json=iceberg_rest_create_body(spec, binding),
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


def load_optional_rest_catalog(rest_uri: str) -> object:
    """Load pyiceberg RestCatalog only when the iceberg extra is installed."""

    try:
        module = importlib.import_module("pyiceberg.catalog.rest")
    except ImportError as exc:
        raise RuntimeError("optional extra 'iceberg' is not installed") from exc
    catalog_cls = module.RestCatalog
    return catalog_cls(name="gma-bronze", uri=rest_uri)
