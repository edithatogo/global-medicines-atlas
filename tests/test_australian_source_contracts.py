"""Complete native denominators precede Australian Silver harmonisation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from pydantic import AnyUrl, BaseModel, ValidationError

from global_medicines_atlas import australian_source_contracts as contracts
from global_medicines_atlas.adapters.au_mbs import (
    MBS_NATIVE_FIELDS,
    MbsNativeField,
    parse_mbs_source_xml,
)
from global_medicines_atlas.adapters.au_mbs_workbook import (
    MbsWorkbookBatch,
    MbsWorkbookCell,
    MbsWorkbookSheet,
)
from global_medicines_atlas.australian_source_contracts import (
    AustralianTableContract,
    MbsFieldContract,
    NativeFieldCoverage,
    NativeFieldOccurrence,
    mbs_field_contracts,
    mbs_native_fields,
    pbs_native_fields,
    summarize_native_fields,
    workbook_native_fields,
)
from global_medicines_atlas.models import Provenance
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)


def _receipt(payload: bytes, source_id: str = "au-mbs") -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="synthetic:australian-denominator",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction="AUS",
            authority="Synthetic fixture",
            dataset_title="Synthetic source denominator",
            catalog_version="fixture-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://fixtures.invalid/denominator"),
            retrieved_at=datetime(2026, 8, 30, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="synthetic-native-inventory",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


class _SchemaChecker(Protocol):
    """Typed boundary for jsonschema's dynamically generated validator."""

    def is_valid(self, instance: object) -> bool: ...


def _schema_accepts(model: type[BaseModel], document: object) -> bool:
    validator = cast(
        "_SchemaChecker", Draft202012Validator(model.model_json_schema())
    )
    return validator.is_valid(document)


def test_every_mbs_field_has_one_explicit_semantic_and_type_contract() -> None:
    fields = mbs_field_contracts()
    assert tuple(field.native_name for field in fields) == MBS_NATIVE_FIELDS
    assert len({field.native_name for field in fields}) == 40
    by_name = {field.native_name: field for field in fields}
    assert by_name["ItemNum"].value_type == "identifier"
    assert by_name["ScheduleFee"].value_type == "aud_decimal"
    assert by_name["ScheduleFee"].target_table == "fees"
    assert by_name["DescriptionStartDate"].value_type == "source_date"
    assert by_name["DerivedFee"].value_type == "source_text"
    assert by_name["EMSNPercentageCap"].value_type == "percentage"


def test_mbs_denominator_preserves_every_field_and_missing_vs_null() -> None:
    payload = b"<MBS_XML><Data><ItemNum>001</ItemNum><Description/><Group> P7 </Group></Data></MBS_XML>"
    batch = parse_mbs_source_xml(payload, _receipt(payload))
    fields = tuple(mbs_native_fields(batch))
    assert len(fields) == 40
    by_path = {field.schema_path: field for field in fields}
    assert by_path["/MBS_XML/Data/ItemNum"].value == "001"
    assert by_path["/MBS_XML/Data/Group"].value == " P7 "
    assert by_path["/MBS_XML/Data/Description"].state == "null"
    assert by_path["/MBS_XML/Data/ScheduleFee"].state == "missing_field"
    assert all(
        field.record_id == batch.records[0].source_record_id for field in fields
    )
    coverage = summarize_native_fields(fields)
    assert coverage.occurrence_count == 40
    assert coverage.record_count == 1
    assert coverage.missing_count == 37
    assert coverage.null_count == 1
    assert coverage.value_count == 2
    assert coverage == summarize_native_fields(iter(fields))


def test_full_mbs_schema_cannot_silently_drop_one_of_the_forty_fields() -> None:
    body = "".join(f"<{name}>{name}</{name}>" for name in MBS_NATIVE_FIELDS)
    payload = f"<MBS_XML><Data>{body}</Data></MBS_XML>".encode()
    batch = parse_mbs_source_xml(payload, _receipt(payload))
    fields = tuple(mbs_native_fields(batch))
    assert {field.value for field in fields} == set(MBS_NATIVE_FIELDS)
    full = summarize_native_fields(fields)
    partial = summarize_native_fields(fields[:-1])
    assert full.denominator_sha256 != partial.denominator_sha256
    assert full.occurrence_count != partial.occurrence_count


def _workbook() -> MbsWorkbookBatch:
    return MbsWorkbookBatch(
        schema_era="legacy-fixture-v1",
        provenance=Provenance(
            source_id="au-mbs-p7-legacy-workbook",
            source_uri="https://fixtures.invalid/workbook",
            source_sha256="a" * 64,
        ),
        sheets=tuple(
            MbsWorkbookSheet(
                name=f"Sheet {i}",
                path=f"xl/worksheets/sheet{i}.xml",
                relationship_id=f"rId{i}",
                dimension="A1:D1",
                present_properties=(
                    "name",
                    "relationship_id",
                    "path",
                    "dimension",
                ),
                cells=(
                    MbsWorkbookCell(
                        coordinate="A1",
                        raw_value="001",
                        display_value="001",
                        present_properties=(
                            "coordinate",
                            "raw_value",
                            "display_value",
                        ),
                    ),
                    MbsWorkbookCell(
                        coordinate="B1",
                        formula="1+1",
                        raw_value="2",
                        style_index=3,
                        present_properties=(
                            "coordinate",
                            "formula",
                            "raw_value",
                            "style_index",
                        ),
                    ),
                    MbsWorkbookCell(
                        coordinate="C1",
                        cell_type="e",
                        raw_value="#N/A",
                        present_properties=(
                            "coordinate",
                            "cell_type",
                            "raw_value",
                        ),
                    ),
                    MbsWorkbookCell(
                        coordinate="D1", present_properties=("coordinate",)
                    ),
                ),
            )
            for i in range(1, 5)
        ),
    )


def test_all_workbook_sheets_cells_and_formula_error_states_are_inventoried() -> (
    None
):
    fields = tuple(workbook_native_fields(_workbook()))
    assert len(fields) == 4 * (4 + 4 * 6)
    assert sum(field.value == "1+1" for field in fields) == 4
    assert sum(field.value == "#N/A" for field in fields) == 4
    assert sum(field.value == "e" for field in fields) == 4
    assert sum(field.value == "3" for field in fields) == 4
    assert len({field.record_id for field in fields}) == 20
    assert len({(field.record_id, field.path) for field in fields}) == len(
        fields
    )
    assert summarize_native_fields(fields).occurrence_count == len(fields)


PBS = b'<p:schedule xmlns:p="http://schema.pbs.gov.au/" xmlns:d="http://docbook.org/ns/docbook"><p:pharmaceutical-item code="0001"><d:para>Before <d:emphasis role="bold">inside</d:emphasis> after</d:para><p:unknown-new-field unit="mg"/></p:pharmaceutical-item><p:pharmaceutical-item code="0002"/></p:schedule>'


def test_pbs_inventory_covers_all_elements_attributes_text_and_tails() -> None:
    fields = tuple(pbs_native_fields(PBS, _receipt(PBS, "au-pbs")))
    # Six elements, two slots per element (text and tail), four attributes.
    assert len(fields) == 16
    assert {field.value for field in fields if field.value} >= {
        "0001",
        "0002",
        "Before ",
        "inside",
        " after",
        "bold",
        "mg",
    }
    assert any("unknown-new-field" in field.schema_path for field in fields)
    assert len({(field.record_id, field.path) for field in fields}) == len(
        fields
    )
    assert summarize_native_fields(fields).record_count == 6
    assert summarize_native_fields(fields).field_count < len(fields)


@pytest.mark.parametrize(
    "payload",
    [
        b"<schedule/>",
        b'<p:other xmlns:p="http://schema.pbs.gov.au/"/>',
        b"not XML",
    ],
)
def test_pbs_denominator_rejects_wrong_source_shapes(payload: bytes) -> None:
    with pytest.raises(ValueError, match=r"PBS namespace/root|XML"):
        tuple(pbs_native_fields(payload, _receipt(payload, "au-pbs")))


def test_pbs_denominator_is_bound_to_receipt_bytes() -> None:
    with pytest.raises(ValueError, match="match source bytes"):
        tuple(pbs_native_fields(PBS + b" ", _receipt(PBS, "au-pbs")))


@pytest.mark.parametrize(
    ("source", "subject", "dimension"),
    [
        ("au-mbs", "service", "service_benefit"),
        ("au-mbs-p7-legacy-workbook", "service", "service_benefit"),
        ("au-pbs", "pbs_item", "funding"),
        ("au-pbs", "pbs_item", "formulary"),
        ("au-pbs", "terminology_reference", "terminology"),
    ],
)
def test_table_contract_allows_only_source_appropriate_dimensions(
    source: str, subject: str, dimension: str
) -> None:
    contract = AustralianTableContract.model_validate({
        "source_id": source,
        "subject_kind": subject,
        "dimension": dimension,
    })
    assert contract.schema_version == "1.0"
    assert contract.absence_interpretation == "unknown"
    assert contract.mapping_status == "source_native"
    assert _schema_accepts(
        AustralianTableContract, contract.model_dump(mode="json")
    )
    assert (
        AustralianTableContract.model_validate_json(contract.model_dump_json())
        == contract
    )


@pytest.mark.parametrize(
    "update",
    [
        {"subject_kind": "pbs_item"},
        {"dimension": "funding"},
        {"dimension": "regulatory"},
        {
            "source_id": "au-pbs",
            "subject_kind": "terminology_reference",
            "dimension": "funding",
        },
        {"mapping_status": "reviewed"},
        {"mapping_status": "candidate"},
        {"absence_interpretation": "negative"},
    ],
)
def test_semantic_coercions_and_implicit_promotion_are_rejected(
    update: dict[str, str],
) -> None:
    values = {
        "source_id": "au-mbs",
        "subject_kind": "service",
        "dimension": "service_benefit",
        **update,
    }
    with pytest.raises(ValidationError):
        AustralianTableContract.model_validate(values)
    assert not _schema_accepts(AustralianTableContract, values)


def test_occurrences_reject_fabricated_value_state_and_duplicate_identity() -> (
    None
):
    binding = {
        "source_id": "au-mbs",
        "source_sha256": "a" * 64,
        "schema_era": "fixture-v1",
    }
    values = {
        **binding,
        "record_id": "r",
        "path": "/a",
        "schema_path": "/a",
        "value": "001",
        "state": "missing_field",
    }
    with pytest.raises(ValidationError):
        NativeFieldOccurrence.model_validate(values)
    field = NativeFieldOccurrence.model_validate({**values, "state": "value"})
    with pytest.raises(ValueError, match="duplicate"):
        summarize_native_fields([field, field])
    with pytest.raises(ValueError, match="empty"):
        summarize_native_fields([])


def test_contract_rejects_adapter_field_denominator_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(contracts, "MBS_NATIVE_FIELDS", MBS_NATIVE_FIELDS[:-1])
    with pytest.raises(ValueError, match="denominator differs"):
        mbs_field_contracts()


@pytest.mark.parametrize("change", ["source", "record", "field"])
def test_mbs_inventory_rejects_source_record_or_field_relabelling(
    change: str,
) -> None:
    payload = b"<MBS_XML><Data><ItemNum>1</ItemNum></Data></MBS_XML>"
    batch = parse_mbs_source_xml(payload, _receipt(payload))
    record = batch.records[0]
    if change == "source":
        batch = batch.model_copy(
            update={
                "provenance": batch.provenance.model_copy(
                    update={"source_id": "au-pbs"}
                )
            }
        )
    elif change == "record":
        record = record.model_copy(
            update={
                "provenance": record.provenance.model_copy(
                    update={"source_sha256": "b" * 64}
                )
            }
        )
        batch = batch.model_copy(update={"records": (record,)})
    else:
        record = record.model_copy(
            update={
                "fields": (
                    *record.fields,
                    MbsNativeField(name="Unknown", value="x"),
                )
            }
        )
        batch = batch.model_copy(update={"records": (record,)})
    with pytest.raises(ValueError, match=r"mismatch|not covered"):
        tuple(mbs_native_fields(batch))


@pytest.mark.parametrize(
    "change", ["source", "duplicate_sheet", "coordinate", "digest"]
)
def test_workbook_inventory_rejects_unbound_or_ambiguous_sources(
    change: str,
) -> None:
    batch = _workbook()
    if change == "source":
        batch = batch.model_copy(
            update={
                "provenance": batch.provenance.model_copy(
                    update={"source_id": "au-mbs"}
                )
            }
        )
    elif change == "duplicate_sheet":
        batch = batch.model_copy(
            update={"sheets": (*batch.sheets, batch.sheets[0])}
        )
    elif change == "coordinate":
        sheet = batch.sheets[0].model_copy(
            update={
                "cells": (
                    MbsWorkbookCell(
                        coordinate="invalid", present_properties=("coordinate",)
                    ),
                )
            }
        )
        batch = batch.model_copy(update={"sheets": (sheet,)})
    else:
        batch = batch.model_copy(
            update={
                "provenance": batch.provenance.model_copy(
                    update={"source_sha256": None}
                )
            }
        )
    with pytest.raises(
        ValueError, match=r"mismatch|duplicate|coordinate|source_sha256"
    ):
        tuple(workbook_native_fields(batch))


def test_coverage_cannot_mix_source_snapshots_or_schema_eras() -> None:
    fields = tuple(workbook_native_fields(_workbook()))
    for update in (
        {"source_sha256": "b" * 64},
        {"schema_era": "other"},
        {"source_id": "au-pbs"},
    ):
        with pytest.raises(ValueError, match="bindings differ"):
            summarize_native_fields([
                fields[0],
                fields[1].model_copy(update=update),
            ])


@given(st.one_of(st.none(), st.text()))
def test_native_value_json_roundtrip_and_content_bound_coverage(
    value: str | None,
) -> None:
    field = NativeFieldOccurrence(
        source_id="au-mbs",
        source_sha256="a" * 64,
        schema_era="fixture-v1",
        record_id="native:001",
        path="/Description",
        schema_path="/Description",
        value=value,
        state="null" if value is None else "value",
    )
    restored = NativeFieldOccurrence.model_validate_json(
        field.model_dump_json()
    )
    assert restored == field
    assert _schema_accepts(NativeFieldOccurrence, field.model_dump(mode="json"))
    before = summarize_native_fields([field])
    assert before == summarize_native_fields([restored])
    changed = field.model_copy(
        update={"value": (value or "") + "x", "state": "value"}
    )
    assert (
        before.denominator_sha256
        != summarize_native_fields([changed]).denominator_sha256
    )


def test_inventory_revalidates_untrusted_model_copy_values() -> None:
    field = next(workbook_native_fields(_workbook()))
    tampered = field.model_copy(update={"state": "null", "value": "not null"})
    with pytest.raises(ValueError, match="value and state disagree"):
        summarize_native_fields([tampered])


def test_mbs_contract_rejects_relabelled_serialized_mapping() -> None:
    values = mbs_field_contracts()[0].model_dump()
    values["value_type"] = "aud_decimal"
    with pytest.raises(ValueError, match="mapping differs"):
        MbsFieldContract.model_validate(values)


@pytest.mark.parametrize("change", ["duplicate", "empty", "record_count"])
def test_serialized_coverage_denominators_are_consistent(change: str) -> None:
    coverage = summarize_native_fields(workbook_native_fields(_workbook()))
    values = coverage.model_dump()
    if change == "duplicate":
        values["fields"] = (coverage.fields[0], coverage.fields[0])
    elif change == "empty":
        values["fields"] = (
            coverage.fields[0].model_copy(
                update={"value_count": 0, "null_count": 0, "missing_count": 0}
            ),
        )
    else:
        values["record_count"] = coverage.occurrence_count + 1
    with pytest.raises(
        ValueError, match=r"unique|non-empty|denominator exceeds"
    ):
        NativeFieldCoverage.model_validate(values)


def test_versioned_json_schemas_and_mbs_field_registry_match_runtime() -> None:
    root = Path(__file__).parents[1] / "contracts" / "australian-source" / "v1"
    for name, model in (
        ("table", AustralianTableContract),
        ("native-field", NativeFieldOccurrence),
        ("coverage", NativeFieldCoverage),
    ):
        assert (
            json.loads((root / f"{name}.schema.json").read_text())
            == model.model_json_schema()
        )
    assert json.loads((root / "mbs-fields.json").read_text()) == [
        field.model_dump(mode="json") for field in mbs_field_contracts()
    ]


def test_portable_schema_rejects_cross_domain_table() -> None:
    document = {
        "source_id": "au-mbs",
        "subject_kind": "pbs_item",
        "dimension": "funding",
    }
    assert not _schema_accepts(AustralianTableContract, document)


def test_portable_schema_rejects_contradictory_native_state() -> None:
    field = next(workbook_native_fields(_workbook()))
    document = field.model_dump(mode="json")
    document["state"] = "null"
    assert not _schema_accepts(NativeFieldOccurrence, document)


@pytest.mark.parametrize("level", ["sheet", "cell"])
def test_old_workbook_projections_require_reparse_for_presence(
    level: str,
) -> None:
    batch = _workbook()
    sheet = batch.sheets[0]
    if level == "sheet":
        sheet = sheet.model_copy(update={"present_properties": None})
    else:
        cell = sheet.cells[0].model_copy(update={"present_properties": None})
        sheet = sheet.model_copy(update={"cells": (cell,)})
    batch = batch.model_copy(update={"sheets": (sheet,)})
    with pytest.raises(ValueError, match="presence is unknown; reparse"):
        tuple(workbook_native_fields(batch))


@pytest.mark.parametrize(
    "properties", [(), ("coordinate", "coordinate"), ("coordinate",)]
)
def test_cell_presence_cannot_hide_a_value(properties: tuple[str, ...]) -> None:
    with pytest.raises(
        ValueError, match=r"property presence|property has a value"
    ):
        MbsWorkbookCell.model_validate({
            "coordinate": "A1",
            "raw_value": "1",
            "present_properties": properties,
        })


@pytest.mark.parametrize(
    "properties",
    [
        (),
        ("name", "relationship_id", "path", "path"),
        ("name", "relationship_id", "path"),
    ],
)
def test_sheet_presence_cannot_hide_dimension(
    properties: tuple[str, ...],
) -> None:
    values = _workbook().sheets[0].model_dump()
    values["present_properties"] = properties
    with pytest.raises(
        ValueError, match=r"property presence|dimension has a value"
    ):
        MbsWorkbookSheet.model_validate(values)
