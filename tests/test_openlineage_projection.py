"""OpenLineage projection uses spec field names without replacing receipts."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.iceberg_ready import IcebergReadyTableSpec
from global_medicines_atlas.openlineage_projection import (
    SCHEMA_URL,
    project_openlineage_event,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision


@pytest.mark.unit
def test_openlineage_event_uses_real_field_names(tmp_path: Path) -> None:
    receipt = source_receipt().model_copy(
        update={"reuse": acquire_new_decision("medsafe-product-register")}
    )
    parquet_dir = tmp_path / "parquet"
    table = IcebergReadyTableSpec(
        identifier="bronze.nz_medsafe_products",
        location=str(parquet_dir),
        partition_fields=("jurisdiction", "source_id"),
        schema_fields=(("source_id", "string"),),
    )
    event = project_openlineage_event(
        receipt,
        payload_uri=(tmp_path / "payload.json").as_uri(),
        parquet_uri=(tmp_path / "table.parquet").as_uri(),
        table=table,
    )

    assert event["eventType"] == "COMPLETE"
    assert event["eventTime"] == receipt.temporal.retrieved_at.isoformat()
    assert event["producer"].startswith("https://github.com/edithatogo/")
    assert event["schemaURL"] == SCHEMA_URL
    assert event["run"]["runId"] == receipt.temporal.acquisition_id
    assert event["job"]["namespace"] == "global-medicines-atlas"
    assert event["job"]["name"].startswith("bronze.land.")
    outputs = event["outputs"]
    names = {item["name"] for item in outputs}
    assert len(outputs) == 2
    assert names == {
        f"{receipt.source.source_id}/{receipt.temporal.acquisition_id}",
        table.identifier,
    }
    payload, parquet = outputs
    assert payload["namespace"] != parquet["namespace"]
    assert payload["facets"]["storage"]["fileFormat"] == "raw"
    assert parquet["facets"]["storage"]["fileFormat"] == "parquet"
    assert parquet["facets"]["storage"]["storageLayer"] == "iceberg"
    assert "storageLayer" in parquet["facets"]["storage"]
    temporal = event["run"]["facets"]["gmaTemporalIdentity"]
    assert temporal["retrievedAt"] == event["eventTime"]
    assert temporal["sourcePublishedAt"] is None
    assert temporal["acquisitionId"] == receipt.temporal.acquisition_id
    reuse = event["run"]["facets"]["gmaReuseGate"]
    assert reuse["disposition"] == "acquire-new"
    assert "local_clones" in reuse["searchedSurfaces"]
