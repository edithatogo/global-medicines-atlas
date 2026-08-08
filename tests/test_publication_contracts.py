"""Contracts for deterministic, fail-closed publication packages."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from global_medicines_atlas.publication_contracts import (
    CoverageDeclaration,
    CroissantDistribution,
    CroissantMetadata,
    DataDictionary,
    DatasetCard,
    DecisionState,
    FieldContract,
    IdentifierState,
    ProvenanceDeclaration,
    PublicationIdentity,
    PublicationObjectRole,
    PublicationPackage,
    PublicationState,
    PublicationSystem,
    PublicationVerificationReceipt,
    RightsDeclaration,
    RightsDisposition,
    VerificationCheck,
    VerificationEvidence,
    VerificationOutcome,
    canonical_sha256,
    receipt_is_for_package,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64


def _rights(
    disposition: RightsDisposition = RightsDisposition.PERMITTED,
) -> RightsDeclaration:
    return RightsDeclaration(
        source_id="nz-medsafe",
        disposition=disposition,
        reference_uri="https://example.test/rights",
        reviewed_at=NOW,
        review_note="Reviewed for metadata redistribution.",
    )


def _package(
    *,
    rights: RightsDeclaration | None = None,
) -> PublicationPackage:
    return PublicationPackage(
        contract_version="1",
        data_dictionary=DataDictionary(
            schema_version="1",
            fields=(
                FieldContract(
                    name="medicine_id",
                    description="Stable medicine identifier.",
                    data_type="string",
                    nullable=False,
                    semantic_role="identifier",
                    source_fields=("product_id",),
                ),
            ),
        ),
        dataset_card=DatasetCard(
            title="Global Medicines Atlas",
            summary="Evidence-preserving medicine status comparisons.",
            version="0.7.0",
            created_at=NOW,
            intended_uses=("Cross-jurisdiction research",),
            limitations=("Not clinical advice",),
            coverage=(
                CoverageDeclaration(
                    scope="NZ regulatory products",
                    numerator=10,
                    denominator=10,
                    exclusions=("Veterinary medicines",),
                    jurisdictions=("NZL",),
                ),
            ),
            provenance=(
                ProvenanceDeclaration(
                    source_id="nz-medsafe",
                    source_uri="https://example.test/source",
                    retrieved_at=NOW,
                    source_sha256=SHA_A,
                    transformation_id="normalize-v1",
                    transformation_sha256=SHA_B,
                ),
            ),
            rights=(_rights() if rights is None else rights,),
        ),
        croissant=CroissantMetadata(
            name="Global Medicines Atlas",
            description="Evidence-preserving medicine status comparisons.",
            version="0.7.0",
            license="Rights vary by source; see dataset card.",
            distributions=(
                CroissantDistribution(
                    name="medicines",
                    content_url="data/medicines.parquet",
                    encoding_format="application/vnd.apache.parquet",
                    sha256=SHA_A,
                ),
            ),
        ),
    )


def _evidence(
    check_id: VerificationCheck = VerificationCheck.PACKAGE_CHECKSUM,
    outcome: VerificationOutcome = VerificationOutcome.PASSED,
    *,
    artifact_sha256: str | None = None,
    checked_at: datetime | None = None,
    valid_until: datetime | None = None,
) -> VerificationEvidence:
    privacy_approved = (
        True if check_id is VerificationCheck.PRIVACY_REVIEW else None
    )
    forbidden_content_detected = (
        False if check_id is VerificationCheck.FORBIDDEN_CONTENT_SCAN else None
    )
    return VerificationEvidence(
        check_id=check_id,
        outcome=outcome,
        evidence_uri=f"https://evidence.example.test/{check_id.value}.json",
        evidence_sha256=SHA_B,
        artifact_sha256=artifact_sha256 or _package().sha256(),
        checked_at=checked_at or NOW - timedelta(hours=1),
        valid_until=valid_until or NOW + timedelta(days=1),
        privacy_approved=privacy_approved,
        forbidden_content_detected=forbidden_content_detected,
    )


def _state_evidence(
    state: PublicationState,
) -> tuple[VerificationEvidence, ...]:
    checks = [
        VerificationCheck.PACKAGE_CHECKSUM,
        VerificationCheck.RIGHTS_REVIEW,
        VerificationCheck.PRIVACY_REVIEW,
        VerificationCheck.FORBIDDEN_CONTENT_SCAN,
    ]
    if state in {
        PublicationState.QUALIFIED,
        PublicationState.UPLOADED,
        PublicationState.PUBLIC,
    }:
        checks.append(VerificationCheck.QUALIFICATION)
    if state in {PublicationState.UPLOADED, PublicationState.PUBLIC}:
        checks.append(VerificationCheck.UPLOAD_VERIFICATION)
    if state is PublicationState.PUBLIC:
        checks.append(VerificationCheck.PUBLIC_VERIFICATION)
    return tuple(_evidence(check) for check in checks)


def _identity(**kwargs) -> PublicationIdentity:
    values = {
        "object_id": "software-release",
        "system": PublicationSystem.GITHUB,
        "object_role": PublicationObjectRole.SOFTWARE_SOURCE_RELEASE,
        "identifier": "https://github.com/org/repo/releases/tag/v1.0.0",
        "identifier_state": IdentifierState.VERIFIED,
        "identifier_evidence": "verified_by_github",
        "licence_state": DecisionState.APPROVED,
        "licence_expression": "MIT",
        "licence_decision_evidence": "https://github.com/org/repo/blob/main/LICENSE",
    }
    values.update(kwargs)
    return PublicationIdentity(**values)


def test_identity_validates_system_and_object_role_consistency() -> None:
    with pytest.raises(ValidationError, match="wrong object role"):
        _identity(
            system=PublicationSystem.GITHUB,
            object_role=PublicationObjectRole.DERIVED_DATASET_DISTRIBUTION,
        )


def test_identity_cannot_relate_to_itself() -> None:
    with pytest.raises(ValidationError, match="cannot relate to itself"):
        _identity(object_id="software", related_object_ids=("software",))


def test_identity_related_object_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        _identity(related_object_ids=("other", "other"))


def test_complete_package_is_deterministic_and_content_addressed() -> None:
    package = _package()
    reconstructed = PublicationPackage.model_validate_json(
        package.model_dump_json(by_alias=True)
    )

    assert package.canonical_bytes() == reconstructed.canonical_bytes()
    assert package.sha256() == reconstructed.sha256()
    assert canonical_sha256(package) == package.sha256()
    assert package.croissant.context[0] == "https://schema.org/"


@pytest.mark.parametrize(
    "disposition",
    [
        RightsDisposition.RESTRICTED,
        RightsDisposition.FORBIDDEN,
        RightsDisposition.UNKNOWN,
    ],
)
def test_non_publishable_rights_fail_closed(
    disposition: RightsDisposition,
) -> None:
    with pytest.raises(
        ValidationError,
        match="non-publishable source rights",
    ):
        _package(rights=_rights(disposition))


def test_permitted_rights_require_review_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match="require a reference and review timestamp",
    ):
        RightsDeclaration(
            source_id="nz-medsafe",
            disposition=RightsDisposition.PERMITTED,
        )


def test_provenance_and_rights_must_cover_identical_sources() -> None:
    payload = _package().model_dump()
    payload["dataset_card"]["rights"][0]["source_id"] = "other-source"

    with pytest.raises(
        ValidationError,
        match="must cover the same sources",
    ):
        PublicationPackage.model_validate(payload)


@given(
    numerator=st.integers(min_value=0, max_value=1000),
    denominator=st.integers(min_value=1, max_value=1000),
)
def test_coverage_never_accepts_numerator_above_denominator(
    numerator: int,
    denominator: int,
) -> None:
    values = {
        "scope": "declared population",
        "numerator": numerator,
        "denominator": denominator,
        "exclusions": (),
        "jurisdictions": ("NZL",),
    }
    if numerator > denominator:
        with pytest.raises(ValidationError, match="cannot exceed"):
            CoverageDeclaration(**values)
    else:
        assert CoverageDeclaration(**values).numerator == numerator


def test_missing_coverage_and_provenance_fail_validation() -> None:
    payload = _package().model_dump()
    payload["dataset_card"]["coverage"] = ()
    payload["dataset_card"]["provenance"] = ()

    with pytest.raises(ValidationError) as error:
        PublicationPackage.model_validate(payload)

    messages = {item["msg"] for item in error.value.errors()}
    assert "Tuple should have at least 1 item after validation, not 0" in (
        messages
    )


@pytest.mark.parametrize(
    ("state", "public_uri"),
    [
        (PublicationState.PREPARED, None),
        (PublicationState.QUALIFIED, None),
        (PublicationState.UPLOADED, None),
        (
            PublicationState.PUBLIC,
            "https://example.test/datasets/0.7.0",
        ),
    ],
)
def test_each_success_state_accepts_its_complete_evidence_ladder(
    state: PublicationState,
    public_uri: str | None,
) -> None:
    receipt = PublicationVerificationReceipt(
        receipt_id="receipt-1",
        package_sha256=_package().sha256(),
        state=state,
        verified_at=NOW,
        verifier="qualification-workflow",
        evidence=_state_evidence(state),
        public_uri=public_uri,
    )

    assert receipt.state is state


def test_receipt_is_bound_to_exact_package_digest() -> None:
    package = _package()
    receipt = PublicationVerificationReceipt(
        receipt_id="receipt-1",
        package_sha256=package.sha256(),
        state=PublicationState.QUALIFIED,
        verified_at=NOW,
        verifier="qualification-workflow",
        evidence=_state_evidence(PublicationState.QUALIFIED),
    )
    other_payload = package.model_dump()
    other_payload["dataset_card"]["summary"] = "Changed content."
    other = PublicationPackage.model_validate(other_payload)

    assert receipt_is_for_package(package, receipt)
    assert not receipt_is_for_package(other, receipt)


def test_contracts_reject_unknown_fields() -> None:
    payload = _package().model_dump()
    payload["undocumented"] = True

    with pytest.raises(ValidationError, match="Extra inputs"):
        PublicationPackage.model_validate(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload["data_dictionary"].update(
                fields=payload["data_dictionary"]["fields"]
                + (payload["data_dictionary"]["fields"][0].copy(),)
            ),
            "field names must be unique",
        ),
        (
            lambda payload: payload["data_dictionary"]["fields"][0].update(
                source_fields=("product_id", "product_id")
            ),
            "source_fields must be unique",
        ),
        (
            lambda payload: payload["data_dictionary"].update(
                fields=payload["data_dictionary"]["fields"]
                + (payload["data_dictionary"]["fields"][0].copy(),)
            ),
            "data dictionary field names must be unique",
        ),
        (
            lambda payload: payload["dataset_card"]["coverage"][0].update(
                exclusions=("Veterinary medicines",) * 2
            ),
            "coverage exclusions must be unique",
        ),
        (
            lambda payload: payload["dataset_card"]["coverage"][0].update(
                jurisdictions=("NZL", "NZL")
            ),
            "coverage jurisdictions must be unique",
        ),
        (
            lambda payload: payload["dataset_card"].update(
                provenance=payload["dataset_card"]["provenance"]
                + (payload["dataset_card"]["provenance"][0].copy(),)
            ),
            "provenance source_ids must be unique",
        ),
        (
            lambda payload: payload["dataset_card"].update(
                rights=payload["dataset_card"]["rights"]
                + (payload["dataset_card"]["rights"][0].copy(),)
            ),
            "rights source_ids must be unique",
        ),
        (
            lambda payload: payload["croissant"].update(
                distributions=payload["croissant"]["distributions"]
                + (payload["croissant"]["distributions"][0].copy(),)
            ),
            "distribution names must be unique",
        ),
        (
            lambda payload: payload["croissant"].update(name="Other name"),
            "names must agree",
        ),
        (
            lambda payload: payload["croissant"].update(version="0.8.0"),
            "versions must agree",
        ),
    ],
)
def test_duplicate_and_disagreeing_metadata_fail_closed(
    mutation,
    message: str,
) -> None:
    payload = _package().model_dump()
    mutation(payload)

    with pytest.raises(ValidationError, match=message):
        PublicationPackage.model_validate(payload)


def test_receipt_rejects_duplicate_checks_and_non_public_uri() -> None:
    values = {
        "receipt_id": "receipt-1",
        "package_sha256": _package().sha256(),
        "state": PublicationState.QUALIFIED,
        "verified_at": NOW,
        "verifier": "qualification-workflow",
        "evidence": (_evidence(), _evidence()),
    }
    with pytest.raises(ValidationError, match="check_ids must be unique"):
        PublicationVerificationReceipt(**values)

    values["evidence"] = _state_evidence(PublicationState.QUALIFIED)
    values["public_uri"] = "https://example.test/not-yet-public"
    with pytest.raises(ValidationError, match="only public state"):
        PublicationVerificationReceipt(**values)


@pytest.mark.parametrize(
    ("state", "missing"),
    [
        (PublicationState.PREPARED, VerificationCheck.PACKAGE_CHECKSUM),
        (PublicationState.PREPARED, VerificationCheck.RIGHTS_REVIEW),
        (PublicationState.PREPARED, VerificationCheck.PRIVACY_REVIEW),
        (
            PublicationState.PREPARED,
            VerificationCheck.FORBIDDEN_CONTENT_SCAN,
        ),
        (PublicationState.QUALIFIED, VerificationCheck.QUALIFICATION),
        (PublicationState.UPLOADED, VerificationCheck.UPLOAD_VERIFICATION),
        (PublicationState.PUBLIC, VerificationCheck.PUBLIC_VERIFICATION),
    ],
)
def test_each_state_fails_closed_when_a_required_check_is_missing(
    state: PublicationState,
    missing: VerificationCheck,
) -> None:
    evidence = tuple(
        item for item in _state_evidence(state) if item.check_id is not missing
    )

    with pytest.raises(ValidationError, match="missing checks"):
        PublicationVerificationReceipt(
            receipt_id="receipt-missing",
            package_sha256=_package().sha256(),
            state=state,
            verified_at=NOW,
            verifier="qualification-workflow",
            evidence=evidence,
            public_uri=(
                "https://example.test/public"
                if state is PublicationState.PUBLIC
                else None
            ),
        )


@pytest.mark.parametrize(
    "outcome",
    [VerificationOutcome.FAILED, VerificationOutcome.UNKNOWN],
)
def test_failed_or_unknown_checks_fail_closed(
    outcome: VerificationOutcome,
) -> None:
    evidence = list(_state_evidence(PublicationState.PREPARED))
    evidence[0] = _evidence(outcome=outcome)

    with pytest.raises(
        ValidationError,
        match="failed or unknown evidence requires",
    ):
        PublicationVerificationReceipt(
            receipt_id="receipt-nonpassing",
            package_sha256=_package().sha256(),
            state=PublicationState.PREPARED,
            verified_at=NOW,
            verifier="qualification-workflow",
            evidence=tuple(evidence),
        )

    failed_receipt = PublicationVerificationReceipt(
        receipt_id="receipt-failed",
        package_sha256=_package().sha256(),
        state=PublicationState.VERIFICATION_FAILED,
        verified_at=NOW,
        verifier="qualification-workflow",
        evidence=(_evidence(outcome=outcome),),
    )
    assert failed_receipt.state is PublicationState.VERIFICATION_FAILED


def test_verification_failed_requires_nonpassing_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match="requires failed or unknown evidence",
    ):
        PublicationVerificationReceipt(
            receipt_id="receipt-failed",
            package_sha256=_package().sha256(),
            state=PublicationState.VERIFICATION_FAILED,
            verified_at=NOW,
            verifier="qualification-workflow",
            evidence=(_evidence(),),
        )


@pytest.mark.parametrize(
    ("check", "field", "value", "message"),
    [
        (
            VerificationCheck.PRIVACY_REVIEW,
            "privacy_approved",
            False,
            "privacy review must explicitly approve",
        ),
        (
            VerificationCheck.PRIVACY_REVIEW,
            "privacy_approved",
            None,
            "privacy review must explicitly approve",
        ),
        (
            VerificationCheck.FORBIDDEN_CONTENT_SCAN,
            "forbidden_content_detected",
            True,
            "must explicitly report none",
        ),
        (
            VerificationCheck.FORBIDDEN_CONTENT_SCAN,
            "forbidden_content_detected",
            None,
            "must explicitly report none",
        ),
    ],
)
def test_privacy_and_forbidden_content_findings_are_explicit(
    check: VerificationCheck,
    field: str,
    *,
    value: bool | None,
    message: str,
) -> None:
    payload = _evidence(check).model_dump()
    payload[field] = value

    with pytest.raises(ValidationError, match=message):
        VerificationEvidence.model_validate(payload)


@pytest.mark.parametrize(
    ("check", "field"),
    [
        (VerificationCheck.PACKAGE_CHECKSUM, "privacy_approved"),
        (
            VerificationCheck.RIGHTS_REVIEW,
            "forbidden_content_detected",
        ),
    ],
)
def test_review_findings_cannot_be_attached_to_the_wrong_check(
    check: VerificationCheck,
    field: str,
) -> None:
    payload = _evidence(check).model_dump()
    payload[field] = False

    with pytest.raises(ValidationError, match="only valid"):
        VerificationEvidence.model_validate(payload)


def test_evidence_must_be_bound_to_the_receipted_artifact() -> None:
    evidence = list(_state_evidence(PublicationState.PREPARED))
    evidence[0] = _evidence(artifact_sha256="c" * 64)

    with pytest.raises(ValidationError, match="bound to the package"):
        PublicationVerificationReceipt(
            receipt_id="receipt-unbound",
            package_sha256=_package().sha256(),
            state=PublicationState.PREPARED,
            verified_at=NOW,
            verifier="qualification-workflow",
            evidence=tuple(evidence),
        )


@pytest.mark.parametrize(
    ("checked_at", "valid_until"),
    [
        (NOW + timedelta(seconds=1), NOW + timedelta(days=1)),
        (NOW - timedelta(days=2), NOW - timedelta(seconds=1)),
    ],
)
def test_future_or_stale_evidence_fails_closed(
    checked_at: datetime,
    valid_until: datetime,
) -> None:
    evidence = list(_state_evidence(PublicationState.PREPARED))
    evidence[0] = _evidence(
        checked_at=checked_at,
        valid_until=valid_until,
    )

    with pytest.raises(ValidationError, match="current at verification"):
        PublicationVerificationReceipt(
            receipt_id="receipt-stale",
            package_sha256=_package().sha256(),
            state=PublicationState.PREPARED,
            verified_at=NOW,
            verifier="qualification-workflow",
            evidence=tuple(evidence),
        )


def test_evidence_validity_window_must_be_ordered() -> None:
    payload = _evidence().model_dump()
    payload["valid_until"] = payload["checked_at"]

    with pytest.raises(ValidationError, match="valid window"):
        VerificationEvidence.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_uri", "file:///tmp/evidence.json"),
        ("evidence_uri", "javascript:alert(1)"),
        ("evidence_uri", "https://user:secret@example.test/evidence.json"),
    ],
)
def test_evidence_uri_rejects_unsafe_locations(
    field: str,
    value: str,
) -> None:
    payload = _evidence().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError):
        VerificationEvidence.model_validate(payload)


@pytest.mark.parametrize(
    "public_uri",
    [
        None,
        "file:///tmp/public",
        "https://user:secret@example.test/public",
    ],
)
def test_public_state_requires_safe_observable_http_location(
    public_uri: str | None,
) -> None:
    with pytest.raises(ValidationError):
        PublicationVerificationReceipt(
            receipt_id="receipt-public",
            package_sha256=_package().sha256(),
            state=PublicationState.PUBLIC,
            verified_at=NOW,
            verifier="qualification-workflow",
            evidence=_state_evidence(PublicationState.PUBLIC),
            public_uri=public_uri,
        )
