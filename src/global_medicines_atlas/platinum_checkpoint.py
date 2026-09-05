"""Fail-closed Phase 1 transport preflight without product admission.

This module can prove that one exact bounded public Parquet object is
anonymously readable and structurally queryable. It deliberately cannot admit
that Bronze projection as a Platinum product or complete the Phase 1 gate.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import queue
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import quote, urljoin, urlsplit

import pyarrow as pa
import pyarrow.parquet as pq

if TYPE_CHECKING:
    import httpx

_DATASET = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_REVISION = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_MAX_METADATA_BYTES = 1024 * 1024
_REQUIRED_QUERY_COLUMNS = ("source_record_id", "source_ordinal")
_REASONS = (
    "independently admitted v4 product contract is absent",
    "independently admitted semantic manifest is absent",
    "Australian benefits medallion dataset is not yet published",
)
_HUB = "https://huggingface.co"
_HOSTS = frozenset({
    "huggingface.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.hf.co",
    "cdn-lfs-eu-1.hf.co",
    "cas-bridge.xethub.hf.co",
    "us.aws.cdn.hf.co",
})


@dataclass(frozen=True)
class PublicFixturePin:
    """Exact bounded identity and structural denominator for one fixture."""

    dataset: str
    revision: str
    path: str
    sha256: str
    byte_count: int
    row_count: int
    columns: tuple[str, ...]
    max_bytes: int
    sample_rows: int

    def __post_init__(self) -> None:
        valid_path = (
            type(self.path) is str
            and self.path
            and not self.path.startswith("/")
            and ".." not in self.path.split("/")
            and self.path.endswith(".parquet")
        )
        valid_numbers = all(
            type(value) is int and value > 0
            for value in (self.byte_count, self.row_count, self.max_bytes)
        )
        valid_sample = (
            type(self.sample_rows) is int
            and 0 < self.sample_rows <= self.row_count
        )
        valid_columns = (
            bool(self.columns)
            and len(set(self.columns)) == len(self.columns)
            and all(type(item) is str and item for item in self.columns)
            and set(_REQUIRED_QUERY_COLUMNS) <= set(self.columns)
        )
        if not all((
            type(self.dataset) is str
            and _DATASET.fullmatch(self.dataset) is not None,
            type(self.revision) is str
            and _REVISION.fullmatch(self.revision) is not None,
            valid_path,
            type(self.sha256) is str
            and _SHA256.fullmatch(self.sha256) is not None,
            valid_numbers,
            self.byte_count <= self.max_bytes,
            valid_sample,
            valid_columns,
        )):
            raise ValueError("invalid public fixture pin")


MBS_PUBLIC_FIXTURE = PublicFixturePin(
    dataset="edithatogo/australian-mbs-source-archive",
    revision="75f9f20a36ddb829dfe0ca88660664570782be02",
    path=(
        "bronze/mbs/releases/2026-08-01/"
        "99fada49ebf8e71e8e14417e9275f36840d46577a39746fea02bd89de30a30fc/"
        "p7.parquet"
    ),
    sha256="6362f7f3a5d9870545cc074450b81a82475d68fdb062f38083713f56bd88d2fe",
    byte_count=24_367,
    row_count=165,
    columns=("source_record_id", "source_ordinal", "fields"),
    max_bytes=64 * 1024,
    sample_rows=5,
)


@dataclass(frozen=True)
class CheckpointPreflight:
    """Transport evidence whose admission and checkpoint states stay false."""

    dataset: str
    revision: str
    path: str
    object_sha256: str
    byte_count: int
    metadata_sha256: str
    row_count: int
    columns: tuple[str, ...]
    sample_row_count: int
    sample_sha256: str
    canonical_sample_rows: bytes
    observed_at: str
    layer: Literal["bronze"] = "bronze"
    representation: Literal["projection"] = "projection"
    transport_verified: Literal[True] = True
    product_admitted: Literal[False] = False
    checkpoint_complete: Literal[False] = False
    reasons: tuple[str, ...] = _REASONS

    @property
    def canonical_bytes(self) -> bytes:
        """Encode safe transport evidence without embedding sampled rows."""
        return json.dumps(
            {
                "byte_count": self.byte_count,
                "checkpoint_complete": self.checkpoint_complete,
                "columns": self.columns,
                "dataset": self.dataset,
                "layer": self.layer,
                "metadata_sha256": self.metadata_sha256,
                "object_sha256": self.object_sha256,
                "observed_at": self.observed_at,
                "path": self.path,
                "product_admitted": self.product_admitted,
                "reasons": self.reasons,
                "representation": self.representation,
                "revision": self.revision,
                "row_count": self.row_count,
                "sample_row_count": self.sample_row_count,
                "sample_sha256": self.sample_sha256,
                "transport_verified": self.transport_verified,
                "version": "1.1",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    @property
    def receipt_sha256(self) -> str:
        """Return the content address of the preflight observation."""
        return hashlib.sha256(self.canonical_bytes).hexdigest()


def observe_unadmitted_public_fixture(
    pin: PublicFixturePin,
    metadata_bytes: bytes,
    payload_bytes: bytes,
    *,
    observed_at: datetime | None = None,
) -> CheckpointPreflight:
    """Verify exact public transport while refusing product admission."""
    if not metadata_bytes or len(metadata_bytes) > _MAX_METADATA_BYTES:
        raise ValueError("public fixture metadata exceeds budget")
    try:
        metadata: object = json.loads(metadata_bytes)
    except json.JSONDecodeError:
        raise ValueError("public fixture metadata is invalid") from None
    if not isinstance(metadata, dict):
        raise TypeError("public fixture metadata identity is invalid")
    metadata = cast("dict[str, object]", metadata)
    if (
        metadata.get("sha") != pin.revision
        or metadata.get("private") is not False
        or metadata.get("gated") is not False
    ):
        raise ValueError("public fixture metadata identity is invalid")
    if len(payload_bytes) > pin.max_bytes:
        raise ValueError("public fixture payload exceeds budget")
    if (
        len(payload_bytes) != pin.byte_count
        or hashlib.sha256(payload_bytes).hexdigest() != pin.sha256
    ):
        raise ValueError("public fixture payload identity is invalid")
    try:
        parquet = pq.ParquetFile(io.BytesIO(payload_bytes))
        observed_columns = tuple(parquet.schema_arrow.names)
        observed_rows = parquet.metadata.num_rows
        parquet_reader = cast("Any", parquet)
        sample: pa.Table = parquet_reader.read(
            columns=list(_REQUIRED_QUERY_COLUMNS)
        ).slice(0, pin.sample_rows)
    except OSError, pa.ArrowInvalid:
        raise ValueError("public fixture Parquet is invalid") from None
    if observed_columns != pin.columns:
        raise ValueError("public fixture columns changed")
    if observed_rows != pin.row_count:
        raise ValueError("public fixture row count changed")
    canonical_sample = json.dumps(
        sample.to_pylist(),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    observation_time = observed_at or datetime.now(UTC)
    if observation_time.tzinfo is None:
        raise ValueError("observation time must include a timezone")
    return CheckpointPreflight(
        dataset=pin.dataset,
        revision=pin.revision,
        path=pin.path,
        object_sha256=pin.sha256,
        byte_count=pin.byte_count,
        metadata_sha256=hashlib.sha256(metadata_bytes).hexdigest(),
        row_count=observed_rows,
        columns=observed_columns,
        sample_row_count=sample.num_rows,
        sample_sha256=hashlib.sha256(canonical_sample).hexdigest(),
        canonical_sample_rows=canonical_sample,
        observed_at=observation_time.astimezone(UTC).isoformat(),
    )


def _safe_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _HOSTS
        or parsed.username is not None
        or parsed.port not in {None, 443}
        or parsed.fragment
    ):
        raise ValueError("unapproved anonymous HTTP destination")


def _download(
    client: httpx.Client, url: str, *, limit: int, deadline: float
) -> bytes:
    for _attempt in range(4):
        _safe_url(url)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("HTTP retrieval deadline exceeded")
        client.cookies.clear()
        with client.stream("GET", url, timeout=remaining) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if location is None:
                    raise ValueError("HTTP redirect missing location")
                url = urljoin(url, location)
                continue
            if response.status_code != HTTPStatus.OK:
                raise ValueError("anonymous HTTP retrieval failed")
            if (
                response.headers.get("content-encoding", "identity")
                != "identity"
            ):
                raise ValueError("HTTP content encoding is not identity")
            return _read_until_deadline(
                response, limit=limit, deadline=deadline
            )
    raise ValueError("HTTP redirect limit exceeded")


def _read_until_deadline(
    response: httpx.Response, *, limit: int, deadline: float
) -> bytes:
    """Consume until deadline, cancelling queue delivery on every exit.

    Closing the response requests transport cleanup. A transport that ignores
    close may still block its daemon read, but no abandoned queue put persists
    after that read returns.
    """
    events: queue.Queue[tuple[bytes | None, Exception | None]] = queue.Queue(1)
    cancelled = threading.Event()

    def emit(event: tuple[bytes | None, Exception | None]) -> bool:
        while not cancelled.is_set():
            try:
                events.put(event, timeout=0.01)
            except queue.Full:
                continue
            return True
        return False

    def produce() -> None:
        try:
            for chunk in response.iter_bytes(64 * 1024):
                if not emit((chunk, None)):
                    return
            emit((None, None))
        except Exception as error:  # pragma: no cover - transport-specific
            emit((None, error))

    threading.Thread(target=produce, daemon=True).start()
    chunks: list[bytes] = []
    size = 0
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("HTTP retrieval deadline exceeded")
            try:
                chunk, error = events.get(timeout=remaining)
            except queue.Empty:
                raise ValueError("HTTP retrieval deadline exceeded") from None
            if error is not None:
                raise error
            if chunk is None:
                return b"".join(chunks)
            size += len(chunk)
            if size > limit:
                raise ValueError("remote size exceeds budget")
            chunks.append(chunk)
    finally:
        cancelled.set()
        response.close()


def _require_anonymous_client(client: httpx.Client) -> None:
    """Reject state that can add credentials to the preflight requests."""
    credential_headers = {"authorization", "cookie", "proxy-authorization"}
    credential_state = (
        client.auth is not None
        or len(client.cookies) > 0
        or credential_headers.intersection(client.headers.keys())
        or client.event_hooks.get("request")
        or client.event_hooks.get("response")
    )
    unsafe_defaults = bool(client.params) or client.follow_redirects
    if credential_state or unsafe_defaults:
        raise ValueError(
            "anonymous client must not carry credentials, hooks, parameters, "
            "or automatic redirects"
        )


def fetch_unadmitted_public_fixture(
    pin: PublicFixturePin,
    client: httpx.Client,
    *,
    timeout_seconds: float = 30,
) -> CheckpointPreflight:
    """Fetch an exact anonymous fixture and return its unadmitted preflight."""
    if (
        type(timeout_seconds) not in {int, float}
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout must be finite positive seconds")
    _require_anonymous_client(client)
    deadline = time.monotonic() + timeout_seconds
    metadata = _download(
        client,
        f"{_HUB}/api/datasets/{pin.dataset}/revision/{pin.revision}",
        limit=_MAX_METADATA_BYTES,
        deadline=deadline,
    )
    encoded_path = quote(pin.path, safe="/")
    payload = _download(
        client,
        f"{_HUB}/datasets/{pin.dataset}/resolve/{pin.revision}/{encoded_path}",
        limit=pin.max_bytes,
        deadline=deadline,
    )
    return observe_unadmitted_public_fixture(pin, metadata, payload)
