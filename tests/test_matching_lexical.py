from global_medicines_atlas.matching_lexical import (
    compare_features,
    lexical_score,
)
from global_medicines_atlas.matching_normalization import build_features


def test_lexical_evidence_exposes_each_medicine_feature() -> None:
    source = build_features(
        name="Paracetamol 500 mg tablet",
        ingredients=("paracetamol",),
        strength_value=500,
        strength_unit="mg",
        dose_form="tablet",
        route="oral",
    )
    target = build_features(
        name="Paracetamol tablet 500mg",
        ingredients=("Paracetamol",),
        strength_value="500.0",
        strength_unit="milligrams",
        dose_form="tablet",
        route="oral",
    )

    evidence = compare_features(source, target)

    assert tuple(item.feature for item in evidence) == (
        "name",
        "ingredients",
        "strength",
        "unit",
        "form",
        "route",
    )
    assert lexical_score(evidence) > 0.9


def test_missing_features_do_not_count_as_agreement() -> None:
    evidence = compare_features(
        build_features(name="Medicine A"),
        build_features(name="Medicine B"),
    )

    assert next(item for item in evidence if item.feature == "route").score == 0
