"""Content-addressed evidence for bounded read-only API observations.

The envelope records the request and response identity only.  It deliberately
does not retain response rows or source payloads, so it can safely accompany a
public federated product while the payload remains in its governed dataset.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_METHOD = Literal["GET", "HEAD"]
_HTTP_STATUS_MIN = 100
_HTTP_STATUS_MAX = 599
_MAX_REQUEST_ID_LENGTH = 128


class ApiContractError(ValueError):
    """Raised when an API observation is not a bounded read-only contract."""


@dataclass(frozen=True)
class ApiObservation:
    """Exact request/response identity without embedding response content."""

    method: _METHOD
    path: str
    query_sha256: str
    response_sha256: str
    status_code: int
    request_id: str

    @property
    def canonical_bytes(self) -> bytes:
        """Return deterministic metadata suitable for a receipt or manifest."""
        return json.dumps(
            {
                "method": self.method,
                "path": self.path,
                "query_sha256": self.query_sha256,
                "request_id": self.request_id,
                "response_sha256": self.response_sha256,
                "status_code": self.status_code,
                "version": "1.0",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    @property
    def observation_sha256(self) -> str:
        """Return the content address of this exact observation."""
        return hashlib.sha256(self.canonical_bytes).hexdigest()


def make_api_observation(
    *,
    method: str,
    path: str,
    canonical_query: bytes,
    response_bytes: bytes,
    status_code: int,
    request_id: str,
) -> ApiObservation:
    """Validate and bind one bounded read-only API observation.

    Only digests of query and response bytes are retained.  The method and
    path checks prevent mutation operations and accidental absolute URLs from
    becoming part of the federated public contract.
    """
    if method not in {"GET", "HEAD"}:
        raise ApiContractError("only GET and HEAD observations are permitted")
    if not path.startswith("/api/v1/") or "?" in path or "#" in path:
        raise ApiContractError("path must be a relative versioned API path")
    if type(status_code) is not int or not _HTTP_STATUS_MIN <= status_code <= _HTTP_STATUS_MAX:
        raise ApiContractError("status code is invalid")
    if (
        not request_id
        or len(request_id) > _MAX_REQUEST_ID_LENGTH
        or not request_id.isascii()
    ):
        raise ApiContractError("request id is invalid")
    query_sha256 = hashlib.sha256(canonical_query).hexdigest()
    response_sha256 = hashlib.sha256(response_bytes).hexdigest()
    if not _DIGEST.fullmatch(query_sha256) or not _DIGEST.fullmatch(
        response_sha256
    ):
        raise ApiContractError("observation digest is invalid")
    return ApiObservation(
        method=method,  # type: ignore[arg-type]
        path=path,
        query_sha256=query_sha256,
        response_sha256=response_sha256,
        status_code=status_code,
        request_id=request_id,
    )


__all__ = ["ApiContractError", "ApiObservation", "make_api_observation"]
