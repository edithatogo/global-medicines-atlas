"""Native demographic rows retain independent measures and unknown categories."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from global_medicines_atlas import mbs_demographic_silver as module
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    RawEvidenceState,
    build_raw_evidence_reference_from_acquisition,
)
from global_medicines_atlas.mbs_demographic_silver import (
    DemographicCell,
    DemographicRow,
    DemographicSource,
    iter_demographic_silver_batches,
    summarize_demographic_batches,
)
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    RetrievalEvidence,
)
from global_medicines_atlas.silver_field_semantics import (
    compatible_measure_values,
)

CSV_HEADERS = (
    "Year",
    "Month of Processing",
    "Item Number",
    "State",
    "Age Range",
    "Gender",
    "Services",
    "Benefit",
)


def source(kind="csv", payload=b"synthetic q1"):
    digest = sha256(payload).hexdigest()
    event = AcquisitionEvent(
        acquisition_id="b" * 64,
        content_id=digest,
        payload_sha256=digest,
        source_id="au-data-gov-mbs-demographics",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        evidence_class=EvidenceClass.SYNTHETIC,
        retrieval=RetrievalEvidence(
            uri="https://fixtures.invalid/source",
            retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
    )
    record = build_raw_evidence_reference_from_acquisition(
        event,
        external_reference=f"https://fixtures.invalid/datasets/synthetic/mbs-demographics/resolve/{'1' * 40}/synthetic/q1.{'csv' if kind == 'csv' else 'xlsx'}",
    )
    return DemographicSource(
        acquisition=event,
        raw_manifest=RawEvidenceManifest.from_rows((record,)),
        dataset="synthetic/mbs-demographics",
        source_format=kind,
        source_revision="1" * 40,
        source_path=f"synthetic/q1.{'csv' if kind == 'csv' else 'xlsx'}",
    )


def row(context, index, age="Unknown", benefit="12.345", services="-2"):
    values = (
        "2016",
        "3",
        "SYNTHETIC_ITEM",
        "SYNTHETIC_STATE",
        age,
        "F",
        services,
        benefit,
    )
    return DemographicRow(
        row_index=index,
        cells=tuple(
            DemographicCell(
                name=name,
                state="null" if value is None else "value",
                value=value,
            )
            for name, value in zip(context.headers, values, strict=True)
        ),
    )


def test_unknown_rows_survive_native_projection_and_coverage():
    context = source()
    batches = list(
        iter_demographic_silver_batches(
            [
                row(context, 2),
                row(context, 3, age="0-4", benefit="0"),
                row(context, 4, age="Unknown", benefit=None),
            ],
            context,
            rows_per_batch=2,
        )
    )
    assert [batch.num_rows for batch in batches] == [2, 1]
    rows = pa.Table.from_batches(batches).to_pylist()
    assert rows[0]["age_native"] == "Unknown"
    assert rows[0]["age_lower_bound"] is None
    assert rows[0]["age_suppression_relationship"] == "unresolved"
    assert rows[0]["benefit_decimal"] == Decimal("12.345")
    assert rows[0]["services_count"] == -2
    assert rows[0]["patient_rate_state"] == "unavailable"
    assert len(rows[0]["native_cells"]) == 8
    summary = summarize_demographic_batches(batches)
    assert summary[context.object_id]["native_rows"] == 3
    assert summary[context.object_id]["native_fields"] == 24
    assert summary[context.object_id]["literal_unknown_age_rows"] == 2
    output = BytesIO()
    pq.write_table(pa.Table.from_batches(batches), output)
    restored = pq.read_table(BytesIO(output.getvalue()))
    assert restored.to_pylist() == rows


def test_workbook_and_csv_benefits_are_separate_unresolved_measures():
    csv_source, workbook_source = (
        source(),
        source("workbook", b"synthetic workbook"),
    )
    assert (
        csv_source.benefit_semantics.measure_identity
        != workbook_source.benefit_semantics.measure_identity
    )
    with pytest.raises(ValueError, match="interpreted"):
        compatible_measure_values([
            (csv_source.benefit_semantics, Decimal(1)),
            (workbook_source.benefit_semantics, Decimal(1)),
        ])
    for context, index in ((csv_source, 2), (workbook_source, 4)):
        rows = next(
            iter_demographic_silver_batches([row(context, index)], context)
        ).to_pylist()
        assert rows[0]["benefit_interpretation_state"] == "native_unresolved"
        assert rows[0]["benefit_native_name"] == context.headers[7]


def test_unrepresentable_numeric_values_and_native_properties_are_preserved():
    context = source("workbook")
    observation = row(context, 4, benefit="1.00000000001")
    cells = list(observation.cells)
    cells[4] = cells[4].model_copy(
        update={
            "native_properties": {
                "formula_present": True,
                "formula": '"Unknown"',
                "shared_index": "2",
            }
        }
    )
    observation = observation.model_copy(update={"cells": tuple(cells)})
    result = next(
        iter_demographic_silver_batches([observation], context)
    ).to_pylist()[0]
    assert result["benefit_decimal"] is None
    assert result["benefit_conversion_status"] == "unrepresentable"
    assert result["native_cells"][7]["value"] == "1.00000000001"
    assert (
        '"shared_index":"2"'
        in result["native_cells"][4]["native_properties_json"]
    )


def test_order_headers_and_batch_bounds_are_enforced():
    context = source()
    with pytest.raises(ValueError, match="order"):
        list(
            iter_demographic_silver_batches(
                [row(context, 3), row(context, 2)], context
            )
        )
    with pytest.raises(ValueError, match="batch"):
        list(iter_demographic_silver_batches([], context, rows_per_batch=0))
    bad = row(context, 2)
    with pytest.raises(ValueError, match="headers"):
        list(
            iter_demographic_silver_batches(
                [bad.model_copy(update={"cells": tuple(reversed(bad.cells))})],
                context,
            )
        )
    with pytest.raises(ValidationError, match="state"):
        DemographicCell(name="Benefit", state="null", value="1")


@pytest.mark.parametrize(
    ("benefit", "services", "benefit_status", "services_status"),
    [
        ("", "", "blank", "blank"),
        ("NaN", "1.5", "invalid", "non_integral"),
        (None, None, "null", "null"),
        ("9" * 40, "9" * 30, "unrepresentable", "unrepresentable"),
    ],
)
def test_numeric_exceptions_do_not_drop_native_rows(
    benefit, services, benefit_status, services_status
):
    context = source()
    observation = row(context, 2, benefit=benefit, services=services)
    result = next(
        iter_demographic_silver_batches([observation], context)
    ).to_pylist()[0]
    assert result["benefit_conversion_status"] == benefit_status
    assert result["services_conversion_status"] == services_status
    assert result["native_cells"][7]["value"] == benefit
    assert result["native_cells"][6]["value"] == services


def test_absent_errors_and_unsupported_storage_remain_explicit():
    context = source()
    base = row(context, 2)
    for replacement, expected in (
        (
            DemographicCell(
                name=context.headers[7], state="absent", value=None
            ),
            "absent",
        ),
        (
            DemographicCell(
                name=context.headers[7], state="source_error", value="#VALUE!"
            ),
            "source_error",
        ),
        (
            DemographicCell(
                name=context.headers[7],
                state="value",
                value="1",
                native_properties={"cell_type": "b"},
            ),
            "unsupported_storage_type",
        ),
        (
            DemographicCell(
                name=context.headers[7],
                state="value",
                value="1",
                native_properties={"cell_type": []},
            ),
            "unsupported_storage_type",
        ),
    ):
        cells = (*base.cells[:7], replacement)
        batches = list(
            iter_demographic_silver_batches(
                [base.model_copy(update={"cells": cells})], context
            )
        )
        assert (
            batches[0].to_pylist()[0]["benefit_conversion_status"] == expected
        )
        report = summarize_demographic_batches(batches)[context.object_id]
        assert report["native_field_slots"] == 8
        assert report["native_fields"] == (7 if expected == "absent" else 8)


def test_source_identity_revision_family_and_kind_cannot_be_relabelled():
    context = source()
    for change, message in (
        ({"source_path": "../q1.csv"}, "path/format"),
        ({"source_path": "/q1.csv"}, "path/format"),
        ({"source_path": "other.xlsx"}, "path/format"),
        ({"source_path": "other.csv"}, "B2 reference"),
        ({"source_revision": "2" * 40}, "B2 reference"),
        (
            {
                "acquisition": context.acquisition.model_copy(
                    update={"source_id": "other"}
                )
            },
            "family",
        ),
        (
            {
                "acquisition": context.acquisition.model_copy(
                    update={"retrieval": None}
                )
            },
            "succeeded",
        ),
    ):
        with pytest.raises(ValidationError, match=message):
            DemographicSource.model_validate(context.model_dump() | change)
    raw = context.raw_manifest.rows[0]
    for change, message in (
        ({"content_id": "c" * 64}, "identity"),
        ({"kind": RawEvidenceKind.DOCUMENT}, "payload reference"),
        (
            {
                "state": RawEvidenceState.BLOCKED,
                "blocked_reason": "synthetic hold",
            },
            "payload reference",
        ),
    ):
        manifest = RawEvidenceManifest.from_rows((
            raw.model_copy(update=change),
        ))
        with pytest.raises(ValidationError, match=message):
            DemographicSource.model_validate(
                context.model_dump() | {"raw_manifest": manifest}
            )
    duplicate = RawEvidenceManifest.from_rows((raw, raw))
    with pytest.raises(ValidationError, match="one exact"):
        DemographicSource.model_validate(
            context.model_dump() | {"raw_manifest": duplicate}
        )


def test_byte_budget_splits_batches_and_rejects_oversized_rows(monkeypatch):
    context = source()
    example = next(
        iter_demographic_silver_batches([row(context, 2)], context)
    ).to_pylist()[0]
    size = len(json.dumps(example, separators=(",", ":"), default=str).encode())
    monkeypatch.setattr(module, "MAX_BATCH_BYTES", size + 10)
    batches = list(
        iter_demographic_silver_batches(
            [row(context, 2), row(context, 3)], context
        )
    )
    assert [batch.num_rows for batch in batches] == [1, 1]
    monkeypatch.setattr(module, "MAX_BATCH_BYTES", 1)
    with pytest.raises(ValueError, match="byte bound"):
        list(iter_demographic_silver_batches([row(context, 2)], context))


def test_property_bounds_empty_input_and_age_group_accounting(monkeypatch):
    context = source()
    assert list(iter_demographic_silver_batches([], context)) == []
    assert summarize_demographic_batches([]) == {}
    observations = [row(context, 2), row(context, 3, age='"Unknown"')]
    report = summarize_demographic_batches(
        iter_demographic_silver_batches(observations, context)
    )[context.object_id]
    assert (
        sum(group["rows"] for group in report["native_age_groups"])
        == report["native_rows"]
        == 2
    )
    assert report["native_age_groups"] == [
        {"state": "value", "label": '"Unknown"', "rows": 1},
        {"state": "value", "label": "Unknown", "rows": 1},
    ]
    cells = list(observations[0].cells)
    cells[0] = cells[0].model_copy(
        update={"native_properties": {"x": "synthetic"}}
    )
    monkeypatch.setattr(module, "MAX_PROPERTIES_BYTES", 1)
    with pytest.raises(ValueError, match="properties exceed"):
        list(
            iter_demographic_silver_batches(
                [observations[0].model_copy(update={"cells": tuple(cells)})],
                context,
            )
        )


def test_native_ooxml_exponents_are_typed_without_guessing_csv_notation():
    context = source("workbook")
    observation = row(context, 4, benefit="1.25e2", services="2e1")
    cells = tuple(
        cell.model_copy(update={"native_properties": {"cell_type": "n"}})
        if index in {6, 7}
        else cell
        for index, cell in enumerate(observation.cells)
    )
    result = next(
        iter_demographic_silver_batches(
            [observation.model_copy(update={"cells": cells})], context
        )
    ).to_pylist()[0]
    assert result["benefit_decimal"] == Decimal(125)
    assert result["services_count"] == 20
    assert result["native_cells"][7]["value"] == "1.25e2"
    csv_context = source()
    csv_row = row(csv_context, 2, benefit="1.25e2")
    assert (
        next(
            iter_demographic_silver_batches([csv_row], csv_context)
        ).to_pylist()[0]["benefit_conversion_status"]
        == "invalid"
    )


@pytest.mark.parametrize(
    (
        "benefit",
        "services",
        "expected_benefit",
        "benefit_status",
        "services_status",
    ),
    [
        ("0e999999", "0e999999", Decimal(0), "converted", "converted"),
        ("1e999999", "1e999999", None, "unrepresentable", "unrepresentable"),
        ("1e-999999", "1e-999999", None, "unrepresentable", "non_integral"),
    ],
)
def test_extreme_ooxml_exponents_are_bounded_before_arrow_or_integer_conversion(
    benefit, services, expected_benefit, benefit_status, services_status
):
    context = source("workbook")
    observation = row(context, 4, benefit=benefit, services=services)
    cells = tuple(
        cell.model_copy(update={"native_properties": {"cell_type": None}})
        if index in {6, 7}
        else cell
        for index, cell in enumerate(observation.cells)
    )
    result = next(
        iter_demographic_silver_batches(
            [observation.model_copy(update={"cells": cells})], context
        )
    ).to_pylist()[0]
    assert result["benefit_decimal"] == expected_benefit
    assert result["benefit_conversion_status"] == benefit_status
    assert result["services_conversion_status"] == services_status


def test_json_contracts_are_reproducible_and_preserve_presence_constraints():
    root = Path(__file__).resolve().parents[1]
    for name, model in (
        ("mbs-demographic-source-v1", DemographicSource),
        ("mbs-demographic-row-v1", DemographicRow),
    ):
        schema = json.loads((root / f"schemas/{name}.json").read_text())
        schema.pop("$id")
        schema.pop("$schema")
        assert schema == model.model_json_schema()
    validator = Draft202012Validator(DemographicCell.model_json_schema())
    assert not validator.is_valid({
        "name": "Benefit",
        "state": "null",
        "value": "1",
    })
    assert validator.is_valid({
        "name": "Benefit",
        "state": "value",
        "value": "",
    })


def test_identical_content_at_distinct_paths_keeps_object_coverage_separate():
    context = source()
    path = "synthetic/alias.csv"
    reference = context.raw_manifest.rows[0].model_copy(
        update={
            "external_reference": f"https://fixtures.invalid/datasets/{context.dataset}/resolve/{context.source_revision}/{path}"
        }
    )
    alias = DemographicSource.model_validate(
        context.model_dump()
        | {
            "source_path": path,
            "raw_manifest": RawEvidenceManifest.from_rows((reference,)),
        }
    )
    assert context.source_sha256 == alias.source_sha256
    assert context.object_id != alias.object_id
    assert context.source_measure_id != alias.source_measure_id
    assert (
        context.benefit_semantics.measure_identity
        != alias.benefit_semantics.measure_identity
    )
    assert context.benefit_semantics.source_object_id == context.object_id
    first = list(iter_demographic_silver_batches([row(context, 2)], context))
    second = list(iter_demographic_silver_batches([row(alias, 2)], alias))
    assert (
        first[0].to_pylist()[0]["source_row_id"]
        != second[0].to_pylist()[0]["source_row_id"]
    )
    summary = summarize_demographic_batches([*first, *second])
    assert len(summary) == 2
    assert all(value["native_rows"] == 1 for value in summary.values())
