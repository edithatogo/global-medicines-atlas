"""OpenLineage extensions use versioned schemas and standard facets."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Protocol, cast

import pytest
from jsonschema import Draft202012Validator
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
)
from global_medicines_atlas.bronze_transformation import receipt_for_parquet
from global_medicines_atlas.iceberg_ready import IcebergReadyTableSpec
from global_medicines_atlas.openlineage_projection import (
    CATALOG_SCHEMA_URL,
    CUSTOM_FACET_SCHEMA_PATHS,
    CUSTOM_FACET_SCHEMA_URLS,
    DATA_QUALITY_ASSERTIONS_SCHEMA_URL,
    DATASET_TYPE_SCHEMA_URL,
    conform_run_event,
    project_openlineage_events,
)
from global_medicines_atlas.receipts import require_temporal
from global_medicines_atlas.reuse_gate import acquire_new_decision

ROOT = Path(__file__).resolve().parents[1]
PINNED_SCHEMA = re.compile(
    r"^https://raw\.githubusercontent\.com/edithatogo/"
    r"global-medicines-atlas/[0-9a-f]{40}/schemas/openlineage/"
)


class _SchemaValidator(Protocol):
    def validate(self, instance: object) -> None: ...


def _projection(tmp_path: Path):
    receipt = source_receipt().model_copy(
        update={"reuse": acquire_new_decision("medsafe-product-register")}
    )
    temporal = require_temporal(receipt.temporal)
    parquet_path = tmp_path / "manifest.parquet"
    parquet_path.write_bytes(b"parquet-output")
    run = receipt_for_parquet(
        parquet_path,
        acquisition_id=temporal.acquisition_id,
        input_content_id=receipt.payload.sha256,
        completed_at=temporal.retrieved_at,
    )
    admission = create_admission_decision(
        acquisition_id=temporal.acquisition_id,
        content_id=receipt.payload.sha256,
        state=BronzeAdmissionState.ACCEPTED,
        validation_results=(
            ValidationResult(
                check_id="checksum",
                passed=True,
                message="payload digest matches receipt",
            ),
            ValidationResult(
                check_id="archive-safety",
                passed=True,
                message="archive limits satisfied",
            ),
        ),
        decided_at=temporal.retrieved_at,
    )
    table = IcebergReadyTableSpec(
        identifier="bronze.nz_medsafe_products",
        location=str(tmp_path / "warehouse"),
        schema_fields=(("payload_sha256", "string"),),
    )
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
def test_every_custom_facet_has_a_committed_json_schema() -> None:
    assert set(CUSTOM_FACET_SCHEMA_PATHS) == {
        "gma_acquisition",
        "gma_temporalIdentity",
        "gma_reuseGate",
        "gma_transformation",
        "gma_rights",
        "gma_icebergReady",
    }
    for key, relative_path in CUSTOM_FACET_SCHEMA_PATHS.items():
        path = ROOT / relative_path
        schema = json.loads(path.read_bytes())
        Draft202012Validator.check_schema(schema)
        assert schema["title"].startswith("Gma")
        assert schema["title"].endswith(("RunFacet", "DatasetFacet"))
        assert key in schema["x-openlineage-facet-key"]


@pytest.mark.unit
def test_custom_facet_urls_are_immutable_and_keys_are_prefixed(
    tmp_path: Path,
) -> None:
    _receipt, _run, events = _projection(tmp_path)
    assert set(CUSTOM_FACET_SCHEMA_URLS) == set(CUSTOM_FACET_SCHEMA_PATHS)
    assert all(
        PINNED_SCHEMA.match(url) for url in CUSTOM_FACET_SCHEMA_URLS.values()
    )
    observed: dict[str, dict[str, object]] = {}
    for event in events:
        entities = [event["run"], *event["inputs"], *event["outputs"]]
        for entity in entities:
            for facet_group in ("facets", "inputFacets", "outputFacets"):
                for key, facet in entity.get(facet_group, {}).items():
                    if key.startswith("gma"):
                        observed[key] = facet
                        assert key.startswith("gma_")
                        assert (
                            facet["_schemaURL"]
                            == (CUSTOM_FACET_SCHEMA_URLS[key])
                        )
                        assert "/blob/main/" not in facet["_schemaURL"]
    assert set(observed) == set(CUSTOM_FACET_SCHEMA_PATHS)
    for key, facet in observed.items():
        schema = json.loads(
            (ROOT / CUSTOM_FACET_SCHEMA_PATHS[key]).read_bytes()
        )
        validator = cast(
            "_SchemaValidator", Draft202012Validator(schema["allOf"][1])
        )
        validator.validate(facet)


@pytest.mark.unit
def test_acquisition_and_transformation_are_distinct_linked_runs(
    tmp_path: Path,
) -> None:
    receipt, run, events = _projection(tmp_path)
    acquisition, transformation = events
    assert acquisition["job"]["name"].startswith("bronze.acquire.")
    assert transformation["job"]["name"].startswith("bronze.transform.")
    assert acquisition["run"]["runId"] != transformation["run"]["runId"]
    assert (
        acquisition["run"]["facets"]["gma_acquisition"]["acquisitionId"]
        == require_temporal(receipt.temporal).acquisition_id
    )
    assert (
        transformation["run"]["facets"]["gma_transformation"][
            "transformationRunId"
        ]
        == run.run_id
    )
    assert (
        transformation["run"]["facets"]["parent"]["run"]["runId"]
        == acquisition["run"]["runId"]
    )
    assert acquisition["outputs"][0]["namespace"] == "gma.payload"
    assert transformation["inputs"][0]["namespace"] == "gma.payload"


@pytest.mark.unit
def test_standard_catalog_type_and_quality_facets_are_used(
    tmp_path: Path,
) -> None:
    _receipt, _run, events = _projection(tmp_path)
    acquisition, transformation = events
    payload_output = acquisition["outputs"][0]
    payload_input = transformation["inputs"][0]
    by_namespace = {
        dataset["namespace"]: dataset for dataset in transformation["outputs"]
    }
    assert payload_output["facets"]["datasetType"]["_schemaURL"] == (
        DATASET_TYPE_SCHEMA_URL
    )
    assert payload_output["facets"]["datasetType"]["datasetType"] == "FILE"
    assertions = payload_input["inputFacets"]["dataQualityAssertions"]
    assert assertions["_schemaURL"] == DATA_QUALITY_ASSERTIONS_SCHEMA_URL
    assert assertions["assertions"] == [
        {
            "assertion": "checksum",
            "success": True,
            "name": "checksum",
            "severity": "error",
            "description": "payload digest matches receipt",
        },
        {
            "assertion": "archive-safety",
            "success": True,
            "name": "archive-safety",
            "severity": "error",
            "description": "archive limits satisfied",
        },
    ]
    catalogue = by_namespace["gma.catalogue"]
    assert catalogue["facets"]["catalog"]["_schemaURL"] == CATALOG_SCHEMA_URL
    assert catalogue["facets"]["catalog"]["framework"] == "iceberg"
    assert catalogue["facets"]["datasetType"]["datasetType"] == "TABLE"


@pytest.mark.edge
def test_conformance_rejects_bad_custom_key_and_mutable_schema_url(
    tmp_path: Path,
) -> None:
    _receipt, _run, events = _projection(tmp_path)
    bad_key = copy.deepcopy(events.transformation)
    facet = bad_key["run"]["facets"].pop("gma_transformation")
    bad_key["run"]["facets"]["gmaTransformation"] = facet
    with pytest.raises(ValueError, match="custom facet key"):
        conform_run_event(bad_key)

    mutable_url = copy.deepcopy(events.transformation)
    mutable_url["run"]["facets"]["gma_transformation"]["_schemaURL"] = (
        "https://github.com/edithatogo/global-medicines-atlas/"
        "blob/main/schemas/openlineage/transformation-run-facet-v1.json"
    )
    with pytest.raises(ValueError, match="immutable schema URL"):
        conform_run_event(mutable_url)
