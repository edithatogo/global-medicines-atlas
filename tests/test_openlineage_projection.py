"""OpenLineage projection uses spec field names without replacing receipts."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
)
from global_medicines_atlas.bronze_transformation import receipt_for_parquet
from global_medicines_atlas.iceberg_ready import (
    IcebergPartitionField,
    IcebergReadyTableSpec,
)
from global_medicines_atlas.openlineage_projection import (
    COLUMN_LINEAGE_SCHEMA_URL,
    EVENT_TYPES,
    SCHEMA_URL,
    SYMLINKS_SCHEMA_URL,
    conform_run_event,
    parquet_dataset_name,
    payload_dataset_name,
    project_openlineage_event,
    project_openlineage_events,
)
from global_medicines_atlas.receipts import SourceReceipt, require_temporal
from global_medicines_atlas.reuse_gate import acquire_new_decision


def _table(tmp_path: Path) -> IcebergReadyTableSpec:
    return IcebergReadyTableSpec(
        identifier="bronze.nz_medsafe_products",
        location=str(tmp_path / "parquet"),
        partition_fields=(
            IcebergPartitionField(
                source_field="gma_acquired_at",
                name="gma_acquired_at_month",
                transform="month",
            ),
        ),
        schema_fields=(
            ("jurisdiction", "string"),
            ("source_id", "string"),
            ("gma_acquired_at", "timestamptz"),
        ),
    )


def _admission(receipt: SourceReceipt):
    temporal = require_temporal(receipt.temporal)
    return create_admission_decision(
        acquisition_id=temporal.acquisition_id,
        content_id=receipt.payload.sha256,
        state=BronzeAdmissionState.ACCEPTED,
        validation_results=(
            ValidationResult(
                check_id="checksum",
                passed=True,
                message="payload digest matches receipt",
            ),
        ),
        decided_at=temporal.retrieved_at,
    )


def _event(tmp_path: Path, *, table: IcebergReadyTableSpec | None = None):
    receipt = source_receipt().model_copy(
        update={"reuse": acquire_new_decision("medsafe-product-register")}
    )
    parquet_path = tmp_path / "table.parquet"
    parquet_path.write_bytes(b"parquet-output")
    temporal = require_temporal(receipt.temporal)
    run = receipt_for_parquet(
        parquet_path,
        acquisition_id=temporal.acquisition_id,
        input_content_id=receipt.payload.sha256,
        completed_at=temporal.retrieved_at,
    )
    admission = _admission(receipt)
    events = project_openlineage_events(
        receipt,
        payload_uri=(tmp_path / "payload.json").as_uri(),
        parquet_uri=parquet_path.as_uri(),
        transformation_run=run,
        admission=admission,
        table=table,
    )
    return receipt, run, events


@pytest.mark.unit
def test_openlineage_event_uses_real_field_names(tmp_path: Path) -> None:
    receipt, run, events = _event(tmp_path, table=_table(tmp_path))
    acquisition, event = events

    assert event["eventType"] == "COMPLETE"
    assert (
        event["eventTime"]
        == require_temporal(receipt.temporal).retrieved_at.isoformat()
    )
    assert event["producer"].startswith("https://github.com/edithatogo/")
    assert event["schemaURL"] == SCHEMA_URL
    assert (
        event["run"]["facets"]["gma_transformation"]["transformationRunId"]
        == run.run_id
    )
    assert event["job"]["namespace"] == "global-medicines-atlas"
    assert event["job"]["name"].startswith("bronze.transform.")
    outputs = {item["namespace"]: item for item in event["outputs"]}
    assert set(outputs) == {"gma.parquet", "gma.catalogue"}
    payload = acquisition["outputs"][0]
    parquet = outputs["gma.parquet"]
    catalogue = outputs["gma.catalogue"]
    assert payload["name"] == payload_dataset_name(receipt)
    assert parquet["name"] == parquet_dataset_name(receipt, run)
    assert catalogue["name"] == _table(tmp_path).identifier
    assert payload["facets"]["storage"]["fileFormat"] == "raw"
    assert parquet["facets"]["storage"]["fileFormat"] == "parquet"
    assert parquet["facets"]["storage"]["storageLayer"] == "file"
    assert catalogue["facets"]["storage"]["storageLayer"] == "iceberg"
    expected_partitions = [
        {
            "sourceField": "gma_acquired_at",
            "name": "gma_acquired_at_month",
            "transform": "month",
        }
    ]
    assert parquet["facets"]["gma_icebergReady"]["partitionFields"] == (
        expected_partitions
    )
    assert catalogue["facets"]["gma_icebergReady"]["partitionFields"] == (
        expected_partitions
    )
    temporal = acquisition["run"]["facets"]["gma_temporalIdentity"]
    assert temporal["retrievedAt"] == acquisition["eventTime"]
    assert temporal["sourcePublishedAt"] is None
    assert (
        acquisition["run"]["facets"]["gma_acquisition"]["acquisitionId"]
        == require_temporal(receipt.temporal).acquisition_id
    )
    reuse = acquisition["run"]["facets"]["gma_reuseGate"]
    assert reuse["disposition"] == "acquire-new"
    assert "local_clones" in reuse["searchedSurfaces"]


@pytest.mark.unit
def test_openlineage_without_table_keeps_payload_distinct_from_parquet(
    tmp_path: Path,
) -> None:
    _receipt, _run, events = _event(tmp_path)
    payload = events.acquisition["outputs"][0]
    parquet = events.transformation["outputs"][0]
    assert payload["namespace"] == "gma.payload"
    assert parquet["namespace"] == "gma.parquet"
    assert parquet["facets"]["storage"]["storageLayer"] == "file"
    assert "gma_icebergReady" not in parquet["facets"]
    assert len(events.transformation["outputs"]) == 1
    assert payload["name"] != parquet["name"]


@pytest.mark.unit
def test_payload_parquet_and_catalogue_identities_are_not_collapsed(
    tmp_path: Path,
) -> None:
    receipt, run, events = _event(tmp_path, table=_table(tmp_path))
    by_ns = {
        item["namespace"]: item for item in events.transformation["outputs"]
    }
    payload = events.acquisition["outputs"][0]
    parquet = by_ns["gma.parquet"]
    catalogue = by_ns["gma.catalogue"]
    iceberg_id = _table(tmp_path).identifier

    assert payload["name"] != iceberg_id
    assert parquet["name"] != iceberg_id
    assert payload["name"] != parquet["name"]
    assert payload["namespace"] != parquet["namespace"]
    assert payload["namespace"] != catalogue["namespace"]
    assert payload["facets"]["version"]["datasetVersion"] == (
        receipt.payload.sha256
    )
    assert parquet["facets"]["version"]["datasetVersion"] == (run.output.sha256)
    assert catalogue["name"] == iceberg_id
    payload_symlink_names = {
        item["name"]
        for item in payload["facets"].get("symlinks", {}).get("identifiers", [])
    }
    assert iceberg_id not in payload_symlink_names


@pytest.mark.unit
def test_parquet_derives_from_payload_and_catalogue_is_alternative_identity(
    tmp_path: Path,
) -> None:
    _receipt, _run, events = _event(tmp_path, table=_table(tmp_path))
    by_ns = {
        item["namespace"]: item for item in events.transformation["outputs"]
    }
    payload = events.acquisition["outputs"][0]
    parquet = by_ns["gma.parquet"]
    catalogue = by_ns["gma.catalogue"]

    lineage = parquet["facets"]["columnLineage"]
    assert lineage["_schemaURL"] == COLUMN_LINEAGE_SCHEMA_URL
    source_fields = lineage["fields"]["payload_sha256"]["inputFields"]
    assert source_fields[0]["namespace"] == payload["namespace"]
    assert source_fields[0]["name"] == payload["name"]
    assert source_fields[0]["field"] == "sha256"

    parquet_links = parquet["facets"]["symlinks"]
    assert parquet_links["_schemaURL"] == SYMLINKS_SCHEMA_URL
    identifiers = parquet_links["identifiers"]
    assert {
        "namespace": catalogue["namespace"],
        "name": catalogue["name"],
        "type": "TABLE",
    } in identifiers
    catalogue_links = catalogue["facets"]["symlinks"]["identifiers"]
    assert {
        "namespace": parquet["namespace"],
        "name": parquet["name"],
        "type": "LOCATION",
    } in catalogue_links


@pytest.mark.unit
def test_facets_project_acquisition_temporal_reuse_rights_and_digests(
    tmp_path: Path,
) -> None:
    receipt, _run, events = _event(tmp_path, table=_table(tmp_path))
    run_facets = events.acquisition["run"]["facets"]
    payload = events.acquisition["outputs"][0]
    identity = run_facets["gma_acquisition"]
    rights = payload["facets"]["gma_rights"]
    assert (
        identity["acquisitionId"]
        == require_temporal(receipt.temporal).acquisition_id
    )
    assert identity["contentId"] == receipt.payload.sha256
    assert identity["sourceId"] == receipt.source.source_id
    assert identity["catalogVersion"] == receipt.source.catalog_version
    assert rights["rightsState"] == receipt.rights_state.value
    assert str(receipt.rights_reference) in str(rights["rightsReference"])
    assert run_facets["gma_temporalIdentity"]["retrievedAt"] == (
        require_temporal(receipt.temporal).retrieved_at.isoformat()
    )
    assert run_facets["gma_reuseGate"]["disposition"] == "acquire-new"


@pytest.mark.unit
def test_projection_does_not_mutate_native_receipt(tmp_path: Path) -> None:
    receipt = source_receipt().model_copy(
        update={"reuse": acquire_new_decision("medsafe-product-register")}
    )
    before = receipt.canonical_json()
    parquet_path = tmp_path / "t.parquet"
    parquet_path.write_bytes(b"parquet-output")
    run = receipt_for_parquet(
        parquet_path,
        acquisition_id=require_temporal(receipt.temporal).acquisition_id,
        input_content_id=receipt.payload.sha256,
        completed_at=require_temporal(receipt.temporal).retrieved_at,
    )
    project_openlineage_event(
        receipt,
        payload_uri=(tmp_path / "p.bin").as_uri(),
        parquet_uri=parquet_path.as_uri(),
        transformation_run=run,
        admission=_admission(receipt),
        table=_table(tmp_path),
    )
    assert receipt.canonical_json() == before


@pytest.mark.edge
def test_projection_rejects_mismatched_transformation_run(
    tmp_path: Path,
) -> None:
    receipt = source_receipt().model_copy(
        update={"reuse": acquire_new_decision("medsafe-product-register")}
    )
    parquet_path = tmp_path / "table.parquet"
    parquet_path.write_bytes(b"parquet-output")
    wrong_acquisition = receipt_for_parquet(
        parquet_path,
        acquisition_id="f" * 64,
        input_content_id=receipt.payload.sha256,
        completed_at=require_temporal(receipt.temporal).retrieved_at,
    )
    with pytest.raises(ValueError, match="does not match acquisition"):
        project_openlineage_event(
            receipt,
            payload_uri=(tmp_path / "payload").as_uri(),
            parquet_uri=parquet_path.as_uri(),
            transformation_run=wrong_acquisition,
            admission=_admission(receipt),
        )

    valid_run = receipt_for_parquet(
        parquet_path,
        acquisition_id=require_temporal(receipt.temporal).acquisition_id,
        input_content_id=receipt.payload.sha256,
        completed_at=require_temporal(receipt.temporal).retrieved_at,
    )
    admission = _admission(receipt)
    with pytest.raises(
        ValueError, match="admission does not match acquisition"
    ):
        project_openlineage_event(
            receipt,
            payload_uri=(tmp_path / "payload").as_uri(),
            parquet_uri=parquet_path.as_uri(),
            transformation_run=valid_run,
            admission=admission.model_copy(update={"acquisition_id": "e" * 64}),
        )
    with pytest.raises(ValueError, match="admission does not match content"):
        project_openlineage_event(
            receipt,
            payload_uri=(tmp_path / "payload").as_uri(),
            parquet_uri=parquet_path.as_uri(),
            transformation_run=valid_run,
            admission=admission.model_copy(update={"content_id": "e" * 64}),
        )
    with pytest.raises(ValueError, match="requires accepted admission"):
        project_openlineage_event(
            receipt,
            payload_uri=(tmp_path / "payload").as_uri(),
            parquet_uri=parquet_path.as_uri(),
            transformation_run=valid_run,
            admission=admission.model_copy(
                update={"state": BronzeAdmissionState.QUARANTINED}
            ),
        )
    wrong_input = receipt_for_parquet(
        parquet_path,
        acquisition_id=require_temporal(receipt.temporal).acquisition_id,
        input_content_id="f" * 64,
        completed_at=require_temporal(receipt.temporal).retrieved_at,
    )
    with pytest.raises(ValueError, match="does not match input content"):
        project_openlineage_event(
            receipt,
            payload_uri=(tmp_path / "payload").as_uri(),
            parquet_uri=parquet_path.as_uri(),
            transformation_run=wrong_input,
            admission=_admission(receipt),
        )


@pytest.mark.unit
def test_run_event_conforms_to_openlineage_required_shape(
    tmp_path: Path,
) -> None:
    _, _, events = _event(tmp_path, table=_table(tmp_path))
    event = events.transformation
    conform_run_event(event)
    clone = copy.deepcopy(event)
    del clone["schemaURL"]
    with pytest.raises(ValueError, match="schemaURL"):
        conform_run_event(clone)
    empty_run_facets = copy.deepcopy(event)
    empty_run_facets["run"]["facets"] = {}
    conform_run_event(empty_run_facets)


@pytest.mark.unit
def test_run_event_rejects_non_conforming_shapes(tmp_path: Path) -> None:
    _, _, events = _event(tmp_path, table=_table(tmp_path))
    event = events.transformation
    not_object = copy.deepcopy(event)
    not_object["run"] = []
    with pytest.raises(TypeError, match="run must be an object"):
        conform_run_event(not_object)
    not_array = copy.deepcopy(event)
    not_array["inputs"] = {}
    with pytest.raises(TypeError, match="inputs must be an array"):
        conform_run_event(not_array)
    missing_keys = copy.deepcopy(event)
    missing_keys["outputs"][0]["facets"]["storage"] = {"not": "a facet"}
    with pytest.raises(ValueError, match="facet is missing spec keys"):
        conform_run_event(missing_keys)
    bad_schema_type = copy.deepcopy(event)
    bad_schema_type["outputs"][0]["facets"]["storage"]["_schemaURL"] = 1
    with pytest.raises(TypeError, match="schemaURL is not a string"):
        conform_run_event(bad_schema_type)
    bad_schema_url = copy.deepcopy(event)
    bad_schema_url["outputs"][0]["facets"]["storage"]["_schemaURL"] = (
        "https://example.test/not-openlineage"
    )
    with pytest.raises(ValueError, match="not a spec URL"):
        conform_run_event(bad_schema_url)
    missing_dataset_key = copy.deepcopy(event)
    del missing_dataset_key["outputs"][0]["namespace"]
    with pytest.raises(ValueError, match="missing namespace"):
        conform_run_event(missing_dataset_key)
    bad_event_type = copy.deepcopy(event)
    bad_event_type["eventType"] = "DONE"
    with pytest.raises(ValueError, match="eventType is not a spec value"):
        conform_run_event(bad_event_type)
    wrong_schema = copy.deepcopy(event)
    wrong_schema["schemaURL"] = f"{SCHEMA_URL}/other"
    with pytest.raises(
        ValueError, match="schemaURL must be the RunEvent schema"
    ):
        conform_run_event(wrong_schema)
    missing_run_id = copy.deepcopy(event)
    del missing_run_id["run"]["runId"]
    with pytest.raises(ValueError, match="run missing runId"):
        conform_run_event(missing_run_id)
    missing_job = copy.deepcopy(event)
    del missing_job["job"]["name"]
    with pytest.raises(ValueError, match="job missing namespace or name"):
        conform_run_event(missing_job)
    incomplete_run_facet = copy.deepcopy(event)
    incomplete_run_facet["run"]["facets"]["gma_rights"] = {"_producer": "x"}
    with pytest.raises(ValueError, match="facet is missing spec keys"):
        conform_run_event(incomplete_run_facet)


@pytest.mark.property
@given(st.sampled_from(sorted(EVENT_TYPES)))
def test_event_type_enum_matches_openlineage_spec(event_type: str) -> None:
    assert event_type in EVENT_TYPES
    assert event_type.isupper()
