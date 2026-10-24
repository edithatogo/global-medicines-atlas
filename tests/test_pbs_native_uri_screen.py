"""Synthetic coverage for strict, aggregate-only PBS URI resolution."""

import hashlib
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


def test_binds_selected_occurrence_outcome_by_address_digest_only():
    member = b"""<pbs:root xmlns:pbs="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <pbs:target rdf:about="https://synthetic.example/target"/>
      <pbs:link rdf:resource="https://synthetic.example/target"/>
    </pbs:root>"""
    address = (
        "/{http:~1~1schema.pbs.gov.au~1}root/1/"
        "{http:~1~1schema.pbs.gov.au~1}link/1/attributes/"
        "{http:~1~1www.w3.org~11999~102~122-rdf-syntax-ns#}resource"
    )
    case_id = "a" * 64
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
            "uri_resolution": "absolute_uri_unique_candidate",
            "adjudication": "unreviewed",
            "semantic_relationship_qualified": False,
        }
    ]
    assert address not in json.dumps(report)
    assert "https://synthetic.example" not in json.dumps(report)
    assert report["review_cases_adjudicated"] == 0
    assert report["review_case_sampling_is_probability_based"] is False


def test_selected_uri_review_case_must_match_a_unique_reference_occurrence():
    member = b"<root><link/></root>"
    with pytest.raises(ValueError, match="occurrence is absent"):
        screen_pbs_native_uris(
            member,
            review_cases=[
                {
                    "case_id": "a" * 64,
                    "reference_occurrence": "/root/1/link/1/attributes/missing",
                }
            ],
        )
    with pytest.raises(ValueError, match="binding is invalid"):
        screen_pbs_native_uris(
            member,
            review_cases=[{"case_id": "bad", "reference_occurrence": "/x"}],
        )


def test_review_case_count_and_occurrence_address_are_bounded():
    with pytest.raises(ValueError, match="case bound exceeded"):
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
    with pytest.raises(ValueError, match="binding is invalid"):
        screen_pbs_native_uris(
            b"<root/>",
            review_cases=[
                {
                    "case_id": "a" * 64,
                    "reference_occurrence": "/" + "x" * 4096,
                }
            ],
        )


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
    with pytest.raises(ValueError, match="URI bound"):
        screen_pbs_native_uris(
            b'<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><a rdf:resource="long"/></root>'
        )
    monkeypatch.setattr(module, "MAX_URI_CHARS", 100)
    monkeypatch.setattr(module, "MAX_INDEXED_URI_CHARS", 0)
    with pytest.raises(ValueError, match="indexed URI bound"):
        screen_pbs_native_uris(
            b'<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><a rdf:resource="x"/></root>'
        )


def test_reference_and_element_count_bounds(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(module, "MAX_REFERENCE_ROWS", 0)
    with pytest.raises(ValueError, match="reference bound"):
        screen_pbs_native_uris(
            b'<root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><a rdf:resource="x"/></root>'
        )
    monkeypatch.setattr(module, "MAX_REFERENCE_ROWS", 8_000_000)
    monkeypatch.setattr(module, "MAX_ELEMENTS", 1)
    element = type("Element", (), {"tag": "root", "attrib": {}})()

    def over_limit_events(_member, *, policy):
        del policy
        yield "start", element, None
        yield "start", element, None

    monkeypatch.setattr(module, "iter_xml_events", over_limit_events)
    with pytest.raises(ValueError, match="element bound"):
        screen_pbs_native_uris(b"<root><child/></root>")


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
