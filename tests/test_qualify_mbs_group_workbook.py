"""Group workbook qualification uses actual workbook rows and native consumers."""

import io
import json
import zipfile
from contextlib import nullcontext
from pathlib import Path

import pytest
from scripts import qualify_mbs_group_workbook as module
from scripts import qualify_mbs_q1hr_benefit_scale_comparison as reader
from test_mbs_group_workbook_silver import context, fixture_payload


def test_local_context_stops_before_transport(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify("a" * 40)


def test_actual_synthetic_complete_package_matches_independent_source_reader(
    tmp_path,
):
    payload = fixture_payload()
    report = module.qualify_object(payload, context(payload), tmp_path)
    assert report["coverage"]["native_primary_rows"] == 1
    assert report["coverage"]["native_workbook_cells"] == 18
    assert report["independent_primary_native_fields_equal"] == 8
    assert report["duckdb_consumer_counts_equal"] is True
    assert report["unqualified_pooling_blocked"] is True
    assert report["source_date_alignment"] == "unqualified"


@pytest.mark.parametrize("shared", [False, True])
def test_independent_reader_excludes_phonetic_guides(shared):
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rich = "<r><t>first</t></r><rPh><t>guide</t></rPh><r><t>last</t></r>"
    cell = (
        '<c r="A4" t="s"><v>0</v></c>'
        if shared
        else f'<c r="A4" t="inlineStr"><is>{rich}</is></c>'
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{namespace}"><sheetData><row r="4">{cell}</row></sheetData></worksheet>',
        )
        if shared:
            archive.writestr(
                "xl/sharedStrings.xml",
                f'<sst xmlns="{namespace}"><si>{rich}</si></sst>',
            )
    assert reader.workbook_rows(output.getvalue())[0][0] == "firstlast"


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("GITHUB_REPOSITORY", "other/repo"),
        ("GITHUB_REF", "refs/heads/other"),
        ("GITHUB_SHA", "b" * 40),
    ],
)
def test_hosted_identity_must_match_before_source_access(
    monkeypatch, variable, value
):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify("a" * 40)


@pytest.mark.parametrize("mutation", ["denominator", "value"])
def test_independent_reader_disagreement_rejects_candidate(
    tmp_path, monkeypatch, mutation
):
    payload = fixture_payload()
    if mutation == "denominator":
        altered = []
    else:
        original = module.source_reader.workbook_rows(payload)
        altered = [("SYNTHETIC CHANGED", *original[0][1:])]
    monkeypatch.setattr(
        module.source_reader, "workbook_rows", lambda _: altered
    )
    with pytest.raises(ValueError, match="independent native"):
        module.qualify_object(payload, context(payload), tmp_path)


def test_hosted_driver_uses_exact_bound_source_and_removes_derivatives(
    monkeypatch,
):
    payload = fixture_payload()
    source = context(payload)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setattr(module, "load_group_workbook_source", lambda _: source)
    reference = {"synthetic": True}
    monkeypatch.setattr(module, "load_reference", lambda _: reference)
    monkeypatch.setattr(module.source_reader, "DATASET", source.dataset)
    monkeypatch.setattr(
        module.source_reader, "REVISION", source.source_revision
    )
    monkeypatch.setattr(
        module.httpx, "Client", lambda **_: nullcontext(object())
    )
    observed = []
    original = module.qualify_object

    def fetch(_, selected):
        assert selected is reference
        return payload

    def qualify(data, bound, directory):
        assert data == payload
        assert bound == source
        observed.append(directory)
        return original(data, bound, directory)

    monkeypatch.setattr(module.source_reader, "fetch_exact_source_bytes", fetch)
    monkeypatch.setattr(module, "qualify_object", qualify)
    report = module.qualify("a" * 40)
    assert report["temporary_derivatives_removed"] is True
    assert observed
    assert not observed[0].exists()
    assert report["boundaries"]["new_admissions"] == 0
    assert report["boundaries"]["publications"] == 0


def test_retained_actual_group_workbook_qualification_preserves_exceptions():
    path = (
        Path(__file__).resolve().parents[1]
        / "quality/qualifications/mbs-group-workbook-native-qualification-20261022-39669037532.json"
    )
    report = json.loads(path.read_bytes())
    result = report["result"]
    assert (
        report["workflow_commit"] == "4e6d4cd6159c9d11518f2aa0d30fc24af6ec8dfb"
    )
    assert result["coverage"]["native_primary_rows"] == 164555
    assert result["coverage"]["native_workbook_cells"] == 1316692
    assert (
        result["coverage"]["benefit_conversion_statuses"]["unrepresentable"]
        == 23987
    )
    assert result["complete_source_restore"] is True
    assert result["unqualified_pooling_blocked"] is True
    assert report["boundaries"]["new_admissions"] == 0
    assert report["boundaries"]["benefit_equivalence_established"] is False
