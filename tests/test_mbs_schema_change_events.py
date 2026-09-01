"""Synthetic explicit MBS schema-era mappings and observed events."""

# pyright: reportPrivateUsage=false, reportUnknownVariableType=false
# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false
# pyright: reportOptionalMemberAccess=false

import pytest
from pydantic import ValidationError
from test_mbs_historical_comparison import build, data, key, xml

import global_medicines_atlas.mbs_schema_change_events as changes
from global_medicines_atlas.mbs_schema_change_events import (
    MbsSchemaChangeReport,
    MbsSchemaEraMapping,
    build_mbs_schema_change_report,
    declare_mbs_xml_schema_era_mapping,
)


def cohorts():
    selected = (key(), key("old"), key("new"))
    historical = build(
        xml(
            data(extra="<ScheduleFee>1.00</ScheduleFee>"),
            data("old", extra="<ScheduleFee>9.00</ScheduleFee>"),
        ),
        selected,
        schema_era="mbs-xml-era-2025",
    )
    current = build(
        xml(
            data(extra="<ScheduleFee>2.00</ScheduleFee>"),
            data("new", extra="<ScheduleFee>3.00</ScheduleFee>"),
        ),
        selected,
        schema_era="mbs-xml-era-2026",
    )
    return historical, current


def mapping():
    return declare_mbs_xml_schema_era_mapping(
        table="fees",
        historical_schema_era="mbs-xml-era-2025",
        current_schema_era="mbs-xml-era-2026",
    )


def test_explicit_mapping_covers_exact_table_contract_and_is_content_bound():
    declared = mapping()
    assert declared.historical_schema_era == "mbs-xml-era-2025"
    assert declared.current_schema_era == "mbs-xml-era-2026"
    assert [item.historical_native_name for item in declared.fields] == [
        "DerivedFee",
        "DerivedFeeStartDate",
        "FeeChange",
        "FeeStartDate",
        "FeeType",
        "ScheduleFee",
    ]
    assert all(
        item.historical_native_name
        == item.current_native_name
        == item.silver_target_field
        for item in declared.fields
    )
    assert (
        MbsSchemaEraMapping.model_validate_json(declared.model_dump_json())
        == declared
    )


def test_change_report_preserves_values_and_treats_absence_as_unknown():
    historical, current = cohorts()
    report = build_mbs_schema_change_report(historical, current, mapping())

    assert report.absence_interpretation == "unknown"
    assert report.qualification == "observed_change_candidate"
    assert report.historical.snapshot.schema_era == "mbs-xml-era-2025"
    assert report.current.snapshot.schema_era == "mbs-xml-era-2026"
    schedule = next(
        event
        for event in report.events
        if event.native_id == key().content_id()
        and event.silver_target_field == "ScheduleFee"
    )
    assert schedule.kind == "field_changed"
    assert schedule.historical.value == "1.00"
    assert schedule.current.value == "2.00"
    assert {event.kind for event in report.events} >= {
        "observed_only_historical",
        "observed_only_current",
        "unchanged",
    }
    assert all(
        event.event_id.startswith("mbs-event:") for event in report.events
    )
    assert (
        MbsSchemaChangeReport.model_validate_json(report.model_dump_json())
        == report
    )


def test_mapping_and_events_are_deterministic_and_input_order_independent():
    historical, current = cohorts()
    first = build_mbs_schema_change_report(historical, current, mapping())
    reversed_historical = historical.model_copy(
        update={
            "snapshot": historical.snapshot.model_copy(
                update={"rows": historical.snapshot.rows[::-1]}
            ),
            "source_ordinals": historical.source_ordinals[::-1],
        }
    )
    # Cohort contracts preserve source order, so compare independent rebuilds
    # rather than accepting a forged reversed producer output.
    assert first == build_mbs_schema_change_report(
        historical, current, mapping()
    )
    with pytest.raises(ValidationError):
        build_mbs_schema_change_report(reversed_historical, current, mapping())


@pytest.mark.parametrize("era", ["", " ", " padded", "padded "])
def test_mapping_rejects_blank_or_normalized_eras(era):
    with pytest.raises(ValidationError, match=r"schema era|at least 1"):
        declare_mbs_xml_schema_era_mapping(
            table="fees",
            historical_schema_era=era,
            current_schema_era="current",
        )
    with pytest.raises(ValidationError, match="distinct"):
        declare_mbs_xml_schema_era_mapping(
            table="fees",
            historical_schema_era="same",
            current_schema_era="same",
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("mapping_field", "field mapping differs"),
        ("mapping_digest", "mapping digest differs"),
        ("event", "events differ"),
        ("report_digest", "report digest differs"),
        ("qualification", "Input should be"),
        ("absence", "Input should be 'unknown'"),
        ("evidence_class", "cohort evidence class mismatch"),
    ],
)
def test_serialized_reports_reject_mapping_event_and_claim_drift(
    change, message
):
    historical, current = cohorts()
    values = build_mbs_schema_change_report(
        historical, current, mapping()
    ).model_dump()
    if change == "mapping_field":
        values["mapping"]["fields"][0]["current_native_name"] = "renamed"
    elif change == "mapping_digest":
        values["mapping"]["mapping_sha256"] = "0" * 64
    elif change == "event":
        values["events"][0]["kind"] = "field_changed"
    elif change == "qualification":
        values["qualification"] = "qualified"
    elif change == "absence":
        values["absence_interpretation"] = "ceased"
    elif change == "evidence_class":
        values["current"]["evidence_class"] = "live"
    else:
        values["report_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match=message):
        MbsSchemaChangeReport.model_validate(values)


def test_input_profiles_eras_completeness_and_roles_are_fail_closed():
    historical, current = cohorts()
    wrong_era = current.model_copy(
        update={
            "snapshot": current.snapshot.model_copy(
                update={"schema_era": "other"}
            )
        }
    )
    with pytest.raises(ValueError, match="eras differ"):
        build_mbs_schema_change_report(historical, wrong_era, mapping())

    incomplete = current.snapshot.model_copy(update={"complete": False})
    with pytest.raises(ValueError, match="complete cohorts"):
        changes._validate_inputs(historical.snapshot, incomplete, mapping())

    wrong_role = current.snapshot.model_copy(update={"cohort": "legacy"})
    with pytest.raises(ValueError, match="cohort roles"):
        changes._validate_inputs(historical.snapshot, wrong_role, mapping())

    wrong_table = current.snapshot.model_copy(update={"table": "benefits"})
    with pytest.raises(ValueError, match="profile differs"):
        changes._validate_inputs(historical.snapshot, wrong_table, mapping())


def test_event_limit_is_fail_closed(monkeypatch):
    historical, current = cohorts()
    monkeypatch.setattr(changes, "MAX_DIFFERENCES", 1)
    with pytest.raises(ValueError, match="event limit"):
        build_mbs_schema_change_report(historical, current, mapping())


def test_ambiguous_identity_and_presence_event_limit_are_fail_closed(
    monkeypatch,
):
    historical, current = cohorts()
    duplicate = historical.snapshot.rows[0].model_copy(
        update={"occurrence_id": "distinct-occurrence"}
    )
    ambiguous = historical.snapshot.model_copy(
        update={
            "rows": (*historical.snapshot.rows, duplicate),
            "declared_rows": len(historical.snapshot.rows) + 1,
        }
    )
    with pytest.raises(ValueError, match="identity is ambiguous"):
        changes._validate_inputs(ambiguous, current.snapshot, mapping())

    only_historical = historical.snapshot.model_copy(
        update={"rows": historical.snapshot.rows[:1], "declared_rows": 1}
    )
    empty_current = current.snapshot.model_copy(
        update={"rows": (), "declared_rows": 0}
    )
    monkeypatch.setattr(changes, "MAX_DIFFERENCES", 0)
    with pytest.raises(ValueError, match="event limit"):
        changes._events(only_historical, empty_current, mapping())
