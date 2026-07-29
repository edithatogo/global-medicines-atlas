from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import given
from hypothesis import strategies as st

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
    VerificationCheck,
    VerificationEvidence,
    VerificationOutcome,
)
from global_medicines_atlas.publication_package import (
    PackageGenerationError,
    generate_publication_package,
)

SHA = "a" * 64
NOW = datetime(2026, 7, 29, tzinfo=UTC)


def _contract() -> PublicationPackage:
    provenance = ProvenanceDeclaration(
        source_id="nz",
        source_uri="https://example.test/nz",
        retrieved_at=NOW,
        source_sha256=SHA,
        transformation_id="normalise-v1",
        transformation_sha256="b" * 64,
    )
    rights = RightsDeclaration(
        source_id="nz",
        disposition=RightsDisposition.PERMITTED,
        reference_uri="https://example.test/rights",
        reviewed_at=NOW,
        review_note="Approved fixture",
    )
    return PublicationPackage(
        contract_version="1",
        data_dictionary=DataDictionary(
            schema_version="1",
            fields=(
                FieldContract(
                    name="source_id",
                    description="Stable source identifier",
                    data_type="string",
                    nullable=False,
                    semantic_role="provenance",
                    source_fields=("source",),
                ),
                FieldContract(
                    name="medicine_id",
                    description="Source medicine identifier",
                    data_type="string",
                    nullable=False,
                    semantic_role="identifier",
                    source_fields=("id",),
                ),
                FieldContract(
                    name="name",
                    description="Medicine name",
                    data_type="string",
                    nullable=False,
                    semantic_role="label",
                    source_fields=("name",),
                ),
            ),
        ),
        dataset_card=DatasetCard(
            title="Reviewed medicines",
            summary="A reviewed test dataset",
            version="0.7.0",
            created_at=NOW,
            intended_uses=("Comparison research",),
            limitations=("Fixture only",),
            coverage=(
                CoverageDeclaration(
                    scope="fixture",
                    numerator=2,
                    denominator=2,
                    exclusions=(),
                    jurisdictions=("NZ",),
                ),
            ),
            provenance=(provenance,),
            rights=(rights,),
        ),
        croissant=CroissantMetadata(
            name="Reviewed medicines",
            description="A reviewed test dataset",
            version="0.7.0",
            license="rights-declared-per-source",
            distributions=(
                CroissantDistribution(
                    name="data/medicines.parquet",
                    content_url="data/medicines.parquet",
                    encoding_format="application/vnd.apache.parquet",
                    sha256="0" * 64,
                ),
            ),
        ),
    )


def _receipt(
    contract: PublicationPackage,
) -> PublicationVerificationReceipt:
    evidence = tuple(
        VerificationEvidence(
            check_id=check,
            outcome=VerificationOutcome.PASSED,
            evidence_uri=f"https://example.test/evidence/{check.value}",
            evidence_sha256="c" * 64,
            artifact_sha256=contract.sha256(),
            checked_at=NOW,
            valid_until=NOW + timedelta(days=1),
            privacy_approved=True
            if check is VerificationCheck.PRIVACY_REVIEW
            else None,
            forbidden_content_detected=False
            if check is VerificationCheck.FORBIDDEN_CONTENT_SCAN
            else None,
        )
        for check in (
            VerificationCheck.PACKAGE_CHECKSUM,
            VerificationCheck.RIGHTS_REVIEW,
            VerificationCheck.PRIVACY_REVIEW,
            VerificationCheck.FORBIDDEN_CONTENT_SCAN,
            VerificationCheck.QUALIFICATION,
        )
    )
    return PublicationVerificationReceipt(
        receipt_id="qualification-1",
        package_sha256=contract.sha256(),
        state=PublicationState.QUALIFIED,
        verified_at=NOW,
        verifier="test-suite",
        evidence=evidence,
    )


def _rows() -> list[dict[str, str]]:
    return [
        {"source_id": "nz", "medicine_id": "2", "name": "Zulu"},
        {"source_id": "nz", "medicine_id": "1", "name": "Alpha"},
    ]


@pytest.mark.integration
def test_generates_complete_readable_deterministic_package():
    contract = _contract()
    first = generate_publication_package(contract, _receipt(contract), _rows())
    second = generate_publication_package(
        contract, _receipt(contract), reversed(_rows())
    )

    assert first == second
    assert first.sha256 == second.sha256
    assert tuple(item.path for item in first.files) == (
        "SHA256SUMS",
        "data/medicines.parquet",
        "metadata/citations.json",
        "metadata/coverage.json",
        "metadata/croissant.json",
        "metadata/data-dictionary.json",
        "metadata/dataset-card.json",
        "metadata/qualification.json",
        "package-manifest.json",
    )
    table = pq.read_table(
        pa.BufferReader(first.file("data/medicines.parquet").content)
    )
    assert table.column_names == ["source_id", "medicine_id", "name"]
    assert table.column("medicine_id").to_pylist() == ["1", "2"]


def test_manifest_and_checksums_bind_exact_emitted_bytes():
    contract = _contract()
    generated = generate_publication_package(
        contract, _receipt(contract), _rows()
    )
    manifest = json.loads(generated.file("package-manifest.json").content)
    entries = {item["path"]: item for item in manifest["files"]}
    for path, entry in entries.items():
        member = generated.file(path)
        assert entry == {
            "path": path,
            "sha256": member.sha256,
            "size": member.size,
        }
    assert manifest["contract_sha256"] == contract.sha256()
    expected_sums = "".join(
        f"{item.sha256}  {item.path}\n"
        for item in generated.files
        if item.path not in {"SHA256SUMS", "package-manifest.json"}
    ).encode()
    assert generated.file("SHA256SUMS").content == expected_sums


def test_croissant_is_bound_to_canonical_parquet():
    contract = _contract()
    generated = generate_publication_package(
        contract, _receipt(contract), _rows()
    )
    parquet = generated.file("data/medicines.parquet")
    croissant = json.loads(generated.file("metadata/croissant.json").content)
    distribution = croissant["distributions"][0]
    assert distribution["sha256"] == parquet.sha256
    assert distribution["content_url"] == parquet.path


@pytest.mark.parametrize(
    "state",
    [
        PublicationState.PREPARED,
        PublicationState.UPLOADED,
        PublicationState.PUBLIC,
        PublicationState.VERIFICATION_FAILED,
    ],
)
def test_rejects_every_nonqualified_state(state):
    contract = _contract()
    receipt = _receipt(contract).model_copy(update={"state": state})
    with pytest.raises(PackageGenerationError, match="qualified receipt"):
        generate_publication_package(contract, receipt, _rows())


def test_rejects_receipt_for_different_contract():
    contract = _contract()
    altered = contract.model_copy(update={"contract_version": "2"})
    with pytest.raises(PackageGenerationError, match="not bound"):
        generate_publication_package(altered, _receipt(contract), _rows())


@pytest.mark.parametrize(
    "row",
    [
        {"source_id": "restricted", "medicine_id": "1", "name": "A"},
        {"source_id": "", "medicine_id": "1", "name": "A"},
        {"medicine_id": "1", "name": "A"},
        {
            "source_id": "nz",
            "medicine_id": "1",
            "name": "A",
            "secret": "restricted payload",
        },
    ],
)
def test_rejects_unpermitted_or_undeclared_payload(row):
    contract = _contract()
    with pytest.raises(PackageGenerationError):
        generate_publication_package(contract, _receipt(contract), [row])


def test_requires_source_id_in_dictionary():
    contract = _contract()
    dictionary = contract.data_dictionary.model_copy(
        update={"fields": contract.data_dictionary.fields[1:]}
    )
    altered = contract.model_copy(update={"data_dictionary": dictionary})
    with pytest.raises(PackageGenerationError, match="declare source_id"):
        generate_publication_package(altered, _receipt(altered), [])


def test_requires_exactly_one_canonical_croissant_distribution():
    contract = _contract()
    croissant = contract.croissant.model_copy(
        update={
            "distributions": (
                contract.croissant.distributions[0].model_copy(
                    update={"name": "other.parquet"}
                ),
            )
        }
    )
    altered = contract.model_copy(update={"croissant": croissant})
    with pytest.raises(PackageGenerationError, match="canonical Parquet"):
        generate_publication_package(altered, _receipt(altered), _rows())


def test_rejects_unsupported_reviewed_data_type():
    contract = _contract()
    field = contract.data_dictionary.fields[-1].model_copy(
        update={"data_type": "executable"}
    )
    dictionary = contract.data_dictionary.model_copy(
        update={
            "fields": (*contract.data_dictionary.fields[:-1], field),
        }
    )
    altered = contract.model_copy(update={"data_dictionary": dictionary})
    with pytest.raises(PackageGenerationError, match="unsupported"):
        generate_publication_package(altered, _receipt(altered), _rows())


def test_rejects_null_in_non_nullable_reviewed_field():
    contract = _contract()
    rows = _rows()
    rows[0]["name"] = None  # type: ignore[assignment]
    with pytest.raises(PackageGenerationError, match="non-nullable"):
        generate_publication_package(contract, _receipt(contract), rows)


def test_empty_package_retains_reviewed_semantic_schema():
    contract = _contract()
    generated = generate_publication_package(contract, _receipt(contract), [])
    table = pq.read_table(
        pa.BufferReader(generated.file("data/medicines.parquet").content)
    )
    assert tuple(str(field.type) for field in table.schema) == (
        "large_string",
        "large_string",
        "large_string",
    )


@given(st.permutations(_rows()))
@pytest.mark.property
def test_row_order_never_changes_any_package_byte(rows):
    contract = _contract()
    expected = generate_publication_package(
        contract, _receipt(contract), _rows()
    )
    actual = generate_publication_package(contract, _receipt(contract), rows)
    assert actual.files == expected.files


def test_package_identity_is_content_addressed():
    contract = _contract()
    generated = generate_publication_package(
        contract, _receipt(contract), _rows()
    )
    digest = hashlib.sha256()
    for item in generated.files:
        digest.update(item.path.encode())
        digest.update(b"\0")
        digest.update(item.sha256.encode())
        digest.update(b"\n")
    assert generated.sha256 == digest.hexdigest()


def test_missing_file_lookup_is_explicit():
    contract = _contract()
    generated = generate_publication_package(
        contract, _receipt(contract), _rows()
    )
    with pytest.raises(KeyError, match="absent"):
        generated.file("absent")
