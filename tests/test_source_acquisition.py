from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    DestinationPolicyError,
    acquire_source,
    validate_remote_destination,
)
from global_medicines_atlas.countries import SourceDimension
from global_medicines_atlas.receipts import (
    EvidenceClass,
    FailureReceipt,
    SourceReceipt,
)
from global_medicines_atlas.source_catalog import (
    AccessMode,
    AuthenticationMode,
    InterfaceStatus,
    MedicineDataSource,
    SourceReadiness,
)

NOW = datetime(2026, 7, 29, 4, 5, 6, tzinfo=UTC)
SMALL_POLICY = AcquisitionPolicy(max_bytes=32)


def catalog_source(
    *,
    access_mode: AccessMode = AccessMode.DOWNLOAD,
    download_url: str | None = "https://example.test/medicines.zip",
) -> MedicineDataSource:
    return MedicineDataSource.from_legacy(
        source_id="test-regulator",
        jurisdictions=("NZL",),
        authority="Test Regulator",
        title="Test medicines",
        dimension=SourceDimension.REGULATORY,
        access_mode=access_mode,
        interface_status=(
            InterfaceStatus.SUPPORTED
            if access_mode is AccessMode.API
            else InterfaceStatus.DOCUMENTED_DOWNLOAD
        ),
        formats=("json",) if access_mode is AccessMode.API else ("zip",),
        authentication=AuthenticationMode.NONE,
        product_grain="test product",
        historical_scope="fixture snapshot",
        native_identifier="test identifier",
        last_verified_at=NOW.date(),
        documentation_url="https://example.test/docs",
        landing_page="https://example.test/",
        download_url=download_url,
        api_url="https://example.test/api"
        if access_mode is AccessMode.API
        else None,
        update_cadence="daily",
        rights_status="review_required",
        readiness=SourceReadiness.CANDIDATE,
        evidence_limit="Fixture-only test source.",
    )


def acquire(
    tmp_path: Path,
    handler,
    *,
    destination: Path = Path("artifacts/source.bin"),
    policy: AcquisitionPolicy = SMALL_POLICY,
    evidence_class: EvidenceClass = EvidenceClass.FIXTURE,
):
    return acquire_source(
        "test-regulator",
        destination,
        repository_root=tmp_path,
        catalog=(catalog_source(),),
        transport=httpx.MockTransport(handler),
        policy=policy,
        evidence_class=evidence_class,
        clock=lambda: NOW,
    )


@pytest.mark.integration
def test_acquisition_stages_hashes_and_atomically_promotes(
    tmp_path: Path,
) -> None:
    payload = b"governed fixture"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://example.test/medicines.zip"
        return httpx.Response(
            200,
            headers={"content-type": "application/zip"},
            content=payload,
        )

    receipt = acquire(tmp_path, handler)

    assert isinstance(receipt, SourceReceipt)
    assert receipt.evidence_class is EvidenceClass.FIXTURE
    assert not receipt.satisfies_live_gate
    assert receipt.payload.matches(payload)
    assert (tmp_path / "artifacts/source.bin").read_bytes() == payload
    assert not tuple((tmp_path / "artifacts").glob("*.tmp"))


@pytest.mark.unit
def test_api_catalog_surface_is_selected_without_arbitrary_url(
    tmp_path: Path,
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b"{}",
        )

    receipt = acquire_source(
        "test-regulator",
        Path("runs/api.json"),
        repository_root=tmp_path,
        catalog=(
            catalog_source(access_mode=AccessMode.API, download_url=None),
        ),
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    )

    assert isinstance(receipt, SourceReceipt)
    assert seen == ["https://example.test/api"]


@pytest.mark.edge
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (
            httpx.Response(302, headers={"location": "https://elsewhere.test"}),
            "redirect_rejected",
        ),
        (
            httpx.Response(
                200, headers={"content-type": "text/html"}, text="no"
            ),
            "content_type_rejected",
        ),
        (httpx.Response(503, text="down"), "http_status"),
    ],
)
def test_rejected_responses_emit_failure_receipts(
    tmp_path: Path,
    response: httpx.Response,
    code: str,
) -> None:
    receipt = acquire(tmp_path, lambda _: response)

    assert isinstance(receipt, FailureReceipt)
    assert receipt.failure_code == code
    assert not (tmp_path / "artifacts/source.bin").exists()


@pytest.mark.edge
def test_oversized_stream_is_removed_without_promotion(tmp_path: Path) -> None:
    receipt = acquire(
        tmp_path,
        lambda _: httpx.Response(
            200,
            headers={"content-type": "application/octet-stream"},
            content=b"x" * 33,
        ),
    )

    assert isinstance(receipt, FailureReceipt)
    assert receipt.failure_code == "max_bytes_exceeded"
    assert not (tmp_path / "artifacts/source.bin").exists()
    assert not tuple((tmp_path / "artifacts").glob("*.tmp"))


@pytest.mark.edge
def test_timeout_is_recorded_once_without_implicit_retry(
    tmp_path: Path,
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("offline", request=request)

    receipt = acquire(tmp_path, handler)

    assert isinstance(receipt, FailureReceipt)
    assert receipt.failure_code == "timeout"
    assert receipt.retryable
    assert attempts == 1


@pytest.mark.edge
@pytest.mark.parametrize(
    "destination",
    [Path("../escaped.bin"), Path("src/payload.bin")],
)
def test_destination_must_be_local_and_ignored(
    tmp_path: Path,
    destination: Path,
) -> None:
    with pytest.raises(ValueError, match="destination"):
        acquire(
            tmp_path,
            lambda _: pytest.fail("transport should not run"),
            destination=destination,
        )


@pytest.mark.edge
def test_unknown_or_non_automatable_source_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(LookupError):
        acquire_source(
            "missing",
            Path("artifacts/source.bin"),
            repository_root=tmp_path,
            catalog=(catalog_source(),),
        )

    with pytest.raises(ValueError, match="no automatable"):
        acquire_source(
            "test-regulator",
            Path("artifacts/source.bin"),
            repository_root=tmp_path,
            catalog=(
                catalog_source(
                    access_mode=AccessMode.WEB_SEARCH,
                    download_url=None,
                ),
            ),
        )


@pytest.mark.unit
def test_requested_live_class_remains_distinct_from_live_gate(
    tmp_path: Path,
) -> None:
    receipt = acquire(
        tmp_path,
        lambda _: httpx.Response(
            200,
            headers={"content-type": "application/octet-stream"},
            content=b"fixture",
        ),
        evidence_class=EvidenceClass.LIVE,
    )

    assert isinstance(receipt, SourceReceipt)
    assert receipt.evidence_class is EvidenceClass.LIVE
    assert not receipt.satisfies_live_gate


@pytest.mark.edge
@pytest.mark.parametrize(
    "url",
    [
        "http://example.test/medicines.zip",
        "https://127.0.0.1/medicines.zip",
        "https://169.254.169.254/latest/meta-data/",
        "https://[::1]/medicines.zip",
    ],
)
def test_acquisition_rejects_disallowed_or_private_destinations(
    tmp_path: Path,
    url: str,
) -> None:
    source = catalog_source(download_url=url)
    receipt = acquire_source(
        "test-regulator",
        Path("artifacts/source.bin"),
        repository_root=tmp_path,
        catalog=(source,),
        transport=httpx.MockTransport(
            lambda _: pytest.fail("transport should not run")
        ),
        clock=lambda: NOW,
    )

    assert isinstance(receipt, FailureReceipt)
    assert receipt.failure_code in {"scheme_rejected", "network_rejected"}


@pytest.mark.edge
def test_acquisition_rejects_dns_resolution_to_private_network(
    tmp_path: Path,
) -> None:
    resolver_calls: list[str] = []

    def private_resolver(hostname: str) -> tuple[str, ...]:
        resolver_calls.append(hostname)
        return ("10.0.0.8",)

    receipt = acquire_source(
        "test-regulator",
        Path("artifacts/source.bin"),
        repository_root=tmp_path,
        catalog=(catalog_source(),),
        transport=httpx.MockTransport(
            lambda _: pytest.fail("transport should not run")
        ),
        resolver=private_resolver,
        clock=lambda: NOW,
    )

    assert isinstance(receipt, FailureReceipt)
    assert receipt.failure_code == "network_rejected"
    assert resolver_calls == ["example.test"]


@pytest.mark.unit
def test_acquisition_policy_requires_https_and_bounded_host_budget() -> None:
    policy = AcquisitionPolicy()

    assert policy.allowed_schemes == ("https",)
    assert policy.max_attempts == 1
    assert policy.max_concurrency_per_host == 2
    with pytest.raises(ValueError, match="allowed_schemes"):
        AcquisitionPolicy(allowed_schemes=())


@pytest.mark.unit
def test_live_destination_requires_explicit_hostname_admission() -> None:
    with pytest.raises(DestinationPolicyError, match="not admitted"):
        validate_remote_destination(
            "https://example.test/data",
            AcquisitionPolicy(),
            resolver=lambda _: ("93.184.216.34",),
            require_host_allowlist=True,
        )

    validate_remote_destination(
        "https://example.test/data",
        AcquisitionPolicy(allowed_hosts=("example.test",)),
        resolver=lambda _: ("93.184.216.34",),
        require_host_allowlist=True,
    )


@pytest.mark.edge
def test_mixed_public_private_dns_answer_is_rejected() -> None:
    with pytest.raises(DestinationPolicyError, match="non-public"):
        validate_remote_destination(
            "https://example.test/data",
            AcquisitionPolicy(allowed_hosts=("example.test",)),
            resolver=lambda _: ("93.184.216.34", "10.0.0.2"),
            require_host_allowlist=True,
        )
