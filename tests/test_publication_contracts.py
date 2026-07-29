"""Contracts for deterministic, fail-closed publication packages."""

from __future__ import annotations

from datetime import UTC, datetime

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
    FieldContract,
    ProvenanceDeclaration,
    PublicationPackage,
    PublicationState,
    PublicationVerificationReceipt,
    RightsDeclaration,
    RightsDisposition,
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
    outcome: VerificationOutcome = VerificationOutcome.PASSED,
) -> VerificationEvidence:
    return VerificationEvidence(
        check_id="package-checksum",
        outcome=outcome,
        evidence_uri="evidence/checksum.json",
        evidence_sha256=SHA_B,
    )


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
    ("state", "outcome", "public_uri", "valid"),
    [
        (PublicationState.PREPARED, VerificationOutcome.PASSED, None, True),
        (PublicationState.QUALIFIED, VerificationOutcome.PASSED, None, True),
        (PublicationState.UPLOADED, VerificationOutcome.PASSED, None, True),
        (
            PublicationState.PUBLIC,
            VerificationOutcome.PASSED,
            "https://example.test/datasets/0.7.0",
            True,
        ),
        (
            PublicationState.VERIFICATION_FAILED,
            VerificationOutcome.FAILED,
            None,
            True,
        ),
        (PublicationState.PUBLIC, VerificationOutcome.PASSED, None, False),
        (PublicationState.PREPARED, VerificationOutcome.FAILED, None, False),
        (
            PublicationState.VERIFICATION_FAILED,
            VerificationOutcome.PASSED,
            None,
            False,
        ),
    ],
)
def test_receipt_states_require_matching_evidence(
    state: PublicationState,
    outcome: VerificationOutcome,
    public_uri: str | None,
    *,
    valid: bool,
) -> None:
    values = {
        "receipt_id": "receipt-1",
        "package_sha256": _package().sha256(),
        "state": state,
        "verified_at": NOW,
        "verifier": "qualification-workflow",
        "evidence": (_evidence(outcome),),
        "public_uri": public_uri,
    }
    if not valid:
        with pytest.raises(ValidationError):
            PublicationVerificationReceipt(**values)
        return
    assert PublicationVerificationReceipt(**values).state is state


def test_receipt_is_bound_to_exact_package_digest() -> None:
    package = _package()
    receipt = PublicationVerificationReceipt(
        receipt_id="receipt-1",
        package_sha256=package.sha256(),
        state=PublicationState.QUALIFIED,
        verified_at=NOW,
        verifier="qualification-workflow",
        evidence=(_evidence(),),
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
            "field names must be unique",
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

    values["evidence"] = (_evidence(),)
    values["public_uri"] = "https://example.test/not-yet-public"
    with pytest.raises(ValidationError, match="only public state"):
        PublicationVerificationReceipt(**values)
