"""Legacy-workbook-to-XML mappings remain deterministic candidates."""

# pyright: reportPrivateUsage=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportArgumentType=false

import pytest
from pydantic import ValidationError
from test_mbs_historical_comparison import build, data, key, xml
from test_mbs_workbook_domain import fixture
from test_mbs_workbook_silver import (
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic receipt
)

from global_medicines_atlas.mbs_workbook_xml_mapping import (
    MbsWorkbookXmlCandidateMatch,
    MbsWorkbookXmlCandidateReport,
    MbsWorkbookXmlFieldMapping,
    MbsWorkbookXmlSchemaMapping,
    build_mbs_workbook_xml_candidate_report,
    declare_mbs_workbook_xml_mapping,
)


def inputs():
    payload = fixture()
    cohort = build(
        xml(data("00123", sub="")),
        (key("00123", state="missing", value=None),),
        table="services",
        schema_era="mbs-xml-fixture-v1",
    )
    mapping = declare_mbs_workbook_xml_mapping(
        xml_schema_era="mbs-xml-fixture-v1"
    )
    return payload, cohort, mapping


def test_mapping_is_exhaustive_and_keeps_legacy_annotations_source_only():
    _, _, mapping = inputs()
    fields = {field.workbook_native_header: field for field in mapping.fields}
    assert fields["ItemNum"].xml_native_name == "ItemNum"
    assert fields["ScheduleFee"].disposition == "exact_native_header"
    assert fields["Element"].xml_native_name is None
    assert fields["Declining List"].disposition == "legacy_annotation_only"
    assert (
        MbsWorkbookXmlSchemaMapping.model_validate_json(
            mapping.model_dump_json()
        )
        == mapping
    )


def test_candidate_report_matches_literal_keys_without_semantic_promotion():
    payload, cohort, mapping = inputs()
    report = build_mbs_workbook_xml_candidate_report(
        payload, _receipt(payload), cohort, mapping
    )
    assert report.qualification == "fixture_candidate_only"
    assert report.semantic_equivalence_asserted is False
    assert report.publication_performed is False
    assert report.absence_interpretation == "unknown"
    assert len(report.matches) == 3
    assert {match.match_status for match in report.matches} == {"matched_once"}
    assert [match.workbook_occurrence_id for match in report.matches] == sorted(
        match.workbook_occurrence_id for match in report.matches
    )
    assert (
        MbsWorkbookXmlCandidateReport.model_validate_json(
            report.model_dump_json()
        )
        == report
    )


def test_unobserved_keys_remain_unknown_and_output_is_deterministic():
    payload, cohort, mapping = inputs()
    first = build_mbs_workbook_xml_candidate_report(
        payload, _receipt(payload), cohort, mapping
    )
    other = build(
        xml(data("99999")),
        (key("99999"),),
        table="services",
        schema_era="mbs-xml-fixture-v1",
    )
    second = build_mbs_workbook_xml_candidate_report(
        payload, _receipt(payload), other, mapping
    )
    assert first == build_mbs_workbook_xml_candidate_report(
        payload, _receipt(payload), cohort, mapping
    )
    assert {match.match_status for match in second.matches} == {"not_observed"}


def test_contracts_reject_mapping_report_and_status_tampering():
    payload, cohort, mapping = inputs()
    report = build_mbs_workbook_xml_candidate_report(
        payload, _receipt(payload), cohort, mapping
    )
    changed = mapping.model_dump()
    legacy_index = next(
        index
        for index, field in enumerate(changed["fields"])
        if field["workbook_native_header"] == "Element"
    )
    changed["fields"][legacy_index]["disposition"] = "exact_native_header"
    changed["fields"][legacy_index]["xml_native_name"] = changed["fields"][
        legacy_index
    ]["workbook_native_header"]
    with pytest.raises(ValidationError, match="field mapping differs"):
        MbsWorkbookXmlSchemaMapping.model_validate(changed)
    changed_report = report.model_dump()
    changed_report["matches"][0]["match_status"] = "ambiguous"
    with pytest.raises(ValidationError, match="match status differs"):
        MbsWorkbookXmlCandidateReport.model_validate(changed_report)
    changed_report = report.model_dump()
    changed_report["report_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="report digest differs"):
        MbsWorkbookXmlCandidateReport.model_validate(changed_report)

    changed_report = report.model_dump()
    changed_report["mapping"]["xml_schema_era"] = "other-era"
    # Rebind the nested mapping only far enough to exercise the report-era gate.
    changed_report["mapping"] = declare_mbs_workbook_xml_mapping(
        xml_schema_era="other-era"
    ).model_dump()
    with pytest.raises(ValidationError, match="XML era differs"):
        MbsWorkbookXmlCandidateReport.model_validate(changed_report)

    changed_report = report.model_dump()
    changed_report["matches"] = changed_report["matches"][::-1]
    with pytest.raises(ValidationError, match="not deterministic"):
        MbsWorkbookXmlCandidateReport.model_validate(changed_report)


def test_individual_mapping_and_match_contracts_are_content_bound():
    with pytest.raises(ValidationError, match="disposition differs"):
        MbsWorkbookXmlFieldMapping(
            workbook_native_header="Element",
            disposition="exact_native_header",
        )
    with pytest.raises(ValidationError, match="renamed"):
        MbsWorkbookXmlFieldMapping(
            workbook_native_header="ItemNum",
            xml_native_name="Other",
            disposition="exact_native_header",
        )
    with pytest.raises(ValidationError, match="candidate key differs"):
        MbsWorkbookXmlCandidateMatch(
            workbook_occurrence_id="fixture:sheet#row=2",
            sheet_name="Sheet1",
            row_index=2,
            item_num="00123",
            sub_item_state="missing",
            xml_native_id="mbs-key:" + "0" * 64,
            match_status="not_observed",
        )


def test_mapping_digest_is_revalidated():
    mapping = declare_mbs_workbook_xml_mapping(xml_schema_era="fixture-era")
    changed = mapping.model_dump()
    changed["mapping_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="mapping digest differs"):
        MbsWorkbookXmlSchemaMapping.model_validate(changed)


@pytest.mark.parametrize("era", ["", " padded", "padded "])
def test_xml_schema_era_is_explicit(era: str):
    with pytest.raises(
        ValidationError, match=r"schema era|at least 1 character"
    ):
        declare_mbs_workbook_xml_mapping(xml_schema_era=era)
