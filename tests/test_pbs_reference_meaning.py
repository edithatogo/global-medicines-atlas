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


def _per_kind_receipt(tmp_path):
    receipt = json.loads((ROOT / SCREEN_RECEIPT).read_text())
    qualification = receipt["report"]["qualification"]
    qualification["reference_kind_status_counts"] = {
        "rdf_resource": {"unique_exact_literal": 1_500_000},
        "xlink_href": {
            "unique_exact_literal": 586_489,
            "no_exact_literal": 73_577,
        },
    }
    qualification["reference_kind_counts"] = {
        "rdf_resource": 1_500_000,
        "xlink_href": 660_066,
    }
    canonical = json.dumps(
        receipt["report"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    receipt["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    path = tmp_path / "hosted-screen.json"
    path.write_text(json.dumps(receipt))
    return path


def test_per_kind_receipt_is_bound_and_never_promoted(tmp_path):
    path = _per_kind_receipt(tmp_path)
    report = review_reference_meanings(tmp_path, path, require_per_kind=True)
    assert report["schema_version"] == 2
    assert (
        report["source"]["screen_receipt_sha256"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    assert report["source"]["screen_run_id"] == "39730665004"
    assert report["source"]["screen_workflow_commit"] == (
        "c9fd61e92bf9c36d46f37d941a0cbdaf3db1b1f4"
    )
    assert (
        report["exact_source_screen"]["per_kind"]["rdf_resource"][
            "reference_fields"
        ]
        == 1_500_000
    )
    assert (
        report["exact_source_screen"]["per_kind_match_counts_available"] is True
    )
    assert report["scope"]["semantic_relationships_qualified"] is False
    assert all(
        not item["semantic_links_qualified"]
        for item in report["exact_source_screen"]["per_kind"].values()
    )


def test_per_kind_receipt_rejects_denominator_or_identity_mismatch(tmp_path):
    path = _per_kind_receipt(tmp_path)
    receipt = json.loads(path.read_text())
    receipt["report"]["qualification"]["reference_kind_counts"][
        "xlink_href"
    ] -= 1
    canonical = json.dumps(
        receipt["report"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    receipt["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="denominator differs"):
        review_reference_meanings(tmp_path, path, require_per_kind=True)

    receipt["report"]["revision"] = "0" * 40
    canonical = json.dumps(
        receipt["report"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    receipt["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="source contract differs"):
        review_reference_meanings(tmp_path, path, require_per_kind=True)


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
