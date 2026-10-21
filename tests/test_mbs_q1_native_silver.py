"""Hosted Q1 candidate qualification uses exact inputs and aggregate receipts."""

import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest
import yaml
from scripts import qualify_mbs_q1_native_silver as module
from test_mbs_demographic_extraction import rewrite_package, workbook
from test_mbs_demographic_silver import source

PAYLOAD = b"Year,Month of Processing,Item Number,State,Age Range,Gender,Services,Benefit\n2016,3,00123,SYNTHETIC,Unknown,F,2,12.5\n"


def test_native_csv_qualification_restores_without_emitting_values(
    tmp_path: Path,
):
    context = source("csv", PAYLOAD)
    report = module.qualify_object(PAYLOAD, context, tmp_path, expected_rows=1)
    assert report["source_native_primary_fields_equal"] == 8
    assert report["coverage"]["literal_unknown_age_rows"] == 1
    assert report["unqualified_pooling_blocked"] is True
    assert report["candidate_only"] is True
    assert "SYNTHETIC" not in json.dumps(report)
    assert "12.5" not in json.dumps(report)
    assert "native_age_groups" not in report["coverage"]


def test_independent_row_denominator_is_enforced(tmp_path: Path):
    with pytest.raises(ValueError, match="independent source row denominator"):
        module.qualify_object(
            PAYLOAD, source("csv", PAYLOAD), tmp_path, expected_rows=2
        )


def test_local_qualification_stops_before_network(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify("a" * 40)


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("GITHUB_REPOSITORY", "other/repo"),
        ("GITHUB_REF", "refs/heads/other"),
        ("GITHUB_SHA", "b" * 40),
    ],
)
def test_wrong_hosted_identity_stops_before_network(
    monkeypatch, variable, value
):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify("a" * 40)


def test_retained_b1_b2_contexts_bind_exact_existing_objects():
    contexts = [module.source_context(index) for index in range(2)]
    assert (
        contexts[0].source_sha256 == module.source_reader.OBJECTS[0]["sha256"]
    )
    assert (
        contexts[1].source_sha256 == module.source_reader.OBJECTS[1]["sha256"]
    )
    assert contexts[0].source_measure_id != contexts[1].source_measure_id


def test_workflow_only_uploads_aggregate_receipt():
    text = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/mbs-q1-native-silver-candidate.yml"
    ).read_text()
    assert "refs/heads/main" in text
    assert "path: q1-native-silver-candidate.json" in text
    assert "contents: read" in text
    assert "persist-credentials: false" in text
    assert "issues: write" not in text
    assert "*.parquet" not in text


def test_independent_field_parity_rejects_changed_reader(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        module.source_reader, "csv_rows", lambda _: [("changed",) * 8]
    )
    with pytest.raises(ValueError, match="native field parity"):
        module.qualify_object(
            PAYLOAD, source("csv", PAYLOAD), tmp_path, expected_rows=1
        )


def test_qualification_rejects_different_rebuild(tmp_path: Path, monkeypatch):
    original = module.build_demographic_package

    def build(payload, context, output):
        report = original(payload, context, output)
        if output.name == "second":
            report["changed"] = True
        return report

    monkeypatch.setattr(module, "build_demographic_package", build)
    with pytest.raises(ValueError, match="rebuild differs"):
        module.qualify_object(
            PAYLOAD, source("csv", PAYLOAD), tmp_path, expected_rows=1
        )


def test_cli_suppresses_source_bearing_exception(
    tmp_path: Path, monkeypatch, capsys
):
    def fail(_):
        raise ValueError("SYNTHETIC_SOURCE_DETAIL")

    monkeypatch.setattr(module, "qualify", fail)
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["qualify", "--exact-commit", "a" * 40, "--output", str(output)],
    )
    with pytest.raises(SystemExit, match="source details withheld"):
        module.main()
    assert not output.exists()
    assert "SYNTHETIC_SOURCE_DETAIL" not in str(capsys.readouterr())


def test_workbook_parity_uses_independent_source_reader(tmp_path: Path):
    values = ("2016", "3", "00123", "SYNTHETIC", "Unknown", "F", "2", "12.5")
    payload = workbook(
        data_row="".join(
            f'<c r="{chr(65 + i)}4" t="str"><v>{value}</v></c>'
            for i, value in enumerate(values)
        )
    )
    payload = rewrite_package(
        payload,
        lambda _, content: content,
        {
            "xl/sharedStrings.xml": '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'
        },
    )
    report = module.qualify_object(
        payload, source("workbook", payload), tmp_path, expected_rows=1
    )
    assert report["source_native_primary_fields_equal"] == 8
    assert report["native_workbook_cells"] == 18


def hosted_environment(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)


def test_hosted_orchestration_removes_temporary_outputs(monkeypatch):
    hosted_environment(monkeypatch)
    directories = []
    monkeypatch.setattr(
        module.source_reader,
        "fetch_exact_source_bytes",
        lambda *_: b"synthetic",
    )

    def check(_, context, directory, **kwargs):
        directories.append(directory)
        assert directory.exists()
        assert kwargs["expected_rows"] > 0
        return {"source_measure_id": context.source_measure_id}

    monkeypatch.setattr(module, "qualify_object", check)
    report = module.qualify("a" * 40)
    assert report["temporary_derivatives_removed"] is True
    assert len(directories) == 2
    assert all(not directory.exists() for directory in directories)
    assert report["boundaries"]["new_admissions"] == 0


def test_hosted_orchestration_rejects_collapsed_measures(monkeypatch):
    hosted_environment(monkeypatch)
    monkeypatch.setattr(
        module.source_reader,
        "fetch_exact_source_bytes",
        lambda *_: b"synthetic",
    )
    monkeypatch.setattr(
        module,
        "qualify_object",
        lambda *_args, **_kwargs: {"source_measure_id": "collapsed"},
    )
    with pytest.raises(ValueError, match="measures collapsed"):
        module.qualify("a" * 40)


def test_cli_writes_aggregate_only(tmp_path: Path, monkeypatch):
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(module, "qualify", lambda _: {"candidate_only": True})
    monkeypatch.setattr(
        sys,
        "argv",
        ["qualify", "--exact-commit", "a" * 40, "--output", str(output)],
    )
    module.main()
    assert json.loads(output.read_text()) == {"candidate_only": True}


def test_retained_context_digest_mismatch_fails_closed(monkeypatch):
    item = dict(module.source_reader.OBJECTS[0])
    item["sha256"] = "0" * 64
    monkeypatch.setattr(module.source_reader, "OBJECTS", (item,))
    with pytest.raises(ValueError, match="context digest differs"):
        module.source_context(0)


def test_registered_workflow_selects_one_guarded_qualification_lane():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/mbs-q1-source-meaning-diagnostics.yml"
    )
    document = yaml.load(workflow.read_text(), Loader=yaml.BaseLoader)
    mode = document["on"]["workflow_dispatch"]["inputs"]["qualification_scope"]
    assert mode["default"] == "meaning-diagnostics"
    assert mode["options"] == [
        "meaning-diagnostics",
        "native-silver",
        "quarterly-csv",
        "group-csv",
        "quarterly-workbooks",
        "group-workbook-layout",
        "group-workbook-silver",
        "sidecar-layout",
        "archive-members",
    ]
    assert (
        document["jobs"]["qualify"]["if"]
        == "inputs.qualification_scope != 'native-silver' && inputs.qualification_scope != 'quarterly-csv' && inputs.qualification_scope != 'group-csv' && inputs.qualification_scope != 'quarterly-workbooks' && inputs.qualification_scope != 'group-workbook-layout' && inputs.qualification_scope != 'group-workbook-silver' && inputs.qualification_scope != 'sidecar-layout' && inputs.qualification_scope != 'archive-members'"
    )
    native = document["jobs"]["native-silver"]
    assert native["if"] == "inputs.qualification_scope == 'native-silver'"
    assert native["permissions"] == {"contents": "read"}
    run = next(step["run"] for step in native["steps"] if "run" in step)
    assert "test \"${GITHUB_REF}\" = 'refs/heads/main'" in run
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in run
    assert "scripts/qualify_mbs_q1_native_silver.py" in run
    artifact = native["steps"][-1]["with"]
    assert artifact["path"] == "q1-native-silver-candidate.json"


def test_registered_workflow_quarterly_lane_retains_exact_matrix_and_receipts():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/mbs-q1-source-meaning-diagnostics.yml"
    )
    document = yaml.load(workflow.read_text(), Loader=yaml.BaseLoader)
    quarterly = document["jobs"]["quarterly-csv"]
    assert quarterly["if"] == "inputs.qualification_scope == 'quarterly-csv'"
    assert quarterly["strategy"]["matrix"]["quarter"] == ["1", "2", "3"]
    assert quarterly["permissions"] == {"contents": "read"}
    run = next(step["run"] for step in quarterly["steps"] if "run" in step)
    assert "scripts/qualify_mbs_demographic_csv_cohort.py" in run
    assert "test \"${GITHUB_REF}\" = 'refs/heads/main'" in run
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in run
    assert (
        quarterly["steps"][-1]["with"]["path"]
        == "demographic-csv-candidate.json"
    )


def test_retained_q1_hosted_receipt_preserves_exact_scope():
    path = (
        Path(__file__).resolve().parents[1]
        / "quality/qualifications/mbs-q1-native-silver-qualification-20261022-39627539043.json"
    )
    assert (
        sha256(path.read_bytes()).hexdigest()
        == "e0d22895cfd4a8e159c22273aee7856426f0063129607bd1e879272880b68110"
    )
    report = json.loads(path.read_text())
    assert (
        report["workflow_commit"] == "ebd4e300f4aafc809fedfe4b1214fdbe44b381ca"
    )
    workbook, csv = report["objects"]
    for index, obj in enumerate((workbook, csv)):
        context = module.source_context(index)
        assert obj["source_object_id"] == context.object_id
        assert obj["source_sha256"] == context.source_sha256
        assert obj["rebuild_equal"]
        assert obj["independent_parquet_restore"]
        assert obj["duckdb_consumer_counts_equal"]
        assert obj["unqualified_pooling_blocked"]
        assert obj["patient_rate_state"] == "unavailable"
        assert (
            obj["source_native_primary_fields_equal"]
            == obj["coverage"]["native_fields"]
        )
    assert workbook["coverage"]["native_rows"] == 545074
    assert workbook["coverage"]["literal_unknown_age_rows"] == 58
    assert workbook["coverage"]["benefit_unrepresentable"] == 76287
    assert csv["coverage"]["native_rows"] == 545070
    assert workbook["source_measure_id"] != csv["source_measure_id"]
    assert not report["boundaries"]["benefit_equivalence_established"]
    assert report["boundaries"]["new_admissions"] == 0
    assert report["boundaries"]["new_sources"] == 0
