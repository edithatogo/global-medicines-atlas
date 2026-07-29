"""Bounded, governed acquisition of catalogued source payloads."""

from __future__ import annotations

import os
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from ipaddress import ip_address
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import AnyUrl

from .receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    FailureReceipt,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)
from .source_catalog import AccessMode, MedicineDataSource, load_source_catalog

Receipt = SourceReceipt | FailureReceipt
Clock = Callable[[], datetime]
Resolver = Callable[[str], tuple[str, ...]]


class _WritableBinary(Protocol):
    def write(self, data: bytes, /) -> int: ...

    def flush(self) -> None: ...

    def fileno(self) -> int: ...


_LOCAL_PAYLOAD_ROOTS = frozenset({
    "artifacts",
    "drugbank",
    "ema_data",
    "gtop_data",
    "medsafe_exports",
    "nzulm_2023_data",
    "pbs_data",
    "runs",
    "tga_exports",
})


@dataclass(frozen=True, slots=True)
class AcquisitionPolicy:
    """Explicit resource and response constraints for one retrieval."""

    timeout_seconds: float = 30.0
    max_bytes: int = 64 * 1024 * 1024
    allowed_schemes: tuple[str, ...] = ("https",)
    allowed_hosts: tuple[str, ...] = ()
    max_attempts: int = 1
    max_concurrency_per_host: int = 2
    max_redirects: int = 3
    reject_private_networks: bool = True
    allowed_content_types: tuple[str, ...] = (
        "application/json",
        "application/octet-stream",
        "application/zip",
        "text/csv",
        "text/plain",
        "text/xml",
    )

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        if not self.allowed_schemes:
            raise ValueError("allowed_schemes must not be empty")
        if any(not host.strip() for host in self.allowed_hosts):
            raise ValueError("allowed_hosts must contain non-empty hostnames")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if self.max_concurrency_per_host <= 0:
            raise ValueError("max_concurrency_per_host must be positive")
        if self.max_redirects < 0:
            raise ValueError("max_redirects must not be negative")
        if not self.allowed_content_types:
            raise ValueError("allowed_content_types must not be empty")


DEFAULT_ACQUISITION_POLICY = AcquisitionPolicy()


class DestinationPolicyError(Exception):
    """A source destination or response violated acquisition policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _catalog_source(
    source_id: str,
    catalog: Iterable[MedicineDataSource],
) -> MedicineDataSource:
    matches = [source for source in catalog if source.source_id == source_id]
    if len(matches) != 1:
        raise LookupError(
            f"catalog source_id must resolve exactly once: {source_id}"
        )
    return matches[0]


def _download_surface(
    source: MedicineDataSource,
) -> tuple[str, AcquisitionMethod]:
    if source.download_url is not None and source.access_mode in {
        AccessMode.DOWNLOAD,
        AccessMode.API_AND_DOWNLOAD,
    }:
        return str(source.download_url), AcquisitionMethod.DOWNLOAD
    if source.api_url is not None and source.access_mode in {
        AccessMode.API,
        AccessMode.API_AND_DOWNLOAD,
    }:
        return str(source.api_url), AcquisitionMethod.API
    raise ValueError(
        "catalog source has no automatable API or download surface"
    )


def _system_resolver(hostname: str) -> tuple[str, ...]:
    """Resolve all addresses used for destination policy enforcement."""

    return tuple({
        str(item[4][0])
        for item in socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    })


def _network_is_private(value: str) -> bool:
    address = ip_address(value)
    return not address.is_global


def _validated_scheme_and_hostname(
    uri: str,
    policy: AcquisitionPolicy,
) -> str:
    parsed = urlsplit(uri)
    if parsed.scheme.lower() not in policy.allowed_schemes:
        raise DestinationPolicyError(
            "scheme_rejected",
            "Source URI scheme is not permitted by acquisition policy.",
        )
    hostname = parsed.hostname
    if hostname is None:
        raise DestinationPolicyError(
            "network_rejected",
            "Source URI must include a hostname.",
        )
    return hostname


def validate_remote_destination(
    uri: str,
    policy: AcquisitionPolicy,
    *,
    resolver: Resolver | None,
    require_host_allowlist: bool,
) -> tuple[str, ...]:
    """Return the public addresses admitted for this exact destination."""

    hostname = _validated_scheme_and_hostname(uri, policy)
    allowed_hosts = frozenset(host.lower() for host in policy.allowed_hosts)
    if require_host_allowlist and hostname.lower() not in allowed_hosts:
        raise DestinationPolicyError(
            "host_rejected",
            "Source hostname is not admitted by acquisition policy.",
        )
    try:
        addresses = (str(ip_address(hostname)),)
    except ValueError:
        if resolver is not None:
            addresses = resolver(hostname)
        elif require_host_allowlist:
            addresses = _system_resolver(hostname)
        else:
            return ()
    public_addresses = tuple(
        address for address in addresses if not _network_is_private(address)
    )
    if policy.reject_private_networks and len(public_addresses) != len(
        addresses
    ):
        raise DestinationPolicyError(
            "network_rejected",
            "Source URI resolved to a non-public network.",
        )
    if not public_addresses:
        raise DestinationPolicyError(
            "network_rejected",
            "Source URI did not resolve to a public address.",
        )
    return public_addresses


def policy_for_catalog_uri(
    policy: AcquisitionPolicy,
    uri: str,
) -> AcquisitionPolicy:
    """Admit the governed catalog hostname when no stricter set was supplied."""

    if policy.allowed_hosts:
        return policy
    hostname = urlsplit(uri).hostname
    if hostname is None:
        raise DestinationPolicyError(
            "network_rejected",
            "Source URI must include a hostname.",
        )
    return replace(policy, allowed_hosts=(hostname.lower(),))


class BoundIPAddressTransport(httpx.BaseTransport):
    """Connect to a validated IP while preserving HTTP authority and TLS SNI."""

    def __init__(
        self,
        *,
        policy: AcquisitionPolicy,
        resolver: Resolver | None = None,
        inner: httpx.BaseTransport | None = None,
    ) -> None:
        self._policy = policy
        self._resolver = resolver
        self._inner = inner or httpx.HTTPTransport(trust_env=False)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        hostname = request.url.host
        addresses = validate_remote_destination(
            str(request.url),
            self._policy,
            resolver=self._resolver,
            require_host_allowlist=True,
        )
        selected_address = addresses[0]
        port = request.url.port
        default_port = 443 if request.url.scheme == "https" else 80
        authority = (
            hostname if port in {None, default_port} else f"{hostname}:{port}"
        )
        headers = request.headers.copy()
        headers["host"] = authority
        extensions = dict(request.extensions)
        extensions["sni_hostname"] = hostname
        bound_url = request.url.copy_with(host=selected_address)
        bound_request = httpx.Request(
            request.method,
            bound_url,
            headers=headers,
            content=request.stream,
            extensions=extensions,
        )
        return self._inner.handle_request(bound_request)

    def close(self) -> None:
        self._inner.close()


def transport_for_destination(
    uri: str,
    policy: AcquisitionPolicy,
    *,
    resolver: Resolver | None,
    transport: httpx.BaseTransport | None,
) -> httpx.BaseTransport:
    """Build the production binding transport or validate a test boundary."""

    if transport is None:
        return BoundIPAddressTransport(policy=policy, resolver=resolver)
    validate_remote_destination(
        uri,
        policy,
        resolver=resolver,
        require_host_allowlist=False,
    )
    return transport


def _local_destination(repository_root: Path, destination: Path) -> Path:
    root = repository_root.resolve()
    target = (
        (root / destination).resolve()
        if not destination.is_absolute()
        else destination.resolve()
    )
    try:
        relative = target.relative_to(root)
    except ValueError as error:
        raise ValueError(
            "destination must remain inside the repository"
        ) from error
    if not relative.parts or relative.parts[0] not in _LOCAL_PAYLOAD_ROOTS:
        raise ValueError(
            "destination must be within a governed git-ignored payload root"
        )
    return target


def _source_identity(source: MedicineDataSource) -> SourceIdentity:
    return SourceIdentity(
        catalog_id=source.source_id,
        source_id=source.source_id,
        jurisdiction=source.jurisdictions[0],
        authority=source.authority,
        dataset_title=source.title,
        catalog_version="1",
    )


def _failure(
    *,
    source: MedicineDataSource,
    uri: str,
    method: AcquisitionMethod,
    observed_at: datetime,
    code: str,
    message: str,
    status: AcquisitionStatus = AcquisitionStatus.FAILED,
    retryable: bool = False,
) -> FailureReceipt:
    return FailureReceipt(
        receipt_id=f"{source.source_id}-{observed_at.isoformat()}-{code}",
        source=_source_identity(source),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(uri),
            retrieved_at=observed_at,
            acquisition_method=method,
            status=status,
        ),
        evidence_class=EvidenceClass.UNAVAILABLE,
        rights_state=RightsState.UNKNOWN,
        failure_code=code,
        failure_message=message,
        retryable=retryable,
    )


def _reject_oversize() -> None:
    raise DestinationPolicyError(
        "max_bytes_exceeded", "response exceeded max_bytes"
    )


def _write_bounded(
    response: httpx.Response,
    staged: _WritableBinary,
    *,
    max_bytes: int,
) -> PayloadEvidence:
    digest = sha256()
    byte_count = 0
    for chunk in response.iter_bytes():
        byte_count += len(chunk)
        if byte_count > max_bytes:
            _reject_oversize()
        staged.write(chunk)
        digest.update(chunk)
    staged.flush()
    os.fsync(staged.fileno())
    return PayloadEvidence(sha256=digest.hexdigest(), byte_count=byte_count)


def _stage_response(
    response: httpx.Response,
    *,
    target: Path,
    policy: AcquisitionPolicy,
) -> tuple[Path, PayloadEvidence]:
    if response.is_redirect:
        raise DestinationPolicyError(
            "redirect_rejected",
            "Redirect responses are not accepted.",
        )
    response.raise_for_status()
    content_type = (
        response.headers.get("content-type", "").split(";", 1)[0].lower()
    )
    if content_type not in policy.allowed_content_types:
        raise DestinationPolicyError(
            "content_type_rejected",
            f"Response content type is not allowed: {content_type or 'missing'}",
        )

    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as staged:
            temporary_path = Path(staged.name)
            payload = _write_bounded(
                response,
                staged,
                max_bytes=policy.max_bytes,
            )
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path, payload


def _success(
    *,
    source: MedicineDataSource,
    uri: str,
    method: AcquisitionMethod,
    observed_at: datetime,
    payload: PayloadEvidence,
    evidence_class: EvidenceClass,
) -> SourceReceipt:
    transformation_id = "raw-acquisition-v1"
    return SourceReceipt(
        receipt_id=f"{source.source_id}-{observed_at.isoformat()}-{payload.sha256[:12]}",
        source=_source_identity(source),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(uri),
            retrieved_at=observed_at,
            acquisition_method=method,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=payload,
        rights_state=RightsState.UNKNOWN,
        evidence_class=evidence_class,
        transformation=TransformationEvidence(
            transformation_id=transformation_id,
            transformation_sha256=sha256(
                transformation_id.encode()
            ).hexdigest(),
            output_sha256=payload.sha256,
            output_byte_count=payload.byte_count,
        ),
    )


def acquire_source(
    source_id: str,
    destination: Path,
    *,
    repository_root: Path,
    policy: AcquisitionPolicy = DEFAULT_ACQUISITION_POLICY,
    catalog: Iterable[MedicineDataSource] | None = None,
    transport: httpx.BaseTransport | None = None,
    resolver: Resolver | None = None,
    evidence_class: EvidenceClass = EvidenceClass.FIXTURE,
    clock: Clock = lambda: datetime.now(UTC),
) -> Receipt:
    """Acquire one catalogued payload without retries or publication side effects."""

    sources = load_source_catalog() if catalog is None else tuple(catalog)
    source = _catalog_source(source_id, sources)
    uri, method = _download_surface(source)
    effective_policy = policy_for_catalog_uri(policy, uri)
    observed_at = clock()
    target = _local_destination(repository_root, destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None

    try:
        effective_transport = transport_for_destination(
            uri,
            effective_policy,
            resolver=resolver,
            transport=transport,
        )
        with (
            httpx.Client(
                transport=effective_transport,
                timeout=effective_policy.timeout_seconds,
                follow_redirects=transport is None,
                max_redirects=effective_policy.max_redirects,
            ) as client,
            client.stream("GET", uri) as response,
        ):
            temporary_path, payload = _stage_response(
                response,
                target=target,
                policy=effective_policy,
            )

        temporary_path.replace(target)
        temporary_path = None
        return _success(
            source=source,
            uri=uri,
            method=method,
            observed_at=observed_at,
            payload=payload,
            evidence_class=evidence_class,
        )
    except DestinationPolicyError as error:
        return _failure(
            source=source,
            uri=uri,
            method=method,
            observed_at=observed_at,
            code=error.code,
            message=str(error),
        )
    except httpx.TimeoutException as error:
        return _failure(
            source=source,
            uri=uri,
            method=method,
            observed_at=observed_at,
            code="timeout",
            message=str(error),
            retryable=True,
        )
    except httpx.HTTPStatusError as error:
        return _failure(
            source=source,
            uri=uri,
            method=method,
            observed_at=observed_at,
            code="http_status",
            message=f"HTTP status {error.response.status_code}",
        )
    except httpx.HTTPError as error:
        return _failure(
            source=source,
            uri=uri,
            method=method,
            observed_at=observed_at,
            code="transport_error",
            message=str(error),
            retryable=True,
        )
    finally:
        if isinstance(temporary_path, Path):
            temporary_path.unlink(missing_ok=True)
