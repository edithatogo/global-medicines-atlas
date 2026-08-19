"""OpenLineage projection uses spec field names without replacing receipts."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.iceberg_ready import IcebergReadyTableSpec
from global_medicines_atlas.openlineage_projection import (
    COLUMN_LINEAGE_SCHEMA_URL,
    EVENT_TYPES,
    SCHEMA_URL,
    SYMLINKS_SCHEMA_URL,
    conform_run_event,
    parquet_dataset_name,
    payload_dataset_name,
    project_openlineage_event,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision


def _table(tmp_path: Path) -> IcebergReadyTableSpec:
    return IcebergReadyTableSpec(
        identifier="bronze.nz_medsafe_products",
        location=str(tmp_path / "parquet"),
        partition_fields=("jurisdiction", "source_id"),
        schema_fields=(
            ("jurisdiction", "string"),
            ("source_id", "string"),
        ),
    )


def _event(tmp_path: Path, *, table: IcebergReadyTableSpec | None = None):
    receipt = source_receipt().model_copy(
        update={"reuse": acquire_new_decision("medsafe-product-register")}
    )
    event = project_openlineage_event(
        receipt,
        payload_uri=(tmp_path / "payload.json").as_uri(),
        parquet_uri=(tmp_path / "table.parquet").as_uri(),
        table=table,
    )
    return receipt, event


@pytest.mark.unit
def test_openlineage_event_uses_real_field_names(tmp_path: Path) -> None:
    receipt, event = _event(tmp_path, table=_table(tmp_path))

    assert event["eventType"] == "COMPLETE"
    assert event["eventTime"] == receipt.temporal.retrieved_at.isoformat()
    assert event["producer"].startswith("https://github.com/edithatogo/")
    assert event["schemaURL"] == SCHEMA_URL
    assert event["run"]["runId"] == receipt.temporal.acquisition_id
    assert event["job"]["namespace"] == "global-medicines-atlas"
    assert event["job"]["name"].startswith("bronze.land.")
    outputs = {item["namespace"]: item for item in event["outputs"]}
    assert set(outputs) == {"gma.payload", "gma.parquet", "gma.catalogue"}
    payload = outputs["gma.payload"]
    parquet = outputs["gma.parquet"]
    catalogue = outputs["gma.catalogue"]
    assert payload["name"] == payload_dataset_name(receipt)
    assert parquet["name"] == parquet_dataset_name(receipt)
    assert catalogue["name"] == _table(tmp_path).identifier
    assert payload["facets"]["storage"]["fileFormat"] == "raw"
    assert parquet["facets"]["storage"]["fileFormat"] == "parquet"
    assert parquet["facets"]["storage"]["storageLayer"] == "file"
    assert catalogue["facets"]["storage"]["storageLayer"] == "iceberg"
    temporal = event["run"]["facets"]["gmaTemporalIdentity"]
    assert temporal["retrievedAt"] == event["eventTime"]
    assert temporal["sourcePublishedAt"] is None
    assert temporal["acquisitionId"] == receipt.temporal.acquisition_id
    reuse = event["run"]["facets"]["gmaReuseGate"]
    assert reuse["disposition"] == "acquire-new"
    assert "local_clones" in reuse["searchedSurfaces"]


@pytest.mark.unit
def test_openlineage_without_table_keeps_payload_distinct_from_parquet(
    tmp_path: Path,
) -> None:
    _receipt, event = _event(tmp_path)
    payload, parquet = event["outputs"]
    assert payload["namespace"] == "gma.payload"
    assert parquet["namespace"] == "gma.parquet"
    assert parquet["facets"]["storage"]["storageLayer"] == "file"
    assert "gmaIcebergReady" not in parquet["facets"]
    assert len(event["outputs"]) == 2
    assert payload["name"] != parquet["name"]


@pytest.mark.unit
def test_payload_parquet_and_catalogue_identities_are_not_collapsed(
    tmp_path: Path,
) -> None:
    receipt, event = _event(tmp_path, table=_table(tmp_path))
    by_ns = {item["namespace"]: item for item in event["outputs"]}
    payload = by_ns["gma.payload"]
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
    assert parquet["facets"]["version"]["datasetVersion"] == (
        receipt.transformation.output_sha256
    )
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
    _receipt, event = _event(tmp_path, table=_table(tmp_path))
    by_ns = {item["namespace"]: item for item in event["outputs"]}
    payload = by_ns["gma.payload"]
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
    receipt, event = _event(tmp_path, table=_table(tmp_path))
    run_facets = event["run"]["facets"]
    payload = next(
        item for item in event["outputs"] if item["namespace"] == "gma.payload"
    )
    identity = payload["facets"]["gmaAcquisitionIdentity"]
    rights = payload["facets"]["gmaRights"]
    assert identity["acquisitionId"] == receipt.temporal.acquisition_id
    assert identity["contentId"] == receipt.payload.sha256
    assert identity["sourceId"] == receipt.source.source_id
    assert identity["catalogVersion"] == receipt.source.catalog_version
    assert rights["rightsState"] == receipt.rights_state.value
    assert str(receipt.rights_reference) in str(rights["rightsReference"])
    assert run_facets["gmaTemporalIdentity"]["retrievedAt"] == (
        receipt.temporal.retrieved_at.isoformat()
    )
    assert run_facets["gmaReuseGate"]["disposition"] == "acquire-new"


@pytest.mark.unit
def test_projection_does_not_mutate_native_receipt(tmp_path: Path) -> None:
    receipt = source_receipt().model_copy(
        update={"reuse": acquire_new_decision("medsafe-product-register")}
    )
    before = receipt.canonical_json()
    project_openlineage_event(
        receipt,
        payload_uri=(tmp_path / "p.bin").as_uri(),
        parquet_uri=(tmp_path / "t.parquet").as_uri(),
        table=_table(tmp_path),
    )
    assert receipt.canonical_json() == before


@pytest.mark.unit
def test_run_event_conforms_to_openlineage_required_shape(
    tmp_path: Path,
) -> None:
    _, event = _event(tmp_path, table=_table(tmp_path))
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
    _, event = _event(tmp_path, table=_table(tmp_path))
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
    incomplete_run_facet["run"]["facets"]["gmaRights"] = {"_producer": "x"}
    with pytest.raises(ValueError, match="facet is missing spec keys"):
        conform_run_event(incomplete_run_facet)


@pytest.mark.property
@given(st.sampled_from(sorted(EVENT_TYPES)))
def test_event_type_enum_matches_openlineage_spec(event_type: str) -> None:
    assert event_type in EVENT_TYPES
    assert event_type.isupper()
