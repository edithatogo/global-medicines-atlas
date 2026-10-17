"""Aggregate-only qualification of bounded MBS Gold edge consumers."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from .api import create_app
from .atlas import AtlasQueryService, create_atlas_app
from .cli import app as cli_app
from .platinum_edge_configuration import load_gold_edges
from .platinum_edges import MAX_EDGE_ROWS
from .query_service import ReadOnlyQueryService

if TYPE_CHECKING:
    import pyarrow as pa

_BINDING_KEYS = {
    "input_admission_sha256": b"input_admission_sha256",
    "input_semantic_manifest_sha256": b"input_semantic_manifest_sha256",
    "graph_sha256": b"graph_sha256",
}
_HTTP_OK = 200


class _AtlasPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.edge_ids: list[str] = []
        self.next_hrefs: list[str] = []
        self._dt = False
        self._dt_text: list[str] = []
        self._edge_dd = False
        self._code = False
        self._code_text: list[str] = []
        self._anchor: str | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "dt":
            self._dt = True
            self._dt_text = []
        elif tag == "dd" and "Edge identifier" in "".join(self._dt_text):
            self._edge_dd = True
        elif tag == "code" and self._edge_dd:
            self._code = True
            self._code_text = []
        elif tag == "a":
            self._anchor = attributes.get("href")
            self._anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "dt":
            self._dt = False
        elif tag == "code" and self._code:
            self._code = False
        elif tag == "dd" and self._edge_dd:
            value = "".join(self._code_text).strip()
            if value:
                self.edge_ids.append(value)
            self._edge_dd = False
        elif tag == "a":
            if self._anchor is not None and "".join(
                self._anchor_text
            ).startswith("Next "):
                self.next_hrefs.append(self._anchor)
            self._anchor = None

    def handle_data(self, data: str) -> None:
        if self._dt:
            self._dt_text.append(data)
        if self._code:
            self._code_text.append(data)
        if self._anchor is not None:
            self._anchor_text.append(data)


class _TestResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> object: ...


class _TestClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> _TestResponse: ...


def _mapping(value: object, message: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise TypeError(message)
    return cast("Mapping[str, object]", value)


def _bindings(
    edges: pa.Table,
    qualification: Mapping[str, object],
    expected: Mapping[str, str] | None,
) -> dict[str, str]:
    metadata = edges.schema.metadata or {}
    values = {
        name: metadata[key].decode() for name, key in _BINDING_KEYS.items()
    }
    graph = _mapping(
        qualification.get("graph"), "qualification graph is missing"
    )
    if graph.get("graph_sha256") != values["graph_sha256"]:
        raise ValueError("candidate graph digest differs from qualification")
    if expected is not None and values != dict(expected):
        raise ValueError(
            "candidate admission bindings differ from expected inputs"
        )
    if any(
        not re.fullmatch(r"[0-9a-f]{64}", value) for value in values.values()
    ):
        raise ValueError("candidate admission binding is malformed")
    if metadata.get(b"qualification") != b"admitted_real_silver_candidate_only":
        raise ValueError("edge file is not the admitted real candidate")
    return values


def _page_ids(
    payload: Mapping[str, object],
    *,
    offset: int,
    edge_count: int,
    bindings: Mapping[str, str],
    page_size: int,
) -> list[str]:
    if payload.get("qualification") != "admitted_real_silver_candidate_only":
        raise ValueError("consumer returned a non-candidate qualification")
    if payload.get("admission_bindings") != dict(bindings):
        raise ValueError("consumer changed admission or graph bindings")
    if payload.get("total") != edge_count or payload.get("offset") != offset:
        raise ValueError("consumer page total or offset differs")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise TypeError("consumer edge page is invalid")
    items = cast("list[object]", raw_items)
    expected_size = min(page_size, max(0, edge_count - offset))
    if len(items) != expected_size:
        raise ValueError("consumer returned an unexpected page size")
    edge_ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("consumer edge row is invalid")
        edge = cast("Mapping[str, object]", item)
        edge_id = edge.get("edge_id")
        if not isinstance(edge_id, str) or not re.fullmatch(
            r"mbs-gold-edge:[0-9a-f]{64}", edge_id
        ):
            raise ValueError("consumer edge identity is invalid")
        controls = edge.get("controls")
        review_state = edge.get("review_state")
        if review_state is None and isinstance(controls, dict):
            review_state = cast("Mapping[str, object]", controls).get(
                "review_state"
            )
        if review_state != "not_reviewed":
            raise ValueError("candidate edge review state changed")
        edge_ids.append(edge_id)
    if payload.get("has_more") is not (offset + len(edge_ids) < edge_count):
        raise ValueError("consumer continuation state is inconsistent")
    return edge_ids


def _api_ids(
    edges: pa.Table,
    kind: str,
    edge_count: int,
    bindings: Mapping[str, str],
    page_size: int,
) -> list[str]:
    client = cast(
        "_TestClient",
        TestClient(
            create_app(cast("ReadOnlyQueryService", object()), gold_edges=edges)
        ),
    )
    edge_ids: list[str] = []
    for offset in range(0, edge_count, page_size):
        response = client.get(
            "/api/v1/edges",
            params={"kind": kind, "limit": page_size, "offset": offset},
        )
        if response.status_code != _HTTP_OK:
            raise ValueError("API consumer rejected the candidate page")
        edge_ids.extend(
            _page_ids(
                _mapping(response.json(), "API edge page is invalid"),
                offset=offset,
                edge_count=edge_count,
                bindings=bindings,
                page_size=page_size,
            )
        )
    return edge_ids


def _cli_ids(
    edge_path: Path,
    kind: str,
    edge_count: int,
    bindings: Mapping[str, str],
    page_size: int,
) -> list[str]:
    runner = CliRunner()
    edge_ids: list[str] = []
    for offset in range(0, edge_count, page_size):
        result = runner.invoke(
            cli_app,
            [
                "edges",
                "--edge-file",
                str(edge_path),
                "--kind",
                kind,
                "--limit",
                str(page_size),
                "--offset",
                str(offset),
            ],
        )
        if result.exit_code != 0:
            raise ValueError("CLI consumer rejected the candidate page")
        edge_ids.extend(
            _page_ids(
                _mapping(json.loads(result.stdout), "CLI edge page is invalid"),
                offset=offset,
                edge_count=edge_count,
                bindings=bindings,
                page_size=page_size,
            )
        )
    return edge_ids


def _atlas_ids(
    edges: pa.Table,
    kind: str,
    edge_count: int,
    bindings: Mapping[str, str],
    page_size: int,
) -> tuple[list[str], list[int]]:
    client = cast(
        "_TestClient",
        TestClient(
            create_atlas_app(
                cast("AtlasQueryService", object()), gold_edges=edges
            )
        ),
    )
    href = f"/gold/edges?kind={kind}&limit={page_size}&offset=0"
    edge_ids: list[str] = []
    offsets: list[int] = []
    for expected_offset in range(0, edge_count, page_size):
        parsed = urlsplit(href)
        params = parse_qs(parsed.query)
        offset = int(params.get("offset", ["0"])[0])
        if offset != expected_offset:
            raise ValueError("Atlas next link skipped or repeated a page")
        if params.get("kind") != [kind] or params.get("limit") != [
            str(page_size)
        ]:
            raise ValueError("Atlas next link did not preserve its filter")
        request_path = href if href.startswith("/") else f"/gold/edges{href}"
        response = client.get(request_path)
        if response.status_code != _HTTP_OK:
            raise ValueError("Atlas consumer rejected the candidate page")
        page = _AtlasPageParser()
        page.feed(response.text)
        expected_size = min(page_size, edge_count - offset)
        if len(page.edge_ids) != expected_size:
            raise ValueError("Atlas rendered an unexpected page size")
        if response.text.count(
            "<dt>Review state</dt><dd>not_reviewed</dd>"
        ) != len(page.edge_ids):
            raise ValueError("Atlas rendered a changed review state")
        if not all(value in response.text for value in bindings.values()):
            raise ValueError("Atlas omitted a candidate identity binding")
        if f"{edge_count} candidate edge" not in response.text:
            raise ValueError("Atlas omitted the full matching edge count")
        edge_ids.extend(page.edge_ids)
        offsets.append(offset)
        if offset + len(page.edge_ids) < edge_count:
            if len(page.next_hrefs) != 1:
                raise ValueError("Atlas omitted its rendered next-page link")
            href = page.next_hrefs[0]
        elif page.next_hrefs:
            raise ValueError("Atlas rendered an unexpected continuation link")
    return edge_ids, offsets


def _id_digest(edge_ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(edge_ids) + "\n").encode()).hexdigest()


def qualify_consumers(
    edge_path: Path,
    qualification: Mapping[str, object],
    *,
    page_size: int = MAX_EDGE_ROWS,
    expected_bindings: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Traverse the complete candidate graph without returning edge values."""
    if not 1 <= page_size <= MAX_EDGE_ROWS:
        raise ValueError("page size must be between 1 and 1000")
    edges = load_gold_edges(edge_path)
    graph = _mapping(
        qualification.get("graph"), "qualification graph is missing"
    )
    edge_count = graph.get("edge_count")
    if type(edge_count) is not int or edges.num_rows != edge_count:
        raise ValueError("candidate edge count differs from qualification")
    bindings = _bindings(edges, qualification, expected_bindings)
    kinds = set(edges.column("kind").to_pylist())
    if len(kinds) != 1 or not isinstance(next(iter(kinds)), str):
        raise ValueError(
            "candidate graph must have one stable relationship kind"
        )
    kind = next(iter(kinds))
    if not isinstance(kind, str):
        raise TypeError("candidate relationship kind is invalid")
    traversals = {
        "API": _api_ids(edges, kind, edge_count, bindings, page_size),
        "CLI": _cli_ids(edge_path, kind, edge_count, bindings, page_size),
    }
    atlas_ids, offsets = _atlas_ids(
        edges, kind, edge_count, bindings, page_size
    )
    traversals["Atlas"] = atlas_ids
    digests = {surface: _id_digest(ids) for surface, ids in traversals.items()}
    authoritative_ids = sorted(
        cast("list[str]", edges.column("edge_id").to_pylist())
    )
    if (
        len(authoritative_ids) != edge_count
        or len(set(authoritative_ids)) != edge_count
    ):
        raise ValueError("candidate edge identities are not unique")
    if any(ids != authoritative_ids for ids in traversals.values()):
        raise ValueError(
            "consumer traversal does not match authoritative candidate edges"
        )
    if any(len(ids) != edge_count for ids in traversals.values()):
        raise ValueError("consumer did not traverse every candidate edge")
    if len(set(digests.values())) != 1:
        raise ValueError("consumer surfaces returned different edge sequences")
    return {
        "candidate_only": True,
        "edge_count": edge_count,
        "graph_sha256": bindings["graph_sha256"],
        "input_admission_sha256": bindings["input_admission_sha256"],
        "input_semantic_manifest_sha256": bindings[
            "input_semantic_manifest_sha256"
        ],
        "page_offsets": offsets,
        "page_size": page_size,
        "public_publication_performed": False,
        "review_state": "not_reviewed",
        "source_payload_bytes_retained": False,
        "surface_edge_id_sha256": digests,
        "surfaces": sorted(traversals),
    }
