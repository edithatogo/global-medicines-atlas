"""Source-local lexical reference screening never asserts vocabulary equivalence."""

import json
from types import SimpleNamespace

import pytest
from test_au_pbs_v3 import (
    _zip,  # ruff: ignore[import-private-name] -- synthetic bytes
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic receipt
)
from test_pbs_historical_silver import PATH, SOURCE

from global_medicines_atlas import pbs_native_reference_screen as module
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)


def inputs():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:xlink="http://www.w3.org/1999/xlink">
    <a xml:id="SYNTHETIC-ID" rdf:about="https://example.test/one"/>
    <a rdf:about="https://example.test/duplicate"/><a rdf:about="https://example.test/duplicate"/>
    <b rdf:resource="https://example.test/one"/><b rdf:resource="https://example.test/duplicate"/>
    <b rdf:resource="https://example.test/missing"/><b rdf:resource=""/>
    <b xlink:href="#SYNTHETIC-ID"/><b xlink:href="#missing"/>
    <b xlink:href="https://example.test/one"/>
    </root>"""
    archive = _zip([(PATH, xml)])
    parent = _receipt(archive, SOURCE)
    return archive, xml, parent, build_pbs_xml_member_binding(archive, parent)


def test_all_exact_matches_ambiguities_missing_and_empty_are_accounted():
    screen_inputs = inputs()
    report = module.screen_native_references(*screen_inputs)
    assert report["schema_version"] == 2
    assert report["definition_fields"] == 4
    assert report["reference_fields"] == 7
    assert report["definition_kind_counts"] == {"rdf_about": 3, "xml_id": 1}
    assert report["reference_kind_counts"] == {
        "rdf_resource": 4,
        "xlink_href": 3,
    }
    assert report["reference_kind_status_counts"] == {
        "rdf_resource": {
            "ambiguous_exact_literal": 1,
            "empty_literal": 1,
            "no_exact_literal": 1,
            "unique_exact_literal": 1,
        },
        "xlink_href": {
            "no_exact_literal": 1,
            "unique_exact_literal": 1,
            "unsupported_reference_form": 1,
        },
    }
    assert report["reference_status_counts"] == {
        "unique_exact_literal": 2,
        "ambiguous_exact_literal": 1,
        "no_exact_literal": 2,
        "empty_literal": 1,
        "unsupported_reference_form": 1,
    }
    assert (
        sum(report["reference_status_counts"].values())
        == report["reference_fields"]
    )
    assert report["semantic_relationships_qualified"] is False
    assert report["external_targets_fetched"] == 0
    assert "SYNTHETIC-ID" not in json.dumps(report)
    assert "example.test" not in json.dumps(report)
    assert report == module.screen_native_references(*screen_inputs)


def test_progress_is_aggregate_and_reports_match_phase():
    checkpoints = []
    report = module.screen_native_references(
        *inputs(), progress=lambda *values: checkpoints.append(values)
    )
    assert checkpoints == [
        ("native-reference-match", 1, report["native_fields"])
    ]


def test_index_progress_at_first_bounded_checkpoint(monkeypatch):
    slot = SimpleNamespace(path="/root/text", value=None, record_id="synthetic")
    monkeypatch.setattr(
        module,
        "iter_pbs_xml_slots",
        lambda _member: (slot for _ in range(100_000)),
    )
    checkpoints = []
    report = module.screen_native_references(
        *inputs(), progress=lambda *values: checkpoints.append(values)
    )
    assert report["native_fields"] == 100_000
    assert report["reference_fields"] == 0
    assert checkpoints == [
        ("native-reference-index", 1, 100_000),
        ("native-reference-match", 1, 100_000),
    ]


@pytest.mark.parametrize(
    "limit",
    [
        "MAX_LITERAL_BYTES",
        "MAX_INDEX_ROWS",
        "MAX_NATIVE_FIELDS",
        "MAX_INDEX_BYTES",
    ],
)
def test_screen_limits_reject_without_partial_success(monkeypatch, limit):
    monkeypatch.setattr(module, limit, 1)
    with pytest.raises(ValueError, match="reference screen"):
        module.screen_native_references(*inputs())


def test_exact_member_is_required_before_screening():
    archive, xml, parent, binding = inputs()
    with pytest.raises(ValueError, match="member"):
        module.screen_native_references(
            archive, xml + b"changed", parent, binding
        )


def test_identifier_namespaces_and_exact_literals_do_not_collapse():
    archive, xml, _, _ = inputs()
    xml = xml.replace(
        b"</root>",
        b'<a xml:id="shared"/><b rdf:resource="shared"/><a rdf:about="Case"/><b rdf:resource="case"/><a id="unqualified"/><b xlink:href="#unqualified"/></root>',
    )
    archive = _zip([(PATH, xml)])
    parent = _receipt(archive, SOURCE)
    report = module.screen_native_references(
        archive, xml, parent, build_pbs_xml_member_binding(archive, parent)
    )
    assert report["definition_fields"] == 6
    assert report["reference_fields"] == 10
    assert report["reference_status_counts"]["unique_exact_literal"] == 2
    assert report["reference_status_counts"]["no_exact_literal"] == 5


def test_exact_rdf_literal_with_different_xml_base_stays_a_candidate():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xml:base="https://one.example/">
      <rdf:Description rdf:about="item"/>
      <group xml:base="https://two.example/">
        <link rdf:resource="item"/>
      </group>
    </root>"""
    archive = _zip([(PATH, xml)])
    parent = _receipt(archive, SOURCE)
    report = module.screen_native_references(
        archive, xml, parent, build_pbs_xml_member_binding(archive, parent)
    )
    # The lexical screener correctly reports exact spelling but cannot resolve
    # xml:base. These relative URI references can therefore denote different
    # targets even though the source literals are identical.
    assert report["reference_status_counts"] == {"unique_exact_literal": 1}
    assert report["semantic_relationships_qualified"] is False
    assert report["native_values_emitted"] is False


def test_index_files_are_removed_on_success_and_parse_failure(
    tmp_path, monkeypatch
):
    original = module.TemporaryDirectory
    paths = []

    def tracked(*args, **kwargs):
        temporary = original(*args, dir=tmp_path, **kwargs)
        paths.append(temporary.name)
        return temporary

    monkeypatch.setattr(module, "TemporaryDirectory", tracked)
    module.screen_native_references(*inputs())
    monkeypatch.setattr(module, "MAX_INDEX_ROWS", 1)
    with pytest.raises(ValueError, match="index row bound"):
        module.screen_native_references(*inputs())
    assert len(paths) == 2
    assert list(tmp_path.iterdir()) == []


def test_screen_bounds_allow_complete_pinned_member_profile():
    # The first protected run stopped at 13.5m fields with a generic
    # validation failure. Increase finite index bounds for the retry.
    assert module.MAX_NATIVE_FIELDS >= 18_208_758
    assert module.MAX_INDEX_ROWS == 8_000_000
    assert module.MAX_INDEX_BYTES == 4 * 1024**3
