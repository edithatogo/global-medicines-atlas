"""Synthetic coverage for strict, aggregate-only PBS URI resolution."""

import hashlib
import json
import sys
from pathlib import Path

import pytest
from scripts.qualify_pbs_uri_structural_review import (
    main as structural_review_main,
)
from scripts.qualify_pbs_uri_structural_review import (
    write_receipt as write_structural_review_receipt,
)

import global_medicines_atlas.pbs_native_uri_screen as module
import global_medicines_atlas.pbs_uri_structural_review as structural_review
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


def test_binds_selected_occurrence_outcome_by_address_digest_only():
    member = b"""<pbs:root xmlns:pbs="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <pbs:mpp rdf:about="https://synthetic.example/target"/>
      <pbs:mp rdf:resource="https://synthetic.example/target"/>
    </pbs:root>"""
    address = (
        "/{http:~1~1schema.pbs.gov.au~1}root/1/"
        "{http:~1~1schema.pbs.gov.au~1}mp/1/attributes/"
        "{http:~1~1www.w3.org~11999~102~122-rdf-syntax-ns#}resource"
    )
    case_id = "a" * 64
    target_address = (
        "/{http:~1~1schema.pbs.gov.au~1}root/1/"
        "{http:~1~1schema.pbs.gov.au~1}mpp/1"
    )
    report = screen_pbs_native_uris(
        member,
        review_cases=[{"case_id": case_id, "reference_occurrence": address}],
    )
    assert report["review_case_uri_bindings"] == [
        {
            "case_id": case_id,
            "reference_occurrence_sha256": hashlib.sha256(
                address.encode()
            ).hexdigest(),
            "reference_kind": "rdf_resource",
            "structural_role": "rdf_resource_attribute",
            "reference_element_qname": "pbs:mp",
            "uri_resolution": "absolute_uri_unique_candidate",
            "target_element_qname": "pbs:mpp",
            "target_occurrence_sha256": hashlib.sha256(
                target_address.encode()
            ).hexdigest(),
            "semantic_review_state": "pending",
            "adjudication": "unreviewed",
            "semantic_relationship_qualified": False,
        }
    ]
    assert address not in json.dumps(report)
    assert "https://synthetic.example" not in json.dumps(report)
    assert report["review_cases_adjudicated"] == 0
    assert report["review_case_sampling_is_probability_based"] is False
    assert report["schema_version"] == module.URI_SCREEN_SCHEMA_VERSION


def test_selected_uri_review_case_must_match_a_unique_reference_occurrence():
    member = b"<root><link/></root>"
    with pytest.raises(
        module.UriScreenError, match="occurrence is absent"
    ) as caught:
        screen_pbs_native_uris(
            member,
            review_cases=[
                {
                    "case_id": "a" * 64,
                    "reference_occurrence": "/root/1/link/1/attributes/missing",
                }
            ],
        )
    assert caught.value.code == "review-occurrence-absent"
    with pytest.raises(
        module.UriScreenError, match="binding is invalid"
    ) as caught:
        screen_pbs_native_uris(
            member,
            review_cases=[{"case_id": "bad", "reference_occurrence": "/x"}],
        )
    assert caught.value.code == "review-case-binding-invalid"


def test_selected_unresolved_case_has_no_target_identity():
    member = b"""<pbs:root xmlns:pbs="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <pbs:covert-field rdf:resource="https://synthetic.example/missing"/>
    </pbs:root>"""
    address = (
        "/{http:~1~1schema.pbs.gov.au~1}root/1/"
        "{http:~1~1schema.pbs.gov.au~1}covert-field/1/attributes/"
        "{http:~1~1www.w3.org~11999~102~122-rdf-syntax-ns#}resource"
    )
    report = screen_pbs_native_uris(
        member,
        review_cases=[{"case_id": "b" * 64, "reference_occurrence": address}],
    )
    binding = report["review_case_uri_bindings"][0]
    assert binding["uri_resolution"] == "absolute_uri_no_member_definition"
    assert binding["reference_kind"] == "rdf_resource"
    assert binding["structural_role"] == "rdf_resource_attribute"
    assert binding["reference_element_qname"] == "other_or_unresolved"
    assert binding["semantic_review_state"] == "pending"
    assert binding["target_element_qname"] is None
    assert binding["target_occurrence_sha256"] is None
    encoded = json.dumps(binding)
    assert "synthetic.example" not in encoded
    assert "covert-field" not in encoded


def test_binds_unique_xlink_target_element_without_emitting_id_value():
    member = b"""<pbs:root xmlns:pbs="http://schema.pbs.gov.au/"
      xmlns:xlink="http://www.w3.org/1999/xlink">
      <pbs:pharmaceutical-item xml:id="private-id"/>
      <pbs:mp xlink:href="#private-id"/>
    </pbs:root>"""
    address = (
        "/{http:~1~1schema.pbs.gov.au~1}root/1/"
        "{http:~1~1schema.pbs.gov.au~1}mp/1/attributes/"
        "{http:~1~1www.w3.org~11999~1xlink}href"
    )
    target_address = (
        "/{http:~1~1schema.pbs.gov.au~1}root/1/"
        "{http:~1~1schema.pbs.gov.au~1}pharmaceutical-item/1"
    )
    report = screen_pbs_native_uris(
        member,
        review_cases=[{"case_id": "c" * 64, "reference_occurrence": address}],
    )
    binding = report["review_case_uri_bindings"][0]
    assert binding["uri_resolution"] == "same_member_unique_id"
    assert binding["reference_kind"] == "xlink_href"
    assert binding["structural_role"] == "xlink_href_attribute"
    assert binding["reference_element_qname"] == "pbs:mp"
    assert binding["target_element_qname"] == "pbs:pharmaceutical-item"
    assert (
        binding["target_occurrence_sha256"]
        == hashlib.sha256(target_address.encode()).hexdigest()
    )
    assert "private-id" not in json.dumps(binding)


def test_review_allowlist_preserves_observed_secondary_pbs_namespace_qname():
    member = b"""<pbs:root xmlns:pbs="http://schema.pbs.gov.au/"
      xmlns:data="http://pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <data:pricing rdf:about="https://synthetic.example/target"/>
      <pbs:mp rdf:resource="https://synthetic.example/target"/>
    </pbs:root>"""
    address = (
        "/{http:~1~1schema.pbs.gov.au~1}root/1/"
        "{http:~1~1schema.pbs.gov.au~1}mp/1/attributes/"
        "{http:~1~1www.w3.org~11999~102~122-rdf-syntax-ns#}resource"
    )
    report = screen_pbs_native_uris(
        member,
        review_cases=[{"case_id": "d" * 64, "reference_occurrence": address}],
    )
    binding = report["review_case_uri_bindings"][0]
    assert binding["reference_element_qname"] == "pbs:mp"
    assert binding["target_element_qname"] == "pbsdata:pricing"
    encoded = json.dumps(report)
    assert "https://synthetic.example" not in encoded
    assert address not in encoded


def test_selected_unique_target_buckets_unrecognized_target_qname():
    member = b"""<pbs:root xmlns:pbs="http://schema.pbs.gov.au/"
      xmlns:other="urn:synthetic:unknown"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <other:covert rdf:about="https://synthetic.example/target"/>
      <pbs:mp rdf:resource="https://synthetic.example/target"/>
    </pbs:root>"""
    address = (
        "/{http:~1~1schema.pbs.gov.au~1}root/1/"
        "{http:~1~1schema.pbs.gov.au~1}mp/1/attributes/"
        "{http:~1~1www.w3.org~11999~102~122-rdf-syntax-ns#}resource"
    )
    report = screen_pbs_native_uris(
        member,
        review_cases=[{"case_id": "e" * 64, "reference_occurrence": address}],
    )
    binding = report["review_case_uri_bindings"][0]
    assert binding["uri_resolution"] == "absolute_uri_unique_candidate"
    assert binding["target_element_qname"] == "other_or_unresolved"
    assert isinstance(binding["target_occurrence_sha256"], str)
    encoded = json.dumps(binding)
    assert "covert" not in encoded
    assert "synthetic.example" not in encoded


def test_review_target_context_bounds_and_duplicate_targets(
    monkeypatch: pytest.MonkeyPatch,
):
    element = type("Element", (), {"tag": "root", "attrib": {}})()

    def over_limit_events(_member, *, policy):
        del policy
        yield "start", element, None
        yield "start", element, None

    monkeypatch.setattr(module, "MAX_ELEMENTS", 1)
    monkeypatch.setattr(module, "iter_xml_events", over_limit_events)
    with pytest.raises(module.UriScreenError, match="element bound") as caught:
        module._review_target_contexts(b"<root/>", {("xml_id", "target")}, None)
    assert caught.value.code == "element-bound"

    target_uri = "https://synthetic.example/target"
    duplicate = type(
        "Element",
        (),
        {"tag": "root", "attrib": {module.RDF_ABOUT: target_uri}},
    )()

    def duplicate_events(_member, *, policy):
        del policy
        yield "start", duplicate, None
        yield "start", duplicate, None

    monkeypatch.setattr(module, "MAX_ELEMENTS", 20_000_000)
    monkeypatch.setattr(module, "iter_xml_events", duplicate_events)
    with pytest.raises(
        module.UriScreenError, match="target is not unique"
    ) as caught:
        module._review_target_contexts(
            b"<root/>", {("rdf_about", target_uri)}, None
        )
    assert caught.value.code == "review-case-binding-invalid"


def test_review_target_context_progress_is_coarse_and_value_free(
    monkeypatch: pytest.MonkeyPatch,
):
    target = type(
        "Element",
        (),
        {"tag": "root", "attrib": {module.XML_ID: "synthetic-id"}},
    )()
    element = type("Element", (), {"tag": "other", "attrib": {}})()

    def many_events(_member, *, policy):
        del policy
        yield "start", target, None
        for _ in range(99_999):
            yield "start", element, None

    monkeypatch.setattr(module, "iter_xml_events", many_events)
    progress = []
    result = module._review_target_contexts(
        b"<root/>",
        {("xml_id", "synthetic-id")},
        lambda *args: progress.append(args),
    )
    assert progress == [("pbs-uri-review-target-context", 1, 100_000)]
    assert set(result) == {("xml_id", "synthetic-id")}
    assert "synthetic-id" not in str(progress)


def test_review_target_context_wraps_parser_safety_and_rejects_missing_target(
    monkeypatch: pytest.MonkeyPatch,
):
    def unsafe_events(_member, *, policy):
        del policy
        raise module.ParserSafetyError("synthetic parser failure")
        yield  # pragma: no cover

    monkeypatch.setattr(module, "iter_xml_events", unsafe_events)
    with pytest.raises(
        module.UriScreenError, match="malformed or unsafe"
    ) as caught:
        module._review_target_contexts(
            b"<root/>", {("xml_id", "missing")}, None
        )
    assert caught.value.code == "xml-malformed-or-unsafe"

    element = type("Element", (), {"tag": "root", "attrib": {}})()

    def missing_events(_member, *, policy):
        del policy
        yield "start", element, None

    monkeypatch.setattr(module, "iter_xml_events", missing_events)
    with pytest.raises(
        module.UriScreenError, match="occurrence is absent"
    ) as caught:
        module._review_target_contexts(
            b"<root/>", {("xml_id", "missing")}, None
        )
    assert caught.value.code == "review-occurrence-absent"


def test_review_case_count_and_occurrence_address_are_bounded():
    with pytest.raises(
        module.UriScreenError, match="case bound exceeded"
    ) as caught:
        screen_pbs_native_uris(
            b"<root/>",
            review_cases=[
                {
                    "case_id": f"{index:064x}",
                    "reference_occurrence": f"/r/{index}",
                }
                for index in range(65)
            ],
        )
    assert caught.value.code == "review-case-bound"
    with pytest.raises(
        module.UriScreenError, match="binding is invalid"
    ) as caught:
        screen_pbs_native_uris(
            b"<root/>",
            review_cases=[
                {
                    "case_id": "a" * 64,
                    "reference_occurrence": "/" + "x" * 4096,
                }
            ],
        )
    assert caught.value.code == "review-case-binding-invalid"


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


@pytest.mark.parametrize(
    ("definition", "reference"),
    [
        ('rdf:about=""', 'rdf:resource="https://synthetic.example/doc"'),
        ('rdf:about="https://synthetic.example/doc"', 'rdf:resource=""'),
    ],
)
def test_empty_rdf_reference_resolves_only_with_an_absolute_base(
    definition: str, reference: str
):
    member = (
        '<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xml:base="https://synthetic.example/doc">'
        f"<rdf:Description {definition}/><link {reference}/></root>"
    ).encode()
    report = screen_pbs_native_uris(member)
    assert report["outcome_counts_by_kind"]["rdf_resource"] == {
        "absolute_uri_unique_candidate": 1
    }


def test_empty_rdf_reference_abstains_without_an_absolute_base():
    member = (
        b'<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<link rdf:resource=""/></root>'
    )
    report = screen_pbs_native_uris(member)
    assert report["outcome_counts_by_kind"]["rdf_resource"] == {
        "unresolved_unknown_base": 1
    }


def test_qname_denominators_are_aggregate_and_unknown_namespaces_are_bucketed():
    member = b"""<pbs:root xmlns:pbs="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns:other="urn:synthetic:unknown">
      <rdf:Description rdf:about="https://synthetic.example/subject">
        <pbs:mp rdf:resource="https://synthetic.example/target"/>
        <pbs:covert-field rdf:resource="https://synthetic.example/hidden"/>
        <other:covert rdf:resource="https://synthetic.example/unknown"/>
      </rdf:Description>
    </pbs:root>"""
    report = screen_pbs_native_uris(member)
    assert report["definition_element_qname_counts"] == {"rdf:Description": 1}
    assert report["predicate_qname_counts"] == {
        "other_or_unresolved": 2,
        "pbs:mp": 1,
    }
    assert report["target_element_qname_counts"] == {
        "other_or_unresolved": 2,
        "pbs:mp": 1,
    }
    encoded = json.dumps(report)
    assert "urn:synthetic:unknown" not in encoded
    assert "covert-field" not in encoded
    assert "covert" not in encoded


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
    with pytest.raises(module.UriScreenError, match="byte bound") as caught:
        screen_pbs_native_uris(b"<root/>")
    assert caught.value.code == "member-byte-bound"
    assert "root" not in str(caught.value)
    monkeypatch.setattr(module, "MAX_MEMBER_BYTES", 100)
    with pytest.raises(
        module.UriScreenError, match="XML is malformed"
    ) as caught:
        screen_pbs_native_uris(b"<root>PRIVATE-SYNTHETIC-TOKEN")
    assert caught.value.code == "xml-malformed-or-unsafe"
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


@pytest.mark.parametrize("value", ["a:b", "1starts-with-digit"])
def test_ncname_rejects_invalid_start_or_colon(value: str):
    assert module._is_ncname(value) is False


@pytest.mark.parametrize(
    "value", [None, "relative", "https://bad host/x", "https://bad/%GG"]
)
def test_absolute_base_rejects_missing_or_malformed_values(value: str | None):
    assert module._absolute_base(value) is None


def test_absolute_base_rejects_empty_parsed_scheme(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        module,
        "urlsplit",
        lambda _value: type("Parts", (), {"scheme": "", "port": None})(),
    )
    assert module._absolute_base("scheme:value") is None


def test_absolute_base_rejects_invalid_authority_port(
    monkeypatch: pytest.MonkeyPatch,
):
    class InvalidPort:
        scheme = "https"

        @property
        def port(self):
            raise ValueError("private synthetic authority")

    monkeypatch.setattr(module, "urlsplit", lambda _value: InvalidPort())
    assert module._absolute_base("https://synthetic.example/") is None


def test_base_and_reference_join_errors_abstain(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        module,
        "urljoin",
        lambda *_args: (_ for _ in ()).throw(ValueError("private")),
    )
    assert module._effective_base("https://synthetic.example/", "child") is None
    assert module._resolve("child", "https://synthetic.example/") is None


def test_relative_xml_base_resolves_against_parent():
    assert (
        module._effective_base("https://synthetic.example/root/", "child/")
        == "https://synthetic.example/root/child/"
    )


@pytest.mark.parametrize(
    ("value", "base"),
    [
        (None, "https://synthetic.example/"),
        ("x" * (module.MAX_URI_CHARS + 1), "https://synthetic.example/"),
        ("https://synthetic.example/%GG", None),
    ],
)
def test_missing_oversized_or_invalid_uri_abstains(
    value: str | None, base: str | None
):
    assert module._resolve(value, base) is None


@pytest.mark.parametrize(
    ("member", "expected"),
    [
        (
            b'<root xmlns:xlink="http://www.w3.org/1999/xlink"><a xlink:href="#bad%GG"/></root>',
            "abstained_malformed_fragment",
        ),
        (
            b'<root xmlns:xlink="http://www.w3.org/1999/xlink"><a xlink:href="#%FF"/></root>',
            "abstained_malformed_fragment",
        ),
        (
            b'<root xmlns:xlink="http://www.w3.org/1999/xlink"><a xlink:href="https://synthetic.example/item"/></root>',
            "external_or_nonfragment_xlink_unresolved",
        ),
    ],
)
def test_xlink_abstention_outcomes(member: bytes, expected: str):
    report = screen_pbs_native_uris(member)
    assert report["outcome_counts_by_kind"]["xlink_href"] == {expected: 1}


def test_uri_reference_and_indexed_character_bounds(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(module, "MAX_URI_CHARS", 2)
    with pytest.raises(module.UriScreenError, match="URI bound") as caught:
        screen_pbs_native_uris(
            b'<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><a rdf:resource="long"/></root>'
        )
    assert caught.value.code == "uri-value-bound"
    monkeypatch.setattr(module, "MAX_URI_CHARS", 100)
    monkeypatch.setattr(module, "MAX_INDEXED_URI_CHARS", 0)
    with pytest.raises(
        module.UriScreenError, match="indexed URI bound"
    ) as caught:
        screen_pbs_native_uris(
            b'<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><a rdf:resource="x"/></root>'
        )
    assert caught.value.code == "indexed-uri-bound"


def test_reference_and_element_count_bounds(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "MAX_REFERENCE_ROWS", 0)
    with pytest.raises(
        module.UriScreenError, match="reference bound"
    ) as caught:
        screen_pbs_native_uris(
            b'<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><a rdf:resource="x"/></root>'
        )
    assert caught.value.code == "reference-row-bound"
    monkeypatch.setattr(module, "MAX_REFERENCE_ROWS", 8_000_000)
    monkeypatch.setattr(module, "MAX_ELEMENTS", 1)
    element = type("Element", (), {"tag": "root", "attrib": {}})()

    def over_limit_events(_member, *, policy):
        del policy
        yield "start", element, None
        yield "start", element, None

    monkeypatch.setattr(module, "iter_xml_events", over_limit_events)
    with pytest.raises(module.UriScreenError, match="element bound") as caught:
        screen_pbs_native_uris(b"<root><child/></root>")
    assert caught.value.code == "element-bound"


def test_parse_progress_is_coarse_and_value_free(
    monkeypatch: pytest.MonkeyPatch,
):
    element = type("Element", (), {"tag": "root", "attrib": {}})()

    def many_events(_member, *, policy):
        del policy
        for _ in range(100_000):
            yield "start", element, None

    monkeypatch.setattr(module, "iter_xml_events", many_events)
    progress = []
    report = screen_pbs_native_uris(
        b"<root/>", progress=lambda *args: progress.append(args)
    )
    assert progress == [
        ("pbs-uri-screen-parse", 1, 100_000),
        ("pbs-uri-screen-classify", 1, 0),
    ]
    assert report["xml_elements"] == 100_000


def test_pinned_uri_sample_structural_review_is_narrow_and_value_free():
    root = Path(__file__).resolve().parents[1]
    report = structural_review.review_structural_match_behavior(root)
    assert report["case_count"] == 46
    assert report["outcome_counts"] == {
        "same_member_unique_id": 17,
        "absolute_uri_unique_candidate": 18,
        "no_member_definition_negative_controls": 11,
    }
    cases = report["cases"]
    assert len(cases) == 46
    assert sum(case["relationship_label"] is not None for case in cases) == 35
    assert all(case["candidate_edge_emitted"] is False for case in cases)
    assert all(
        set(case)
        == {
            "case_id",
            "reference_occurrence_sha256",
            "target_occurrence_sha256",
            "structural_disposition",
            "relationship_label",
            "candidate_edge_emitted",
        }
        for case in cases
    )
    assert (
        report["review_scope"] == "structural_match_behavior_calibration_only"
    )
    assert report["limitations"]["clinical_meaning_asserted"] is False
    assert report["limitations"]["precision_claimed"] is False
    assert report["limitations"]["recall_claimed"] is False
    assert report["limitations"]["generalized_to_corpus"] is False
    encoded = json.dumps(report)
    assert '"uri":' not in encoded
    assert '"literal":' not in encoded
    assert '"source_element_qname":' not in encoded


def test_structural_review_fails_closed_on_changed_reconciliation(tmp_path):
    root = Path(__file__).resolve().parents[1]
    destination = tmp_path / "quality/qualifications"
    destination.mkdir(parents=True)
    source = (
        root
        / "quality/qualifications"
        / structural_review.RECONCILIATION_FILENAME
    )
    (destination / structural_review.RECONCILIATION_FILENAME).write_bytes(
        source.read_bytes() + b" "
    )
    with pytest.raises(
        structural_review.StructuralReviewError,
        match="pinned reconciliation bytes differ",
    ):
        structural_review.review_structural_match_behavior(tmp_path)


def _write_structural_input(root, monkeypatch, *, report=None, envelope=None):
    destination = root / "quality/qualifications"
    destination.mkdir(parents=True, exist_ok=True)
    report_digest = structural_review.RECONCILIATION_REPORT_SHA256
    if envelope is None:
        if report is None:
            source = (
                Path(__file__).resolve().parents[1]
                / "quality/qualifications"
                / structural_review.RECONCILIATION_FILENAME
            )
            report = json.loads(source.read_bytes())["report"]
        canonical = json.dumps(
            report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        report_digest = hashlib.sha256(canonical).hexdigest()
        envelope = {"report": report, "report_sha256": report_digest}
    raw = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    target = destination / structural_review.RECONCILIATION_FILENAME
    target.write_bytes(raw)
    monkeypatch.setattr(
        structural_review,
        "RECONCILIATION_SHA256",
        hashlib.sha256(raw).hexdigest(),
    )
    monkeypatch.setattr(
        structural_review,
        "RECONCILIATION_REPORT_SHA256",
        report_digest,
    )
    return target


def test_structural_review_rejects_noncanonical_input():
    with pytest.raises(
        structural_review.StructuralReviewError,
        match="input report is not canonical JSON",
    ):
        structural_review._canonical_digest({"not-json": {1, 2}})


def _pinned_review_report():
    source = (
        Path(__file__).resolve().parents[1]
        / "quality/qualifications"
        / structural_review.RECONCILIATION_FILENAME
    )
    report = json.loads(source.read_bytes())["report"]
    return json.loads(json.dumps(report))


def _assert_structural_review_rejected(
    tmp_path, monkeypatch, report, message, envelope=None
):
    _write_structural_input(
        tmp_path, monkeypatch, report=report, envelope=envelope
    )
    with pytest.raises(structural_review.StructuralReviewError, match=message):
        structural_review.review_structural_match_behavior(tmp_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("not-a-dict-envelope", "pinned reconciliation shape differs"),
        ("missing-report", "pinned reconciliation shape differs"),
        (
            "declared-report-digest",
            "pinned reconciliation report digest differs",
        ),
        ("canonical-report-digest", "reconciliation report digest is invalid"),
        ("source-binding", "source and receipt binding differs"),
        ("cases-not-list", "pinned case inventory differs"),
        ("case-count", "pinned case inventory differs"),
    ],
)
def test_structural_review_rejects_changed_input_scope(
    tmp_path, monkeypatch, mutation, message
):
    report = _pinned_review_report()
    envelope = None
    if mutation == "not-a-dict-envelope":
        envelope = ["invalid"]
    elif mutation == "missing-report":
        envelope = {"report": None, "report_sha256": "0" * 64}
    elif mutation == "declared-report-digest":
        envelope = {"report": report, "report_sha256": "0" * 64}
        monkeypatch.setattr(
            structural_review,
            "RECONCILIATION_REPORT_SHA256",
            structural_review._canonical_digest(report),
        )
    elif mutation == "canonical-report-digest":
        report["test_only_mutation"] = True
        envelope = {
            "report": report,
            "report_sha256": structural_review.RECONCILIATION_REPORT_SHA256,
        }
    elif mutation == "source-binding":
        report["dataset"] = "different-dataset"
    elif mutation == "cases-not-list":
        report["cases"] = None
    elif mutation == "case-count":
        report["cases"].pop()
    _assert_structural_review_rejected(
        tmp_path, monkeypatch, report, message, envelope
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("case-shape", "pinned case shape differs"),
        ("case-identity", "pinned case identity or limits differ"),
        ("unique-target-base", "unique-target case is not eligible"),
        ("negative-control-target", "negative control has target evidence"),
        ("unsupported-outcome", "case outcome is outside pinned review scope"),
        ("outcome-distribution", "pinned outcome distribution differs"),
    ],
)
def test_structural_review_rejects_changed_case_controls(
    tmp_path, monkeypatch, mutation, message
):
    report = _pinned_review_report()
    cases = report["cases"]
    if mutation == "case-shape":
        report["cases"][0] = None
    elif mutation == "case-identity":
        report["cases"][0]["case_id"] = "bad"
    if mutation == "unique-target-base":
        case = next(
            item
            for item in cases
            if item["uri_resolution"] in structural_review.UNIQUE_OUTCOMES
        )
        case["target_xml_base_context"] = "xml_base_present"
    elif mutation == "negative-control-target":
        case = next(
            item
            for item in cases
            if item["uri_resolution"] == "absolute_uri_no_member_definition"
        )
        case["target_occurrence_sha256"] = "a" * 64
    elif mutation == "unsupported-outcome":
        cases[0]["uri_resolution"] = "unsupported"
    elif mutation == "outcome-distribution":
        case = next(
            item
            for item in cases
            if item["uri_resolution"] == "same_member_unique_id"
        )
        case["uri_resolution"] = "absolute_uri_unique_candidate"
    _assert_structural_review_rejected(tmp_path, monkeypatch, report, message)


def test_structural_review_rejects_unreadable_reconciliation(tmp_path):
    with pytest.raises(
        structural_review.StructuralReviewError,
        match="pinned reconciliation cannot be read",
    ):
        structural_review.review_structural_match_behavior(tmp_path)


def test_structural_review_cli_writes_once_and_main_runs(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "nested/review.json"
    write_structural_review_receipt(root, output)
    envelope = json.loads(output.read_bytes())
    assert envelope["report"]["case_count"] == 46
    assert len(envelope["report_sha256"]) == 64
    with pytest.raises(FileExistsError):
        write_structural_review_receipt(root, output)

    main_output = tmp_path / "main-review.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify_pbs_uri_structural_review.py",
            "--root",
            str(root),
            "--output",
            str(main_output),
        ],
    )
    assert structural_review_main() == 0
    assert json.loads(main_output.read_bytes())["report"]["case_count"] == 46


def test_structural_review_cli_fails_with_sanitized_input_error(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify_pbs_uri_structural_review.py",
            "--root",
            str(tmp_path),
            "--output",
            str(tmp_path / "bad.json"),
        ],
    )
    with pytest.raises(SystemExit, match="2"):
        structural_review_main()
