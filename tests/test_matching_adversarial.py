from datetime import UTC, datetime

from global_medicines_atlas.matching_features import (
    FeatureDisposition as D,
)
from global_medicines_atlas.matching_features import (
    FeatureKind as K,
)
from global_medicines_atlas.matching_features import (
    MatchFeatures,
    feature,
)
from global_medicines_atlas.matching_models import MappingLevel, ReviewState
from global_medicines_atlas.matching_policy import (
    MatchCandidate,
    PolicyReason,
    ReviewOnlyPolicy,
)


def test_semantic_and_rxnorm_similarity_cannot_override_product_conflict() -> (
    None
):
    missing = {kind: feature(kind, D.MISSING, 0, "Missing") for kind in K}
    features = MatchFeatures(
        mapping_level=MappingLevel.PRESENTATION,
        identifiers=missing[K.IDENTIFIER],
        ingredients=feature(K.INGREDIENT, D.AGREEMENT, 0.25, "Same ingredient"),
        strength=feature(K.STRENGTH, D.CONFLICT, -0.5, "5 mg versus 50 mg"),
        unit=feature(K.UNIT, D.AGREEMENT, 0.05, "Same unit"),
        form=feature(K.FORM, D.CONFLICT, -0.3, "Tablet versus injection"),
        route=feature(K.ROUTE, D.CONFLICT, -0.3, "Oral versus intravenous"),
        lexical=feature(K.LEXICAL, D.AGREEMENT, 0.3, "Very similar names"),
        semantic=feature(K.SEMANTIC, D.AGREEMENT, 0.3, "High vector score"),
        rxnorm=feature(K.RXNORM, D.AGREEMENT, 0.3, "Related RxNorm result"),
        temporal=feature(K.TEMPORAL, D.CONFLICT, -0.2, "No overlap"),
        feature_version="v1",
        evaluated_at=datetime(2026, 7, 29, tzinfo=UTC),
    )
    candidate = MatchCandidate(
        candidate_id="adversarial-1",
        source_concept_id="source",
        target_concept_id="target",
        source_jurisdiction="NZ",
        target_jurisdiction="US",
        mapping_level=MappingLevel.PRESENTATION,
        features=features,
        index_version="v1",
        model_version="v1",
    )

    decision = ReviewOnlyPolicy().evaluate(candidate)

    assert decision.review_state is ReviewState.PENDING_REVIEW
    assert decision.abstained
    assert {
        PolicyReason.STRENGTH_CONFLICT,
        PolicyReason.FORM_CONFLICT,
        PolicyReason.ROUTE_CONFLICT,
        PolicyReason.TEMPORAL_CONFLICT,
    }.issubset(decision.reason_codes)
