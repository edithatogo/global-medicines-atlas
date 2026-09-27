"""Deterministic, receipt-bound packaging for MBS Silver v4 publication."""

import json
from datetime import UTC, date, datetime
from hashlib import sha256

import pyarrow.parquet as pq
import pytest
from pydantic import AnyUrl

from global_medicines_atlas.mbs_silver_publication import (
    DESTINATION_PREFIX,
    MBS_SOURCE_URI,
    build_mbs_silver_v4_package,
    validate_mbs_silver_v4_package,
)
from global_medicines_atlas.mbs_silver_qualification import (
    OFFICIAL_MBS_V3_URI,
    MbsSourceEraVerification,
)
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    DataSensitivity,
    EvidenceClass,
    PayloadEvidence,
    PersonalDataState,
    PublicationDisposition,
    RetrievalEvidence,
    RightsState,
    SensitivityClassification,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
    temporal_identity_from_source,
)


def _xml(body: str) -> bytes:
    row = f"<Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum>{body}</Data>"
    return f"<MBS_XML>{row}</MBS_XML>".encode()


def _authorized_receipt(
    payload: bytes, commit: str = "b" * 40
) -> SourceReceipt:
    digest = sha256(payload).hexdigest()
    retrieved_at = datetime(2026, 8, 29, 8, 57, 21, tzinfo=UTC)
    return SourceReceipt(
        receipt_id=f"public-archive:au-mbs:{digest}",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="July 2025 Medicare Benefits Schedule XML",
            catalog_version="2025-07-version-3",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(MBS_SOURCE_URI),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=PayloadEvidence.from_bytes(payload),
        temporal=temporal_identity_from_source(
            retrieved_at=retrieved_at,
            source_id="au-mbs",
            payload_sha256=digest,
            source_version="2025-07-version-3",
            original_uri=MBS_SOURCE_URI,
        ),
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(
            "https://github.com/edithatogo/global-medicines-atlas/issues/340"
        ),
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.NON_SENSITIVE,
            personal_data=PersonalDataState.NONE,
            publication=PublicationDisposition.PERMITTED,
            reason_codes=(
                "qualified_official_mbs_schedule",
                "exact_release_approval",
            ),
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="exact-public-source-restore-v1",
            transformation_sha256=sha256(commit.encode("ascii")).hexdigest(),
            output_sha256=digest,
            output_byte_count=len(payload),
        ),
    )


def _verification(payload: bytes) -> MbsSourceEraVerification:
    return MbsSourceEraVerification(
        official_source_uri=AnyUrl(OFFICIAL_MBS_V3_URI),
        release_id="MBS-XML-20250701 Version 3",
        released_at=date(2025, 6, 16),
        effective_at=date(2025, 7, 1),
        official_source_sha256=sha256(payload).hexdigest(),
        official_source_byte_count=len(payload),
        compared_at=datetime(2026, 9, 27, tzinfo=UTC),
    )


def test_package_is_deterministic_and_contains_all_six_source_faithful_tables(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "global_medicines_atlas.mbs_silver_publication._authorization_identity",
        lambda *_: ("a" * 64, "b" * 64),
    )
    payload = _xml(
        "<ItemStartDate>30.08.2026</ItemStartDate>"
        "<ScheduleFee>42.500</ScheduleFee>"
        "<Benefit85>85.00</Benefit85>"
        "<Description>Example service</Description>"
    )
    receipt = _authorized_receipt(payload, "b" * 40)
    verification = _verification(payload)
    first = build_mbs_silver_v4_package(
        payload,
        receipt,
        exact_commit="b" * 40,
        source_era_verification=verification,
        output_dir=tmp_path / "first",
    )
    second = build_mbs_silver_v4_package(
        payload,
        receipt,
        exact_commit="b" * 40,
        source_era_verification=verification,
        output_dir=tmp_path / "second",
    )

    assert first.manifest_sha256 == second.manifest_sha256
    assert first.destination_prefix == DESTINATION_PREFIX
    assert set(first.files) == set(second.files)
    assert {name: path.read_bytes() for name, path in first.files.items()} == {
        name: path.read_bytes() for name, path in second.files.items()
    }
    assert len(first.objects) == 8  # six tables, B1 receipt, qualification
    assert "source.xml" not in first.files
    manifest = json.loads(first.manifest_path.read_text())
    assert manifest["candidate_only"] is True
    assert manifest["source"]["sha256"] == sha256(payload).hexdigest()
    assert manifest["source"]["receipt_sha256"] == receipt.digest()
    assert manifest["official_release"]["release_id"] == (
        "MBS-XML-20250701 Version 3"
    )
    assert manifest["authorization_basis"]["destination"] == (
        "edithatogo/australian-mbs-source-archive"
    )

    validate_mbs_silver_v4_package(first)
    services_path = first.files[f"{DESTINATION_PREFIX}/services.parquet"]
    services = pq.read_table(services_path)
    assert services.schema.metadata[b"schema_version"] == b"1.1"
    assert services.column("ItemStartDate")[0].as_py()["native_value"] == (
        "30.08.2026"
    )


@pytest.mark.parametrize(
    "mutation",
    ["payload", "receipt", "manifest", "missing_object", "extra_object"],
)
def test_package_validation_rejects_any_drift(
    tmp_path, mutation: str, monkeypatch
) -> None:
    monkeypatch.setattr(
        "global_medicines_atlas.mbs_silver_publication._authorization_identity",
        lambda *_: ("a" * 64, "b" * 64),
    )
    payload = _xml("<ScheduleFee>42.00</ScheduleFee>")
    package = build_mbs_silver_v4_package(
        payload,
        _authorized_receipt(payload, "c" * 40),
        exact_commit="c" * 40,
        source_era_verification=_verification(payload),
        output_dir=tmp_path / "package",
    )
    if mutation == "payload":
        package.objects[0].path.write_bytes(b"changed")
    elif mutation == "receipt":
        next(
            item.path
            for item in package.objects
            if item.role == "b1_source_receipt"
        ).write_bytes(b"changed")
    elif mutation == "manifest":
        package.manifest_path.write_bytes(b"{}")
    elif mutation == "missing_object":
        package.objects[0].path.unlink()
    else:
        (package.path / "unmanifested.bin").write_bytes(b"extra")

    with pytest.raises(ValueError, match=r"package|object|manifest|receipt"):
        validate_mbs_silver_v4_package(package)
