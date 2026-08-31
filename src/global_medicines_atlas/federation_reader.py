"""Anonymous immutable-object reader, not a rights or receipt admission engine.

The caller's admitted contract digests must come from independent authority,
receipt and lineage verification. Schema-valid claims alone are never admitted.
Only synthetic test transports are exercised locally during qualification.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import tempfile
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, BinaryIO, Literal, Self, cast
from urllib.parse import urljoin, urlsplit

import httpx
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from .acquisition import AcquisitionPolicy, BoundIPAddressTransport
from .federation import validate_federation_semantics

SCHEMA_SHA256 = (
    "ac28485a70e0853266e4c140f9a07cd557eb27816b0b408b9bf2927a4cffacec"
)
HUB = "https://huggingface.co"
HOSTS = (
    "huggingface.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.hf.co",
    "cdn-lfs-eu-1.hf.co",
    "cas-bridge.xethub.hf.co",
    "us.aws.cdn.hf.co",
)
CHUNK_BYTES = 64 * 1024
METADATA_BYTES = 1024 * 1024


@dataclass(frozen=True)
class VerifiedRead:
    """A seekable, context-owned stream; no bytes escape before verification."""

    stream: BinaryIO
    origin: Literal["remote", "verified_cache"]
    contract_sha256: str
    sha256: str
    byte_count: int


@dataclass
class _Cached:
    stream: BinaryIO
    size: int
    expires_at: datetime
    owner: ExitStack


class FederatedReader:
    """Read admitted v4 identities with bounded spool files and explicit offline use.

    Cache storage is private to this reader, unnamed where supported, and
    removed on eviction/close. Active results are separate context-owned files.
    The finite storage bound is cache_bytes + max_open_reads * max_object_bytes.
    Caller admission is an explicit trust boundary, not inferred from JSON.
    """

    def __init__(
        self,
        *,
        schema: bytes,
        admitted_contracts: frozenset[str],
        max_object_bytes: int = 1024 * 1024 * 1024,
        cache_bytes: int = 64 * 1024 * 1024,
        max_entries: int = 32,
        max_open_reads: int = 2,
        timeout_seconds: float = 30,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        transport_factory: Callable[[], httpx.BaseTransport] | None = None,
    ) -> None:
        if hashlib.sha256(schema).hexdigest() != SCHEMA_SHA256:
            raise ValueError("federation schema digest mismatch")
        for value in (
            max_object_bytes,
            cache_bytes,
            max_entries,
            max_open_reads,
        ):
            if type(value) is not int or value <= 0:
                raise ValueError("reader budgets must be positive integers")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("reader timeout must be finite and positive")
        if any(
            re.fullmatch(r"[0-9a-f]{64}", pin) is None
            for pin in admitted_contracts
        ):
            raise ValueError("invalid admitted contract digest")
        formats = FormatChecker()
        if not {"date", "date-time", "uri"} <= formats.checkers.keys():
            raise ValueError(
                "required federation format validators are missing"
            )
        self._validator = Draft202012Validator(
            json.loads(schema), format_checker=formats
        )
        self._admitted = frozenset(admitted_contracts)
        self._max_object = max_object_bytes
        self._cache_budget = cache_bytes
        self._max_entries = max_entries
        self._timeout = timeout_seconds
        self._clock = clock
        self._factory = transport_factory
        self._cache: OrderedDict[str, _Cached] = OrderedDict()
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(max_open_reads)
        self._closed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @property
    def cached_bytes(self) -> int:
        """Return the current cache occupancy, excluding active result files."""
        with self._lock:
            self._purge_expired()
            return sum(item.size for item in self._cache.values())

    def _purge_expired(self) -> None:
        now = self._clock()
        expired = [
            key for key, item in self._cache.items() if item.expires_at <= now
        ]
        for key in expired:
            self._cache.pop(key).owner.close()

    def _evict(self) -> None:
        for item in self._cache.values():
            item.owner.close()
        self._cache.clear()

    def evict(self) -> None:
        """Remove this reader's verified temporary copies, never remote objects."""
        with self._lock:
            self._evict()

    def close(self) -> None:
        """Close the cache; outstanding result contexts retain their own lifetime."""
        with self._lock:
            self._evict()
            self._closed = True

    def _document(self, raw: bytes) -> tuple[str, dict[str, Any]]:
        if len(raw) > METADATA_BYTES:
            raise ValueError("contract exceeds metadata budget")
        digest = hashlib.sha256(raw).hexdigest()
        if digest not in self._admitted:
            raise ValueError("contract is not independently admitted")
        try:
            document: dict[str, Any] = json.loads(raw)
            validator = cast("Any", self._validator)
            validator.validate(document)
            validate_federation_semantics(document)
        except ValueError, TypeError, KeyError, ValidationError:
            raise ValueError("invalid federation contract") from None
        if document["authority"]["schema_sha256"] != SCHEMA_SHA256:
            raise ValueError("invalid federation contract schema pin")
        self._source_origin(document)
        if document["location"]["bytes"] > min(
            self._max_object, document["cache"]["max_bytes"]
        ):
            raise ValueError("object exceeds admitted reader budget")
        return digest, document

    @staticmethod
    def _source_origin(document: dict[str, Any]) -> None:
        if (
            document["evidence_kind"] != "live"
            or document["source"]["representation"] != "raw"
        ):
            return
        if (
            os.environ.get("GITHUB_ACTIONS") != "true"
            or re.fullmatch(r"[1-9][0-9]*", os.environ.get("GITHUB_RUN_ID", ""))
            is None
            or re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", ""))
            is None
        ):
            raise ValueError("live raw source reads require GitHub Actions")

    @staticmethod
    def _url(url: str) -> None:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in HOSTS
            or parsed.username is not None
            or parsed.port not in {None, 443}
            or parsed.fragment
        ):
            raise ValueError("unapproved anonymous HTTP destination")

    def _download(self, url: str, target: BinaryIO, limit: int) -> None:
        policy = AcquisitionPolicy(
            allowed_hosts=HOSTS, timeout_seconds=self._timeout
        )
        transport = (
            self._factory()
            if self._factory
            else BoundIPAddressTransport(policy=policy)
        )
        deadline = time.monotonic() + self._timeout
        with httpx.Client(
            transport=transport,
            trust_env=False,
            timeout=self._timeout,
            follow_redirects=False,
            headers={"Accept-Encoding": "identity"},
        ) as client:
            try:
                self._request(client, url, target, limit, deadline)
            except httpx.HTTPError:
                raise ValueError("anonymous HTTP transport failed") from None

    def _request(
        self,
        client: httpx.Client,
        url: str,
        target: BinaryIO,
        limit: int,
        deadline: float,
    ) -> None:
        for _attempt in range(4):
            self._url(url)
            if time.monotonic() > deadline:
                raise ValueError("HTTP retrieval deadline exceeded")
            client.cookies.clear()
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if location is None:
                        raise ValueError("HTTP redirect missing location")
                    url = urljoin(url, location)
                    continue
                self._response(response, target, limit, deadline)
                return
        raise ValueError("HTTP redirect limit exceeded")

    @staticmethod
    def _response(
        response: httpx.Response,
        target: BinaryIO,
        limit: int,
        deadline: float,
    ) -> None:
        if response.status_code != HTTPStatus.OK:
            raise ValueError("anonymous HTTP retrieval failed")
        if response.headers.get("content-encoding", "identity") != "identity":
            raise ValueError("HTTP content encoding is not identity")
        size = 0
        for chunk in response.iter_bytes(CHUNK_BYTES):
            size += len(chunk)
            if size > limit:
                raise ValueError("remote size exceeds budget")
            if time.monotonic() > deadline:
                raise ValueError("HTTP retrieval deadline exceeded")
            target.write(chunk)
        target.seek(0)

    def _remote(self, document: dict[str, Any], output: BinaryIO) -> None:
        location = document["location"]
        dataset, revision = location["dataset"], location["revision"]
        with tempfile.TemporaryFile("w+b") as metadata:
            self._download(
                f"{HUB}/api/datasets/{dataset}/revision/{revision}",
                metadata,
                METADATA_BYTES,
            )
            raw_state: object = json.load(metadata)
        if not isinstance(raw_state, dict):
            raise TypeError("public dataset metadata must be an object")
        state = cast("dict[str, object]", raw_state)
        if (
            state.get("private") is not False
            or state.get("gated") is not False
            or state.get("sha") != revision
        ):
            raise ValueError(
                "exact dataset revision is not public and non-gated"
            )
        self._download(
            f"{HUB}/datasets/{dataset}/resolve/{revision}/{location['path']}",
            output,
            location["bytes"],
        )

    @staticmethod
    def _verify(stream: BinaryIO, location: dict[str, Any]) -> None:
        stream.seek(0)
        digest = hashlib.sha256()
        size = 0
        while chunk := stream.read(CHUNK_BYTES):
            size += len(chunk)
            digest.update(chunk)
        if (
            size != location["bytes"]
            or digest.hexdigest() != location["sha256"]
        ):
            raise ValueError("object size or digest mismatch")
        stream.seek(0)

    @staticmethod
    def _copy(source: BinaryIO, target: BinaryIO) -> None:
        source.seek(0)
        while chunk := source.read(CHUNK_BYTES):
            target.write(chunk)
        source.seek(0)
        target.seek(0)

    def _retain(
        self, key: str, output: BinaryIO, document: dict[str, Any]
    ) -> None:
        size = document["location"]["bytes"]
        expiry = datetime.fromisoformat(document["cache"]["expires_at"])
        if size > self._cache_budget or expiry <= self._clock():
            return
        if key in self._cache:
            self._cache.pop(key).owner.close()
        while self._cache and (
            sum(item.size for item in self._cache.values()) + size
            > self._cache_budget
            or len(self._cache) >= self._max_entries
        ):
            self._cache.popitem(last=False)[1].owner.close()
        with ExitStack() as owner:
            cached = owner.enter_context(tempfile.TemporaryFile("w+b"))
            self._copy(output, cached)
            self._cache[key] = _Cached(cached, size, expiry, owner.pop_all())

    @contextmanager
    def open(
        self, raw: bytes, *, offline: bool = False
    ) -> Generator[VerifiedRead]:
        """Yield exact verified bytes; online errors never silently select a cache."""
        if not self._slots.acquire(blocking=False):
            raise ValueError("reader open-result budget exceeded")
        try:
            with tempfile.TemporaryFile("w+b") as output:
                with self._lock:
                    if self._closed:
                        raise ValueError("reader is closed")
                    self._purge_expired()
                    key, document = self._document(raw)
                    origin: Literal["remote", "verified_cache"] = "remote"
                    if offline:
                        cached = self._cache.get(key)
                        if (
                            document["cache"]["offline_behavior"]
                            != "verified_exact_digest_only"
                            or cached is None
                            or cached.expires_at <= self._clock()
                        ):
                            raise ValueError(
                                "offline exact verified cache unavailable"
                            )
                        self._copy(cached.stream, output)
                        self._cache.move_to_end(key)
                        origin = "verified_cache"
                    else:
                        self._remote(document, output)
                    self._verify(output, document["location"])
                    if not offline:
                        self._retain(key, output, document)
                with io.BufferedReader(output) as readonly:
                    yield VerifiedRead(
                        readonly,
                        origin,
                        key,
                        document["location"]["sha256"],
                        document["location"]["bytes"],
                    )
        finally:
            self._slots.release()
