"""Reference meaning review preserves lexical candidates without promoting links."""

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
