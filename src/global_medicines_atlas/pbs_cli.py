"""Offline PBS donor compatibility over digest-bound archive inputs.

These commands neither acquire nor publish data. Hosted publication remains
the durable data-plane authority; these outputs are diagnostic projections.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from enum import StrEnum
from itertools import islice
from pathlib import Path
from typing import Annotated
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import]
    ElementTree as ET,
)
from zipfile import BadZipFile

import typer

from .adapters.au_pbs import (
    PBS_ARCHIVE_POLICY,
    PBS_V3_NAMESPACE,
    PBS_XML_POLICY,
    PbsV3Archive,
    parse_pbs_v3_archive,
)
from .parser_safety import parse_xml

app = typer.Typer(add_completion=False, no_args_is_help=True)
ArchiveOption = Annotated[
    Path,
    typer.Option("--archive", exists=True, dir_okay=False, readable=True),
]
DigestOption = Annotated[str, typer.Option("--sha256")]
SHA256_LENGTH = 64


class OutputFormat(StrEnum):
    """Supported diagnostic presentations."""

    TEXT = "text"
    JSON = "json"


def _read_archive(archive: Path, digest: str) -> bytes:
    if len(digest) != SHA256_LENGTH or any(
        c not in "0123456789abcdef" for c in digest
    ):
        raise ValueError("expected a lowercase SHA-256 digest")
    with archive.open("rb") as stream:
        payload = stream.read(PBS_ARCHIVE_POLICY.max_archive_bytes + 1)
    if len(payload) > PBS_ARCHIVE_POLICY.max_archive_bytes:
        raise ValueError("archive exceeds the PBS byte bound")
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError("archive digest mismatch")
    return payload


def _load(archive: Path, digest: str) -> PbsV3Archive:
    try:
        return parse_pbs_v3_archive(_read_archive(archive, digest))
    except (OSError, ValueError, BadZipFile) as error:
        typer.echo(f"PBS input rejected: {error}", err=True)
        raise typer.Exit(2) from error


def _emit_bounded(text: str, limit: int = 1048576) -> None:
    if len(text.encode("utf-8")) + 1 > limit:
        typer.echo("PBS inspection exceeds the output byte bound", err=True)
        raise typer.Exit(2)
    typer.echo(text)


def _metadata(batch: PbsV3Archive) -> dict[str, object]:
    return {
        "source_id": "au-pbs",
        "archive_sha256": batch.archive_sha256,
        "member": asdict(batch.member),
        "effective_date": batch.effective_date,
        "namespace_uri": batch.namespace_uri,
        "publication_status": "not_published_by_this_command",
        "evidence_scope": "source_native_funding_not_regulatory_or_clinical",
    }


@app.command("parse")
def parse_items(
    archive: ArchiveOption,
    sha256: DigestOption,
    max_items: Annotated[
        int, typer.Option("--max-items", "--max_items", min=1, max=1000)
    ] = 5,
    output_format: Annotated[
        OutputFormat, typer.Option("--format")
    ] = OutputFormat.TEXT,
) -> None:
    """Print bounded item details, preserving the donor's useful labels."""
    batch = _load(archive, sha256)
    records = batch.records[:max_items]
    if output_format is OutputFormat.JSON:
        _emit_bounded(
            json.dumps(
                {
                    **_metadata(batch),
                    "total_items": len(batch.records),
                    "truncated": len(records) < len(batch.records),
                    "records": [asdict(record) for record in records],
                },
                sort_keys=True,
            )
        )
        return
    lines = [f"Archive SHA-256: {batch.archive_sha256}"]
    for index, record in enumerate(records, 1):
        amt = "; ".join(
            f"{code} (Resource: {resource or 'N/A'})"
            for code, resource in record.amt_references
        )
        lines.extend([
            f"--- Item {index} ---",
            f"  PBS Item Code (xml:id): {record.item_code}",
            f"  Drug Name/Description: {record.product_name}",
            f"  AMT Codes Info: {amt or 'N/A'}",
            f"  ATC Codes: {', '.join(record.atc_codes) or 'N/A'}",
        ])
    lines.append(
        f"Printed details for {len(records)} of {len(batch.records)} item(s)."
    )
    _emit_bounded("\n".join(lines))


@app.command("inspect")
def inspect_item(
    archive: ArchiveOption,
    sha256: DigestOption,
    max_tags: Annotated[int, typer.Option(min=1, max=4096)] = 128,
    max_output_bytes: Annotated[int, typer.Option(min=1, max=1048576)] = 65536,
) -> None:
    """Inspect the first item as normalized XML, never as exact source bytes."""
    batch = _load(archive, sha256)
    root = parse_xml(batch.xml_payload, policy=PBS_XML_POLICY)
    item = next(root.iter(f"{{{PBS_V3_NAMESPACE}}}pharmaceutical-item"))
    payload = ET.tostring(item, encoding="unicode")
    _emit_bounded(
        json.dumps(
            {
                **_metadata(batch),
                "xml_representation": "normalized_not_source_bytes",
                "first_item_xml": payload,
                "tag_sample": [
                    element.tag for element in islice(root.iter(), max_tags)
                ],
            },
            sort_keys=True,
        ),
        max_output_bytes,
    )
