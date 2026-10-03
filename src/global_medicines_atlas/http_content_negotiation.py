"""Small HTTP Accept negotiation helpers for JSON-only APIs."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from starlette.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.requests import Request

_QUALITY = re.compile(r"^(?:0(?:\.\d{0,3})?|1(?:\.0{0,3})?)$")
_SPECIFICITY = {"*/*": 0, "application/*": 1, "application/json": 2}


def _quality(parts: list[str]) -> float | None:
    quality = 1.0
    seen = False
    for parameter in parts[1:]:
        name, separator, raw_value = parameter.partition("=")
        if not separator:
            return None
        if name.strip().lower() != "q":
            continue
        if seen:
            return None
        seen = True
        token = raw_value.strip()
        if not _QUALITY.fullmatch(token):
            return None
        quality = float(token)
    return quality


def accepts_json(accept_header: str | None) -> bool:
    """Return whether the most-specific Accept range permits JSON."""
    if accept_header is None or not accept_header.strip():
        return True

    best_specificity = -1
    best_quality = 0.0
    for value in accept_header.split(","):
        parts = [part.strip() for part in value.split(";")]
        specificity = _SPECIFICITY.get(parts[0].lower())
        if specificity is None:
            continue
        quality = _quality(parts)
        if quality is None:
            continue

        if specificity > best_specificity:
            best_specificity = specificity
            best_quality = quality
        elif specificity == best_specificity:
            best_quality = max(best_quality, quality)

    return best_specificity >= 0 and best_quality > 0


def install_json_accept_negotiation(
    app: FastAPI,
    *,
    api_base_path: str,
) -> None:
    """Reject API requests that cannot accept its sole JSON representation."""

    docs_path = f"{api_base_path}/docs"

    async def require_acceptable_json(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        is_api_path = path == api_base_path or path.startswith(
            f"{api_base_path}/"
        )
        is_docs_path = path == docs_path or path.startswith(f"{docs_path}/")
        if (
            is_api_path
            and not is_docs_path
            and not accepts_json(request.headers.get("accept"))
        ):
            return Response(
                status_code=406,
                headers={"cache-control": "no-store", "vary": "Accept"},
            )
        return await call_next(request)

    app.middleware("http")(require_acceptable_json)
