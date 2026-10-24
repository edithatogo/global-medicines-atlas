"""PBS contextual screening emits structure and counts, never source values."""

import base64
import hashlib
import json
import zlib

import pytest

import global_medicines_atlas.pbs_reference_context as context_module
from global_medicines_atlas.pbs_reference_context import (
    ReferenceContextError,
    screen_reference_context,
)


def test_context_screen_reports_occurrence_structure_without_literals():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns:xlink="http://www.w3.org/1999/xlink">
      <rdf:Description xml:id="private-id" rdf:about="https://example.invalid/private">
        <rdf:resource rdf:resource="https://example.invalid/private"/>
      </rdf:Description>
      <group xml:base="https://example.invalid/base/">
        <link xlink:href="#private-id"/>
        <link xlink:href="relative-target"/>
      </group>
    </root>"""
    report = screen_reference_context(xml)
    serialized = json.dumps(report)
    assert report["reference_occurrences"] == 3
    assert report["literal_values_emitted"] is False
    assert report["raw_source_emitted"] is False
    assert report["semantic_relationships_qualified"] is False
    assert report["uri_resolution_performed"] is False
    assert report["uri_resolution_screen_performed"] is True
    assert report["document_scope"] == "single_xml_member"
    assert report["external_targets_fetched"] == 0
    assert "private-id" not in serialized
    assert "example.invalid" not in serialized
    assert "relative-target" not in serialized
    assert any(
        row["match_status"] == "unique_exact_literal"
        and row["literal_shape"] == "absolute_looking"
        for row in report["strata"]
    )
    assert any(
        row["xml_base_context"] == "xml_base_present"
        and row["literal_shape"] == "fragment"
        for row in report["strata"]
    )
    assert any(
        row["uri_resolution_profile"] == "same_member_fragment_candidate"
        and row["predicate_role"] == "xlink_href_attribute"
        for row in report["strata"]
    )
    assert any(
        row["target_element_type_occurrence_counts"] for row in report["strata"]
    )


def test_context_screen_emits_value_free_substage_progress(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context_module, "CONTEXT_PROGRESS_EVENT_INTERVAL", 1)
    monkeypatch.setattr(
        context_module, "CONTEXT_PROGRESS_OCCURRENCE_INTERVAL", 1
    )
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <edge rdf:resource="private-target"/>
    </root>"""
    checkpoints: list[tuple[str, int, int]] = []

    report = screen_reference_context(
        xml,
        progress=lambda phase, batches, rows: checkpoints.append((
            phase,
            batches,
            rows,
        )),
    )

    assert [checkpoint[0] for checkpoint in checkpoints] == [
        "reference-context-index",
        "reference-context-index",
        "reference-context-index",
        "reference-context-index",
        "reference-context-index",
        "reference-context-join",
        "reference-context-aggregate",
        "reference-context-report",
    ]
    assert checkpoints[0] == ("reference-context-index", 0, 0)
    assert checkpoints[5:] == [
        ("reference-context-join", 1, 1),
        ("reference-context-aggregate", 1, 1),
        ("reference-context-report", 1, 1),
    ]
    assert "private-target" not in json.dumps(checkpoints)
    assert report["reference_occurrences"] == 1


def test_context_failure_code_rejects_values_outside_allowlist():
    with pytest.raises(
        ValueError, match="invalid reference context diagnostic code"
    ):
        ReferenceContextError("private-source-value", "must not be retained")


def test_context_screen_is_deterministic_and_classifies_negative_controls():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <a rdf:about="same"/><a rdf:about="same"/>
      <b rdf:resource="same"/><b rdf:resource="missing"/><b rdf:resource=""/>
    </root>"""
    report = screen_reference_context(xml)
    assert report == screen_reference_context(xml)
    statuses = {row["match_status"] for row in report["strata"]}
    assert statuses == {
        "ambiguous_exact_literal",
        "no_exact_literal",
        "empty_literal",
    }


def test_context_screen_classifies_uri_resolution_without_emitting_uri():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <group xml:base="https://private.example/base/">
        <edge rdf:resource="relative-target"/>
      </group>
      <edge rdf:resource="unbased-relative"/>
      <edge rdf:resource="https://private.example/absolute"/>
    </root>"""

    report = screen_reference_context(xml)

    profiles = {row["uri_resolution_profile"] for row in report["strata"]}
    assert profiles == {
        "resolved_against_absolute_xml_base_candidate",
        "document_uri_unavailable",
        "absolute_uri_candidate",
    }
    serialized = json.dumps(report)
    assert "private.example" not in serialized
    assert "relative-target" not in serialized
    assert "unbased-relative" not in serialized


def test_context_examples_cover_structural_strata_without_emitting_values():
    links = "".join(
        f'<edge-{index} rdf:resource="missing-{index}"/>' for index in range(20)
    )
    xml = (
        '<root xmlns="http://schema.pbs.gov.au/" '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        'xmlns:xml="http://www.w3.org/XML/1998/namespace">'
        '<target rdf:about="shared-target"/>'
        '<target xml:id="fragment-target"/>'
        + links
        + '<exact rdf:resource="shared-target"/>'
        + '<fragment xlink:href="#fragment-target"/>'
        + "</root>"
    ).encode()

    report = screen_reference_context(xml)

    assert report["examples_emitted"] == report["strata_count"]
    assert all(len(row["examples"]) == 1 for row in report["strata"])
    assert all(
        row["examples_omitted"] == row["occurrences"] - 1
        for row in report["strata"]
    )
    serialized = json.dumps(report)
    for private_value in (
        "missing-",
        "shared-target",
        "fragment-target",
    ):
        assert private_value not in serialized


def test_context_receipt_compression_round_trips_the_complete_profile():
    context = screen_reference_context(
        b'<root xmlns="http://schema.pbs.gov.au/" '
        b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<edge rdf:resource="private-target"/></root>'
    )

    receipt = context_module.encode_reference_context_receipt(context)

    assert receipt["schema_id"].endswith("-compressed")
    assert context_module.decode_reference_context_receipt(receipt) == context
    assert len(json.dumps(receipt).encode()) <= (
        context_module.MAX_COMPRESSED_RECEIPT_BYTES
    )


def test_context_receipt_compression_fits_high_cardinality_profile():
    strata = [
        {
            "kind": "rdf_resource",
            "match_status": "unique_exact_literal",
            "predicate_element_qname": (
                "{http://schema.pbs.gov.au/}reference-element-" + str(index)
            ),
            "nearest_subject_element_qname": (
                "{http://schema.pbs.gov.au/}subject-element-" + str(index)
            ),
            "nearest_identifier_element_qname": "none",
            "xml_base_context": "no_xml_base",
            "literal_shape": "absolute_looking",
            "occurrences": 1,
            "unique_target_occurrences": 1,
            "ambiguous_target_occurrences": 0,
            "no_xml_base_exact_target_occurrences": 1,
            "unique_exact_literal_no_xml_base_candidates": 1,
            "examples_omitted": 0,
            "examples": [],
        }
        for index in range(400)
    ]
    context = {
        "schema_id": "global-medicines-atlas.pbs-reference-context-screen",
        "schema_version": 1,
        "reference_occurrences": len(strata),
        "strata_count": len(strata),
        "examples_emitted": 0,
        "examples_omitted": 0,
        "unique_exact_literal_no_xml_base_candidates": len(strata),
        "strata": strata,
        "uri_resolution_performed": False,
        "literal_values_emitted": False,
        "raw_source_emitted": False,
        "semantic_relationships_qualified": False,
        "external_targets_fetched": 0,
    }

    uncompressed = json.dumps(context, separators=(",", ":")).encode()
    receipt = context_module.encode_reference_context_receipt(context)

    assert len(uncompressed) > 31_000
    assert len(json.dumps(receipt).encode()) < len(uncompressed)
    assert context_module.decode_reference_context_receipt(receipt) == context


def test_context_receipt_compression_enforces_parent_receipt_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = screen_reference_context(
        b'<root xmlns="http://schema.pbs.gov.au/"/>'
    )
    monkeypatch.setattr(context_module, "MAX_COMPRESSED_RECEIPT_BYTES", 1)
    with pytest.raises(ReferenceContextError) as captured:
        context_module.encode_reference_context_receipt(context)
    assert captured.value.diagnostic_code == (
        "context-compressed-report-byte-limit"
    )


def test_context_receipt_decoder_rejects_tampered_payload():
    context = screen_reference_context(
        b'<root xmlns="http://schema.pbs.gov.au/"/>'
    )
    receipt = context_module.encode_reference_context_receipt(context)
    receipt["payload_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="integrity differs"):
        context_module.decode_reference_context_receipt(receipt)


def _envelope_for_payload(payload: bytes) -> dict[str, object]:
    return {
        "schema_id": (
            "global-medicines-atlas.pbs-reference-context-screen-compressed"
        ),
        "schema_version": 1,
        "encoding": "zlib-base64-json",
        "uncompressed_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "payload": base64.b64encode(zlib.compress(payload)).decode("ascii"),
    }


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("schema_id", "wrong-schema"),
        ("schema_version", 2),
        ("encoding", "gzip-json"),
        ("uncompressed_bytes", True),
        ("uncompressed_bytes", -1),
        (
            "uncompressed_bytes",
            context_module.MAX_REPORT_STRATA_BYTES + 1,
        ),
        ("payload_sha256", None),
        ("payload_sha256", "0" * 63),
        ("payload_sha256", "z" * 64),
        ("payload", None),
        ("payload", "\u2603"),
        ("payload", "x" * (context_module.MAX_COMPRESSED_RECEIPT_BYTES + 1)),
    ],
)
def test_context_receipt_decoder_rejects_invalid_envelope_fields(
    field: str, replacement: object
) -> None:
    receipt = _envelope_for_payload(b"{}")
    receipt[field] = replacement

    with pytest.raises((TypeError, ValueError)):
        context_module.decode_reference_context_receipt(receipt)


def test_context_receipt_decoder_rejects_wrong_shape_and_payload_type():
    with pytest.raises(TypeError, match="must be an object"):
        context_module.decode_reference_context_receipt([])

    receipt = _envelope_for_payload(b"{}")
    receipt.pop("payload")
    with pytest.raises(ValueError, match="schema differs"):
        context_module.decode_reference_context_receipt(receipt)

    receipt = _envelope_for_payload(b"[]")
    with pytest.raises(TypeError, match="payload differs"):
        context_module.decode_reference_context_receipt(receipt)


@pytest.mark.parametrize(
    "encoded",
    ["!", base64.b64encode(b"not-zlib").decode("ascii")],
)
def test_context_receipt_decoder_rejects_invalid_compressed_bytes(encoded: str):
    receipt = _envelope_for_payload(b"{}")
    receipt["payload"] = encoded

    with pytest.raises(ValueError, match="is invalid"):
        context_module.decode_reference_context_receipt(receipt)


@pytest.mark.parametrize(
    "compressed",
    [
        zlib.compress(b"{}")[:-1],
        zlib.compress(b"{}") + b"trailing",
    ],
)
def test_context_receipt_decoder_rejects_incomplete_or_trailing_streams(
    compressed: bytes,
):
    receipt = _envelope_for_payload(b"{}")
    receipt["payload"] = base64.b64encode(compressed).decode("ascii")

    with pytest.raises(ValueError, match="integrity differs"):
        context_module.decode_reference_context_receipt(receipt)


def test_context_receipt_decoder_rejects_length_and_decompression_overflow():
    receipt = _envelope_for_payload(b"{}")
    receipt["uncompressed_bytes"] = 3
    with pytest.raises(ValueError, match="integrity differs"):
        context_module.decode_reference_context_receipt(receipt)

    oversized = b"x" * (context_module.MAX_REPORT_STRATA_BYTES + 1)
    receipt = _envelope_for_payload(oversized)
    receipt["uncompressed_bytes"] = context_module.MAX_REPORT_STRATA_BYTES
    with pytest.raises(ValueError, match="integrity differs"):
        context_module.decode_reference_context_receipt(receipt)


def test_context_report_uncompressed_bound_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = screen_reference_context(
        b'<root xmlns="http://schema.pbs.gov.au/"/>'
    )
    monkeypatch.setattr(context_module, "MAX_REPORT_STRATA_BYTES", 1)

    with pytest.raises(ReferenceContextError) as captured:
        context_module.encode_reference_context_receipt(context)
    assert captured.value.diagnostic_code == "context-report-byte-limit"


def test_nested_subject_and_duplicate_targets_have_exact_occurrence_addresses():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <outer rdf:about="urn:subject">
        <wrapper><edge rdf:resource="urn:target"/></wrapper>
      </outer>
      <target rdf:about="urn:target"/>
      <target rdf:about="urn:target"/>
    </root>"""
    report = screen_reference_context(xml)
    row = next(
        row
        for row in report["strata"]
        if row["match_status"] == "ambiguous_exact_literal"
    )
    example = row["examples"][0]
    assert row["predicate_element_qname"] == "{http://schema.pbs.gov.au/}edge"
    assert (
        row["nearest_subject_element_qname"]
        == "{http://schema.pbs.gov.au/}outer"
    )
    assert (
        example["predicate_element"]["qname"]
        == "{http://schema.pbs.gov.au/}edge"
    )
    assert example["predicate_element"]["occurrence"].endswith("}edge/1")
    assert (
        example["nearest_subject_element"]["qname"]
        == "{http://schema.pbs.gov.au/}outer"
    )
    assert example["nearest_subject_element"]["occurrence"].endswith("}outer/1")
    assert example["target_multiplicity"] == 2
    assert [target["qname"] for target in example["targets"]] == [
        "{http://schema.pbs.gov.au/}target",
        "{http://schema.pbs.gov.au/}target",
    ]
    assert [
        target["occurrence"].rsplit("/", 1)[-1] for target in example["targets"]
    ] == ["1", "2"]
    serialized = json.dumps(report)
    assert "urn:subject" not in serialized
    assert "urn:target" not in serialized


def test_reference_and_target_base_contexts_are_reported_without_resolution():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <target rdf:about="https://example.invalid/clean"/>
      <edge rdf:resource="https://example.invalid/clean"/>
      <scope xml:base="https://example.invalid/base/">
        <target rdf:about="https://example.invalid/target-based"/>
      </scope>
      <edge rdf:resource="https://example.invalid/target-based"/>
      <target rdf:about="https://example.invalid/reference-based"/>
      <scope xml:base="https://example.invalid/other/">
        <edge rdf:resource="https://example.invalid/reference-based"/>
      </scope>
      <target rdf:about="https://example.invalid/shared"/>
      <edge rdf:resource="https://example.invalid/shared"/>
      <scope xml:base="https://example.invalid/scope/">
        <edge rdf:resource="https://example.invalid/shared"/>
      </scope>
    </root>"""
    report = screen_reference_context(xml)
    assert report["unique_exact_literal_no_xml_base_candidates"] == 2
    rows = [
        row
        for row in report["strata"]
        if row["kind"] == "rdf_resource"
        and row["match_status"] == "unique_exact_literal"
    ]
    target_contexts = [
        (row["xml_base_context"], example["targets"][0]["xml_base_context"])
        for row in rows
        for example in row["examples"]
    ]
    assert ("no_xml_base", "no_xml_base") in target_contexts
    assert ("no_xml_base", "xml_base_present") in target_contexts
    assert ("xml_base_present", "no_xml_base") in target_contexts
    reference_contexts_by_target: dict[str, set[str]] = {}
    for row in rows:
        for example in row["examples"]:
            for target in example["targets"]:
                reference_contexts_by_target.setdefault(
                    target["occurrence"], set()
                ).add(row["xml_base_context"])
    assert {
        "no_xml_base",
        "xml_base_present",
    } in reference_contexts_by_target.values()
    assert report["uri_resolution_performed"] is False
    serialized = json.dumps(report)
    assert "example.invalid" not in serialized


def test_xml_id_is_not_misreported_as_an_rdf_subject():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:xlink="http://www.w3.org/1999/xlink">
      <identifier xml:id="private-id"><link xlink:href="#private-id"/></identifier>
    </root>"""
    report = screen_reference_context(xml)
    example = next(
        row["examples"][0]
        for row in report["strata"]
        if row["kind"] == "xlink_href"
    )
    assert example["nearest_subject_element"] is None
    assert example["nearest_identifier_element"]["qname"] == (
        "{http://schema.pbs.gov.au/}identifier"
    )
    assert example["nearest_identifier_element"]["occurrence"].endswith(
        "}identifier/1"
    )
    assert report["semantic_relationships_qualified"] is False


@pytest.mark.parametrize(
    ("attribute", "namespaces"),
    [
        (b'xml:id="', b""),
        (
            b'rdf:about="',
            b' xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
        ),
        (
            b'rdf:resource="',
            b' xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
        ),
        (b'xlink:href="', b' xmlns:xlink="http://www.w3.org/1999/xlink"'),
    ],
)
def test_oversized_indexed_literals_fail_closed(
    attribute: bytes, namespaces: bytes
) -> None:
    literal = b"x" * (context_module.MAX_LITERAL_BYTES + 1)
    xml = (
        b'<root xmlns="http://schema.pbs.gov.au/"'
        + namespaces
        + b"><entry "
        + attribute
        + literal
        + b'"/></root>'
    )
    with pytest.raises(ValueError, match="literal byte bound"):
        screen_reference_context(xml)


def test_high_cardinality_context_strata_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(context_module, "MAX_STRATA", 1)
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <first rdf:resource="one"/><second rdf:resource="two"/>
    </root>"""
    with pytest.raises(ValueError, match="stratum bound"):
        screen_reference_context(xml)


def test_global_example_budget_records_omitted_occurrences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(context_module, "MAX_REPORT_EXAMPLES", 1)
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <target rdf:about="https://example.invalid/one"/>
      <target rdf:about="https://example.invalid/two"/>
      <edge rdf:resource="https://example.invalid/one"/>
      <edge rdf:resource="https://example.invalid/two"/>
    </root>"""
    report = screen_reference_context(xml)
    assert report["examples_emitted"] == 1
    assert report["examples_omitted"] == 1
    assert sum(row["examples_omitted"] for row in report["strata"]) == 1


def test_context_screen_rejects_wrong_root():
    with pytest.raises(ValueError, match="root does not match"):
        screen_reference_context(b"<wrong/>")
