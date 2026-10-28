"""Test helpers for serving an ASGI application on loopback."""

from __future__ import annotations

import socket
from collections.abc import Generator
from contextlib import contextmanager
from threading import Thread
from time import monotonic, sleep
from typing import TYPE_CHECKING

import uvicorn

if TYPE_CHECKING:
    from starlette.types import ASGIApp


@contextmanager
def serve_asgi_on_loopback(app: ASGIApp) -> Generator[str]:
    """Serve an ASGI app on an ephemeral loopback port for the context."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            lifespan="off",
            access_log=False,
            log_level="error",
        )
    )
    thread = Thread(
        target=server.run,
        kwargs={"sockets": [listener]},
        daemon=True,
    )
    thread.start()
    deadline = monotonic() + 10
    while not server.started and thread.is_alive() and monotonic() < deadline:
        sleep(0.01)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        if thread.is_alive():
            listener.close()
            raise RuntimeError(
                "The ASGI server did not start and shutdown timed out"
            )
        listener.close()
        raise RuntimeError("The ASGI server did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("The ASGI server did not stop")
        listener.close()
