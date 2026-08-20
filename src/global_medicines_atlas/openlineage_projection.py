"""Project OpenLineage events from authoritative native receipts.

Acquisition and transformation are distinct runs. Native receipts remain
richer provenance, while standard OpenLineage facets are preferred whenever
the specification already represents the required concept.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal, NamedTuple, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from .bronze_admission import BronzeAdmissionRecord, BronzeAdmissionState
from .bronze_transformation import TransformationRunReceipt
from .iceberg_ready import IcebergReadyTableSpec
from .receipts import SourceReceipt, require_temporal
from .reuse_gate import HF_CATALOGUE_REVISION

PRODUCER = "https://github.com/edithatogo/global-medicines-atlas"
SCHEMA_REVISION = "804f5ce5a718922bd5597c5421d45ec65700b640"
CUSTOM_SCHEMA_BASE = (
    "https://raw.githubusercontent.com/edithatogo/global-medicines-atlas/"
    f"{SCHEMA_REVISION}/schemas/openlineage"
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
CATALOG_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/1-0-0/CatalogDatasetFacet.json"
)
DATASET_TYPE_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/1-0-0/DatasetTypeDatasetFacet.json"
)
DATA_QUALITY_ASSERTIONS_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/1-1-0/"
    "DataQualityAssertionsDatasetFacet.json"
)
PARENT_RUN_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/1-0-0/ParentRunFacet.json"
)
CUSTOM_FACET_SCHEMA_PATHS = {
    "gma_acquisition": (
        "schemas/openlineage/gma-acquisition-run-facet-v1.json"
    ),
    "gma_temporalIdentity": (
        "schemas/openlineage/gma-temporal-identity-run-facet-v1.json"
    ),
    "gma_reuseGate": ("schemas/openlineage/gma-reuse-gate-run-facet-v1.json"),
    "gma_transformation": (
        "schemas/openlineage/gma-transformation-run-facet-v1.json"
    ),
    "gma_rights": "schemas/openlineage/gma-rights-dataset-facet-v1.json",
    "gma_icebergReady": (
        "schemas/openlineage/gma-iceberg-ready-dataset-facet-v1.json"
    ),
}
CUSTOM_FACET_SCHEMA_URLS = {
    key: f"{CUSTOM_SCHEMA_BASE}/{path.rsplit('/', maxsplit=1)[-1]}"
    for key, path in CUSTOM_FACET_SCHEMA_PATHS.items()
}
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
CUSTOM_FACET_KEY = re.compile(r"^gma_[a-z][A-Za-z0-9]*$")
PINNED_CUSTOM_SCHEMA_URL = re.compile(
    r"^https://raw\.githubusercontent\.com/edithatogo/"
    r"global-medicines-atlas/[0-9a-f]{40}/schemas/openlineage/"
)


class OpenLineageEventPair(NamedTuple):
    """Acquisition and transformation events for one Bronze product."""

    acquisition: dict[str, Any]
    transformation: dict[str, Any]


def _facet(schema_url: str, **fields: object) -> dict[str, object]:
    return {"_producer": PRODUCER, "_schemaURL": schema_url, **fields}


def _custom_facet(key: str, **fields: object) -> dict[str, object]:
    return _facet(CUSTOM_FACET_SCHEMA_URLS[key], **fields)


def _openlineage_run_id(kind: str, native_id: str) -> str:
    """Return a stable UUID for one native append-only run identity."""

    return str(uuid5(NAMESPACE_URL, f"gma:{kind}:{native_id}"))


def payload_dataset_name(receipt: SourceReceipt) -> str:
    """Stable OpenLineage name for payload bytes, keyed by content digest."""

    return f"{receipt.source.source_id}/{receipt.payload.sha256}"


def parquet_dataset_name(
    receipt: SourceReceipt,
    transformation_run: TransformationRunReceipt,
    product: Literal[
        "parquet", "acquisition_manifest", "source_records"
    ] = "parquet",
) -> str:
    """Stable OpenLineage name for source-faithful Parquet, not Iceberg."""

    return (
        f"{receipt.source.source_id}/{product}/"
        f"{transformation_run.output.sha256}"
    )


def catalogue_dataset_name(table: IcebergReadyTableSpec) -> str:
    """Rebuildable catalogue identity over Parquet, never payload identity."""

    return table.identifier


def _symlink(*, namespace: str, name: str, kind: str) -> dict[str, str]:
    return {"namespace": namespace, "name": name, "type": kind}


def _column_lineage(
    *, field: str, namespace: str, name: str, input_field: str
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
    version: str | int,
    dataset_type: str,
    extra: dict[str, object] | None = None,
    input_facets: dict[str, object] | None = None,
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
        "version": _facet(VERSION_SCHEMA_URL, datasetVersion=str(version)),
        "lifecycleStateChange": _facet(
            LIFECYCLE_SCHEMA_URL, lifecycleStateChange="CREATE"
        ),
        "datasetType": _facet(
            DATASET_TYPE_SCHEMA_URL, datasetType=dataset_type
        ),
    }
    if extra:
        facets.update(extra)
    dataset: dict[str, object] = {
        "namespace": namespace,
        "name": name,
        "facets": facets,
    }
    if input_facets:
        dataset["inputFacets"] = input_facets
    return dataset


def _rights_facet(receipt: SourceReceipt) -> dict[str, object]:
    reference = (
        str(receipt.rights_reference)
        if receipt.rights_reference is not None
        else None
    )
    return _custom_facet(
        "gma_rights",
        rightsState=receipt.rights_state.value,
        rightsReference=reference,
    )


def _acquisition_run_facets(receipt: SourceReceipt) -> dict[str, object]:
    temporal = require_temporal(receipt.temporal)
    reuse = receipt.reuse
    return {
        "gma_acquisition": _custom_facet(
            "gma_acquisition",
            acquisitionId=temporal.acquisition_id,
            contentId=temporal.content_id or receipt.payload.sha256,
            sourceId=receipt.source.source_id,
            catalogVersion=receipt.source.catalog_version,
            sourceVersion=temporal.source_version,
        ),
        "gma_temporalIdentity": _custom_facet(
            "gma_temporalIdentity",
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
        ),
        "gma_reuseGate": _custom_facet(
            "gma_reuseGate",
            disposition=(
                reuse.disposition.value if reuse is not None else "unknown"
            ),
            searchedSurfaces=(
                list(reuse.searched_surfaces) if reuse is not None else []
            ),
            catalogueRevision=HF_CATALOGUE_REVISION,
        ),
    }


def _transformation_run_facets(
    transformation_run: TransformationRunReceipt,
    *,
    acquisition_run_id: str,
    acquisition_job_name: str,
) -> dict[str, object]:
    return {
        "parent": _facet(
            PARENT_RUN_SCHEMA_URL,
            run={"runId": acquisition_run_id},
            job={"namespace": JOB_NAMESPACE, "name": acquisition_job_name},
        ),
        "gma_transformation": _custom_facet(
            "gma_transformation",
            transformationRunId=transformation_run.run_id,
            acquisitionId=transformation_run.acquisition_id,
            inputContentId=transformation_run.input_content_id,
            parserIdentity=transformation_run.parser_identity,
            transformationIdentity=(transformation_run.transformation_identity),
            codeCommit=transformation_run.code_commit,
            outputSchemaVersion=transformation_run.output_schema_version,
            environmentSha256=transformation_run.environment_sha256,
            outputSha256=transformation_run.output.sha256,
            outputByteCount=transformation_run.output.byte_count,
        ),
    }


def _quality_assertions(
    admission: BronzeAdmissionRecord,
) -> dict[str, object]:
    return _facet(
        DATA_QUALITY_ASSERTIONS_SCHEMA_URL,
        assertions=[
            {
                "assertion": result.check_id,
                "success": result.passed,
                "name": result.check_id,
                "severity": "error",
                "description": result.message,
            }
            for result in admission.validation_results
        ],
    )


def _iceberg_ready_facet(
    table: IcebergReadyTableSpec,
) -> dict[str, object]:
    return _custom_facet(
        "gma_icebergReady",
        identifier=table.identifier,
        location=table.location,
        partitionFields=[
            {
                "sourceField": field.source_field,
                "name": field.name,
                "transform": field.transform,
            }
            for field in table.partition_fields
        ],
        formatVersion=table.format_version,
    )


def _require_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"OpenLineage {label} must be an object")
    return cast("dict[str, object]", value)


def _require_sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise TypeError(f"OpenLineage {label} must be an array")
    return cast("list[object]", value)


def _conform_facet(facet: Mapping[str, object], label: str, name: str) -> None:
    if "_producer" not in facet or "_schemaURL" not in facet:
        raise ValueError(f"OpenLineage {label} facet is missing spec keys")
    schema_url = facet["_schemaURL"]
    if not isinstance(schema_url, str):
        raise TypeError(f"OpenLineage {label} facet schemaURL is not a string")
    if name.startswith("gma"):
        if not CUSTOM_FACET_KEY.fullmatch(name):
            raise ValueError(
                f"OpenLineage {label} has invalid custom facet key"
            )
        expected = CUSTOM_FACET_SCHEMA_URLS.get(name)
        if (
            expected is None
            or schema_url != expected
            or PINNED_CUSTOM_SCHEMA_URL.match(schema_url) is None
        ):
            raise ValueError(
                f"OpenLineage {label} custom facet needs immutable schema URL"
            )
        return
    if not schema_url.startswith("https://openlineage.io/spec/"):
        raise ValueError(
            f"OpenLineage {label} facet schemaURL is not a spec URL"
        )


def _conform_dataset(dataset: object, label: str) -> None:
    mapping = _require_mapping(dataset, label)
    for key in ("namespace", "name", "facets"):
        if key not in mapping:
            raise ValueError(f"OpenLineage {label} missing {key}")
    for group in ("facets", "inputFacets", "outputFacets"):
        facets = _require_mapping(mapping.get(group, {}), f"{label}.{group}")
        for name, facet in facets.items():
            _conform_facet(
                _require_mapping(facet, f"{label}.{group}.{name}"),
                f"{label}.{name}",
                name,
            )


def conform_run_event(event: Mapping[str, object]) -> None:
    """Raise if a document is not a conformant OpenLineage RunEvent."""

    for key in REQUIRED_EVENT_KEYS:
        if key not in event:
            raise ValueError(f"OpenLineage RunEvent missing {key}")
    if event["eventType"] not in EVENT_TYPES:
        raise ValueError("OpenLineage eventType is not a spec value")
    if event["schemaURL"] != SCHEMA_URL:
        raise ValueError("OpenLineage schemaURL must be the RunEvent schema")
    run = _require_mapping(event["run"], "run")
    run_id = run.get("runId")
    if run_id is None:
        raise ValueError("OpenLineage run missing runId")
    if not isinstance(run_id, str):
        raise TypeError("OpenLineage runId must be a string")
    try:
        UUID(run_id)
    except ValueError as error:
        raise ValueError("OpenLineage runId must be a UUID") from error
    job = _require_mapping(event["job"], "job")
    if "namespace" not in job or "name" not in job:
        raise ValueError("OpenLineage job missing namespace or name")
    run_facets = _require_mapping(run.get("facets", {}), "run.facets")
    for name, facet in run_facets.items():
        _conform_facet(
            _require_mapping(facet, f"run.facets.{name}"),
            f"run.{name}",
            name,
        )
    for label in ("inputs", "outputs"):
        datasets = _require_sequence(event.get(label, []), label)
        for index, dataset in enumerate(datasets):
            _conform_dataset(dataset, f"{label}[{index}]")


def project_openlineage_events(  # ruff: ignore[too-many-locals]
    receipt: SourceReceipt,
    *,
    payload_uri: str,
    parquet_uri: str,
    transformation_run: TransformationRunReceipt,
    admission: BronzeAdmissionRecord,
    table: IcebergReadyTableSpec | None = None,
    parquet_product: Literal[
        "parquet", "acquisition_manifest", "source_records"
    ] = "parquet",
) -> OpenLineageEventPair:
    """Emit distinct acquisition and transformation COMPLETE RunEvents."""

    temporal = require_temporal(receipt.temporal)
    acquisition_id = temporal.acquisition_id
    content_id = temporal.content_id or receipt.payload.sha256
    if transformation_run.acquisition_id != acquisition_id:
        raise ValueError("transformation run does not match acquisition")
    if transformation_run.input_content_id != receipt.payload.sha256:
        raise ValueError("transformation run does not match input content")
    if admission.acquisition_id != acquisition_id:
        raise ValueError("admission does not match acquisition")
    if admission.content_id != content_id:
        raise ValueError("admission does not match content")
    if admission.state is not BronzeAdmissionState.ACCEPTED:
        raise ValueError("OpenLineage projection requires accepted admission")

    source_uri = str(receipt.retrieval.uri)
    payload_name = payload_dataset_name(receipt)
    parquet_name = parquet_dataset_name(
        receipt, transformation_run, parquet_product
    )
    parquet_namespace = {
        "parquet": "gma.parquet",
        "acquisition_manifest": "gma.acquisition_manifest",
        "source_records": "gma.source_records",
    }[parquet_product]
    rights: dict[str, object] = {"gma_rights": _rights_facet(receipt)}
    source_dataset = _dataset(
        namespace="gma.source",
        name=receipt.source.source_id,
        storage_layer="http",
        file_format="source",
        source_uri=source_uri,
        version=receipt.source.catalog_version,
        dataset_type="FILE",
        extra=dict(rights),
    )
    payload_dataset = _dataset(
        namespace="gma.payload",
        name=payload_name,
        storage_layer="file",
        file_format="raw",
        source_uri=payload_uri,
        version=receipt.payload.sha256,
        dataset_type="FILE",
        extra=dict(rights),
    )
    acquisition_run_id = _openlineage_run_id("acquisition", acquisition_id)
    acquisition_job_name = f"bronze.acquire.{receipt.source.source_id}"
    acquisition_event: dict[str, Any] = {
        "eventType": "COMPLETE",
        "eventTime": temporal.retrieved_at.isoformat(),
        "producer": PRODUCER,
        "schemaURL": SCHEMA_URL,
        "run": {
            "runId": acquisition_run_id,
            "facets": _acquisition_run_facets(receipt),
        },
        "job": {"namespace": JOB_NAMESPACE, "name": acquisition_job_name},
        "inputs": [source_dataset],
        "outputs": [payload_dataset],
    }

    payload_input = _dataset(
        namespace="gma.payload",
        name=payload_name,
        storage_layer="file",
        file_format="raw",
        source_uri=payload_uri,
        version=receipt.payload.sha256,
        dataset_type="FILE",
        extra=dict(rights),
        input_facets={"dataQualityAssertions": _quality_assertions(admission)},
    )
    parquet_extra: dict[str, object] = dict(rights)
    parquet_extra["columnLineage"] = _column_lineage(
        field=(
            "gma_content_id"
            if parquet_product == "source_records"
            else "payload_sha256"
        ),
        namespace="gma.payload",
        name=payload_name,
        input_field="sha256",
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
        parquet_extra["gma_icebergReady"] = _iceberg_ready_facet(table)
    parquet_dataset = _dataset(
        namespace=parquet_namespace,
        name=parquet_name,
        storage_layer="file",
        file_format="parquet",
        source_uri=parquet_uri,
        version=transformation_run.output.sha256,
        dataset_type="FILE",
        extra=parquet_extra,
    )
    outputs = [parquet_dataset]
    if table is not None:
        catalogue_name = catalogue_dataset_name(table)
        catalogue_extra: dict[str, object] = {
            **rights,
            "symlinks": _facet(
                SYMLINKS_SCHEMA_URL,
                identifiers=[
                    _symlink(
                        namespace=parquet_namespace,
                        name=parquet_name,
                        kind="LOCATION",
                    )
                ],
            ),
            "columnLineage": _column_lineage(
                field="identifier",
                namespace=parquet_namespace,
                name=parquet_name,
                input_field=(
                    "gma_content_id"
                    if parquet_product == "source_records"
                    else "payload_sha256"
                ),
            ),
            "catalog": _facet(
                CATALOG_SCHEMA_URL,
                framework="iceberg",
                type="rest",
                name="global-medicines-atlas-bronze",
                warehouseUri=table.location,
                source="global-medicines-atlas",
            ),
            "gma_icebergReady": _iceberg_ready_facet(table),
        }
        outputs.append(
            _dataset(
                namespace="gma.catalogue",
                name=catalogue_name,
                storage_layer="iceberg",
                file_format="parquet",
                source_uri=table.location,
                version=table.identifier,
                dataset_type="TABLE",
                extra=catalogue_extra,
            )
        )
    transformation_event: dict[str, Any] = {
        "eventType": "COMPLETE",
        "eventTime": transformation_run.completed_at.isoformat(),
        "producer": PRODUCER,
        "schemaURL": SCHEMA_URL,
        "run": {
            "runId": _openlineage_run_id(
                "transformation", transformation_run.run_id
            ),
            "facets": _transformation_run_facets(
                transformation_run,
                acquisition_run_id=acquisition_run_id,
                acquisition_job_name=acquisition_job_name,
            ),
        },
        "job": {
            "namespace": JOB_NAMESPACE,
            "name": (
                f"bronze.transform.{receipt.source.source_id}.{parquet_product}"
            ),
        },
        "inputs": [payload_input],
        "outputs": outputs,
    }
    conform_run_event(acquisition_event)
    conform_run_event(transformation_event)
    return OpenLineageEventPair(acquisition_event, transformation_event)


def project_openlineage_event(
    receipt: SourceReceipt,
    *,
    payload_uri: str,
    parquet_uri: str,
    transformation_run: TransformationRunReceipt,
    admission: BronzeAdmissionRecord,
    table: IcebergReadyTableSpec | None = None,
    parquet_product: Literal[
        "parquet", "acquisition_manifest", "source_records"
    ] = "parquet",
) -> dict[str, Any]:
    """Return the transformation event for compatibility with prior callers."""

    return project_openlineage_events(
        receipt,
        payload_uri=payload_uri,
        parquet_uri=parquet_uri,
        transformation_run=transformation_run,
        admission=admission,
        table=table,
        parquet_product=parquet_product,
    ).transformation
