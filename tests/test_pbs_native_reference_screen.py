"""Source-local lexical reference screening never asserts vocabulary equivalence."""

import json

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
    report = module.screen_native_references(*inputs())
    assert report["definition_fields"] == 4
    assert report["reference_fields"] == 7
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
    assert report == module.screen_native_references(*inputs())


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
