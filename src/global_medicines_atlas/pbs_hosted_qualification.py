"""Main-Actions-only anonymous qualification of one pinned public PBS archive."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import socket
import ssl
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote, urljoin, urlsplit

import httpx

from .acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
    DestinationPolicyError,
)
from .adapters.au_pbs import read_pbs_v3_member
from .pbs_historical_qualification import qualify_pbs_historical_projections
from .pbs_member_identity import build_pbs_xml_member_binding
from .receipts import SourceReceipt

DATASET = "edithatogo/australian-pbs-source-archive"
REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
INFO_URL = f"https://huggingface.co/api/datasets/{DATASET}/revision/{REVISION}"
HOSTS = ("huggingface.co", "us.aws.cdn.hf.co")
MAX_REPORT_BYTES = 48_000
FAILURE_STAGES = frozenset({
    "context",
    "transport-setup",
    "public-before",
    "manifest-read",
    "receipt-read",
    "archive-read",
    "public-after",
    "manifest-validation",
    "receipt-validation",
    "member-extraction",
    "member-binding",
    "projection-qualification",
    "report",
    "unavailable",
})
FAILURE_CATEGORIES = frozenset({
    "validation",
    "structure",
    "transport",
    "transport-connect",
    "transport-read",
    "transport-remote-protocol",
    "transport-decoding",
    "transport-local-protocol",
    "timeout",
    "destination-policy",
    "redirect",
    "http-status",
    "encoding",
    "byte-limit",
    "pin-mismatch",
    "unexpected",
    "unavailable",
})
TRANSPORT_DETAILS = frozenset({
    "dns",
    "tls-certificate",
    "tls",
    "connection-refused",
    "network-unreachable",
    "unknown",
})


def _detail_code(value: object) -> str:
    return (
        value
        if type(value) is str and value in TRANSPORT_DETAILS
        else "unknown"
    )


def _native_transport_detail(error: BaseException) -> str:
    for kind, detail in (
        (socket.gaierror, "dns"),
        (ssl.SSLCertVerificationError, "tls-certificate"),
        (ssl.SSLError, "tls"),
    ):
        if isinstance(error, kind):
            return detail
    if isinstance(error, OSError) and type(error.errno) is int:
        if error.errno == errno.ECONNREFUSED:
            return "connection-refused"
        if error.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
            return "network-unreachable"
    return "unknown"


def _transport_detail(error: BaseException) -> str:
    """Inspect at most eight explicit causes; never messages or request data.

    Fixed type/errno buckets are observations, not retry or recovery decisions.
    Missing, cyclic, truncated and unrecognised causes remain unknown. Implicit
    exception context can be unrelated and is deliberately not consulted.
    """
    current: BaseException | None = error
    seen: set[int] = set()
    for _ in range(8):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        detail = _native_transport_detail(current)
        if detail != "unknown":
            return detail
        current = current.__cause__
    return "unknown"


def _diagnostics(
    event: tuple[str, str] | None,
    retry_detail: object,
    terminal_detail: object,
) -> dict[str, str | None]:
    return {
        "retry_cause": _detail_code(retry_detail)
        if _retry_record(event) is not None
        else None,
        "terminal_cause": None
        if terminal_detail is None
        else _detail_code(terminal_detail),
    }


class QualificationError(ValueError):
    """Carry only fixed, allowlisted diagnostic codes across the CLI boundary."""

    def __init__(
        self, stage: str, category: str, *, transport_detail: str = "unknown"
    ) -> None:
        self.retry_event: tuple[str, str] | None = None
        self.retry_detail = "unknown"
        self.transport_detail = _detail_code(transport_detail)
        self.stage = stage if stage in FAILURE_STAGES else "unavailable"
        self.category = (
            category if category in FAILURE_CATEGORIES else "unexpected"
        )
        super().__init__(
            f"PBS qualification failed: {self.stage}/{self.category}"
        )


class _RejectionError(ValueError):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


def _transport_category(error: httpx.HTTPError) -> str:
    for kind, category in (
        (httpx.ConnectError, "transport-connect"),
        (httpx.ReadError, "transport-read"),
        (httpx.RemoteProtocolError, "transport-remote-protocol"),
        (httpx.DecodingError, "transport-decoding"),
        (httpx.LocalProtocolError, "transport-local-protocol"),
    ):
        if isinstance(error, kind):
            return category
    return "transport"


@dataclass
class _RetryBudget:
    event: tuple[str, str] | None = None
    progress: Callable[[dict[str, Any]], None] | None = None
    started: float = field(default_factory=time.monotonic)
    retry_detail: str = "unknown"

    def checkpoint(
        self,
        stage: str,
        phase: str = "unavailable",
        batches: int = 0,
        rows: int = 0,
    ) -> None:
        if self.progress is None:
            return
        if (
            stage not in FAILURE_STAGES
            or phase
            not in {
                "unavailable",
                "binding-validation",
                "denominator",
                "native",
                "domain",
                "entities",
                "references",
                "dates",
            }
            or any(
                type(value) is not int or not 0 <= value < 2**63
                for value in (batches, rows)
            )
        ):
            raise ValueError("invalid aggregate progress")
        report = failure_report()
        report.update({
            "status": "incomplete",
            "transport_retry": _retry_record(self.event),
            "transport_diagnostics": _diagnostics(
                self.event, self.retry_detail, None
            ),
            "progress": {
                "stage": stage,
                "phase": phase,
                "batches": batches,
                "rows": rows,
                "elapsed_ms": min(
                    2**63 - 1,
                    max(0, int((time.monotonic() - self.started) * 1000)),
                ),
            },
        })
        self.progress(report)


def _retry_record(event: tuple[str, str] | None) -> dict[str, str] | None:
    if event is None:
        return None
    stage, category = event
    if stage not in FAILURE_STAGES or category not in {
        "transport-connect",
        "transport-read",
        "transport-remote-protocol",
    }:
        return None
    return {"stage": stage, "category": category}


def _fetch[T](
    stage: str,
    budget: _RetryBudget,
    deadline: float,
    operation: Callable[[], T],
) -> T:
    """Allow one run-wide transient retry; restart the entire guarded read."""
    with _at(stage, progress=budget.checkpoint):
        try:
            return operation()
        except (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.RemoteProtocolError,
        ) as error:
            if budget.event is not None:
                raise
            if time.monotonic() + 1 >= deadline:
                raise _RejectionError("timeout") from None
            budget.event = (stage, _transport_category(error))
            budget.retry_detail = _transport_detail(error)
            budget.checkpoint(stage)
            time.sleep(1)
            if time.monotonic() >= deadline:
                raise _RejectionError("timeout") from None
            return operation()


@contextmanager
def _at(
    stage: str, *, progress: Callable[[str], None] | None = None
) -> Generator[None]:
    """Classify failures by type/control, never by text or request data."""
    try:
        if progress is not None:
            progress(stage)
        yield
    except QualificationError:
        raise
    except Exception as error:
        if isinstance(error, _RejectionError):
            category = error.category
        elif isinstance(error, (httpx.TimeoutException, TimeoutError)):
            category = "timeout"
        elif isinstance(error, httpx.HTTPError):
            category = _transport_category(error)
        elif isinstance(error, DestinationPolicyError):
            category = "destination-policy"
        elif isinstance(error, (LookupError, TypeError)):
            category = "structure"
        elif isinstance(error, ValueError):
            category = "validation"
        else:
            category = "unexpected"
        raise QualificationError(
            stage, category, transport_detail=_transport_detail(error)
        ) from None


@dataclass(frozen=True)
class PinnedFile:
    """Reviewed file bytes in the already-public immutable archive revision."""

    path: str
    sha256: str
    byte_count: int


MANIFEST = PinnedFile(
    "manifest.json",
    "e6c9abbc62bd44fc47049306a92cc8efc9700031908586262c2b82a907546460",
    7513,
)
RECEIPT = PinnedFile(
    "bronze/2026-04-01/source-receipt.json",
    "a5eb06cf7e655eb0e0d8fe5d244297721ebede51e96c237333f7dffd76e1ccd1",
    3143,
)
ARCHIVE = PinnedFile(
    "raw/2026-04-01/2026-04-01-XML-V3.zip",
    "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20",
    11156706,
)
MEMBER = PinnedFile(
    "bronze/2026-04-01/sch-2026-04-01-r1.xml",
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43",
    313437585,
)
MEMBER_SOURCE_PATH = "sch-2026-04-01-r1.xml"


def file_url(pin: PinnedFile) -> str:
    """Return the immutable public location for a fixed reviewed input."""
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{pin.path}"


def _context(exact_commit: str) -> dict[str, str]:
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": exact_commit,
    }
    if (
        any(os.environ.get(key) != value for key, value in expected.items())
        or re.fullmatch(r"[0-9a-f]{40}", exact_commit) is None
        or re.fullmatch(r"[1-9][0-9]*", os.environ.get("GITHUB_RUN_ID", ""))
        is None
        or re.fullmatch(
            r"[1-9][0-9]*", os.environ.get("GITHUB_RUN_ATTEMPT", "")
        )
        is None
    ):
        raise ValueError(
            "PBS qualification requires exact main Actions context"
        )
    return {
        "workflow_commit": exact_commit,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
    }


def _safe_url(url: str, initial: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username is not None
        or parsed.port not in {None, 443}
        or parsed.fragment
    ):
        raise _RejectionError("destination-policy")
    if parsed.hostname == "huggingface.co":
        initial_path = urlsplit(initial).path
        resolve_prefix = f"/datasets/{DATASET}/resolve/{REVISION}/"
        cache_prefix = f"/api/resolve-cache/datasets/{DATASET}/{REVISION}/"
        cache_paths: set[str] = set()
        if initial_path.startswith(resolve_prefix):
            suffix = initial_path.removeprefix(resolve_prefix)
            cache_paths = {
                cache_prefix + suffix,
                cache_prefix + quote(suffix, safe=""),
            }
        if parsed.path not in {initial_path, *cache_paths}:
            raise _RejectionError("redirect")
        seen: set[str] = set()
        for part in parsed.query.split("&") if parsed.query else ():
            key, separator, value = part.partition("=")
            if key == quote(initial_path, safe=""):
                # Hub GET redirects carry the exact original path as an empty
                # encoded query key. Do not drop it with parse_qs or
                # admit arbitrary decoding, mutable paths or unrelated keys.
                if parsed.path not in cache_paths or value:
                    raise _RejectionError("redirect")
                key = "original-path"
            elif not separator or key not in {"download", "etag"}:
                raise _RejectionError("redirect")
            if key in seen:
                raise _RejectionError("redirect")
            seen.add(key)


def _read(client: httpx.Client, url: str, limit: int, deadline: float) -> bytes:
    initial = url
    for _ in range(4):
        _safe_url(url, initial)
        if time.monotonic() > deadline:
            raise _RejectionError("timeout")
        client.cookies.clear()
        with client.stream("GET", url) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if location is None:
                    raise _RejectionError("redirect")
                url = urljoin(url, location)
                continue
            if response.status_code != HTTPStatus.OK:
                raise _RejectionError("http-status")
            if (
                response.headers.get("content-encoding", "identity")
                != "identity"
            ):
                raise _RejectionError("encoding")
            data = bytearray()
            for chunk in response.iter_bytes(64 * 1024):
                if len(data) + len(chunk) > limit:
                    raise _RejectionError("byte-limit")
                if time.monotonic() > deadline:
                    raise _RejectionError("timeout")
                data.extend(chunk)
            return bytes(data)
    raise _RejectionError("redirect")


def _file(client: httpx.Client, pin: PinnedFile, deadline: float) -> bytes:
    data = _read(client, file_url(pin), pin.byte_count, deadline)
    if (
        len(data) != pin.byte_count
        or hashlib.sha256(data).hexdigest() != pin.sha256
    ):
        raise _RejectionError("pin-mismatch")
    return data


def _public(client: httpx.Client, deadline: float) -> None:
    raw: object = json.loads(_read(client, INFO_URL, 1024 * 1024, deadline))
    if not isinstance(raw, dict):
        raise TypeError("PBS exact public revision required")
    info = cast("dict[str, Any]", raw)
    if (
        info.get("id") != DATASET
        or info.get("sha") != REVISION
        or info.get("private") is not False
        or info.get("gated") is not False
    ):
        raise ValueError("PBS exact public revision required")


def run_hosted_qualification(
    exact_commit: str,
    *,
    transport: httpx.BaseTransport | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Fetch only pinned metadata and ZIP anonymously on exact main Actions.

    Original B1 is restored, never recreated or relabelled. Extracted XML must
    match the existing public member digest/size/path. Reuse bounded DNS-pinned
    transport and permit only observed public Hub/CDN hosts; no implicit tokens,
    cookies, proxies, mutable revisions or unrestricted redirects. The transport
    hook is for synthetic tests; it cannot bypass context/URL/digest validation.
    Return bounded aggregate metadata only, not bytes, sample text or signed URLs.
    This does not publish datasets, select dates or establish semantic admission.
    Optional progress receives incomplete aggregate receipts for an external
    sink; this hook does not bypass source validation or qualify partial work.
    """
    retry = _RetryBudget(progress=progress)
    try:
        return _run(exact_commit, transport=transport, retry=retry)
    except QualificationError as error:
        error.retry_event = retry.event
        error.retry_detail = retry.retry_detail
        raise


def metadata_probe_report(report: dict[str, Any]) -> dict[str, Any]:
    """Scope aggregate diagnostics without carrying corpus qualification data."""
    allowed = (
        "schema_version",
        "workflow_commit",
        "run_id",
        "run_attempt",
        "failure_stage",
        "failure_category",
        "transport_retry",
        "transport_diagnostics",
        "progress",
    )
    status = report.get("status")
    if type(status) is not str or status not in {
        "metadata_verified",
        "failed",
        "incomplete",
    }:
        status = "failed"
    return {
        **{key: report[key] for key in allowed if key in report},
        "status": status,
        "operation": "pbs-public-metadata-diagnostic",
        "dataset": DATASET,
        "revision": REVISION,
        "reason": "metadata-only-no-corpus-qualification",
        "corpus_qualified": False,
        "source_files_read": False,
        "publication_performed": False,
    }


def _metadata_request(request: httpx.Request) -> None:
    """Keep every diagnostic hop on the one immutable metadata endpoint."""
    if request.method != "GET" or str(request.url) != INFO_URL:
        raise _RejectionError("destination-policy")


def run_hosted_metadata_probe(
    exact_commit: str,
    *,
    transport: httpx.BaseTransport | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Check only pinned public Hub metadata in exact main Actions context.

    Reuse the qualifier's transport, visibility, deadline and retry policy,
    then stop before any manifest, B1, ZIP, XML or projection access. Progress
    is explicitly metadata-only; successful connectivity is not qualification.
    """

    def checkpoint(report: dict[str, Any]) -> None:
        if progress is not None:
            progress(metadata_probe_report(report))

    retry = _RetryBudget(progress=checkpoint)
    deadline = time.monotonic() + 300
    try:
        with _at("context", progress=retry.checkpoint):
            context = _context(exact_commit)
        with (
            _at("transport-setup", progress=retry.checkpoint),
            httpx.Client(
                transport=transport
                or BoundIPAddressTransport(
                    policy=AcquisitionPolicy(
                        allowed_hosts=HOSTS, timeout_seconds=30
                    )
                ),
                trust_env=False,
                follow_redirects=False,
                timeout=30,
                headers={"Accept-Encoding": "identity"},
                event_hooks={"request": [_metadata_request]},
            ) as client,
        ):
            _fetch(
                "public-before",
                retry,
                deadline,
                lambda: _public(client, deadline),
            )
    except QualificationError as error:
        error.retry_event = retry.event
        error.retry_detail = retry.retry_detail
        raise
    return metadata_probe_report({
        "schema_version": 1,
        "status": "metadata_verified",
        **context,
        "transport_retry": _retry_record(retry.event),
        "transport_diagnostics": _diagnostics(
            retry.event, retry.retry_detail, None
        ),
    })


def _run(
    exact_commit: str,
    *,
    transport: httpx.BaseTransport | None,
    retry: _RetryBudget,
) -> dict[str, Any]:
    with _at("context", progress=retry.checkpoint):
        context = _context(exact_commit)
    started_at = datetime.now(UTC).isoformat()
    deadline = time.monotonic() + 300
    with _at("transport-setup", progress=retry.checkpoint):
        policy = AcquisitionPolicy(allowed_hosts=HOSTS, timeout_seconds=30)
    with (
        _at("transport-setup", progress=retry.checkpoint),
        httpx.Client(
            transport=transport or BoundIPAddressTransport(policy=policy),
            trust_env=False,
            follow_redirects=False,
            timeout=30,
            headers={"Accept-Encoding": "identity"},
        ) as client,
    ):
        _fetch(
            "public-before", retry, deadline, lambda: _public(client, deadline)
        )
        manifest = _fetch(
            "manifest-read",
            retry,
            deadline,
            lambda: json.loads(_file(client, MANIFEST, deadline)),
        )
        receipt_bytes = _fetch(
            "receipt-read",
            retry,
            deadline,
            lambda: _file(client, RECEIPT, deadline),
        )
        archive = _fetch(
            "archive-read",
            retry,
            deadline,
            lambda: _file(client, ARCHIVE, deadline),
        )
        _fetch(
            "public-after", retry, deadline, lambda: _public(client, deadline)
        )
    with _at("manifest-validation", progress=retry.checkpoint):
        for name, pin in (
            ("archive", ARCHIVE),
            ("member", MEMBER),
            ("source_receipt", RECEIPT),
        ):
            entry = manifest[name]
            if (
                entry["path"] != pin.path
                or entry["sha256"] != pin.sha256
                or (
                    name != "source_receipt"
                    and entry["size_bytes"] != pin.byte_count
                )
            ):
                raise _RejectionError("pin-mismatch")
        if (
            manifest["source_id"] != "au-pbs-historical-xml"
            or manifest["destination_dataset"] != DATASET
            or manifest["member"]["source_path"] != MEMBER_SOURCE_PATH
        ):
            raise _RejectionError("pin-mismatch")
    with _at("receipt-validation", progress=retry.checkpoint):
        parent = SourceReceipt.model_validate_json(receipt_bytes)
    with _at("member-extraction", progress=retry.checkpoint):
        member, xml = read_pbs_v3_member(archive)
        if (
            member.path != MEMBER_SOURCE_PATH
            or member.sha256 != MEMBER.sha256
            or member.size_bytes != MEMBER.byte_count
        ):
            raise _RejectionError("pin-mismatch")
    with _at("member-binding", progress=retry.checkpoint):
        binding = build_pbs_xml_member_binding(archive, parent)
    with _at("projection-qualification", progress=retry.checkpoint):
        qualification = qualify_pbs_historical_projections(
            archive,
            xml,
            parent,
            binding,
            progress=lambda phase, batches, rows: retry.checkpoint(
                "projection-qualification", phase, batches, rows
            ),
        )
    report = {
        "schema_version": 1,
        "status": "passed",
        "transport_retry": _retry_record(retry.event),
        "transport_diagnostics": _diagnostics(
            retry.event, retry.retry_detail, None
        ),
        **context,
        "dataset": DATASET,
        "revision": REVISION,
        "manifest_sha256": MANIFEST.sha256,
        "source_receipt_file_sha256": RECEIPT.sha256,
        "archive_path": ARCHIVE.path,
        "member_path": MEMBER.path,
        "member_retrieval": "extracted-from-verified-archive",
        "anonymous_public_checks": 2,
        "qualification": qualification,
        "publication_performed": False,
        "retrieval_started_at": started_at,
        "qualification_completed_at": datetime.now(UTC).isoformat(),
        "run_url": f"https://github.com/edithatogo/global-medicines-atlas/actions/runs/{context['run_id']}",
        "public_objects": {
            name: asdict(pin)
            for name, pin in (
                ("manifest", MANIFEST),
                ("source_receipt", RECEIPT),
                ("archive", ARCHIVE),
                ("member", MEMBER),
            )
        },
        "source_publication_receipt": "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5466488482",
    }
    with _at("report", progress=retry.checkpoint):
        if len(json.dumps(report, sort_keys=True).encode()) > MAX_REPORT_BYTES:
            raise _RejectionError("byte-limit")
    return report


def failure_report(error: Exception | None = None) -> dict[str, Any]:
    """Return a bounded failure receipt without exception text or unsafe env."""
    context = {}
    for name, key, pattern in (
        ("workflow_commit", "GITHUB_SHA", r"[0-9a-f]{40}"),
        ("run_id", "GITHUB_RUN_ID", r"[1-9][0-9]*"),
        ("run_attempt", "GITHUB_RUN_ATTEMPT", r"[1-9][0-9]*"),
    ):
        value = os.environ.get(key, "")
        context[name] = value if re.fullmatch(pattern, value) else "unavailable"
    # Revalidate codes at the serialization boundary, including tampered objects.
    failure = QualificationError("unavailable", "unavailable")
    if isinstance(error, QualificationError):
        failure = QualificationError(
            error.stage, error.category, transport_detail=error.transport_detail
        )
    return {
        "schema_version": 1,
        "status": "failed",
        **context,
        "dataset": DATASET,
        "revision": REVISION,
        "reason": "qualification-did-not-complete",
        "failure_stage": failure.stage,
        "failure_category": failure.category,
        "transport_diagnostics": _diagnostics(
            error.retry_event
            if isinstance(error, QualificationError)
            else None,
            error.retry_detail
            if isinstance(error, QualificationError)
            else None,
            failure.transport_detail,
        ),
        "transport_retry": _retry_record(error.retry_event)
        if isinstance(error, QualificationError)
        else None,
        "publication_performed": False,
    }
