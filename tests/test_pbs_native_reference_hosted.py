"""Native reference screening stays behind exact-main source and output gates."""

import json
from pathlib import Path
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import]
    ElementTree as ET,
)

import httpx
import pytest
import yaml
from scripts import screen_historical_pbs_references as cli
from test_pbs_hosted_qualification import SHA, synthetic

import global_medicines_atlas.pbs_reference_context as context_screen
from global_medicines_atlas import pbs_hosted_qualification as module

__all__ = ["synthetic"]


def test_local_route_stops_before_transport(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def refuse(_):
        raise AssertionError("local transport must not run")

    with pytest.raises(module.QualificationError, match="context"):
        module.run_hosted_native_reference_screen(
            SHA, transport=httpx.MockTransport(refuse)
        )


def test_verified_route_returns_only_aggregate(synthetic, monkeypatch):
    def qualify(archive, member, parent, binding, *, progress):
        assert archive
        assert member
        assert binding.member_payload.sha256 == module.MEMBER.sha256
        assert binding.parent_receipt_sha256 == parent.digest()
        progress("native-reference-match", 1, 8)
        return {
            "native_fields": 8,
            "reference_fields": 2,
            "reference_status_counts": {"no_exact_literal": 2},
            "definition_kind_counts": {"rdf_about": 1, "xml_id": 0},
            "reference_kind_counts": {"rdf_resource": 2},
            "reference_kind_status_counts": {
                "rdf_resource": {"no_exact_literal": 2}
            },
            "schema_version": 2,
            "semantic_relationships_qualified": False,
            "native_values_emitted": False,
        }

    monkeypatch.setattr(module, "screen_native_references", qualify)
    context = {
        "schema_id": "global-medicines-atlas.pbs-reference-context-screen",
        "schema_version": 1,
        "reference_occurrences": 2,
        "strata_count": 0,
        "examples_emitted": 0,
        "examples_omitted": 0,
        "unique_exact_literal_no_xml_base_candidates": 0,
        "strata": [],
        "uri_resolution_performed": False,
        "literal_values_emitted": False,
        "raw_source_emitted": False,
        "semantic_relationships_qualified": False,
        "external_targets_fetched": 0,
    }
    monkeypatch.setattr(
        module, "screen_reference_context", lambda _, **__: context
    )
    checkpoints = []
    report = module.run_hosted_native_reference_screen(
        SHA, transport=synthetic[2], progress=checkpoints.append
    )
    assert report["status"] == "passed"
    assert len(synthetic[1]) == 5
    assert checkpoints[-1]["progress"]["phase"] == (
        "reference-context-denominator"
    )
    assert report["qualification"]["semantic_relationships_qualified"] is False
    assert report["qualification"]["schema_version"] == 2
    assert report["qualification"]["reference_kind_counts"] == {
        "rdf_resource": 2
    }
    assert report["qualification"]["reference_context"] == context
    assert report["publication_performed"] is False


def test_context_denominator_must_match_lexical_reference_count(
    synthetic, monkeypatch
):
    def qualify(*_, **__):
        return {
            "reference_fields": 2,
            "schema_version": 2,
            "semantic_relationships_qualified": False,
        }

    monkeypatch.setattr(module, "screen_native_references", qualify)
    monkeypatch.setattr(
        module,
        "screen_reference_context",
        lambda _, **__: {"reference_occurrences": 1},
    )
    with pytest.raises(module.QualificationError, match="denominator"):
        module.run_hosted_native_reference_screen(SHA, transport=synthetic[2])


def test_failure_receipt_retains_only_allowlisted_context_code():
    error = context_screen.ReferenceContextError(
        "source-root-mismatch", "private source bytes must not be included"
    )

    report = module.failure_report(error)

    assert report["diagnostic_code"] == "source-root-mismatch"
    assert "private source bytes" not in json.dumps(report)


def test_hosted_context_failure_receipt_retains_allowlisted_code(
    synthetic, monkeypatch
):
    monkeypatch.setattr(
        module,
        "screen_native_references",
        lambda *_, **__: {"reference_fields": 0},
    )

    def fail_context(*_, **__):
        raise context_screen.ReferenceContextError(
            "source-root-mismatch", "private source bytes must not be included"
        )

    monkeypatch.setattr(module, "screen_reference_context", fail_context)
    with pytest.raises(module.QualificationError) as captured:
        module.run_hosted_native_reference_screen(SHA, transport=synthetic[2])

    report = module.failure_report(captured.value)

    assert report["failure_stage"] == "projection-qualification"
    assert report["diagnostic_code"] == "source-root-mismatch"
    assert "private source bytes" not in json.dumps(report)


def test_context_screen_classifies_root_relative_reference_without_value():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <edge rdf:resource="/private/path"/>
    </root>"""
    report = context_screen.screen_reference_context(xml)
    assert report["strata"][0]["literal_shape"] == "root_relative_looking"
    assert "/private/path" not in json.dumps(report)


def test_context_screen_enforces_structural_qname_bound(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context_screen, "MAX_STRUCTURAL_QNAME_BYTES", 0)
    with pytest.raises(ValueError, match="QName byte bound"):
        context_screen.screen_reference_context(
            b'<root xmlns="http://schema.pbs.gov.au/"/>'
        )


@pytest.mark.parametrize(
    "xml",
    [
        b'<root xmlns="http://schema.pbs.gov.au/"><id xml:id="id"/></root>',
        b"""<root xmlns="http://schema.pbs.gov.au/"
          xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
          <id rdf:about="subject"/>
        </root>""",
    ],
)
def test_context_screen_enforces_definition_index_bound(
    xml: bytes, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(context_screen, "MAX_INDEX_ROWS", 0)
    with pytest.raises(ValueError, match="index row bound"):
        context_screen.screen_reference_context(xml)


def test_context_screen_enforces_reference_index_bound(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context_screen, "MAX_REFERENCE_OCCURRENCES", 0)
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <edge rdf:resource="target"/>
    </root>"""
    with pytest.raises(ValueError, match="occurrence bound"):
        context_screen.screen_reference_context(xml)


def test_context_screen_rejects_end_event_without_open_element(
    monkeypatch: pytest.MonkeyPatch,
):
    element = ET.Element("{http://schema.pbs.gov.au/}root")
    monkeypatch.setattr(
        context_screen,
        "iter_xml_events",
        lambda *_args, **_kwargs: iter([("end", element, None)]),
    )
    with pytest.raises(ValueError, match="stack is inconsistent"):
        context_screen.screen_reference_context(b"unused")


def test_context_screen_rejects_incomplete_event_stream(
    monkeypatch: pytest.MonkeyPatch,
):
    element = ET.Element("{http://schema.pbs.gov.au/}root")
    monkeypatch.setattr(
        context_screen,
        "iter_xml_events",
        lambda *_args, **_kwargs: iter([("start", element, None)]),
    )
    with pytest.raises(ValueError, match="document is incomplete"):
        context_screen.screen_reference_context(b"unused")


def test_context_screen_enforces_reference_occurrence_address_bound(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context_screen, "MAX_OCCURRENCE_ADDRESS_BYTES", 0)
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <edge rdf:resource="target"/>
    </root>"""
    with pytest.raises(ValueError, match="occurrence address bound"):
        context_screen.screen_reference_context(xml)


def test_context_screen_enforces_target_occurrence_address_bound(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context_screen, "MAX_OCCURRENCE_ADDRESS_BYTES", 150)
    chain = b"".join(b"<a>" for _ in range(12))
    close_chain = b"".join(b"</a>" for _ in range(12))
    xml = (
        b'<root xmlns="http://schema.pbs.gov.au/" '
        b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        + chain
        + b'<target rdf:about="same"/>'
        + close_chain
        + b'<edge rdf:resource="same"/></root>'
    )
    with pytest.raises(ValueError, match="target address bound"):
        context_screen.screen_reference_context(xml)


def test_context_screen_enforces_report_byte_bound(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context_screen, "MAX_REPORT_BYTES", 0)
    with pytest.raises(ValueError, match="report byte bound"):
        context_screen.screen_reference_context(
            b'<root xmlns="http://schema.pbs.gov.au/"/>'
        )


def test_context_screen_bounds_examples_for_many_predicate_strata():
    declarations = (
        b'<root xmlns="http://schema.pbs.gov.au/" '
        b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    )
    references = b"".join(
        f"<predicate{index} rdf:resource='unmatched'/>".encode() * 5
        for index in range(62)
    )
    report = context_screen.screen_reference_context(
        declarations + references + b"</root>"
    )
    serialized = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    assert report["strata_count"] == 62
    assert report["reference_occurrences"] == 310
    assert report["examples_omitted"] > 0
    assert report["examples_emitted"] < report["reference_occurrences"]
    assert len(serialized.encode()) <= context_screen.MAX_REPORT_BYTES
    strata_representation = [
        {**row, "examples": []} for row in report["strata"]
    ]
    assert (
        len(
            json.dumps(
                strata_representation,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        )
        <= context_screen.MAX_REPORT_STRATA_BYTES
    )


def test_context_screen_bounds_strata_representation_before_receipt(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context_screen, "MAX_REPORT_STRATA_BYTES", 1)
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <edge rdf:resource="unmatched"/>
    </root>"""
    with pytest.raises(ValueError, match="strata byte bound"):
        context_screen.screen_reference_context(xml)


def test_empty_rdf_literals_do_not_count_as_exact_candidates():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <target rdf:about=""/>
      <edge rdf:resource=""/>
    </root>"""
    report = context_screen.screen_reference_context(xml)
    empty_reference = next(
        row for row in report["strata"] if row["kind"] == "rdf_resource"
    )
    assert empty_reference["match_status"] == "empty_literal"
    assert empty_reference["unique_target_occurrences"] == 0
    assert empty_reference["ambiguous_target_occurrences"] == 0
    assert empty_reference["no_xml_base_exact_target_occurrences"] == 0
    assert empty_reference["unique_exact_literal_no_xml_base_candidates"] == 0
    assert report["unique_exact_literal_no_xml_base_candidates"] == 0


def test_cli_withholds_source_exception_and_preserves_existing_receipt(
    tmp_path, monkeypatch
):
    output = tmp_path / "receipt.json"

    def fail(*_, **__):
        raise ValueError("SYNTHETIC SOURCE TEXT WITHHELD")

    monkeypatch.setattr(cli, "run_hosted_native_reference_screen", fail)
    assert cli.main(["--exact-commit", SHA, "--output", str(output)]) == 1
    report = json.loads(output.read_bytes())
    assert report["report"]["status"] == "failed"
    assert "SYNTHETIC SOURCE TEXT" not in output.read_text()
    with pytest.raises(SystemExit):
        cli.main(["--exact-commit", SHA, "--output", str(output)])


def test_workflow_exact_main_read_only_and_exclusive():
    workflow = yaml.safe_load(
        (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/pbs-historical-qualification.yml"
        ).read_text()
    )
    job = workflow["jobs"]["native-reference-screen"]
    assert job["permissions"] == {"contents": "read"}
    assert job["timeout-minutes"] == 65
    step = next(step for step in job["steps"] if "run" in step)
    assert step["timeout-minutes"] == 55
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in step["run"]
    assert "scripts/screen_historical_pbs_references.py" in step["run"]
    for name, other in workflow["jobs"].items():
        if name == "native-reference-screen":
            continue
        if "inputs.qualification_scope ==" in other["if"]:
            assert (
                "inputs.qualification_scope == 'native-reference-screen'"
                not in other["if"]
            )
            continue
        assert (
            "inputs.qualification_scope != 'native-reference-screen'"
            in other["if"]
        )
