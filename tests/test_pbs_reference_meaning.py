"""Reference meaning review preserves lexical candidates without promoting links."""

import hashlib
import json
from pathlib import Path

import pytest
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE

import global_medicines_atlas.pbs_reference_meaning as meaning_module
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)
from global_medicines_atlas.pbs_native_reference_screen import (
    screen_native_references,
)
from global_medicines_atlas.pbs_reference_context import (
    encode_reference_context_receipt,
)
from global_medicines_atlas.pbs_reference_meaning import (
    MAX_CONTEXT_REPORT_BYTES,
    SCREEN_RECEIPT,
    _count_mapping,  # ruff: ignore[import-private-name]
    _string_keyed_mapping,  # ruff: ignore[import-private-name]
    _validate_expected_run_identity,  # ruff: ignore[import-private-name]
    _validate_reference_context,  # ruff: ignore[import-private-name]
    _validated_per_kind,  # ruff: ignore[import-private-name]
    review_reference_meanings,
)

ROOT = Path(__file__).resolve().parents[1]


def _receipt_with_report(tmp_path, mutate):
    envelope = json.loads((ROOT / SCREEN_RECEIPT).read_bytes())
    mutate(envelope["report"])
    canonical = json.dumps(
        envelope["report"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    envelope["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(envelope))
    return path


def _context(references=2_160_066):
    return {
        "schema_id": "global-medicines-atlas.pbs-reference-context-screen",
        "schema_version": 1,
        "reference_occurrences": references,
        "strata_count": 1,
        "examples_emitted": 0,
        "examples_omitted": 0,
        "unique_exact_literal_no_xml_base_candidates": 0,
        "strata": [
            {
                "kind": "rdf_resource",
                "match_status": "unique_exact_literal",
                "predicate_element_qname": "{urn:source}link",
                "nearest_subject_element_qname": "{urn:source}item",
                "nearest_identifier_element_qname": "none",
                "xml_base_context": "no_xml_base",
                "literal_shape": "relative_or_other",
                "occurrences": references,
                "unique_target_occurrences": 2_086_489,
                "ambiguous_target_occurrences": 0,
                "no_xml_base_exact_target_occurrences": 0,
                "unique_exact_literal_no_xml_base_candidates": 0,
                "examples_omitted": 0,
                "examples": [],
            }
        ],
        "uri_resolution_performed": False,
        "literal_values_emitted": False,
        "raw_source_emitted": False,
        "semantic_relationships_qualified": False,
        "external_targets_fetched": 0,
    }


def _enriched_context(references=2):
    context = _context(references)
    context["schema_version"] = 3
    context["example_selection_policy"] = (
        "up_to_five_value_free_examples_per_structural_stratum"
    )
    context["uri_resolution_screen_performed"] = True
    context["document_scope"] = "single_xml_member"
    for row in context["strata"]:
        row["uri_resolution_profile"] = "document_uri_unavailable"
        row["document_scope"] = "single_xml_member"
        row["predicate_role"] = "rdf_resource_attribute"
        row["target_element_type_occurrence_counts"] = {"{urn:source}target": 1}
    return context


def test_exact_source_review_qualifies_candidate_scope_not_semantic_links():
    report = review_reference_meanings(ROOT)
    assert report["exact_source_screen"]["definitions"] == 567_785
    assert report["exact_source_screen"]["references"] == 2_160_066
    assert (
        report["exact_source_screen"]["unique_exact_literal_candidates"]
        == 2_086_489
    )
    assert report["exact_source_screen"]["no_exact_literal"] == 73_577
    assert (
        report["exact_source_screen"]["per_kind_match_counts_available"]
        is False
    )
    assert (
        report["reference_kinds"]["rdf_resource_to_rdf_about"][
            "semantic_links_qualified"
        ]
        is False
    )
    assert (
        report["reference_kinds"]["xlink_fragment_to_xml_id"][
            "semantic_links_qualified"
        ]
        is False
    )
    assert report["calibration"]["source_semantic_precision"] == (
        "not estimable from aggregate-only source receipt"
    )
    assert report["scope"]["semantic_relationships_qualified"] is False


def test_review_rejects_changed_exact_source_receipt(tmp_path):
    receipt_path = tmp_path / SCREEN_RECEIPT
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes((ROOT / SCREEN_RECEIPT).read_bytes() + b" ")
    with pytest.raises(ValueError, match="receipt digest differs"):
        review_reference_meanings(tmp_path)


def test_per_kind_count_reconciliation_stays_diagnostic():
    qualification = {
        "reference_kind_status_counts": {
            "rdf_resource": {"unique_exact_literal": 150},
            "xlink_href": {
                "unique_exact_literal": 58,
                "no_exact_literal": 42,
            },
        },
        "reference_kind_counts": {"rdf_resource": 150, "xlink_href": 100},
    }
    normalized = _validated_per_kind(
        qualification,
        {"unique_exact_literal": 208, "no_exact_literal": 42},
        250,
    )
    assert normalized is not None
    assert normalized["rdf_resource"]["reference_fields"] == 150
    assert all(
        not item["semantic_links_qualified"] for item in normalized.values()
    )

    qualification["reference_kind_counts"]["xlink_href"] -= 1
    with pytest.raises(ValueError, match="denominator differs"):
        _validated_per_kind(
            qualification,
            {"unique_exact_literal": 208, "no_exact_literal": 42},
            250,
        )


def test_per_kind_counts_reject_boolean_and_non_string_keys():
    qualification = {
        "reference_kind_status_counts": {
            "rdf_resource": {"unique_exact_literal": True},
            "xlink_href": {"unique_exact_literal": 1},
        },
        "reference_kind_counts": {"rdf_resource": 1, "xlink_href": 1},
    }
    with pytest.raises(ValueError, match="status counts are invalid"):
        _validated_per_kind(
            qualification,
            {"unique_exact_literal": 2},
            2,
        )

    qualification["reference_kind_status_counts"] = {
        "rdf_resource": {1: 1},
        "xlink_href": {"unique_exact_literal": 1},
    }
    with pytest.raises(ValueError, match="status counts are invalid"):
        _validated_per_kind(
            qualification,
            {"unique_exact_literal": 2},
            2,
        )


def test_synthetic_screen_receipt_cannot_generate_exact_source_report(tmp_path):
    # This standalone fixture deliberately uses synthetic source and run IDs.
    synthetic = {
        "report": {
            "schema_version": 1,
            "status": "passed",
            "operation": "pbs-native-reference-screen",
            "dataset": "synthetic/pbs-screen-fixture",
            "revision": "synthetic-revision-001",
            "run_id": "10000000001",
            "run_attempt": "1",
            "workflow_commit": "a" * 40,
            "source_receipt_file_sha256": "b" * 64,
            "qualification": {
                "schema_id": "global-medicines-atlas.pbs-native-reference-screen",
                "schema_version": 1,
                "member_sha256": "c" * 64,
                "native_fields": 250,
                "reference_fields": 250,
                "reference_fields_sha256": "d" * 64,
                "reference_status_counts": {
                    "unique_exact_literal": 208,
                    "no_exact_literal": 42,
                },
                "reference_kind_status_counts": {
                    "rdf_resource": {"unique_exact_literal": 150},
                    "xlink_href": {
                        "unique_exact_literal": 58,
                        "no_exact_literal": 42,
                    },
                },
                "reference_kind_counts": {
                    "rdf_resource": 150,
                    "xlink_href": 100,
                },
                "semantic_relationships_qualified": False,
                "domain_semantics_qualified": False,
                "native_values_emitted": False,
                "external_targets_fetched": 0,
                "new_sources": 0,
                "new_admissions": 0,
                "publications": 0,
            },
            "rights_conclusion_changed": False,
            "publication_performed": False,
        }
    }
    canonical = json.dumps(
        synthetic["report"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    synthetic["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    path = tmp_path / "synthetic-screen-receipt.json"
    path.write_text(json.dumps(synthetic))
    with pytest.raises(ValueError, match="source contract differs"):
        review_reference_meanings(
            tmp_path,
            path,
            require_per_kind=True,
            expected_exact_commit="a" * 40,
            expected_run_id="10000000001",
        )


def test_expected_hosted_run_binding_accepts_and_rejects_synthetic_identity():
    report = {
        "workflow_commit": "a" * 40,
        "run_id": "10000000001",
    }
    _validate_expected_run_identity(report, "a" * 40, "10000000001")
    with pytest.raises(ValueError, match="workflow commit differs"):
        _validate_expected_run_identity(report, "b" * 40, "10000000001")
    with pytest.raises(ValueError, match="workflow run ID differs"):
        _validate_expected_run_identity(report, "a" * 40, "10000000002")
    with pytest.raises(ValueError, match="exact-main commit is invalid"):
        _validate_expected_run_identity(report, "bad", "10000000001")
    with pytest.raises(ValueError, match="workflow run ID is invalid"):
        _validate_expected_run_identity(report, "a" * 40, "not-a-run")


def test_receipt_mappings_reject_unknown_keys_and_non_integer_counts():
    assert _string_keyed_mapping([]) is None
    assert _string_keyed_mapping({1: "bad"}) is None
    assert _count_mapping({"unexpected": 1}, {"known"}) is None
    assert _count_mapping({"known": True}, {"known"}) is None
    assert _count_mapping({"known": -1}, {"known"}) is None
    assert _count_mapping({"known": "1"}, {"known"}) is None
    assert _count_mapping({"known": 1}, {"known"}) == {"known": 1}


def test_per_kind_reconciliation_rejects_malformed_maps_and_aggregate_drift():
    assert _validated_per_kind({}, {}, 0) is None
    base = {
        "reference_kind_status_counts": {
            "rdf_resource": {"unique_exact_literal": 2},
            "xlink_href": {"no_exact_literal": 1},
        },
        "reference_kind_counts": {"rdf_resource": 2, "xlink_href": 1},
    }
    aggregate = {"unique_exact_literal": 2, "no_exact_literal": 1}
    for qualification in (
        {**base, "reference_kind_status_counts": {1: "bad"}},
        {**base, "reference_kind_counts": {"rdf_resource": True}},
        {
            **base,
            "reference_kind_status_counts": {
                "rdf_resource": {"unique_exact_literal": 2},
                "xlink_href": {"unique_exact_literal": -1},
            },
        },
    ):
        with pytest.raises(ValueError, match="PBS per-kind"):
            _validated_per_kind(qualification, aggregate, 3)
    with pytest.raises(ValueError, match="aggregate denominators differ"):
        _validated_per_kind(
            base, {"unique_exact_literal": 1, "no_exact_literal": 2}, 3
        )


def test_v2_report_path_keeps_per_kind_candidates_diagnostic(tmp_path):
    def add_synthetic_kinds(report):
        qualification = report["qualification"]
        qualification["reference_context"] = encode_reference_context_receipt(
            _context()
        )
        qualification["reference_kind_status_counts"] = {
            "rdf_resource": {"unique_exact_literal": 1_043_244},
            "xlink_href": {
                "unique_exact_literal": 1_043_245,
                "no_exact_literal": 73_577,
            },
        }
        qualification["reference_kind_counts"] = {
            "rdf_resource": 1_043_244,
            "xlink_href": 1_116_822,
        }

    path = _receipt_with_report(tmp_path, add_synthetic_kinds)
    result = review_reference_meanings(
        ROOT,
        path,
        require_per_kind=True,
        expected_exact_commit="c9fd61e92bf9c36d46f37d941a0cbdaf3db1b1f4",
        expected_run_id="39730665004",
    )
    assert result["schema_version"] == 3
    assert result["source_context_screen"]["reference_occurrences"] == 2_160_066
    assert result["status"] == (
        "source_context_screen_reconciled_semantic_links_unqualified"
    )
    assert result["exact_source_screen"]["per_kind_match_counts_available"]
    assert result["scope"]["semantic_relationships_qualified"] is False


def test_enriched_v3_context_validates_without_promoting_links():
    validated = _validate_reference_context(_enriched_context(), 2)
    assert validated["schema_version"] == 3
    assert validated["document_scope"] == "single_xml_member"
    assert validated["semantic_relationships_qualified"] is False


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda context: context.update({
                "uri_resolution_screen_performed": False
            }),
            "PBS reference context contract differs",
        ),
        (
            lambda context: context["strata"][0].__setitem__(
                "uri_resolution_profile", "unrecognized"
            ),
            "PBS reference context enriched profile is invalid",
        ),
        (
            lambda context: context["strata"][0].__setitem__(
                "predicate_role", "unrecognized"
            ),
            "PBS reference context enriched profile is invalid",
        ),
        (
            lambda context: context["strata"][0].__setitem__(
                "target_element_type_occurrence_counts", {"": 1}
            ),
            "PBS reference context enriched profile is invalid",
        ),
        (
            lambda context: context["strata"][0].__setitem__(
                "target_element_type_occurrence_counts", []
            ),
            "PBS reference context enriched profile is invalid",
        ),
        (
            lambda context: context["strata"][0].__setitem__(
                "target_element_type_occurrence_counts",
                {"{urn:source}target": True},
            ),
            "PBS reference context enriched profile is invalid",
        ),
        (
            lambda context: context["strata"][0].__setitem__(
                "target_element_type_occurrence_counts",
                {"q" * 257: 1},
            ),
            "PBS reference context enriched profile is invalid",
        ),
    ],
)
def test_enriched_v3_context_rejects_malformed_profiles(mutate, message):
    context = _enriched_context()
    mutate(context)
    with pytest.raises(ValueError, match=message):
        _validate_reference_context(context, 2)


def test_missing_default_receipt_uses_the_documented_path_fallback(tmp_path):
    with pytest.raises(FileNotFoundError):
        review_reference_meanings(tmp_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("run_id", "not-a-run", "run identity is invalid"),
        ("workflow_commit", "bad", "workflow commit is invalid"),
        (
            "source_receipt_file_sha256",
            "bad",
            "source receipt digest is invalid",
        ),
    ],
)
def test_source_receipt_rejects_malformed_run_identity(
    tmp_path, field, value, message
):
    path = _receipt_with_report(
        tmp_path, lambda report: report.__setitem__(field, value)
    )
    with pytest.raises(ValueError, match=message):
        review_reference_meanings(ROOT, path)


def test_review_requires_exact_run_binding_and_per_kind_counts():
    with pytest.raises(ValueError, match="expected exact-main commit"):
        review_reference_meanings(ROOT, require_per_kind=True)
    with pytest.raises(
        ValueError, match="per-kind reference counts are required"
    ):
        review_reference_meanings(
            ROOT,
            require_per_kind=True,
            expected_exact_commit="c9fd61e92bf9c36d46f37d941a0cbdaf3db1b1f4",
            expected_run_id="39730665004",
        )


def test_exact_receipt_requires_context_and_context_denominator(tmp_path):
    without_context = _receipt_with_report(
        tmp_path,
        lambda report: report["qualification"].update({
            "reference_kind_status_counts": {
                "rdf_resource": {"unique_exact_literal": 1_043_244},
                "xlink_href": {
                    "unique_exact_literal": 1_043_245,
                    "no_exact_literal": 73_577,
                },
            },
            "reference_kind_counts": {
                "rdf_resource": 1_043_244,
                "xlink_href": 1_116_822,
            },
        }),
    )
    with pytest.raises(ValueError, match="context is required"):
        review_reference_meanings(
            ROOT,
            without_context,
            require_per_kind=True,
            expected_exact_commit="c9fd61e92bf9c36d46f37d941a0cbdaf3db1b1f4",
            expected_run_id="39730665004",
        )

    def add_context(report):
        report["qualification"]["reference_context"] = _context(2_160_065)

    wrong_denominator = _receipt_with_report(tmp_path, add_context)
    with pytest.raises(ValueError, match="denominator differs"):
        review_reference_meanings(ROOT, wrong_denominator)


def test_reference_context_rejects_source_values(tmp_path):
    def add_value(report):
        context = _context()
        context["strata"][0]["examples"] = [
            {"literal": "withheld source value"}
        ]
        context["examples_emitted"] = 1
        report["qualification"]["reference_context"] = context

    path = _receipt_with_report(tmp_path, add_value)
    with pytest.raises(ValueError, match="contains source values"):
        review_reference_meanings(ROOT, path)


def test_reference_context_validation_rejects_non_object_and_non_string_keys():
    with pytest.raises(TypeError, match="must be an object"):
        _validate_reference_context("invalid", 0)
    with pytest.raises(ValueError, match="keys are invalid"):
        _validate_reference_context({1: "invalid"}, 0)


def test_reference_context_validation_accepts_stratified_v2_and_rejects_policy():
    profile = {
        **_context(),
        "schema_version": 2,
        "example_selection_policy": (
            "up_to_five_value_free_examples_per_structural_stratum"
        ),
    }
    assert (
        _validate_reference_context(profile, 2_160_066)[
            "example_selection_policy"
        ]
        == "up_to_five_value_free_examples_per_structural_stratum"
    )
    with pytest.raises(ValueError, match="contract differs"):
        _validate_reference_context(
            {**profile, "example_selection_policy": "unbounded"},
            2_160_066,
        )


def test_reference_context_compressed_envelope_byte_limit_is_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _context()
    envelope = encode_reference_context_receipt(profile)
    monkeypatch.setattr(meaning_module, "MAX_COMPRESSED_RECEIPT_BYTES", 1)

    with pytest.raises(
        ValueError, match="compressed reference context byte bound"
    ):
        _validate_reference_context(envelope, 2_160_066)


@pytest.mark.parametrize(
    ("context", "message"),
    [
        ({"schema_id": "x" * (MAX_CONTEXT_REPORT_BYTES + 1)}, "byte bound"),
        ({**_context(), "unexpected": True}, "schema differs"),
        ({**_context(), "schema_version": True}, "count is invalid"),
        ({**_context(), "schema_id": "wrong"}, "contract differs"),
        (
            {
                **_context(),
                "schema_version": 2,
                "example_selection_policy": "wrong",
            },
            "contract differs",
        ),
        ({**_context(), "strata": "not a list"}, "strata must be a list"),
        ({**_context(), "strata_count": 2}, "contract differs"),
        ({**_context(), "examples_emitted": 1_001}, "contract differs"),
        ({**_context(), "external_targets_fetched": 1}, "contract differs"),
        (
            {**_context(), "semantic_relationships_qualified": True},
            "contract differs",
        ),
        (
            {
                **_context(),
                "strata": [{**_context()["strata"][0], "occurrences": -1}],
            },
            "stratum count is invalid",
        ),
        (
            {**_context(), "strata": ["not an object"]},
            "stratum must be an object",
        ),
        (
            {
                **_context(),
                "strata": [
                    {**_context()["strata"][0], "examples": "not a list"}
                ],
            },
            "examples are invalid",
        ),
        (
            {
                **_context(),
                "strata": [{**_context()["strata"][0], "occurrences": 2}],
            },
            "denominator differs",
        ),
    ],
)
def test_reference_context_rejects_malformed_receipt_contract(
    tmp_path, context, message
):
    path = _receipt_with_report(
        tmp_path,
        lambda report: report["qualification"].__setitem__(
            "reference_context", context
        ),
    )
    with pytest.raises((TypeError, ValueError), match=message):
        review_reference_meanings(ROOT, path)


def test_receipt_reader_and_aggregate_denominators_fail_closed(tmp_path):
    bad_digest = json.loads((ROOT / SCREEN_RECEIPT).read_bytes())
    bad_digest["report"]["run_id"] = "corrupt-receipt"
    path = tmp_path / "bad-report-digest.json"
    path.write_text(json.dumps(bad_digest))
    with pytest.raises(ValueError, match="report digest differs"):
        review_reference_meanings(ROOT, path)

    invalid_counts = _receipt_with_report(
        tmp_path,
        lambda report: report["qualification"].__setitem__(
            "reference_status_counts", {"unique_exact_literal": 1}
        ),
    )
    with pytest.raises(ValueError, match="aggregate counts are invalid"):
        review_reference_meanings(ROOT, invalid_counts)

    wrong_denominator = _receipt_with_report(
        tmp_path,
        lambda report: report["qualification"][
            "reference_status_counts"
        ].__setitem__("unique_exact_literal", 2_086_488),
    )
    with pytest.raises(ValueError, match="denominator differs"):
        review_reference_meanings(ROOT, wrong_denominator)


def test_different_base_uri_contexts_never_promote_same_literal():
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
    screen = screen_native_references(
        archive,
        xml,
        parent,
        build_pbs_xml_member_binding(archive, parent),
    )
    assert screen["reference_status_counts"] == {"unique_exact_literal": 1}
    assert screen["semantic_relationships_qualified"] is False
