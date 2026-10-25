"""Bounded, value-free delivery evidence from independently admitted resources.

This executes the real configuration loader and consumer routes. It neither
creates trust nor admits objects. HTML verification is server rendering evidence,
not a fresh browser accessibility qualification.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Sequence
from contextlib import ExitStack
from html.parser import HTMLParser
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field
from typer.testing import CliRunner

from . import cli
from .api import create_app
from .atlas import create_atlas_app
from .platinum_benefits import BenefitsPage, BenefitsQuery, BenefitsService
from .platinum_configuration import load_benefits_resolver

MAX_REQUESTS = 32

if TYPE_CHECKING:
    import httpx

    from .atlas import AtlasQueryService
    from .query_service import ReadOnlyQueryService


class DeliveryRequest(BaseModel):
    """One small, explicit flat-column read."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    resource_id: str = Field(min_length=1, max_length=256)
    columns: tuple[str, ...] = Field(min_length=1, max_length=32)
    limit: int = Field(default=2, ge=1, le=100)


class DeliveryQualificationError(ValueError):
    """Safe failure that never embeds captured source or CLI output."""


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


class _RenderedTable(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._body = False
        self._cell = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        if tag == "tbody":
            self._body = True
        if self._body and tag == "tr":
            self.rows.append([])
        if self._body and tag == "td":
            self._cell = True
            self.rows[-1].append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "tbody":
            self._body = False
        if tag == "td":
            self._cell = False

    def handle_data(self, data: str) -> None:
        if self._body and self._cell:
            self.rows[-1][-1] += data


def _require(condition: object, message: str) -> None:
    if not condition:
        raise DeliveryQualificationError(message)


def run_product_delivery_qualification(  # ruff: ignore[too-many-locals,too-many-statements] -- one bounded consumer comparison keeps sensitive intermediate values local.
    trust_file: Path,
    metadata_root: Path,
    schema_file: Path,
    requests: Sequence[DeliveryRequest],
    *,
    offline: bool = False,
) -> dict[str, object]:
    """Exercise real local consumer apps, retaining only aggregate evidence.

    Online mode can fetch only the resources authorized by DeploymentTrust.
    Callers must supply separately governed trust, never derive it here from
    candidate contents. CLI env overrides are scoped by CliRunner and restored.
    """
    _require(
        1 <= len(requests) <= MAX_REQUESTS,
        "request count must be between 1 and 32",
    )
    bounded = tuple(DeliveryRequest.model_validate(item) for item in requests)
    for item in bounded:
        BenefitsQuery(columns=item.columns, limit=item.limit, offline=offline)
    with ExitStack() as stack:
        resolver = load_benefits_resolver(
            trust_file=trust_file,
            metadata_root=metadata_root,
            schema_file=schema_file,
        )
        stack.enter_context(resolver)
        secret = secrets.token_hex(32)
        benefits = BenefitsService(resolver, cursor_key=secret.encode())
        # Only benefits routes are exercised; unrelated local catalogue routes
        # remain unconfigured and are never invoked by this qualification.
        api = TestClient(
            create_app(cast("ReadOnlyQueryService", None), benefits=benefits)
        )
        atlas = TestClient(
            create_atlas_app(
                cast("AtlasQueryService", None), federated_benefits=benefits
            )
        )
        stack.enter_context(api)
        stack.enter_context(atlas)
        evidence: list[dict[str, object]] = []
        for item in bounded:
            arguments = [
                "benefits",
                item.resource_id,
                "--trust-file",
                str(trust_file),
                "--metadata-root",
                str(metadata_root),
                "--schema-file",
                str(schema_file),
                "--limit",
                str(item.limit),
            ]
            for column in item.columns:
                arguments.extend(("--column", column))
            if offline:
                arguments.append("--offline")
            cli_result = CliRunner().invoke(
                cli.app, arguments, env={"GMA_CURSOR_SECRET": secret}
            )
            _require(
                cli_result.exit_code == 0,
                "CLI page failed or resource unavailable",
            )
            cli_page = BenefitsPage.model_validate_json(cli_result.stdout)
            params = [("columns", column) for column in item.columns] + [
                ("limit", str(item.limit)),
                ("offline", str(offline).lower()),
            ]
            response = cast("httpx.Client", api).get(
                f"/api/v1/benefits/{item.resource_id}", params=tuple(params)
            )
            _require(
                response.status_code == HTTPStatus.OK, "API page request failed"
            )
            api_page = BenefitsPage.model_validate(response.json())
            _require(
                api_page.status == cli_page.status == "available",
                "resource unavailable",
            )
            _require(bool(api_page.rows), "bounded canary returned no rows")
            _require(
                api_page.identity == cli_page.identity,
                "API and CLI pinned identity mismatch",
            )
            _require(
                api_page.rows == cli_page.rows, "API and CLI rows mismatch"
            )
            _require(
                (
                    api_page.query_sha256,
                    api_page.window_sha256,
                    api_page.page_sha256,
                )
                == (
                    cli_page.query_sha256,
                    cli_page.window_sha256,
                    cli_page.page_sha256,
                ),
                "API and CLI evidence mismatch",
            )
            rendered = cast("httpx.Client", atlas).get(
                "/federated/benefits",
                params={
                    "resource_id": item.resource_id,
                    "columns": ",".join(item.columns),
                    "limit": str(item.limit),
                    "offline": str(offline).lower(),
                },
            )
            _require(
                rendered.status_code == HTTPStatus.OK, "Atlas request failed"
            )
            parser = _RenderedTable()
            parser.feed(rendered.text)
            expected = [
                [str(value) for value in row.values()] for row in api_page.rows
            ]
            _require(parser.rows == expected, "Atlas rendered rows mismatch")
            for value in (
                api_page.identity.object_sha256,
                api_page.identity.contract_sha256,
                api_page.identity.semantic_manifest_sha256,
                api_page.identity.revision,
                api_page.page_sha256,
                api_page.query_sha256,
            ):
                _require(
                    value is not None and value in rendered.text,
                    "Atlas pinned evidence mismatch",
                )
            export = CliRunner().invoke(
                cli.app,
                [
                    *arguments,
                    "--format",
                    "jsonl",
                    "--max-rows",
                    str(item.limit),
                ],
                env={"GMA_CURSOR_SECRET": secret},
            )
            _require(export.exit_code == 0, "CLI export failed")
            records = [json.loads(line) for line in export.stdout.splitlines()]
            summary = records[-1]
            rows = [record["record"] for record in records[:-1]]
            _require(
                summary["type"] == "summary"
                and summary["status"] == "available",
                "export summary unavailable",
            )
            _require(
                rows == list(api_page.rows)
                and summary["row_count"] == len(rows),
                "export rows mismatch",
            )
            _require(
                summary["query_sha256"] == api_page.query_sha256
                and summary["window_sha256"] == api_page.window_sha256
                and summary["page_sha256s"] == [api_page.page_sha256],
                "export query evidence mismatch",
            )
            _require(
                _digest(rows) == api_page.page_sha256, "row digest mismatch"
            )
            cache = resolver.cache_receipt(item.resource_id)
            _require(
                cache.status == "verified_exact_digest",
                "verified cache evidence unavailable",
            )
            identity = api_page.identity.model_dump(mode="json")
            _require(
                summary["identity"] == identity,
                "export pinned identity mismatch",
            )
            _require(
                all(
                    record["identity"] == identity
                    and record["type"] == "record"
                    for record in records[:-1]
                ),
                "export record identity mismatch",
            )
            evidence.append({
                "request_sha256": _digest(item.model_dump(mode="json")),
                "identity_sha256": _digest(identity),
                "row_count": len(rows),
                "rows_sha256": _digest(rows),
                "page_sha256": api_page.page_sha256,
                "window_sha256": api_page.window_sha256,
                "query_sha256": api_page.query_sha256,
                "api_http_status": response.status_code,
                "atlas_http_status": rendered.status_code,
                "cli_exit_code": cli_result.exit_code,
                "export_exit_code": export.exit_code,
                "export_row_count": summary["row_count"],
                "atlas_rendered_row_count": len(parser.rows),
            })
        return {
            "schema_version": 1,
            "status": "passed",
            "request_count": len(bounded),
            "surface_request_counts": {
                "api": len(bounded),
                "atlas": len(bounded),
                "cli_json": len(bounded),
                "cli_jsonl": len(bounded),
            },
            "trust_sha256": hashlib.sha256(trust_file.read_bytes()).hexdigest(),
            "schema_sha256": hashlib.sha256(
                schema_file.read_bytes()
            ).hexdigest(),
            "offline": offline,
            "source_completeness": "not_established",
            "browser_qualification": "not_performed",
            "evidence": evidence,
        }
