"""Contracts for source-family rights review and public eligibility."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from global_medicines_atlas.source_rights_review import (
    EvidenceScope,
    PublicationSensitivity,
    ReusePermission,
    ReviewDisposition,
    RightsEvidence,
    SourceRightsReview,
    validate_catalogue_reviews,
)

NOW = datetime(2026, 8, 21, tzinfo=UTC)
DIGEST = "a" * 64
ROOT = Path(__file__).resolve().parents[1]


def _evidence() -> RightsEvidence:
    return RightsEvidence.model_validate({
        "official_url": "https://example.gov/terms",
        "observed_at": NOW,
        "content_sha256": DIGEST,
        "scope": EvidenceScope.DATASET,
        "reuse_statement": "CC BY 4.0 reuse with attribution.",
    })


def _review(**overrides: object) -> SourceRightsReview:
    values: dict[str, object] = {
        "source_id": "example-source",
        "policy_family_id": "example-government-open-data",
        "evidence": (_evidence(),),
        "redistribute": ReusePermission.PERMITTED,
        "transform": ReusePermission.PERMITTED,
        "publish_source_bytes": ReusePermission.PERMITTED,
        "sensitivity": PublicationSensitivity.PUBLIC,
        "disposition": ReviewDisposition.APPROVED_PUBLIC_SOURCE,
        "attribution": "Example Government, source URL and retrieval date.",
        "field_exclusions": (),
        "maintainer_licence_approved": True,
        "maintainer_publication_approved": True,
        "reviewed_at": NOW,
        "review_trigger": "terms_or_source_change",
    }
    values.update(overrides)
    return SourceRightsReview.model_validate(values)


def test_public_source_requires_affirmative_permissions_and_evidence() -> None:
    review = _review()
    assert review.public_source_eligible is True
    assert review.public_derived_eligible is True


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("redistribute", ReusePermission.UNKNOWN, "redistribute"),
        ("transform", ReusePermission.UNKNOWN, "transform"),
        ("publish_source_bytes", ReusePermission.PROHIBITED, "source bytes"),
        ("sensitivity", PublicationSensitivity.CONTROLLED, "sensitivity"),
        ("evidence", (), "official evidence"),
        ("maintainer_publication_approved", False, "maintainer"),
        ("attribution", None, "attribution"),
    ],
)
def test_public_source_fails_closed(
    field: str,
    value: object,
    match: str,
) -> None:
    with pytest.raises(ValidationError, match=match):
        _review(**{field: value})


def test_derived_only_never_claims_source_byte_permission() -> None:
    review = _review(
        publish_source_bytes=ReusePermission.PROHIBITED,
        disposition=ReviewDisposition.APPROVED_PUBLIC_DERIVED_ONLY,
        field_exclusions=("source narratives",),
    )
    assert review.public_source_eligible is False
    assert review.public_derived_eligible is True


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("evidence", (), "official evidence"),
        ("redistribute", ReusePermission.UNKNOWN, "redistribute"),
        ("transform", ReusePermission.UNKNOWN, "transform"),
        ("sensitivity", PublicationSensitivity.CONTROLLED, "sensitivity"),
        ("maintainer_licence_approved", False, "maintainer"),
        ("attribution", None, "attribution"),
    ],
)
def test_public_derived_data_fails_closed(
    field: str,
    value: object,
    match: str,
) -> None:
    with pytest.raises(ValidationError, match=match):
        _review(
            disposition=ReviewDisposition.APPROVED_PUBLIC_DERIVED_ONLY,
            publish_source_bytes=ReusePermission.PROHIBITED,
            **{field: value},
        )


def test_catalogue_review_requires_exact_source_coverage() -> None:
    first = _review(source_id="first")
    second = _review(source_id="second")
    validate_catalogue_reviews(("first", "second"), (first, second))
    with pytest.raises(ValueError, match="missing"):
        validate_catalogue_reviews(("first", "second"), (first,))
    with pytest.raises(ValueError, match="duplicate"):
        validate_catalogue_reviews(("first",), (first, first))


def test_non_public_review_requires_an_explicit_blocker() -> None:
    with pytest.raises(ValidationError, match="blocker"):
        _review(
            disposition=ReviewDisposition.CATALOGUE_ONLY,
            maintainer_licence_approved=False,
            maintainer_publication_approved=False,
            blocker=None,
        )


def test_catalogue_review_rejects_stale_or_temporally_invalid_evidence() -> (
    None
):
    stale = _review(
        evidence=(
            _evidence().model_copy(
                update={"observed_at": NOW - timedelta(days=366)}
            ),
        )
    )
    with pytest.raises(ValueError, match="stale"):
        validate_catalogue_reviews(("example-source",), (stale,), as_of=NOW)

    future = _review(
        evidence=(
            _evidence().model_copy(
                update={"observed_at": NOW + timedelta(seconds=1)}
            ),
        )
    )
    with pytest.raises(ValueError, match="postdates"):
        validate_catalogue_reviews(("example-source",), (future,), as_of=NOW)


def test_public_evidence_must_be_content_digested() -> None:
    with pytest.raises(ValidationError, match="content_sha256"):
        RightsEvidence.model_validate({
            "official_url": "https://example.gov/terms",
            "observed_at": NOW,
            "content_sha256": "not-a-digest",
            "scope": EvidenceScope.DATASET,
            "reuse_statement": "Open data.",
        })


def test_serialized_review_satisfies_public_schema() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "source-rights-review-v1.json").read_text()
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=None).validate(  # pyright: ignore[reportUnknownMemberType]
        _review().model_dump(
            mode="json",
            exclude={"public_source_eligible", "public_derived_eligible"},
        )
    )
