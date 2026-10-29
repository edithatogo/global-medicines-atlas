"""Group workbook rows retain their own dimensions and native cell properties."""

import json
from pathlib import Path

import pyarrow as pa
import pytest
from test_mbs_demographic_extraction import workbook
from test_mbs_demographic_silver import source
from test_mbs_group_silver import context as csv_context

from global_medicines_atlas import mbs_group_workbook_silver as module
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceManifest,
    build_raw_evidence_reference_from_acquisition,
)
from global_medicines_atlas.mbs_demographic_extraction import (
    DemographicRow,
    iter_native_workbook_records,
)
from global_medicines_atlas.mbs_group_workbook_silver import (
    GROUP_WORKBOOK_HEADERS,
    GroupWorkbookSource,
    iter_group_workbook_batches,
    iter_group_workbook_records,
    load_group_workbook_source,
)

ROOT = Path(__file__).resolve().parents[1]


def context(payload):
    base = source("workbook", payload)
    event = base.acquisition.model_copy(
        update={"source_id": "au-data-gov-mbs-group"}
    )
    raw = build_raw_evidence_reference_from_acquisition(
        event,
        external_reference=f"https://fixtures.invalid/datasets/synthetic/mbs-group/resolve/{'1' * 40}/synthetic/group.xlsx",
    )
    return GroupWorkbookSource(
        acquisition=event,
        raw_manifest=RawEvidenceManifest.from_rows((raw,)),
        dataset="synthetic/mbs-group",
        source_format="workbook",
        source_revision="1" * 40,
        source_path="synthetic/group.xlsx",
    )


def fixture_payload():
    return workbook(
        header=GROUP_WORKBOOK_HEADERS,
        data_row='<c r="A4"><v>2016</v></c><c r="B4"><v>7</v></c><c r="C4" t="inlineStr"><is><t>SYNTHETIC-GROUP</t></is></c><c r="D4" t="inlineStr"><is><t>03</t></is></c><c r="E4" t="inlineStr"><is><t>00123</t></is></c><c r="F4" t="inlineStr"><is><t>SYNTHETIC-STATE</t></is></c><c r="G4"><v>2</v></c><c r="H4"><f>1+2</f><v>1.1234567891</v></c>',
    )


def test_source_binds_real_layout_without_claiming_semantics():
    bound = load_group_workbook_source(ROOT)
    assert bound.headers == GROUP_WORKBOOK_HEADERS
    assert bound.source_path.endswith("group/mbs-group-2016hr-july.xlsx")
    assert (
        bound.object_id
        == "b965b467492fb62b85a3a891eeff5a46400cec1d92af31e24318454b85916ea1"
    )
    assert bound.benefit_semantics.state == "native_unresolved"


def test_group_dimensions_and_formula_cache_survive_without_demographic_fields():
    payload = fixture_payload()
    bound = context(payload)
    rows = (
        row
        for row in iter_group_workbook_records(payload, bound)
        if isinstance(row, DemographicRow)
    )
    table = pa.Table.from_batches(
        list(iter_group_workbook_batches(rows, bound))
    )
    row = table.to_pylist()[0]
    assert row["group_native"] == "SYNTHETIC-GROUP"
    assert row["month_native"] == "7"
    assert "processing_month_native" not in table.schema.names
    assert row["subgroup_native"] == "03"
    assert row["item_number_native"] == "00123"
    assert row["services_count"] == 2
    assert row["benefit_decimal"] is None
    assert row["benefit_conversion_status"] == "unrepresentable"
    assert row["native_cells"][7]["value"] == "1.1234567891"
    assert (
        '"formula": "1+2"' in row["native_cells"][7]["native_properties_json"]
    )
    assert row["patient_rate_state"] == "unavailable"
    assert row["record_kind"] == "native_primary_row"
    assert (
        table.schema.metadata[b"header_record"]
        == b"separate_ancillary_required"
    )
    assert "age_native" not in table.schema.names
    assert "gender_native" not in table.schema.names


def test_wrong_demographic_header_is_rejected():
    payload = workbook()
    with pytest.raises(ValueError, match="header"):
        list(iter_group_workbook_records(payload, context(payload)))


@pytest.mark.parametrize("size", [0, True, 4097])
def test_row_batch_bound_is_strict(size):
    with pytest.raises(ValueError, match="batch"):
        list(
            iter_group_workbook_batches(
                [], context(fixture_payload()), rows_per_batch=size
            )
        )


def records(payload):
    return [
        row
        for row in iter_group_workbook_records(payload, context(payload))
        if isinstance(row, DemographicRow)
    ]


@pytest.mark.parametrize("case", ["order", "header", "property", "row_bytes"])
def test_producer_rejects_unsupported_or_inconsistent_supplied_rows(
    monkeypatch, case
):

    payload = fixture_payload()
    row = records(payload)[0]
    observations = [row]
    if case == "order":
        observations.append(row)
    elif case == "header":
        cells = list(row.cells)
        cells[0] = cells[0].model_copy(update={"name": "Wrong Header"})
        observations = [row.model_copy(update={"cells": tuple(cells)})]
    elif case == "property":
        monkeypatch.setattr(module, "MAX_PROPERTIES_BYTES", 1)
    else:
        monkeypatch.setattr(module, "MAX_BATCH_BYTES", 1)
    with pytest.raises(ValueError, match=r"order|profile|byte bound"):
        list(iter_group_workbook_batches(observations, context(payload)))


def test_batch_row_and_byte_limits_preserve_every_supplied_row(monkeypatch):

    payload = fixture_payload()
    row = records(payload)[0]
    observations = [row, row.model_copy(update={"row_index": 5})]
    single = next(
        iter_group_workbook_batches([row], context(payload))
    ).to_pylist()[0]
    size = len(json.dumps(single, default=str, separators=(",", ":")).encode())
    monkeypatch.setattr(module, "MAX_BATCH_BYTES", size + 1)
    batches = list(iter_group_workbook_batches(observations, context(payload)))
    assert [batch.num_rows for batch in batches] == [1, 1]
    batches = list(
        iter_group_workbook_batches(
            observations, context(payload), rows_per_batch=1
        )
    )
    assert [batch.num_rows for batch in batches] == [1, 1]


def test_shared_physical_extractor_rejects_csv_and_changed_bytes():

    payload = fixture_payload()
    with pytest.raises(ValueError, match="workbook format"):
        list(iter_native_workbook_records(payload, csv_context(payload)))
    with pytest.raises(ValueError, match="identity"):
        list(
            iter_group_workbook_records(payload + b"changed", context(payload))
        )


def test_group_profile_does_not_accept_csv_source_context():

    with pytest.raises(ValueError, match="workbook format"):
        GroupWorkbookSource.model_validate(
            csv_context(b"synthetic").model_dump()
        )
