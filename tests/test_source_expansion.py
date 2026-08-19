"""Bronze source-expansion program for WHO, Africa, FDA, EMA, utilisation."""

from __future__ import annotations

from pathlib import Path

import pytest

from global_medicines_atlas.adapters.source_expansion import (
    parse_native_records,
)
from global_medicines_atlas.bronze_landing import EVIDENTIARY_TRUTH_SENTENCE
from global_medicines_atlas.reuse_gate import (
    ReuseGateRequiredError,
    acquire_new_decision,
)
from global_medicines_atlas.source_catalog import load_source_catalog
from global_medicines_atlas.source_expansion import (
    AFRICAN_COVERAGE_JURISDICTIONS,
    HF_ROLE,
    INDEPENDENT_DIMENSIONS,
    INDEX_ID,
    CoverageFacet,
    acquire_expansion_source,
    acquire_without_reuse_gate,
    african_source_coverage_matrix,
    assert_program_invariants,
    binding_for,
    build_source_index,
    classify_bronze_disposition,
    dimensions_remain_independent,
    expansion_tracks,
    required_source_ids,
    run_expansion_reuse_gate,
    track_outcomes,
    write_source_index,
)
from global_medicines_atlas.source_expansion_catalog import (
    apply_expansion_to_catalog,
    existing_source_patches,
    expansion_jurisdictions,
    expansion_source_rows,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "source_expansion"


@pytest.mark.unit
def test_thirty_six_tracks_are_registered_in_order() -> None:
    tracks = expansion_tracks()
    assert [track.track_id for track in tracks] == list(range(1, 37))
    assert_program_invariants()
    families = {track.family.value for track in tracks}
    assert families >= {
        "who",
        "africa",
        "fda",
        "ema",
        "utilisation",
        "pharmacovigilance",
        "reconciliation",
    }


@pytest.mark.unit
def test_catalog_contains_every_inventoried_expansion_source() -> None:
    catalog_ids = {source.source_id for source in load_source_catalog()}
    required = required_source_ids() - {"global-medicines-source-index"}
    missing = sorted(required - catalog_ids)
    assert missing == []
    generated = {row["source_id"] for row in expansion_source_rows()}
    assert generated <= catalog_ids


@pytest.mark.unit
def test_reuse_gate_is_mandatory_before_acquire() -> None:
    with pytest.raises(ReuseGateRequiredError):
        acquire_without_reuse_gate("us-fda-nsde")
    with pytest.raises(ReuseGateRequiredError):
        acquire_expansion_source(
            "us-fda-nsde",
            repository_root=ROOT,
            reuse=None,
        )
    decision = run_expansion_reuse_gate("us-fda-nsde", repository_root=ROOT)
    assert decision.searched_surfaces == (
        "local_clones",
        "github",
        "hugging_face",
        "source_registry",
    )
    result = acquire_expansion_source(
        "us-fda-nsde",
        repository_root=ROOT,
        reuse=decision,
    )
    assert result.landed is False
    assert result.reuse_disposition
    assert result.blocker is not None


@pytest.mark.unit
def test_nsde_uses_verified_fda_spl_dataset() -> None:
    nsde = next(
        source
        for source in load_source_catalog()
        if source.source_id == "us-fda-nsde"
    )
    landing = str(nsde.landing_page)
    assert "structured-product-labeling-resources/nsde" in landing
    assert "open.fda.gov" not in landing
    assert "authoritative" in nsde.evidence_limit.lower() or (
        "verified" in nsde.evidence_limit.lower()
    )
    derived = next(
        source
        for source in load_source_catalog()
        if source.source_id == "us-openfda-nsde"
    )
    assert "derived" in derived.evidence_limit.lower()


@pytest.mark.unit
def test_faers_parse_is_lossless_and_not_causal() -> None:
    payload = (FIXTURES / "faers.json").read_bytes()
    records = parse_native_records(
        "us-fda-faers",
        payload,
        media_hint="json",
    )
    assert records[0]["primaryid"] == "1001"
    assert records[0]["caseid"] == "2001"
    assert "causality" not in records[0]
    eml = parse_native_records(
        "global-who-eml",
        (FIXTURES / "who-eml.csv").read_bytes(),
        media_hint="csv",
    )
    assert eml[0]["who_eml_id"] == "EML-001"
    assert "reimbursed" not in eml[0]


@pytest.mark.unit
def test_independent_dimensions_and_orange_book_te_limit() -> None:
    assert INDEPENDENT_DIMENSIONS == (
        "regulatory",
        "formulary",
        "reimbursement",
        "procurement",
        "pharmacovigilance",
        "utilisation",
        "terminology",
    )
    for source in load_source_catalog():
        if source.source_id in required_source_ids():
            assert dimensions_remain_independent(source)
    orange = next(
        source
        for source in load_source_catalog()
        if source.source_id == "us-fda-orange-book"
    )
    assert "substitutability" in orange.evidence_limit.lower()
    assert "Appl_No" in orange.native_identifier


@pytest.mark.unit
def test_credentialed_sources_are_metadata_only_not_coverage() -> None:
    catalog = {source.source_id: source for source in load_source_catalog()}
    vigibase = catalog["global-umc-vigibase"]
    pms = catalog["eu-ema-pms-fhir"]
    assert classify_bronze_disposition(vigibase).value == (
        "credentialed_metadata_only"
    )
    assert "not bronze coverage" in pms.evidence_limit.lower() or (
        "metadata-only" in pms.evidence_limit.lower()
    )
    xevmpd = catalog["eu-ema-xevmpd-credentialed"]
    article57 = catalog["eu-ema-article57"]
    assert xevmpd.source_id != article57.source_id
    assert xevmpd.authentication.value != "none"


@pytest.mark.unit
def test_african_matrix_and_versioned_index() -> None:
    matrix = african_source_coverage_matrix()
    jurisdictions = {cell.jurisdiction for cell in matrix}
    assert set(AFRICAN_COVERAGE_JURISDICTIONS) <= jurisdictions
    uganda_reg = next(
        cell
        for cell in matrix
        if cell.jurisdiction == "UGA"
        and cell.facet is CoverageFacet.REGISTRATION
    )
    assert uganda_reg.state == "catalogued"
    assert "ug-nda-register" in uganda_reg.source_ids
    for jurisdiction in ("MUS", "NGA", "ZAF"):
        pv = next(
            cell
            for cell in matrix
            if cell.jurisdiction == jurisdiction
            and cell.facet is CoverageFacet.PHARMACOVIGILANCE
        )
        assert pv.state == "catalogued"
    empty_note = "not negative evidence"
    index = build_source_index()
    assert index["index_id"] == INDEX_ID
    assert index["hugging_face_role"] == HF_ROLE
    assert index["silver_gold_implemented"] is False
    assert EVIDENTIARY_TRUTH_SENTENCE in str(index["evidentiary_truth"])
    assert index["schema_id"] == "global-medicines-atlas.source-index"
    outcomes = track_outcomes()
    assert len(outcomes) == 36
    who_eml = next(item for item in outcomes if item.track_id == 1)
    assert "global-who-eml" in who_eml.landed_source_ids
    assert any(empty_note in cell.evidence_limit.lower() for cell in matrix)


@pytest.mark.unit
def test_part_d_and_nice_population_limits() -> None:
    catalog = {source.source_id: source for source in load_source_catalog()}
    part_d = catalog["us-cms-partd-spending"]
    assert "not total US utilisation" in part_d.evidence_limit
    nice = catalog["gb-nice-ta"]
    assert "not actual funding" in nice.evidence_limit.lower()
    gip = catalog["nl-gipdatabank"]
    assert "No ATC" in gip.evidence_limit


@pytest.mark.unit
def test_catalog_merge_patches_existing_rows_without_live_ingest(
    tmp_path: Path,
) -> None:
    patches = existing_source_patches()
    assert (
        "substitutability"
        in patches["us-fda-orange-book"]["evidence_limit"].lower()
    )
    assert (
        "not bronze coverage"
        in patches["eu-ema-pms-fhir"]["evidence_limit"].lower()
    )
    with pytest.raises(KeyError):
        binding_for("not-a-catalogued-source")
    with pytest.raises(ValueError, match="repository_root"):
        acquire_expansion_source(
            "us-fda-nsde",
            repository_root=tmp_path / "missing-repo",
            reuse=run_expansion_reuse_gate("us-fda-nsde", repository_root=ROOT),
        )
    with pytest.raises(KeyError, match="not in the governed registry"):
        acquire_expansion_source(
            "not-a-catalogued-source",
            repository_root=ROOT,
            reuse=acquire_new_decision("not-a-catalogued-source"),
        )
    document = {
        "reviewed_at": "2020-01-01",
        "jurisdictions": [{"jurisdiction": "USA", "name": "United States"}],
        "sources": [
            {
                "source_id": "us-fda-orange-book",
                "native_identifier": "old",
                "evidence_limit": "old limit",
            }
        ],
    }
    merged = apply_expansion_to_catalog(document)
    assert merged["reviewed_at"] == "2026-08-20"
    codes = {row["jurisdiction"] for row in merged["jurisdictions"]}
    assert {"EGY", "IRL", "UGA", "USA"} <= codes
    ireland = next(
        row for row in expansion_jurisdictions() if row["jurisdiction"] == "IRL"
    )
    assert ireland["priority_cohorts"] == ["source_expansion_20260820"]
    orange = next(
        row
        for row in merged["sources"]
        if row["source_id"] == "us-fda-orange-book"
    )
    assert "substitutability" in orange["evidence_limit"].lower()
    generated = {row["source_id"] for row in expansion_source_rows()}
    merged_ids = {row["source_id"] for row in merged["sources"]}
    assert generated <= merged_ids
    written = write_source_index(tmp_path / "source_index.json")
    assert written.is_file()
    assert INDEX_ID in written.read_text(encoding="utf-8")
