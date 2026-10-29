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
from .platinum_structure import SourceStructurePage, SourceStructureService
from .platinum_v2_api import create_v2_app

MAX_COLUMNS = 32
MAX_ROWS = 100

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


def qualify_structure_consumers(
    *,
    trust_file: Path,
    metadata_root: Path,
    schema_file: Path,
    resource_id: str,
    columns: tuple[str, ...],
    view: Literal["records", "fields"] = "records",
    limit: int = 2,
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
        command = CliRunner().invoke(cli.app, arguments)
        if command.exit_code != 0:
            raise ValueError("source-structure CLI canary failed")
        cli_page = SourceStructurePage.model_validate_json(command.stdout)
        if (
            cli_page.identity != page.identity
            or cli_page.rows != page.rows
            or cli_page.query_sha256 != page.query_sha256
        ):
            raise ValueError("source-structure API and CLI evidence differs")
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
            "consumers": ["api_v2", "cli", "atlas"],
            "comparison_validity": page.comparison_validity,
            "public_export_performed": False,
        }
