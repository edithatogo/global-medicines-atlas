"""Project OpenLineage events from native acquisition receipts.

Receipts remain the richer provenance. This module emits OpenLineage
RunEvent documents with real spec field names. Payload datasets are not
Parquet datasets. Marquez is not part of the default install.
"""

from __future__ import annotations

from typing import Any

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
JOB_NAMESPACE = "global-medicines-atlas"


def _facet(schema_url: str, **fields: object) -> dict[str, object]:
    return {
        "_producer": PRODUCER,
        "_schemaURL": schema_url,
        **fields,
    }


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
    }
    if extra:
        facets.update(extra)
    return {"namespace": namespace, "name": name, "facets": facets}


def project_openlineage_event(
    receipt: SourceReceipt,
    *,
    payload_uri: str,
    parquet_uri: str,
    table: IcebergReadyTableSpec | None = None,
) -> dict[str, Any]:
    """Emit one COMPLETE RunEvent from a native source receipt."""

    temporal = require_temporal(receipt.temporal)
    reuse = receipt.reuse
    acquisition_id = temporal.acquisition_id
    source_uri = str(receipt.retrieval.uri)
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
    payload_name = f"{receipt.source.source_id}/{acquisition_id}"
    parquet_name = (
        table.identifier
        if table is not None
        else f"parquet.{receipt.source.source_id}"
    )
    table_facet = None
    if table is not None:
        table_facet = _facet(
            f"{PRODUCER}#iceberg-ready",
            identifier=table.identifier,
            location=table.location,
            partitionFields=list(table.partition_fields),
            formatVersion=table.format_version,
        )
    parquet_extra: dict[str, object] = {
        "gmaTemporalIdentity": temporal_facet,
        "gmaReuseGate": reuse_facet,
    }
    if table_facet is not None:
        parquet_extra["gmaIcebergReady"] = table_facet
    payload_dataset = _dataset(
        namespace="gma.payload",
        name=payload_name,
        storage_layer="file",
        file_format="raw",
        source_uri=payload_uri,
        version=acquisition_id,
        extra={
            "gmaTemporalIdentity": temporal_facet,
            "gmaReuseGate": reuse_facet,
        },
    )
    parquet_dataset = _dataset(
        namespace="gma.parquet",
        name=parquet_name,
        storage_layer="iceberg" if table is not None else "file",
        file_format="parquet",
        source_uri=parquet_uri,
        version=acquisition_id,
        extra=parquet_extra,
    )
    source_dataset = _dataset(
        namespace="gma.source",
        name=receipt.source.source_id,
        storage_layer="http",
        file_format="source",
        source_uri=source_uri,
        version=receipt.source.catalog_version,
    )
    return {
        "eventType": "COMPLETE",
        "eventTime": temporal.retrieved_at.isoformat(),
        "producer": PRODUCER,
        "schemaURL": SCHEMA_URL,
        "run": {
            "runId": acquisition_id,
            "facets": {
                "gmaTemporalIdentity": temporal_facet,
                "gmaReuseGate": reuse_facet,
            },
        },
        "job": {
            "namespace": JOB_NAMESPACE,
            "name": f"bronze.land.{receipt.source.source_id}",
            "facets": {},
        },
        "inputs": [source_dataset],
        "outputs": [payload_dataset, parquet_dataset],
    }
