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

from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)
from global_medicines_atlas.pbs_native_reference_screen import (
    screen_native_references,
)
from global_medicines_atlas.pbs_reference_meaning import (
    SCREEN_RECEIPT,
    _validate_expected_run_identity,  # ruff: ignore[import-private-name]
    _validated_per_kind,  # ruff: ignore[import-private-name]
    review_reference_meanings,
)

ROOT = Path(__file__).resolve().parents[1]


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
