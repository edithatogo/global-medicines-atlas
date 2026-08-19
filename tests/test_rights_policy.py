"""Acquisition rights policy is explicit, fail-closed, and append-only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import AnyUrl, ValidationError
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.publication_package import (
    PackageGenerationError,
    require_publishable_source_bytes,
)
from global_medicines_atlas.receipts import (
    RightsState,
    SourceReceipt,
)
from global_medicines_atlas.rights_policy import (
    AccessRestriction,
    AcquisitionRightsPolicy,
    Permission,
    ReviewStatus,
    RightsPolicyLedger,
    coarse_rights_state,
    evaluate_acquisition_rights,
)

NOW = datetime(2026, 8, 20, tzinfo=UTC)
SHA_A = "a" * 64


def _policy(**overrides: object) -> AcquisitionRightsPolicy:
    values: dict[str, object] = {
        "acquisition_id": SHA_A,
        "source_id": "medsafe-product-register",
        "licence_evidence_uri": AnyUrl("https://example.test/terms"),
        "licence_expression": "source-native terms; not a licence conclusion",
        "retain_evidence": Permission.PERMITTED,
        "publish_bytes": Permission.UNKNOWN,
        "redistribute": Permission.UNKNOWN,
        "transform": Permission.PERMITTED,
        "attribution_requirement": "Cite Medsafe as the source authority.",
        "access_restriction": AccessRestriction.NONE,
        "review_status": ReviewStatus.UNREVIEWED,
        "observed_at": NOW,
        "review_expires_at": None,
        "maintainer_licence_approved": False,
        "maintainer_publication_approved": False,
    }
    values.update(overrides)
    return AcquisitionRightsPolicy.model_validate(values)


@pytest.mark.unit
def test_policy_records_required_acquisition_fields() -> None:
    policy = _policy()
    dumped = policy.model_dump(mode="json")
    assert dumped["licence_evidence_uri"].startswith("https://")
    assert dumped["licence_expression"]
    assert dumped["retain_evidence"] == "permitted"
    assert dumped["publish_bytes"] == "unknown"
    assert dumped["redistribute"] == "unknown"
    assert dumped["transform"] == "permitted"
    assert dumped["attribution_requirement"]
    assert dumped["access_restriction"] == "none"
    assert dumped["review_status"] == "unreviewed"
    assert dumped["observed_at"]
    assert dumped["maintainer_licence_approved"] is False
    assert dumped["maintainer_publication_approved"] is False


@pytest.mark.unit
def test_retain_evidence_is_independent_of_publish_bytes() -> None:
    policy = _policy(
        retain_evidence=Permission.PERMITTED,
        publish_bytes=Permission.PROHIBITED,
        redistribute=Permission.PROHIBITED,
        review_status=ReviewStatus.REVIEWED,
        reviewed_at=NOW,
    )
    decision = evaluate_acquisition_rights(policy, evaluated_at=NOW)
    assert decision.may_retain_internal_provenance is True
    assert decision.may_publish_bytes is False
    assert "publish_bytes" in " ".join(decision.blocking_reasons)


@pytest.mark.unit
def test_unresolved_rights_fail_closed_for_publication() -> None:
    policy = _policy()
    decision = evaluate_acquisition_rights(policy, evaluated_at=NOW)
    assert decision.may_publish_bytes is False
    assert decision.may_retain_internal_provenance is True
    with pytest.raises(PackageGenerationError, match="unresolved"):
        require_publishable_source_bytes(None, evaluated_at=NOW)
    with pytest.raises(PackageGenerationError, match="unresolved"):
        require_publishable_source_bytes((policy,), evaluated_at=NOW)


@pytest.mark.unit
def test_publication_requires_maintainer_human_gates() -> None:
    policy = _policy(
        publish_bytes=Permission.PERMITTED,
        redistribute=Permission.PERMITTED,
        review_status=ReviewStatus.REVIEWED,
        reviewed_at=NOW,
        review_expires_at=NOW + timedelta(days=30),
        maintainer_licence_approved=False,
        maintainer_publication_approved=False,
    )
    decision = evaluate_acquisition_rights(policy, evaluated_at=NOW)
    assert decision.may_publish_bytes is False
    assert any("maintainer" in reason for reason in decision.blocking_reasons)


@pytest.mark.unit
def test_reviewed_permitted_publication_passes_when_gates_are_recorded() -> (
    None
):
    policy = _policy(
        publish_bytes=Permission.PERMITTED,
        redistribute=Permission.PERMITTED,
        review_status=ReviewStatus.REVIEWED,
        reviewed_at=NOW,
        review_expires_at=NOW + timedelta(days=30),
        maintainer_licence_approved=True,
        maintainer_publication_approved=True,
    )
    decision = evaluate_acquisition_rights(policy, evaluated_at=NOW)
    assert decision.may_publish_bytes is True
    assert decision.may_retain_internal_provenance is True
    require_publishable_source_bytes((policy,), evaluated_at=NOW)


@pytest.mark.unit
def test_expired_review_fails_closed_even_if_previously_permitted() -> None:
    policy = _policy(
        observed_at=NOW - timedelta(days=40),
        publish_bytes=Permission.PERMITTED,
        redistribute=Permission.PERMITTED,
        review_status=ReviewStatus.REVIEWED,
        reviewed_at=NOW - timedelta(days=40),
        review_expires_at=NOW - timedelta(days=1),
        maintainer_licence_approved=True,
        maintainer_publication_approved=True,
    )
    decision = evaluate_acquisition_rights(policy, evaluated_at=NOW)
    assert decision.may_publish_bytes is False
    assert any("expir" in reason for reason in decision.blocking_reasons)


@pytest.mark.unit
def test_publish_bytes_cannot_exceed_retention() -> None:
    with pytest.raises(ValidationError, match="retain"):
        _policy(
            retain_evidence=Permission.PROHIBITED,
            publish_bytes=Permission.PERMITTED,
            redistribute=Permission.PERMITTED,
            transform=Permission.PROHIBITED,
            review_status=ReviewStatus.REVIEWED,
            reviewed_at=NOW,
            maintainer_licence_approved=True,
            maintainer_publication_approved=True,
        )


@pytest.mark.unit
def test_credentialed_access_cannot_silently_publish_bytes() -> None:
    policy = _policy(
        publish_bytes=Permission.PERMITTED,
        redistribute=Permission.PERMITTED,
        access_restriction=AccessRestriction.CREDENTIALED,
        review_status=ReviewStatus.REVIEWED,
        reviewed_at=NOW,
        maintainer_licence_approved=True,
        maintainer_publication_approved=True,
    )
    decision = evaluate_acquisition_rights(policy, evaluated_at=NOW)
    assert decision.may_publish_bytes is False
    assert any("credential" in reason for reason in decision.blocking_reasons)
    assert decision.may_retain_internal_provenance is True


@pytest.mark.unit
def test_conflicting_ledger_revisions_fail_closed() -> None:
    first = _policy(
        publish_bytes=Permission.PERMITTED,
        redistribute=Permission.PERMITTED,
        review_status=ReviewStatus.REVIEWED,
        reviewed_at=NOW,
        maintainer_licence_approved=True,
        maintainer_publication_approved=True,
    )
    conflicting = first.model_copy(
        update={
            "publish_bytes": Permission.PROHIBITED,
            "redistribute": Permission.PROHIBITED,
        }
    )
    ledger = RightsPolicyLedger.empty().append(first).append(conflicting)
    decision = ledger.evaluate(SHA_A, evaluated_at=NOW)
    assert decision.may_publish_bytes is False
    assert any("conflict" in reason for reason in decision.blocking_reasons)
    assert decision.may_retain_internal_provenance is True


@pytest.mark.unit
def test_changing_rights_use_later_revision_without_rewriting_history() -> None:
    permitted = _policy(
        publish_bytes=Permission.PERMITTED,
        redistribute=Permission.PERMITTED,
        review_status=ReviewStatus.REVIEWED,
        reviewed_at=NOW,
        review_expires_at=NOW + timedelta(days=10),
        maintainer_licence_approved=True,
        maintainer_publication_approved=True,
    )
    withdrawn = permitted.model_copy(
        update={
            "publish_bytes": Permission.PROHIBITED,
            "redistribute": Permission.PROHIBITED,
            "observed_at": NOW + timedelta(days=1),
            "review_status": ReviewStatus.SUPERSEDED,
            "reviewed_at": NOW + timedelta(days=1),
        }
    )
    ledger = RightsPolicyLedger.empty().append(permitted).append(withdrawn)
    earlier = ledger.evaluate(SHA_A, evaluated_at=NOW)
    later = ledger.evaluate(
        SHA_A,
        evaluated_at=NOW + timedelta(days=1, seconds=1),
    )
    assert earlier.may_publish_bytes is True
    assert later.may_publish_bytes is False
    assert later.may_retain_internal_provenance is True
    assert [item.observed_at for item in ledger.revisions] == [
        permitted.observed_at,
        withdrawn.observed_at,
    ]


@pytest.mark.unit
def test_receipt_policy_must_match_source_and_coarse_rights() -> None:
    policy = _policy(
        acquisition_id="0" * 64,
        source_id="other-source",
        retain_evidence=Permission.UNKNOWN,
        transform=Permission.UNKNOWN,
        publish_bytes=Permission.UNKNOWN,
    )
    receipt = source_receipt()
    payload = receipt.model_dump()
    payload["rights_policy"] = policy
    with pytest.raises(ValidationError, match="rights policy"):
        SourceReceipt.model_validate(payload)


@pytest.mark.unit
def test_receipt_may_bind_matching_internal_policy() -> None:
    receipt = source_receipt()
    temporal = receipt.temporal
    assert temporal is not None
    policy = _policy(
        acquisition_id=temporal.acquisition_id,
        source_id=receipt.source.source_id,
        licence_evidence_uri=receipt.rights_reference,
        retain_evidence=Permission.PERMITTED,
        transform=Permission.PERMITTED,
        publish_bytes=Permission.PROHIBITED,
        redistribute=Permission.PROHIBITED,
        review_status=ReviewStatus.REVIEWED,
        reviewed_at=NOW,
    )
    bound = SourceReceipt.model_validate({
        **receipt.model_dump(),
        "rights_policy": policy,
    })
    assert bound.rights_state is RightsState.PERMITTED
    assert coarse_rights_state(policy) == RightsState.PERMITTED
    assert b"rights_policy" in bound.canonical_json()
    assert b"rights_policy" not in receipt.canonical_json()
    decision = evaluate_acquisition_rights(policy, evaluated_at=NOW)
    assert decision.may_retain_internal_provenance is True
    assert decision.may_publish_bytes is False


@pytest.mark.unit
def test_missing_policy_on_receipt_still_blocks_byte_publication() -> None:
    receipt = source_receipt()
    with pytest.raises(PackageGenerationError, match="unresolved"):
        require_publishable_source_bytes(
            (receipt.rights_policy,),
            evaluated_at=NOW,
        )


@pytest.mark.property
@given(st.sampled_from(tuple(ReviewStatus)))
def test_unreviewed_or_expired_status_never_publishes_bytes(
    status: ReviewStatus,
) -> None:
    expires = None if status is not ReviewStatus.EXPIRED else NOW
    policy = _policy(
        publish_bytes=Permission.PERMITTED,
        redistribute=Permission.PERMITTED,
        review_status=status,
        reviewed_at=NOW if status is ReviewStatus.REVIEWED else None,
        review_expires_at=expires,
        maintainer_licence_approved=True,
        maintainer_publication_approved=True,
    )
    decision = evaluate_acquisition_rights(policy, evaluated_at=NOW)
    if status is ReviewStatus.REVIEWED:
        assert decision.may_publish_bytes is True
    else:
        assert decision.may_publish_bytes is False


@pytest.mark.edge
def test_policy_must_not_carry_credential_material() -> None:
    with pytest.raises(ValidationError, match="credential"):
        _policy(attribution_requirement="Bearer secret-token")
    with pytest.raises(ValidationError, match="credential"):
        _policy(licence_expression="Authorization: Basic abc")


@pytest.mark.unit
def test_reviewed_policy_requires_timestamp_and_licence_evidence() -> None:
    with pytest.raises(ValidationError, match="reviewed_at"):
        _policy(
            review_status=ReviewStatus.REVIEWED,
            reviewed_at=None,
        )
    with pytest.raises(ValidationError, match="licence evidence"):
        _policy(
            review_status=ReviewStatus.REVIEWED,
            reviewed_at=NOW,
            licence_evidence_uri=None,
        )


@pytest.mark.unit
def test_redistribution_cannot_exceed_publish_bytes() -> None:
    with pytest.raises(ValidationError, match="redistribution"):
        _policy(
            publish_bytes=Permission.PROHIBITED,
            redistribute=Permission.PERMITTED,
        )


@pytest.mark.unit
def test_prohibited_retention_blocks_internal_provenance() -> None:
    policy = _policy(
        retain_evidence=Permission.PROHIBITED,
        publish_bytes=Permission.PROHIBITED,
        redistribute=Permission.PROHIBITED,
        transform=Permission.PROHIBITED,
    )
    assert coarse_rights_state(policy) == RightsState.PROHIBITED
    decision = evaluate_acquisition_rights(policy, evaluated_at=NOW)
    assert decision.may_retain_internal_provenance is False
    assert decision.may_publish_bytes is False


@pytest.mark.unit
def test_conditional_and_unknown_transform_project_coarse_state() -> None:
    unknown_transform = _policy(transform=Permission.UNKNOWN)
    assert coarse_rights_state(unknown_transform) == RightsState.UNKNOWN
    conditional = _policy(retain_evidence=Permission.CONDITIONAL)
    assert coarse_rights_state(conditional) == RightsState.RESTRICTED


@pytest.mark.unit
def test_missing_licence_uri_is_recorded_as_unresolved_publication() -> None:
    policy = _policy(
        licence_evidence_uri=None,
        attribution_requirement=None,
    )
    decision = evaluate_acquisition_rights(policy, evaluated_at=NOW)
    assert decision.may_publish_bytes is False
    assert any(
        "licence evidence" in reason for reason in decision.blocking_reasons
    )


@pytest.mark.unit
def test_receipt_policy_acquisition_id_must_match() -> None:
    receipt = source_receipt()
    policy = _policy(
        acquisition_id="0" * 64,
        source_id=receipt.source.source_id,
        retain_evidence=Permission.PERMITTED,
        transform=Permission.PERMITTED,
        publish_bytes=Permission.PROHIBITED,
        redistribute=Permission.PROHIBITED,
    )
    payload = receipt.model_dump()
    payload["rights_policy"] = policy
    with pytest.raises(ValidationError, match="rights policy"):
        SourceReceipt.model_validate(payload)
    decision = RightsPolicyLedger.empty().evaluate(SHA_A, evaluated_at=NOW)
    assert decision.may_publish_bytes is False
    assert decision.may_retain_internal_provenance is False
    assert any("unresolved" in reason for reason in decision.blocking_reasons)


@pytest.mark.unit
def test_empty_ledger_and_unknown_acquisition_fail_closed() -> None:
    decision = RightsPolicyLedger.empty().evaluate(SHA_A, evaluated_at=NOW)
    assert decision.may_publish_bytes is False
    assert decision.may_retain_internal_provenance is False
    assert any("unresolved" in reason for reason in decision.blocking_reasons)


@pytest.mark.unit
def test_expiry_must_follow_observed_at_unless_already_expired() -> None:
    with pytest.raises(ValidationError, match="review_expires_at"):
        _policy(
            review_status=ReviewStatus.REVIEWED,
            reviewed_at=NOW,
            review_expires_at=NOW - timedelta(days=1),
        )
    expired = _policy(
        review_status=ReviewStatus.EXPIRED,
        review_expires_at=NOW,
    )
    decision = evaluate_acquisition_rights(expired, evaluated_at=NOW)
    assert decision.may_publish_bytes is False
    assert decision.may_retain_internal_provenance is True
