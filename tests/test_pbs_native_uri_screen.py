"""Synthetic coverage for strict, aggregate-only PBS URI resolution."""

import json

import pytest

import global_medicines_atlas.pbs_native_uri_screen as module
from global_medicines_atlas.pbs_native_uri_screen import screen_pbs_native_uris


def test_resolves_only_defensible_absolute_rdf_and_bare_member_fragments():
    member = b"""<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns:xlink="http://www.w3.org/1999/xlink">
      <rdf:Description rdf:about="https://synthetic.example/item"/>
      <rdf:Description rdf:about="https://synthetic.example/duplicate"/>
      <rdf:Description rdf:about="https://synthetic.example/duplicate"/>
      <link rdf:resource="https://synthetic.example/item"/>
      <link rdf:resource="https://synthetic.example/duplicate"/>
      <link rdf:resource="https://synthetic.example/missing"/>
      <link xml:id="one"/><link xlink:href="#one"/>
      <link xml:id="twice"/><link xml:id="twice"/><link xlink:href="#twice"/>
      <link xlink:href="#missing"/>
    </root>"""
    report = screen_pbs_native_uris(member)
    assert report["reference_counts_by_kind"] == {
        "rdf_resource": 3,
        "xlink_href": 3,
    }
    assert report["outcome_counts_by_kind"] == {
        "rdf_resource": {
            "absolute_uri_ambiguous_candidate": 1,
            "absolute_uri_no_member_definition": 1,
            "absolute_uri_unique_candidate": 1,
        },
        "xlink_href": {
            "ambiguous_id_target": 1,
            "missing_id_target": 1,
            "same_member_unique_id": 1,
        },
    }
    assert sum(report["reference_counts_by_kind"].values()) == 6
    assert report["uri_resolution_performed"] is True
    assert report["semantic_relationships_qualified"] is False
    assert report["precision_claimed"] is False
    assert report["definition_counts_by_qname"] == {
        "rdf:about": 3,
        "xml:id": 3,
    }
    assert report["predicate_qname_counts"] == {}
    assert report["target_attribute_qname_counts"] == {
        "rdf:resource": 3,
        "xlink:href": 3,
    }


@pytest.mark.parametrize(
    "base", ["relative/", "https://bad host/path", "https://bad/%GG"]
)
def test_relative_or_malformed_base_does_not_resolve_rdf_or_fragment(base):
    member = (
        '<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'xml:base="{base}"><rdf:Description rdf:about="item"/>'
        '<target xml:id="x"/><link rdf:resource="item"/>'
        '<link xlink:href="#x"/></root>'
    ).encode()
    report = screen_pbs_native_uris(member)
    assert report["outcome_counts_by_kind"]["rdf_resource"] == {
        "unresolved_unknown_base": 1
    }
    assert report["outcome_counts_by_kind"]["xlink_href"] == {
        "abstained_xml_base_override": 1
    }


def test_absolute_nested_base_reestablishes_rdf_resolution_but_xlink_abstains():
    member = b"""<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns:xlink="http://www.w3.org/1999/xlink" xml:base="relative/">
      <group xml:base="https://synthetic.example/">
        <rdf:Description rdf:about="item"/><link rdf:resource="item"/>
        <target xml:id="x"/><link xlink:href="#x"/>
      </group>
    </root>"""
    report = screen_pbs_native_uris(member)
    assert report["outcome_counts_by_kind"]["rdf_resource"] == {
        "absolute_uri_unique_candidate": 1
    }
    assert report["outcome_counts_by_kind"]["xlink_href"] == {
        "abstained_xml_base_override": 1
    }


def test_invalid_xml_id_does_not_count_as_a_same_member_target():
    member = b"""<root xmlns:xlink="http://www.w3.org/1999/xlink">
      <target xml:id="not a valid NCName"/>
      <link xlink:href="#not%20a%20valid%20NCName"/>
    </root>"""
    report = screen_pbs_native_uris(member)
    assert report["invalid_xml_id_count"] == 1
    assert report["outcome_counts_by_kind"]["xlink_href"] == {
        "missing_id_target": 1
    }


def test_duplicate_rdf_about_targets_are_ambiguous_and_absolute_without_base_is_safe():
    member = b"""<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <rdf:Description rdf:about="https://synthetic.example/item"/>
      <rdf:Description rdf:about="https://synthetic.example/item"/>
      <link rdf:resource="https://synthetic.example/item"/>
    </root>"""
    report = screen_pbs_native_uris(member)
    assert report["outcome_counts_by_kind"]["rdf_resource"] == {
        "absolute_uri_ambiguous_candidate": 1
    }


def test_qname_denominators_are_aggregate_and_unknown_namespaces_are_bucketed():
    member = b"""<pbs:root xmlns:pbs="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns:other="urn:synthetic:unknown">
      <rdf:Description rdf:about="https://synthetic.example/subject">
        <pbs:item rdf:resource="https://synthetic.example/target"/>
        <other:private rdf:resource="https://synthetic.example/unknown"/>
      </rdf:Description>
    </pbs:root>"""
    report = screen_pbs_native_uris(member)
    assert report["definition_element_qname_counts"] == {"rdf:Description": 1}
    assert report["predicate_qname_counts"] == {
        "other_or_unresolved": 1,
        "pbs:item": 1,
    }
    assert report["target_element_qname_counts"] == {
        "other_or_unresolved": 1,
        "pbs:item": 1,
    }
    encoded = json.dumps(report)
    assert "urn:synthetic:unknown" not in encoded
    assert "private" not in encoded


def test_output_and_errors_do_not_include_source_values():
    private_marker = "PRIVATE-SYNTHETIC-URI-MARKER"
    member = (
        '<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        f'rdf:resource="https://synthetic.example/{private_marker}"/>'
    ).encode()
    output = json.dumps(screen_pbs_native_uris(member))
    assert private_marker not in output
    assert "synthetic.example" not in output
    assert "fragment" not in output


def test_bounded_input_and_malformed_xml_fail_without_echoing_values(
    monkeypatch,
):
    monkeypatch.setattr(module, "MAX_MEMBER_BYTES", 1)
    with pytest.raises(ValueError, match="byte bound") as caught:
        screen_pbs_native_uris(b"<root/>")
    assert "root" not in str(caught.value)
    monkeypatch.setattr(module, "MAX_MEMBER_BYTES", 100)
    with pytest.raises(ValueError, match="XML is malformed") as caught:
        screen_pbs_native_uris(b"<root>PRIVATE-SYNTHETIC-TOKEN")
    assert "PRIVATE-SYNTHETIC-TOKEN" not in str(caught.value)


def test_progress_contains_only_phase_and_counts():
    progress = []
    report = screen_pbs_native_uris(
        b'<root xmlns:xlink="http://www.w3.org/1999/xlink"><a xlink:href="#x"/></root>',
        progress=lambda *args: progress.append(args),
    )
    assert progress == [("pbs-uri-screen-classify", 1, 1)]
    assert report["outcome_counts_by_qname"] == {
        "xlink:href": {"missing_id_target": 1}
    }
