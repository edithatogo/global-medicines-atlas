"""Receipt and parity tests for Drugs@FDA acquisition surfaces."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from global_medicines_atlas.adapters.us_acquisition import (
    acquire_drugsfda_api,
    acquire_drugsfda_bulk,
)
from global_medicines_atlas.adapters.us_drugsfda import (
    compare_drugsfda_surfaces,
    project_drugsfda_api,
    project_drugsfda_bulk,
)
from global_medicines_atlas.countries import SourceDimension
from global_medicines_atlas.ingestors import PayloadMember, PayloadSet
from global_medicines_atlas.models import EvidenceStatus
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    EvidenceClass,
    PayloadEvidence,
    RightsState,
    SourceReceipt,
    TransformationEvidence,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision
from global_medicines_atlas.source_catalog import (
    AccessMode,
    MedicineDataSource,
    SourceReadiness,
)

NOW = datetime(2026, 7, 29, 5, 0, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "us"
APPLICATIONS = "ApplNo\tApplType\tSponsorName\n012345\tNDA\tExample Sponsor\n"
PRODUCTS = "ApplNo\tProductNo\tDrugName\n012345\t001\tExample Drug\n"
MARKETING = "ApplNo\tProductNo\tMarketingStatusID\n012345\t001\t1\n"
STATUSES = "MarketingStatusID\tMarketingStatusDescription\n1\tPrescription\n"


def bulk_payloads(receipt: SourceReceipt) -> PayloadSet:
    values = {
        "applications.tsv": APPLICATIONS.encode(),
        "products.tsv": PRODUCTS.encode(),
        "marketing_status.tsv": MARKETING.encode(),
        "status_lookup.tsv": STATUSES.encode(),
    }
    members = []
    for name, payload in values.items():
        evidence = PayloadEvidence.from_bytes(payload)
        member_receipt = receipt.model_copy(
            update={
                "receipt_id": f"{receipt.receipt_id}:{name}",
                "payload": evidence,
                "transformation": TransformationEvidence(
                    transformation_id=f"extract:{name}",
                    transformation_sha256=receipt.payload.sha256,
                    output_sha256=evidence.sha256,
                    output_byte_count=evidence.byte_count,
                ),
            }
        )
        members.append(
            PayloadMember(name=name, payload=payload, receipt=member_receipt)
        )
    return PayloadSet(
        source_id="us-drugsfda",
        jurisdiction="USA",
        members=tuple(members),
    )


def source() -> MedicineDataSource:
    return MedicineDataSource.from_legacy(
        source_id="us-drugsfda",
        jurisdictions=("USA",),
        authority="US Food and Drug Administration",
        title="Drugs@FDA",
        dimension=SourceDimension.REGULATORY,
        access_mode=AccessMode.API_AND_DOWNLOAD,
        landing_page="https://www.accessdata.fda.gov/scripts/cder/daf/",
        api_url="https://api.fda.gov/drug/drugsfda.json",
        download_url="https://www.fda.gov/drugs/drugsfda-data-files",
        update_cadence="weekday",
        rights_status="fixture test",
        readiness=SourceReadiness.IMPLEMENTED,
        implemented_ingestion=True,
        evidence_limit="Regulatory evidence only.",
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("acquire", "uri", "destination", "content_type", "method"),
    [
        (
            acquire_drugsfda_bulk,
            "https://example.test/drugsfda.zip",
            Path("artifacts/us/drugsfda.zip"),
            "application/zip",
            AcquisitionMethod.DOWNLOAD,
        ),
        (
            acquire_drugsfda_api,
            "https://example.test/drugsfda.json?limit=1",
            Path("runs/us/drugsfda.json"),
            "application/json",
            AcquisitionMethod.API,
        ),
    ],
)
def test_drugsfda_surfaces_are_receipt_backed(
    tmp_path: Path,
    acquire,
    uri: str,
    destination: Path,
    content_type: str,
    method: AcquisitionMethod,
) -> None:
    payload = b"fixture payload"
    keyword = "bulk_url" if method is AcquisitionMethod.DOWNLOAD else "api_url"
    receipt = acquire(
        destination,
        repository_root=tmp_path,
        catalog=(source(),),
        reuse_decision=acquire_new_decision("us-drugsfda"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": content_type},
                content=payload,
            )
        ),
        clock=lambda: NOW,
        **{keyword: uri},
    )

    assert isinstance(receipt, SourceReceipt)
    assert receipt.retrieval.acquisition_method is method
    assert str(receipt.retrieval.uri) == uri
    assert receipt.payload.matches(payload)
    assert (tmp_path / destination).read_bytes() == payload


@pytest.mark.integration
def test_api_and_bulk_fixture_projections_have_parity(tmp_path: Path) -> None:
    api_payload = (FIXTURES / "drugsfda_api.json").read_bytes()
    api_receipt = acquire_drugsfda_api(
        Path("runs/us/drugsfda.json"),
        repository_root=tmp_path,
        api_url="https://example.test/drugsfda.json",
        catalog=(source(),),
        reuse_decision=acquire_new_decision("us-drugsfda"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=api_payload,
            )
        ),
        clock=lambda: NOW,
    )
    bulk_receipt = acquire_drugsfda_bulk(
        Path("artifacts/us/drugsfda.zip"),
        repository_root=tmp_path,
        bulk_url="https://example.test/drugsfda.zip",
        catalog=(source(),),
        reuse_decision=acquire_new_decision("us-drugsfda"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/zip"},
                content=b"bulk fixture",
            )
        ),
        clock=lambda: NOW,
    )
    assert isinstance(api_receipt, SourceReceipt)
    assert isinstance(bulk_receipt, SourceReceipt)
    bulk = project_drugsfda_bulk(payloads=bulk_payloads(bulk_receipt))
    api = project_drugsfda_api(api_payload, receipt=api_receipt)

    assert bulk[0].assertions[0].evidence_status is EvidenceStatus.UNKNOWN
    assert api[0].assertions[0].evidence_status is EvidenceStatus.UNKNOWN
    parity = compare_drugsfda_surfaces(bulk, api)

    assert parity.is_equivalent
    assert parity.matched_product_ids == ("us-drugsfda:012345:001",)


@pytest.mark.unit
def test_api_projection_confirms_only_qualifying_live_receipt(
    tmp_path: Path,
) -> None:
    payload = (FIXTURES / "drugsfda_api.json").read_bytes()
    receipt = acquire_drugsfda_api(
        Path("runs/us/drugsfda.json"),
        repository_root=tmp_path,
        api_url="https://example.test/drugsfda.json",
        catalog=(source(),),
        reuse_decision=acquire_new_decision("us-drugsfda"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=payload,
            )
        ),
        clock=lambda: NOW,
    )
    assert isinstance(receipt, SourceReceipt)
    live_receipt = receipt.model_copy(
        update={
            "evidence_class": EvidenceClass.LIVE,
            "rights_state": RightsState.PERMITTED,
            "rights_reference": "https://rights.example/drugsfda",
        }
    )

    records = project_drugsfda_api(payload, receipt=live_receipt)

    assert live_receipt.satisfies_live_gate
    assert records[0].assertions[0].evidence_status is EvidenceStatus.CONFIRMED


@pytest.mark.edge
def test_parity_reports_status_and_membership_differences(
    tmp_path: Path,
) -> None:
    payload = (
        b'{"results":[{"application_number":"012345","products":['
        b'{"product_number":"001","brand_name":"Example Drug",'
        b'"marketing_status":"Discontinued"},'
        b'{"product_number":"002","brand_name":"Extra",'
        b'"marketing_status":"Prescription"}]}]}'
    )
    receipt = acquire_drugsfda_api(
        Path("runs/us/drugsfda.json"),
        repository_root=tmp_path,
        api_url="https://example.test/drugsfda.json",
        catalog=(source(),),
        reuse_decision=acquire_new_decision("us-drugsfda"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=payload,
            )
        ),
        clock=lambda: NOW,
    )
    assert isinstance(receipt, SourceReceipt)
    bulk_receipt = acquire_drugsfda_bulk(
        Path("artifacts/us/drugsfda.zip"),
        repository_root=tmp_path,
        bulk_url="https://example.test/drugsfda.zip",
        catalog=(source(),),
        reuse_decision=acquire_new_decision("us-drugsfda"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/zip"},
                content=b"bulk fixture",
            )
        ),
        clock=lambda: NOW,
    )
    assert isinstance(bulk_receipt, SourceReceipt)
    bulk = project_drugsfda_bulk(payloads=bulk_payloads(bulk_receipt))

    parity = compare_drugsfda_surfaces(
        bulk,
        project_drugsfda_api(payload, receipt=receipt),
    )

    assert not parity.is_equivalent
    assert parity.status_mismatches == ("us-drugsfda:012345:001",)
    assert parity.api_only_product_ids == ("us-drugsfda:012345:002",)


@pytest.mark.edge
def test_api_projection_rejects_tampered_payload(tmp_path: Path) -> None:
    payload = (FIXTURES / "drugsfda_api.json").read_bytes()
    receipt = acquire_drugsfda_api(
        Path("runs/us/drugsfda.json"),
        repository_root=tmp_path,
        api_url="https://example.test/drugsfda.json",
        catalog=(source(),),
        reuse_decision=acquire_new_decision("us-drugsfda"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=payload,
            )
        ),
        clock=lambda: NOW,
    )
    assert isinstance(receipt, SourceReceipt)

    with pytest.raises(ValueError, match="does not match receipt"):
        project_drugsfda_api(payload + b" ", receipt=receipt)


@pytest.mark.edge
def test_bulk_projection_rejects_tampered_member(
    tmp_path: Path,
) -> None:
    receipt = acquire_drugsfda_bulk(
        Path("artifacts/us/drugsfda.zip"),
        repository_root=tmp_path,
        bulk_url="https://example.test/drugsfda.zip",
        catalog=(source(),),
        reuse_decision=acquire_new_decision("us-drugsfda"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/zip"},
                content=b"bulk fixture",
            )
        ),
        clock=lambda: NOW,
    )
    assert isinstance(receipt, SourceReceipt)
    payloads = bulk_payloads(receipt)
    products = next(
        member for member in payloads.members if member.name == "products.tsv"
    )

    with pytest.raises(ValueError, match="do not match"):
        PayloadMember(
            name=products.name,
            payload=products.payload + b"tampered",
            receipt=products.receipt,
        )
