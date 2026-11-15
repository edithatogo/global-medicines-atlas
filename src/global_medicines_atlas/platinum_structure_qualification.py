"""Qualify source-structure delivery through independently admitted consumers.

The result retains digests and identities, not source values. This routine does
not admit a resource or publish an export.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack
from html.parser import HTMLParser
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from . import cli
from .atlas import create_atlas_app  # pyright: ignore[reportUnknownVariableType]
from .platinum_configuration import load_benefits_resolver
from .platinum_delivery_qualification import (
    DeliveryRequest,
    _qualify_browser_pages,  # pyright: ignore[reportPrivateUsage] -- shared bounded Atlas browser adapter
)
from .platinum_structure import SourceStructurePage, SourceStructureService
from .platinum_v2_api import create_v2_app

MAX_COLUMNS = 32
MAX_ROWS = 100
SAFETY_FIELDS = frozenset({
    "status",
    "view",
    "offset",
    "coverage_state",
    "comparison_validity",
    "semantic_overlay_state",
})

if TYPE_CHECKING:
    import httpx


class _Table(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.body = False
        self.cell = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        if tag == "tbody":
            self.body = True
        if self.body and tag == "tr":
            self.rows.append([])
        if self.body and tag == "td":
            self.cell = True
            self.rows[-1].append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "tbody":
            self.body = False
        if tag == "td":
            self.cell = False

    def handle_data(self, data: str) -> None:
        if self.body and self.cell:
            self.rows[-1][-1] += data


def _qualify_cli_json(arguments: list[str], page: SourceStructurePage) -> None:
    result = CliRunner().invoke(cli.app, arguments)
    if result.exit_code != 0:
        raise ValueError("source-structure CLI JSON canary failed")
    try:
        cli_page = SourceStructurePage.model_validate_json(result.stdout)
    except ValueError:
        raise ValueError("source-structure CLI JSON evidence differs") from None
    # Cache observations can differ across independent, verified resolvers.
    cache_specific = {"query_receipt_sha256", "query_receipt_json"}
    if not SAFETY_FIELDS.issubset(
        cli_page.model_fields_set
    ) or cli_page.model_dump(exclude=cache_specific) != page.model_dump(
        exclude=cache_specific
    ):
        raise ValueError("source-structure CLI JSON evidence differs")


def _qualify_jsonl_export(
    arguments: list[str], page: SourceStructurePage
) -> str:
    export_arguments = [*arguments, "--format", "jsonl"]
    first = CliRunner().invoke(cli.app, export_arguments)
    if first.exit_code != 0:
        raise ValueError("source-structure CLI export failed")
    try:
        export = [json.loads(line) for line in first.stdout.splitlines()]
    except ValueError:
        raise ValueError("source-structure export evidence differs") from None
    if not export or any(not isinstance(row, dict) for row in export):
        raise ValueError("source-structure export evidence differs")
    try:
        canonical = "".join(
            json.dumps(
                record,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for record in export
        )
    except TypeError, ValueError:
        raise ValueError("source-structure export evidence differs") from None
    expected_summary = {
        "type": "summary",
        "status": page.status,
        "identity": page.identity.model_dump(mode="json"),
        "view": page.view,
        "offset": page.offset,
        "query_sha256": page.query_sha256,
        "row_count": len(page.rows),
        "coverage_state": page.coverage_state,
        "comparison_validity": page.comparison_validity,
        "semantic_overlay_state": page.semantic_overlay_state,
        "source_completeness": "not_established",
    }
    # JSON comparison distinguishes booleans from numeric 0/1.
    actual_summary = {key: export[-1].get(key) for key in expected_summary}
    actual_rows = [record.get("record") for record in export[:-1]]
    if (
        canonical != first.stdout
        or len(export) != len(page.rows) + 1
        or any(record.get("type") != "record" for record in export[:-1])
        or json.dumps(actual_rows, sort_keys=True)
        != json.dumps(page.rows, sort_keys=True)
        or json.dumps(actual_summary, sort_keys=True)
        != json.dumps(expected_summary, sort_keys=True)
    ):
        raise ValueError("source-structure export evidence differs")
    repeated = CliRunner().invoke(cli.app, export_arguments)
    if repeated.exit_code != 0 or repeated.stdout != first.stdout:
        raise ValueError("source-structure export is not deterministic")
    return hashlib.sha256(first.stdout.encode()).hexdigest()


def qualify_structure_consumers(
    *,
    trust_file: Path,
    metadata_root: Path,
    schema_file: Path,
    resource_id: str,
    columns: tuple[str, ...],
    view: Literal["records", "fields"] = "records",
    limit: int = 2,
    browser: bool = False,
) -> dict[str, Any]:
    """Exercise bounded API, CLI and Atlas reads against one admitted revision."""
    if not columns or len(columns) > MAX_COLUMNS or not 1 <= limit <= MAX_ROWS:
        raise ValueError("source-structure canary is outside its bounds")
    with ExitStack() as stack:
        resolver = stack.enter_context(
            load_benefits_resolver(
                trust_file=trust_file,
                metadata_root=metadata_root,
                schema_file=schema_file,
            )
        )
        jurisdictions = {
            item: item.split(".", maxsplit=1)[0].upper()
            for item in resolver.resource_ids
        }
        service = SourceStructureService(resolver, jurisdictions=jurisdictions)
        api: Any = stack.enter_context(  # pyright: ignore[reportUnknownVariableType]
            TestClient(
                create_v2_app(cast("Any", None), source_structure=service)
            )
        )
        atlas: Any = stack.enter_context(  # pyright: ignore[reportUnknownVariableType]
            TestClient(
                create_atlas_app(
                    cast("Any", None), federated_source_structure=service
                )
            )
        )
        params = [("columns", column) for column in columns] + [
            ("view", view),
            ("limit", str(limit)),
        ]
        response = cast("httpx.Client", api).get(
            f"/api/v2/source-structure/{resource_id}", params=tuple(params)
        )
        if response.status_code != HTTPStatus.OK:
            raise ValueError("source-structure API canary failed")
        page = SourceStructurePage.model_validate(response.json())
        if (
            page.status != "available"
            or not page.rows
            or page.identity.semantic_dimension != "source_structure"
            or not SAFETY_FIELDS.issubset(page.model_fields_set)
        ):
            raise ValueError("source-structure API returned no admitted rows")
        arguments = [
            "source-structure",
            resource_id,
            "--trust-file",
            str(trust_file),
            "--metadata-root",
            str(metadata_root),
            "--schema-file",
            str(schema_file),
            "--view",
            view,
            "--limit",
            str(limit),
        ]
        for column in columns:
            arguments.extend(("--column", column))
        _qualify_cli_json(arguments, page)
        export_sha256 = _qualify_jsonl_export(arguments, page)
        rendered = cast("httpx.Client", atlas).get(
            "/federated/source-structure",
            params={
                "resource_id": resource_id,
                "columns": ",".join(columns),
                "view": view,
                "limit": str(limit),
            },
        )
        if rendered.status_code != HTTPStatus.OK:
            raise ValueError("source-structure Atlas canary failed")
        if (
            'data-semantic-overlay-state="not_applied"' not in rendered.text
            or "Semantic field interpretation has not been applied"
            not in rendered.text
        ):
            raise ValueError(
                "source-structure Atlas interpretation limit missing"
            )
        table = _Table()
        table.feed(rendered.text)
        if table.rows != [
            [str(value) for value in row.values()] for row in page.rows
        ]:
            raise ValueError("source-structure Atlas rows differ")
        for value in (
            page.identity.object_sha256,
            page.identity.contract_sha256,
            page.identity.semantic_manifest_sha256,
            page.identity.revision,
            page.query_sha256,
        ):
            if value not in rendered.text:
                raise ValueError("source-structure Atlas identity differs")
        browser_evidence: list[dict[str, object]] = []
        if browser:
            browser_evidence = _qualify_browser_pages(
                atlas,  # pyright: ignore[reportUnknownArgumentType] -- Starlette exposes an unknown app type.
                [
                    (
                        DeliveryRequest(
                            resource_id=resource_id,
                            columns=columns,
                            limit=limit,
                        ),
                        list(page.rows),
                        (
                            page.identity.object_sha256,
                            page.identity.contract_sha256,
                            page.identity.semantic_manifest_sha256,
                            page.identity.revision,
                        ),
                    )
                ],
                source_structure_view=view,
            )
            if len(browser_evidence) != 1:
                raise ValueError(
                    "source-structure browser evidence is incomplete"
                )
        rows = json.dumps(
            page.rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        return {
            "schema_id": "global-medicines-atlas.source-structure-consumer-qualification",
            "status": "passed",
            "resource_id": resource_id,
            "view": view,
            "identity": page.identity.model_dump(mode="json"),
            "query_sha256": page.query_sha256,
            "row_count": len(page.rows),
            "rows_sha256": hashlib.sha256(rows).hexdigest(),
            "export_sha256": export_sha256,
            "consumers": ["api_v2", "cli", "atlas"],
            "browser_qualification": "passed" if browser else "not_run",
            "browser_evidence": browser_evidence,
            "comparison_validity": page.comparison_validity,
            "public_export_performed": False,
        }
