"""Metadata-only delta reconciliation must not invent preservation evidence."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.donor_delta import (
    DeltaObservation,
    DeltaReview,
    reconcile_delta,
)


def observation():
    return {
        "repository": "edithatogo/aus-health-data-scraper",
        "baseline": "931da0b9b6ae3e3cec0743568abb71a50d62b7cf",
        "head": "009e80544588a956c8922aaab052ee08947e2b30",
        "ancestry": "ahead",
        "files": [
            {"path": "src/scraper.py", "blob": "a" * 40, "status": "modified"}
        ],
    }


def review():
    return {
        "observation": observation(),
        "dispositions": [
            {
                "path": "src/scraper.py",
                "disposition": "retain-legacy",
                "reason": "Async call compatibility is retained, not claimed equal.",
                "evidence": "tests/test_mbs_compatibility.py",
            }
        ],
    }


def test_scoped_complete_disposition_is_not_preservation():
    result = reconcile_delta(
        DeltaReview.model_validate(review()),
        DeltaObservation.model_validate(observation()),
    )
    assert result.no_data_delta
    assert result.functionality_disposition_complete
    assert not result.current_head_history_preserved
    assert not result.archive_authorized


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("repository", "other/aus-health-data-scraper"),
        ("baseline", "b" * 40),
        ("head", "main"),
        ("ancestry", "diverged"),
    ],
)
def test_invalid_identity_or_ancestry(key, value):
    raw = observation()
    raw[key] = value
    with pytest.raises(ValidationError):
        DeltaObservation.model_validate(raw)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("path", "../src/scraper.py"),
        ("path", "src//scraper.py"),
        ("blob", "main"),
        ("status", "unknown"),
    ],
)
def test_invalid_file(key, value):
    raw = observation()
    raw["files"][0][key] = value
    with pytest.raises(ValidationError):
        DeltaObservation.model_validate(raw)


def test_duplicate_file():
    raw = observation()
    raw["files"] *= 2
    with pytest.raises(ValidationError):
        DeltaObservation.model_validate(raw)


@pytest.mark.parametrize("kind", ["head", "blob", "omission", "extra"])
def test_independent_denominator_substitution(kind):
    raw = review()
    if kind == "head":
        raw["observation"]["head"] = "b" * 40
    elif kind == "blob":
        raw["observation"]["files"][0]["blob"] = "b" * 40
    elif kind == "omission":
        raw["dispositions"] = []
    else:
        raw["dispositions"] *= 2
    with pytest.raises(ValueError, match=r"observed delta|denominator"):
        reconcile_delta(
            DeltaReview.model_validate(raw),
            DeltaObservation.model_validate(observation()),
        )


@pytest.mark.parametrize("path", ["src/main.py", ".github/workflows/ci.yml"])
def test_code_cannot_be_documentation_only(path):
    raw = review()
    raw["observation"]["files"][0]["path"] = path
    raw["dispositions"][0]["path"] = path
    raw["dispositions"][0]["disposition"] = "documentation-only"
    with pytest.raises(ValueError, match="functional review"):
        reconcile_delta(
            DeltaReview.model_validate(raw),
            DeltaObservation.model_validate(raw["observation"]),
        )


def test_pending_and_unknown_file_are_not_complete():
    raw = review()
    raw["observation"]["files"][0]["path"] = "unknown.bin"
    raw["dispositions"][0].update(path="unknown.bin", disposition="pending")
    result = reconcile_delta(
        DeltaReview.model_validate(raw),
        DeltaObservation.model_validate(raw["observation"]),
    )
    assert not result.no_data_delta
    assert not result.functionality_disposition_complete


def test_unknown_authority_fields_rejected():
    raw = review()
    raw["archive_authorized"] = True
    with pytest.raises(ValidationError):
        DeltaReview.model_validate(raw)


def test_committed_observation_covers_exact_live_path_denominators():
    path = Path(__file__).resolve().parents[1] / (
        "quality/qualifications/australian-donor-delta.json"
    )
    fixture = json.loads(path.read_text())
    expected_paths = [
        {"README.md", "SUCCESSOR.md"},
        {
            ".github/workflows/ci.yml",
            "README.md",
            "SUCCESSOR.md",
            "src/main.py",
            "src/processor.py",
            "src/scraper.py",
            "tests/test_processor.py",
            "tests/test_scraper.py",
        },
    ]
    assert not fixture["current_head_history_preserved"]
    assert not fixture["archive_authorized"]
    assert len(fixture["reviews"]) == 2
    for raw, paths in zip(fixture["reviews"], expected_paths, strict=True):
        parsed = DeltaReview.model_validate(raw)
        assert {item.path for item in parsed.observation.files} == paths
        # Fixture consistency only, not independent live authentication.
        result = reconcile_delta(parsed, parsed.observation)
        assert result.no_data_delta
        assert result.functionality_disposition_complete


@pytest.mark.parametrize("value", ["", "/abs", "a\\b", "a\n", " a", "."])
def test_noncanonical_paths(value):
    raw = observation()
    raw["files"][0]["path"] = value
    with pytest.raises(ValidationError):
        DeltaObservation.model_validate(raw)


def test_unchanged_head_rejected():
    raw = observation()
    raw["head"] = raw["baseline"]
    with pytest.raises(ValidationError, match="changed head"):
        DeltaObservation.model_validate(raw)


@pytest.mark.parametrize("value", [" ", " padded "])
def test_blank_evidence_rejected(value):
    raw = review()
    raw["dispositions"][0]["evidence"] = value
    with pytest.raises(ValidationError, match="review text"):
        DeltaReview.model_validate(raw)


@pytest.mark.parametrize(
    "path", ["data/raw.xml", "data/report.md", "unknown.bin"]
)
def test_possible_data_is_not_classified_as_non_data(path):
    raw = review()
    raw["observation"]["files"][0]["path"] = path
    raw["dispositions"][0]["path"] = path
    parsed = DeltaReview.model_validate(raw)
    assert not reconcile_delta(parsed, parsed.observation).no_data_delta


def test_review_cannot_omit_an_observed_file():
    independent = observation()
    independent["files"].append({
        "path": "README.md",
        "blob": "b" * 40,
        "status": "added",
    })
    with pytest.raises(ValueError, match="observed delta"):
        reconcile_delta(
            DeltaReview.model_validate(review()),
            DeltaObservation.model_validate(independent),
        )


@pytest.mark.parametrize("field", ["head", "baseline"])
def test_digest_trailing_newline_rejected(field):
    raw = observation()
    raw[field] += "\n"
    with pytest.raises(ValidationError):
        DeltaObservation.model_validate(raw)


def test_blob_trailing_newline_rejected():
    raw = observation()
    raw["files"][0]["blob"] += "\n"
    with pytest.raises(ValidationError):
        DeltaObservation.model_validate(raw)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repository", "other/repo"),
        ("head", "main"),
    ],
)
def test_revalidates_constructed_observation(field, value):
    parsed = DeltaReview.model_validate(review())
    unsafe = parsed.observation.model_copy(update={field: value})
    with pytest.raises(ValidationError):
        reconcile_delta(
            parsed.model_copy(update={"observation": unsafe}), unsafe
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path", "../raw"),
        ("status", "unknown"),
    ],
)
def test_revalidates_nested_copied_file(field, value):
    parsed = DeltaReview.model_validate(review())
    unsafe_file = parsed.observation.files[0].model_copy(update={field: value})
    unsafe = parsed.observation.model_copy(update={"files": (unsafe_file,)})
    with pytest.raises(ValidationError):
        reconcile_delta(parsed, unsafe)
