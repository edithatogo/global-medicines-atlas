"""Project OpenLineage events from native acquisition receipts.

Receipts remain the richer provenance. This module emits OpenLineage
RunEvent documents with real spec field names. Payload, Parquet, and
optional catalogue datasets stay distinct identities. Marquez is not
part of the default install.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from .iceberg_ready import IcebergReadyTableSpec
from .receipts import SourceReceipt, require_temporal
from .reuse_gate import HF_CATALOGUE_REVISION

PRODUCER = (
    "https://github.com/edithatogo/global-medicines-atlas"
    "/blob/main/src/global_medicines_atlas/openlineage_projection.py"
)
SCHEMA_URL = (
    "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"
)
STORAGE_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/1-0-0/StorageDatasetFacet.json"
)
DATASOURCE_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/1-0-0/DatasourceDatasetFacet.json"
)
VERSION_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/1-0-0/DatasetVersionDatasetFacet.json"
)
SYMLINKS_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/1-0-1/SymlinksDatasetFacet.json"
)
COLUMN_LINEAGE_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/1-2-0/ColumnLineageDatasetFacet.json"
)
LIFECYCLE_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/1-0-0/"
    "LifecycleStateChangeDatasetFacet.json"
)
JOB_NAMESPACE = "global-medicines-atlas"
EVENT_TYPES = frozenset({
    "START",
    "RUNNING",
    "COMPLETE",
    "ABORT",
    "FAIL",
    "OTHER",
})
REQUIRED_EVENT_KEYS = (
    "eventType",
    "eventTime",
    "run",
    "job",
    "producer",
    "schemaURL",
)


def _facet(schema_url: str, **fields: object) -> dict[str, object]:
    return {
        "_producer": PRODUCER,
        "_schemaURL": schema_url,
        **fields,
    }


def payload_dataset_name(receipt: SourceReceipt) -> str:
    """Stable OpenLineage name for payload bytes, keyed by content digest."""

    return f"{receipt.source.source_id}/{receipt.payload.sha256}"


def parquet_dataset_name(receipt: SourceReceipt) -> str:
    """Stable OpenLineage name for source-faithful Parquet, not Iceberg."""

    return f"{receipt.source.source_id}/{receipt.transformation.output_sha256}"


def catalogue_dataset_name(table: IcebergReadyTableSpec) -> str:
    """Rebuildable catalogue identity over Parquet, never payload identity."""

    return table.identifier


def _symlink(*, namespace: str, name: str, kind: str) -> dict[str, str]:
    return {"namespace": namespace, "name": name, "type": kind}


def _column_lineage(
    *,
    field: str,
    namespace: str,
    name: str,
    input_field: str,
) -> dict[str, object]:
    return _facet(
        COLUMN_LINEAGE_SCHEMA_URL,
        fields={
            field: {
                "inputFields": [
                    {
                        "namespace": namespace,
                        "name": name,
                        "field": input_field,
                        "transformations": [
                            {
                                "type": "DIRECT",
                                "subtype": "IDENTITY",
                                "description": "",
                                "masking": False,
                            }
                        ],
                    }
                ]
            }
        },
    )


def _dataset(
    *,
    namespace: str,
    name: str,
    storage_layer: str,
    file_format: str,
    source_uri: str,
    version: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    facets: dict[str, object] = {
        "storage": _facet(
            STORAGE_SCHEMA_URL,
            storageLayer=storage_layer,
            fileFormat=file_format,
        ),
        "dataSource": _facet(
            DATASOURCE_SCHEMA_URL,
            name=name,
            uri=source_uri,
        ),
        "version": _facet(
            VERSION_SCHEMA_URL,
            datasetVersion=version,
        ),
        "lifecycleStateChange": _facet(
            LIFECYCLE_SCHEMA_URL,
            lifecycleStateChange="CREATE",
        ),
    }
    if extra:
        facets.update(extra)
    return {"namespace": namespace, "name": name, "facets": facets}


def _identity_facets(receipt: SourceReceipt) -> dict[str, object]:
    temporal = require_temporal(receipt.temporal)
    reuse = receipt.reuse
    acquisition_id = temporal.acquisition_id
    temporal_facet = _facet(
        f"{PRODUCER}#temporal-identity",
        sourcePublishedAt=(
            temporal.source_published_at.isoformat()
            if temporal.source_published_at is not None
            else None
        ),
        sourceEffectiveAt=(
            temporal.source_effective_at.isoformat()
            if temporal.source_effective_at is not None
            else None
        ),
        retrievedAt=temporal.retrieved_at.isoformat(),
        validFrom=(
            temporal.valid_from.isoformat()
            if temporal.valid_from is not None
            else None
        ),
        validTo=(
            temporal.valid_to.isoformat()
            if temporal.valid_to is not None
            else None
        ),
        acquisitionId=acquisition_id,
        contentId=temporal.content_id or receipt.payload.sha256,
        sourceVersion=temporal.source_version,
    )
    reuse_facet = _facet(
        f"{PRODUCER}#reuse-gate",
        disposition=(
            reuse.disposition.value if reuse is not None else "unknown"
        ),
        searchedSurfaces=(
            list(reuse.searched_surfaces) if reuse is not None else []
        ),
        catalogueRevision=HF_CATALOGUE_REVISION,
    )
    rights_reference = (
        str(receipt.rights_reference)
        if receipt.rights_reference is not None
        else None
    )
    identity_facet = _facet(
        f"{PRODUCER}#acquisition-identity",
        acquisitionId=acquisition_id,
        contentId=temporal.content_id or receipt.payload.sha256,
        sourceId=receipt.source.source_id,
        catalogVersion=receipt.source.catalog_version,
        sourceVersion=temporal.source_version,
    )
    rights_facet = _facet(
        f"{PRODUCER}#rights",
        rightsState=receipt.rights_state.value,
        rightsReference=rights_reference,
    )
    return {
        "gmaTemporalIdentity": temporal_facet,
        "gmaReuseGate": reuse_facet,
        "gmaAcquisitionIdentity": identity_facet,
        "gmaRights": rights_facet,
    }


def _require_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"OpenLineage {label} must be an object")
    return cast("dict[str, object]", value)


def _require_sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise TypeError(f"OpenLineage {label} must be an array")
    return cast("list[object]", value)


def _conform_facet(facet: Mapping[str, object], label: str) -> None:
    if "_producer" not in facet or "_schemaURL" not in facet:
        raise ValueError(f"OpenLineage {label} facet is missing spec keys")
    schema_url = facet["_schemaURL"]
    if not isinstance(schema_url, str):
        raise TypeError(f"OpenLineage {label} facet schemaURL is not a string")
    if "openlineage.io" not in schema_url and PRODUCER not in schema_url:
        raise ValueError(
            f"OpenLineage {label} facet schemaURL is not a spec URL"
        )


def _conform_dataset(dataset: object, label: str) -> None:
    mapping = _require_mapping(dataset, label)
    for key in ("namespace", "name", "facets"):
        if key not in mapping:
            raise ValueError(f"OpenLineage {label} missing {key}")
    facets = _require_mapping(mapping["facets"], f"{label}.facets")
    for name, facet in facets.items():
        _conform_facet(
            _require_mapping(facet, f"{label}.facets.{name}"),
            f"{label}.{name}",
        )


def conform_run_event(event: Mapping[str, object]) -> None:
    """Raise if a document is not a spec-shaped OpenLineage RunEvent."""

    for key in REQUIRED_EVENT_KEYS:
        if key not in event:
            raise ValueError(f"OpenLineage RunEvent missing {key}")
    event_type = event["eventType"]
    if event_type not in EVENT_TYPES:
        raise ValueError("OpenLineage eventType is not a spec value")
    if event["schemaURL"] != SCHEMA_URL:
        raise ValueError("OpenLineage schemaURL must be the RunEvent schema")
    run = _require_mapping(event["run"], "run")
    if "runId" not in run:
        raise ValueError("OpenLineage run missing runId")
    job = _require_mapping(event["job"], "job")
    if "namespace" not in job or "name" not in job:
        raise ValueError("OpenLineage job missing namespace or name")
    run_facets = run.get("facets", {})
    if run_facets:
        mapping = _require_mapping(run_facets, "run.facets")
        for name, facet in mapping.items():
            _conform_facet(
                _require_mapping(facet, f"run.facets.{name}"),
                f"run.{name}",
            )
    for label in ("inputs", "outputs"):
        datasets = _require_sequence(event.get(label, []), label)
        for index, dataset in enumerate(datasets):
            _conform_dataset(dataset, f"{label}[{index}]")


def project_openlineage_event(
    receipt: SourceReceipt,
    *,
    payload_uri: str,
    parquet_uri: str,
    table: IcebergReadyTableSpec | None = None,
) -> dict[str, Any]:
    """Emit one COMPLETE RunEvent from a native source receipt."""

    temporal = require_temporal(receipt.temporal)
    identity = _identity_facets(receipt)
    acquisition_id = temporal.acquisition_id
    source_uri = str(receipt.retrieval.uri)
    payload_name = payload_dataset_name(receipt)
    parquet_name = parquet_dataset_name(receipt)
    payload_extra = dict(identity)
    parquet_extra = dict(identity)
    parquet_extra["columnLineage"] = _column_lineage(
        field="payload_sha256",
        namespace="gma.payload",
        name=payload_name,
        input_field="sha256",
    )
    payload_dataset = _dataset(
        namespace="gma.payload",
        name=payload_name,
        storage_layer="file",
        file_format="raw",
        source_uri=payload_uri,
        version=receipt.payload.sha256,
        extra=payload_extra,
    )
    if table is not None:
        catalogue_name = catalogue_dataset_name(table)
        parquet_extra["symlinks"] = _facet(
            SYMLINKS_SCHEMA_URL,
            identifiers=[
                _symlink(
                    namespace="gma.catalogue",
                    name=catalogue_name,
                    kind="TABLE",
                )
            ],
        )
        parquet_extra["gmaIcebergReady"] = _facet(
            f"{PRODUCER}#iceberg-ready",
            identifier=table.identifier,
            location=table.location,
            partitionFields=list(table.partition_fields),
            formatVersion=table.format_version,
        )
    parquet_dataset = _dataset(
        namespace="gma.parquet",
        name=parquet_name,
        storage_layer="file",
        file_format="parquet",
        source_uri=parquet_uri,
        version=receipt.transformation.output_sha256,
        extra=parquet_extra,
    )
    source_dataset = _dataset(
        namespace="gma.source",
        name=receipt.source.source_id,
        storage_layer="http",
        file_format="source",
        source_uri=source_uri,
        version=receipt.source.catalog_version,
        extra=dict(identity),
    )
    outputs: list[dict[str, object]] = [payload_dataset, parquet_dataset]
    if table is not None:
        catalogue_name = catalogue_dataset_name(table)
        catalogue_extra = dict(identity)
        catalogue_extra["symlinks"] = _facet(
            SYMLINKS_SCHEMA_URL,
            identifiers=[
                _symlink(
                    namespace="gma.parquet",
                    name=parquet_name,
                    kind="LOCATION",
                )
            ],
        )
        catalogue_extra["columnLineage"] = _column_lineage(
            field="identifier",
            namespace="gma.parquet",
            name=parquet_name,
            input_field="payload_sha256",
        )
        catalogue_extra["gmaIcebergReady"] = _facet(
            f"{PRODUCER}#iceberg-ready",
            identifier=table.identifier,
            location=table.location,
            partitionFields=list(table.partition_fields),
            formatVersion=table.format_version,
        )
        outputs.append(
            _dataset(
                namespace="gma.catalogue",
                name=catalogue_name,
                storage_layer="iceberg",
                file_format="parquet",
                source_uri=table.location,
                version=table.identifier,
                extra=catalogue_extra,
            )
        )
    event: dict[str, Any] = {
        "eventType": "COMPLETE",
        "eventTime": temporal.retrieved_at.isoformat(),
        "producer": PRODUCER,
        "schemaURL": SCHEMA_URL,
        "run": {
            "runId": acquisition_id,
            "facets": identity,
        },
        "job": {
            "namespace": JOB_NAMESPACE,
            "name": f"bronze.land.{receipt.source.source_id}",
        },
        "inputs": [source_dataset],
        "outputs": outputs,
    }
    conform_run_event(event)
    return event
