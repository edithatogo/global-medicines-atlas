"""Configured v1 API and Atlas ASGI entry point for an installed package."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

from .api import create_app as create_api
from .atlas import create_atlas_app
from .query_service import QueryServiceError, ReadOnlyQueryService

MINIMUM_CURSOR_SECRET_BYTES = 16


def create_app(
    *, database_path: str | None = None, cursor_secret: str | None = None
) -> ASGIApp:
    """Serve an explicitly configured existing database without creating data.

    Configuration and schema failures stop startup. This factory provides no
    source rights, deployment approval, live-data or accessibility qualification.
    """
    database = (
        database_path
        if database_path is not None
        else os.environ.get("GMA_DATABASE_PATH", "")
    )
    if not database:
        raise ValueError("GMA_DATABASE_PATH is required")
    secret = (
        cursor_secret
        if cursor_secret is not None
        else os.environ.get("GMA_CURSOR_SECRET", "")
    )
    if not secret.strip() or len(secret.encode()) < MINIMUM_CURSOR_SECRET_BYTES:
        raise ValueError(
            "GMA_CURSOR_SECRET requires at least 16 nonblank bytes"
        )
    try:
        service = ReadOnlyQueryService(database, cursor_secret=secret.encode())
    except OSError, ValueError, QueryServiceError:
        raise ValueError(
            "Configured database is unavailable or incompatible"
        ) from None
    api = create_api(service)
    atlas = create_atlas_app(service)

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        root_path = str(scope.get("root_path", ""))
        if root_path and (
            path == root_path or path.startswith(root_path + "/")
        ):
            path = path[len(root_path) :] or "/"
        target = (
            api
            if scope["type"] != "http"
            or path == "/api"
            or path.startswith("/api/")
            else atlas
        )
        await target(scope, receive, send)

    return application
