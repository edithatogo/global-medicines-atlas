"""Real-browser qualification for the bounded Atlas Gold edge route."""

from __future__ import annotations

import re
import socket
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from threading import Thread
from time import monotonic, sleep
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import uvicorn
from playwright.sync_api import Page, sync_playwright

from .atlas import AtlasQueryService, create_atlas_app

if TYPE_CHECKING:
    import pyarrow as pa
    from starlette.types import ASGIApp

_HTTP_OK = 200


@contextmanager
def _serve_atlas_on_loopback(app: ASGIApp) -> Generator[str]:
    """Serve Atlas on an ephemeral loopback HTTP socket."""
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
        listener.close()
        raise RuntimeError("The Atlas browser server did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        if thread.is_alive():
            raise RuntimeError("The Atlas browser server did not stop")


def _check_page_identity(
    page: Page,
    *,
    edge_count: int,
    offset: int,
    kind: str,
    page_size: int,
) -> None:
    params = parse_qs(urlsplit(page.url).query)
    if int(params.get("offset", ["0"])[0]) != offset:
        raise ValueError("Atlas browser skipped or repeated a page")
    if params.get("kind") != [kind] or params.get("limit") != [str(page_size)]:
        raise ValueError("Atlas browser changed candidate filters")
    heading = page.get_by_role(
        "heading", name=re.compile(rf"^{edge_count} candidate edges?$")
    )
    if heading.count() != 1:
        raise ValueError("Atlas browser omitted the full edge count")


def _read_edge_ids(
    page: Page,
    *,
    edge_count: int,
    offset: int,
    page_size: int,
    bindings: Mapping[str, str],
) -> list[str]:
    body_text = page.locator("body").inner_text()
    if not all(value in body_text for value in bindings.values()):
        raise ValueError("Atlas browser omitted a candidate binding")
    raw_rows = page.locator("article.result-card").evaluate_all(
        """cards => cards.map(card => {
          const fields = {};
          for (const row of card.querySelectorAll(':scope > dl > div')) {
            const name = row.querySelector('dt');
            const value = row.querySelector('dd');
            if (name && value) {
              fields[name.textContent.trim()] = value.textContent.trim();
            }
          }
          return fields;
        })"""
    )
    rows = cast("list[object]", raw_rows)
    if len(rows) != min(page_size, edge_count - offset):
        raise ValueError("Atlas browser rendered an unexpected page size")
    edge_ids: list[str] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise TypeError("Atlas browser rendered an invalid edge row")
        row = cast("dict[str, object]", raw_row)
        edge_id = row.get("Edge identifier")
        if not isinstance(edge_id, str) or not re.fullmatch(
            r"mbs-gold-edge:[0-9a-f]{64}", edge_id
        ):
            raise ValueError("Atlas browser rendered an invalid edge identity")
        if row.get("Review state") != "not_reviewed":
            raise ValueError("Atlas browser changed the candidate review state")
        edge_ids.append(edge_id)
    return edge_ids


def _follow_next_link(
    page: Page,
    *,
    has_more: bool,
    kind: str,
    page_size: int,
    next_offset: int,
) -> None:
    link = page.get_by_role(
        "link", name=re.compile(r"^Next \d+ candidate edges$")
    )
    if not has_more:
        if link.count():
            raise ValueError("Atlas browser rendered an extra continuation")
        return
    if link.count() != 1:
        raise ValueError("Atlas browser omitted the next-page link")
    href = link.get_attribute("href")
    if href is None:
        raise ValueError("Atlas browser next-page link has no target")
    params = parse_qs(urlsplit(urljoin(page.url, href)).query)
    if params.get("kind") != [kind] or params.get("limit") != [str(page_size)]:
        raise ValueError("Atlas browser continuation changed its filters")
    if params.get("offset") != [str(next_offset)]:
        raise ValueError("Atlas browser continuation skipped a page")
    link.click()


def _verify_browser_assets(asset_statuses: Mapping[str, int]) -> None:
    if asset_statuses.get("/static/atlas.css") != _HTTP_OK:
        raise ValueError("Atlas browser stylesheet did not load")


def _verify_loopback_requests(request_hosts: set[str], host: str) -> None:
    if request_hosts != {host}:
        raise ValueError("Atlas browser left the loopback host")


def qualify_candidate_atlas_browser(
    edges: pa.Table,
    kind: str,
    edge_count: int,
    bindings: Mapping[str, str],
    page_size: int,
) -> tuple[list[str], list[int]]:
    """Traverse every candidate page in Chromium and retain IDs in memory."""
    app = create_atlas_app(
        cast("AtlasQueryService", object()), gold_edges=edges
    )
    page_offsets: list[int] = []
    edge_ids: list[str] = []
    asset_statuses: dict[str, int] = {}
    request_hosts: set[str] = set()
    query = urlencode({"kind": kind, "limit": page_size, "offset": 0})
    with _serve_atlas_on_loopback(app) as base_url:
        host = urlsplit(base_url).netloc
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.on(
                    "request",
                    lambda request: request_hosts.add(
                        urlsplit(request.url).netloc
                    ),
                )
                page.on(
                    "response",
                    lambda response: asset_statuses.__setitem__(
                        urlsplit(response.url).path, response.status
                    ),
                )
                response = page.goto(
                    f"{base_url}/gold/edges?{query}",
                    wait_until="domcontentloaded",
                )
                if response is None or response.status != _HTTP_OK:
                    raise ValueError("Atlas browser page was not served")
                for offset in range(0, edge_count, page_size):
                    _check_page_identity(
                        page,
                        edge_count=edge_count,
                        offset=offset,
                        kind=kind,
                        page_size=page_size,
                    )
                    page_ids = _read_edge_ids(
                        page,
                        edge_count=edge_count,
                        offset=offset,
                        page_size=page_size,
                        bindings=bindings,
                    )
                    edge_ids.extend(page_ids)
                    page_offsets.append(offset)
                    _follow_next_link(
                        page,
                        has_more=offset + len(page_ids) < edge_count,
                        kind=kind,
                        page_size=page_size,
                        next_offset=offset + len(page_ids),
                    )
                _verify_browser_assets(asset_statuses)
                _verify_loopback_requests(request_hosts, host)
            finally:
                browser.close()
    return edge_ids, page_offsets
