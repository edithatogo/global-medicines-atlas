"""Representative native-format tests for Canadian regulatory sources."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyUrl

from global_medicines_atlas.adapters.canada import (
    compare_dpd_api_bulk,
    project_dpd_api,
    project_dpd_bulk,
    project_noc_extract,
)
from global_medicines_atlas.models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
)
from global_medicines_atlas.parity import ParityStatus
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)

FIXTURES = Path(__file__).parent / "fixtures" / "native" / "ca"
SHA = "a" * 64
Projector = Callable[
    [bytes, SourceReceipt],
    tuple[CanonicalMedicineRecord, ...],
]


def _receipt(
    payload: bytes,
    *,
    source_id: str,
    method: AcquisitionMethod,
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id=f"synthetic:{source_id}:{method}",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction="CAN",
            authority="Health Canada",
            dataset_title=f"Synthetic {source_id} native-format fixture",
            catalog_version="fixture-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(f"https://fixtures.invalid/{source_id}"),
            retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
            acquisition_method=method,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id=f"{source_id}-native-fixture",
            transformation_sha256=SHA,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


@pytest.mark.parametrize(
    ("name", "projector", "source_id", "method", "concept_id", "status"),
    [
        (
            "dpd_api.json",
            project_dpd_api,
            "ca-dpd",
            AcquisitionMethod.API,
            "ca-dpd:12345",
            "marketed",
        ),
        (
            "dpd_bulk.csv",
            project_dpd_bulk,
            "ca-dpd",
            AcquisitionMethod.DOWNLOAD,
            "ca-dpd:23456",
            "approved",
        ),
        (
            "noc_extract.csv",
            project_noc_extract,
            "ca-noc",
            AcquisitionMethod.DOWNLOAD,
            "ca-noc:NOC-2026-001",
            "issued",
        ),
    ],
)
def test_native_adapter_projects_regulatory_evidence(
    name: str,
    projector: Projector,
    source_id: str,
    method: AcquisitionMethod,
    concept_id: str,
    status: str,
) -> None:
    payload = (FIXTURES / name).read_bytes()
    receipt = _receipt(payload, source_id=source_id, method=method)

    records = projector(payload, receipt)

    assert len(records) == 1
    record = records[0]
    assert record.concept.concept_id == concept_id
    assert record.concept.jurisdiction == "CAN"
    assert {item.kind for item in record.assertions} == {
        AssertionKind.REGULATORY
    }
    assertion = record.assertions[0]
    assert assertion.status_code == status
    assert assertion.evidence_status is EvidenceStatus.UNKNOWN
    assert assertion.provenance.source_sha256 == receipt.payload.sha256
    assert assertion.provenance.source_version == "fixture-v1"


@pytest.mark.parametrize(
    ("name", "projector", "source_id", "method"),
    [
        (
            "dpd_api.json",
            project_dpd_api,
            "ca-dpd",
            AcquisitionMethod.API,
        ),
        (
            "dpd_bulk.csv",
            project_dpd_bulk,
            "ca-dpd",
            AcquisitionMethod.DOWNLOAD,
        ),
        (
            "noc_extract.csv",
            project_noc_extract,
            "ca-noc",
            AcquisitionMethod.DOWNLOAD,
        ),
    ],
)
def test_native_adapter_rejects_tampered_payload(
    name: str,
    projector: Projector,
    source_id: str,
    method: AcquisitionMethod,
) -> None:
    payload = (FIXTURES / name).read_bytes()
    receipt = _receipt(payload, source_id=source_id, method=method)

    with pytest.raises(ValueError, match="does not match"):
        projector(payload + b" ", receipt)


def test_dpd_api_rejects_bulk_receipt() -> None:
    payload = (FIXTURES / "dpd_api.json").read_bytes()
    receipt = _receipt(
        payload,
        source_id="ca-dpd",
        method=AcquisitionMethod.DOWNLOAD,
    )

    with pytest.raises(ValueError, match="acquisition method"):
        project_dpd_api(payload, receipt)


def test_dpd_api_rejects_excess_records() -> None:
    payload = (
        b'{"results":['
        + b",".join(
            b'{"drug_code":1,"brand_name":"x","status":"marketed","din":"1"}'
            for _ in range(1_001)
        )
        + b"]}"
    )
    receipt = _receipt(
        payload,
        source_id="ca-dpd",
        method=AcquisitionMethod.API,
    )

    with pytest.raises(ValueError, match="record limit"):
        project_dpd_api(payload, receipt)


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b'{"results":{}}',
        b'{"results":[1]}',
        b'{"results":[{"drug_code":null}]}',
        b'{"results":[{"drug_code":"  "}]}',
        (
            b'{"results":[{"drug_code":"'
            + b"x" * 4_097
            + b'","brand_name":"x","status":"marketed","din":"1"}]}'
        ),
    ],
)
def test_dpd_api_rejects_malformed_native_shapes(payload: bytes) -> None:
    receipt = _receipt(
        payload,
        source_id="ca-dpd",
        method=AcquisitionMethod.API,
    )

    with pytest.raises((TypeError, ValueError)):
        project_dpd_api(payload, receipt)


def test_dpd_api_rejects_payload_over_byte_limit() -> None:
    payload = b" " * (8 * 1024 * 1024 + 1)
    receipt = _receipt(
        payload,
        source_id="ca-dpd",
        method=AcquisitionMethod.API,
    )

    with pytest.raises(ValueError, match="byte limit"):
        project_dpd_api(payload, receipt)


def test_dpd_bulk_rejects_oversized_field() -> None:
    payload = (
        b"DRUG_CODE,BRAND_NAME,STATUS,DIN\n1," + b"x" * 4_097 + b",marketed,1\n"
    )
    receipt = _receipt(
        payload,
        source_id="ca-dpd",
        method=AcquisitionMethod.DOWNLOAD,
    )

    with pytest.raises(ValueError, match="field limit"):
        project_dpd_bulk(payload, receipt)


def test_dpd_bulk_rejects_non_utf8() -> None:
    payload = b"\xff"
    receipt = _receipt(
        payload,
        source_id="ca-dpd",
        method=AcquisitionMethod.DOWNLOAD,
    )

    with pytest.raises(ValueError, match="UTF-8"):
        project_dpd_bulk(payload, receipt)


def test_noc_rejects_missing_required_field() -> None:
    payload = b"NOC_NUMBER,PRODUCT_NAME,NOTICE_STATUS,DIN\n,Example,Issued,1\n"
    receipt = _receipt(
        payload,
        source_id="ca-noc",
        method=AcquisitionMethod.DOWNLOAD,
    )

    with pytest.raises(ValueError, match="NOC_NUMBER"):
        project_noc_extract(payload, receipt)


def test_noc_rejects_invalid_notice_date() -> None:
    payload = (
        b"NOC_NUMBER,PRODUCT_NAME,NOTICE_STATUS,DIN,NOTICE_DATE\n"
        b"NOC-1,Example,Issued,1,29/07/2026\n"
    )
    receipt = _receipt(
        payload,
        source_id="ca-noc",
        method=AcquisitionMethod.DOWNLOAD,
    )

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        project_noc_extract(payload, receipt)


def test_noc_allows_absent_notice_date() -> None:
    payload = (
        b"NOC_NUMBER,PRODUCT_NAME,NOTICE_STATUS,DIN,NOTICE_DATE\n"
        b"NOC-1,Example,Issued,1,\n"
    )
    receipt = _receipt(
        payload,
        source_id="ca-noc",
        method=AcquisitionMethod.DOWNLOAD,
    )

    record = project_noc_extract(payload, receipt)[0]

    assert record.assertions[0].effective_from is None


def _dpd_payloads(
    *,
    api_status: str = "MARKETED",
    bulk_status: str = "MARKETED",
    bulk_drug_code: str = "12345",
) -> tuple[bytes, bytes]:
    api = (
        b'{"results":[{"drug_code":12345,"brand_name":"Examplemab",'
        b'"status":"' + api_status.encode() + b'","din":"01234567"}]}'
    )
    bulk = (
        b"DRUG_CODE,BRAND_NAME,STATUS,DIN\n"
        + bulk_drug_code.encode()
        + b",Examplemab,"
        + bulk_status.encode()
        + b",01234567\n"
    )
    return api, bulk


def test_dpd_api_bulk_parity_reports_equivalent_projections() -> None:
    api, bulk = _dpd_payloads()

    result = compare_dpd_api_bulk(
        api,
        _receipt(api, source_id="ca-dpd", method=AcquisitionMethod.API),
        bulk,
        _receipt(
            bulk,
            source_id="ca-dpd",
            method=AcquisitionMethod.DOWNLOAD,
        ),
        api_population_id="dpd-current-products",
        bulk_population_id="dpd-current-products",
    )

    assert result.status is ParityStatus.EQUIVALENT
    assert result.is_equivalent


@pytest.mark.parametrize(
    ("api_status", "bulk_status", "bulk_drug_code", "expected"),
    [
        ("MARKETED", "CANCELLED", "12345", ("changed",)),
        ("MARKETED", "MARKETED", "99999", ("membership",)),
    ],
)
def test_dpd_api_bulk_parity_reports_differences(
    api_status: str,
    bulk_status: str,
    bulk_drug_code: str,
    expected: tuple[str, ...],
) -> None:
    api, bulk = _dpd_payloads(
        api_status=api_status,
        bulk_status=bulk_status,
        bulk_drug_code=bulk_drug_code,
    )

    result = compare_dpd_api_bulk(
        api,
        _receipt(api, source_id="ca-dpd", method=AcquisitionMethod.API),
        bulk,
        _receipt(
            bulk,
            source_id="ca-dpd",
            method=AcquisitionMethod.DOWNLOAD,
        ),
        api_population_id="dpd-current-products",
        bulk_population_id="dpd-current-products",
    )

    assert result.status is ParityStatus.DIFFERENT
    if expected == ("changed",):
        assert result.changed == ("ca-dpd:12345",)
    else:
        assert result.only_left == ("ca-dpd:12345",)
        assert result.only_right == ("ca-dpd:99999",)


def test_dpd_api_bulk_parity_refuses_different_populations() -> None:
    api, bulk = _dpd_payloads()

    result = compare_dpd_api_bulk(
        api,
        _receipt(api, source_id="ca-dpd", method=AcquisitionMethod.API),
        bulk,
        _receipt(
            bulk,
            source_id="ca-dpd",
            method=AcquisitionMethod.DOWNLOAD,
        ),
        api_population_id="marketed-products",
        bulk_population_id="all-products",
    )

    assert result.status is ParityStatus.NOT_COMPARABLE
    assert result.reasons == ("declared populations differ",)
