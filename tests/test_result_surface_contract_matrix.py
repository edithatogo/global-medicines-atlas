"""Cross-surface guard for evidence and non-evidence result contracts."""

from global_medicines_atlas.historical_change import (
    HistoricalChange,
    HistoricalChangePage,
)
from global_medicines_atlas.historical_comparison import NativeSnapshot
from global_medicines_atlas.mbs_gold_graph import MBS_GOLD_EDGE_SCHEMA
from global_medicines_atlas.pbs_gold_graph import PBS_GOLD_EDGE_SCHEMA
from global_medicines_atlas.platinum_benefits import BenefitsPage
from global_medicines_atlas.platinum_change import ChangePage
from global_medicines_atlas.platinum_history import HistoricalChangeEnvelope
from global_medicines_atlas.platinum_identity_service import DatasetIdentityPage
from global_medicines_atlas.platinum_surface_contracts import (
    DatasetIdentityEnvelope,
)
from global_medicines_atlas.platinum_v2_contracts import (
    V2ComparisonResponse,
    V2Conclusion,
    V2EvidenceItem,
    V2EvidenceResponse,
)
from global_medicines_atlas.product_contracts import (
    ComparisonResponse,
    ConceptSearchResponse,
    CoverageItem,
    CoverageResponse,
    ErrorEnvelope,
    EvidenceContext,
    EvidenceItem,
    EvidenceResponse,
    HealthResponse,
    MatchExplanation,
    ProductConclusion,
    ResponseMetadata,
)


def test_assertion_and_coverage_results_carry_explicit_context_and_clocks() -> (
    None
):
    for model in (
        ProductConclusion,
        CoverageItem,
        EvidenceItem,
        V2Conclusion,
        V2EvidenceItem,
    ):
        assert "evidence_context" in model.model_fields
        assert "valid_time" in model.model_fields

    assert "clocks" in ResponseMetadata.model_fields
    assert EvidenceContext().comparison_cohort == "unknown"
    assert EvidenceContext().entity_granularity == "unknown"
    assert EvidenceContext().review_state == "not_reported"


def test_versioned_comparison_evidence_and_coverage_envelopes_are_explicit() -> (
    None
):
    assert set(ComparisonResponse.model_fields) >= {
        "metadata",
        "conclusions",
        "validity",
    }
    assert set(CoverageResponse.model_fields) >= {"metadata", "coverage"}
    assert set(EvidenceResponse.model_fields) >= {"metadata", "evidence"}
    assert set(V2ComparisonResponse.model_fields) >= {
        "metadata",
        "conclusions",
        "comparison_validity",
        "validity_completeness",
    }
    assert set(V2EvidenceResponse.model_fields) >= {"metadata", "evidence"}


def test_identity_benefit_and_history_results_preserve_their_native_lineage() -> (
    None
):
    assert set(DatasetIdentityEnvelope.model_fields) >= {
        "revision",
        "path",
        "object_sha256",
        "contract_sha256",
        "semantic_manifest_sha256",
        "source_id",
        "acquisition_id",
        "layer",
        "schema_era",
        "comparison_cohort",
        "rows_queried",
    }
    assert "datasets" in DatasetIdentityPage.model_fields

    assert set(BenefitsPage.model_fields) >= {
        "identity",
        "query_sha256",
        "receipt_sha256",
        "window_sha256",
        "page_sha256",
        "coverage_state",
        "confidence_state",
        "uncertainty_state",
        "review_state",
        "comparison_validity",
    }

    snapshot_fields = set(NativeSnapshot.model_fields)
    assert snapshot_fields >= {
        "source_id",
        "table",
        "dimension",
        "schema_era",
        "identity_profile",
        "source_revision",
        "source_path",
        "b1_sha256",
        "b2_sha256",
        "observed_at",
        "cohort",
        "complete",
    }
    assert {"left", "right", "availability", "comparison_state"} <= set(
        HistoricalChange.model_fields
    )
    assert {"items", "offset", "limit", "total"} <= set(
        HistoricalChangePage.model_fields
    )
    assert {
        "comparison",
        "change_sha256",
        "absence_is_negative_evidence",
        "source_outage_is_negative_evidence",
    } <= set(HistoricalChangeEnvelope.model_fields)
    assert {
        "absence_interpretation",
        "comparison_complete",
        "page_sha256",
    } <= set(ChangePage.model_fields)


def test_discovery_and_operational_responses_cannot_claim_evidence_status() -> (
    None
):
    assert MatchExplanation.model_fields["establishes_equivalence"].default is (
        False
    )
    assert "concepts" in ConceptSearchResponse.model_fields
    assert (
        "evidence_version"
        not in ConceptSearchResponse.model_fields[
            "metadata"
        ].annotation.model_fields
    )
    assert "state" in HealthResponse.model_fields
    assert "error" in ErrorEnvelope.model_fields
    assert "conclusions" not in HealthResponse.model_fields
    assert "conclusions" not in ErrorEnvelope.model_fields


def test_gold_edge_transport_remains_a_qualified_structural_projection() -> (
    None
):
    for schema in (MBS_GOLD_EDGE_SCHEMA, PBS_GOLD_EDGE_SCHEMA):
        metadata = schema.metadata or {}
        assert metadata[b"schema_version"] == b"1.0"
        assert metadata[b"qualification"] == b"synthetic_silver_candidate_only"
        assert {"evidence_json", "controls_json"} <= set(schema.names)
