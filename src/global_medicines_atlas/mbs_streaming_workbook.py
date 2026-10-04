"""Separate file-backed structural profile; no cell values or admission."""

# Expat Parse accepts positional flags only; try blocks sanitize parser errors.
# ruff: file-ignore[boolean-positional-value-in-call, too-many-statements-in-try-clause]
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import IO, Any, NoReturn
from xml.parsers import expat
from zipfile import ZipFile

from .archive_safety import DEFAULT_ARCHIVE_POLICY, verify_zip_file

PROFILE = "mbs-utilisation-streaming-xlsx-v1"
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
MIB = 1024 * 1024
ARCHIVE_POLICY = replace(
    DEFAULT_ARCHIVE_POLICY,
    max_archive_bytes=32 * MIB,
    max_total_uncompressed_bytes=1024 * MIB,
)


@dataclass(frozen=True)
class XmlLimits:
    """Independent, finite XML budgets shared across package members."""

    metadata_bytes: int = 8 * MIB
    depth: int = 64
    elements: int = 20_000_000
    text_bytes: int = MIB
    chunk_bytes: int = MIB


class XmlBudget:
    """Stream XML events without retaining nodes, values or shared strings."""

    def __init__(self, limits: XmlLimits) -> None:
        self.limits = limits
        self.elements = 0

    def parse(
        self,
        source: IO[bytes],
        expected_root: str,
        *,
        metadata: bool = False,
        collect: str | None = None,
        collect_depth: int = 2,
    ) -> list[dict[str, str]]:
        """Collect only bounded sheet/relationship attributes from metadata."""
        parser = expat.ParserCreate(namespace_separator="}")
        stack: list[int] = []
        records: list[dict[str, str]] = []
        root_seen = False

        def start(name: str, attrs: dict[str, str]) -> None:
            nonlocal root_seen
            if not root_seen:
                if name != expected_root:
                    raise ValueError("streaming workbook XML root invalid")
                root_seen = True
            stack.append(0)
            self.elements += 1
            if (
                len(stack) > self.limits.depth
                or self.elements > self.limits.elements
            ):
                raise ValueError("streaming workbook XML resource limit")
            if collect == name:
                if len(stack) != collect_depth:
                    raise ValueError("streaming workbook XML root invalid")
                if len(records) >= ARCHIVE_POLICY.max_entries:
                    raise ValueError("streaming workbook metadata record limit")
                records.append(attrs)

        def text(value: str) -> None:
            if stack:
                stack[-1] += len(value.encode("utf-8"))
                if stack[-1] > self.limits.text_bytes:
                    raise ValueError("streaming workbook XML text limit")

        def forbid(*_args: object) -> NoReturn:
            raise ValueError("streaming workbook XML declaration forbidden")

        parser.StartElementHandler = start
        parser.EndElementHandler = lambda _name: stack.pop()
        parser.CharacterDataHandler = text
        parser.StartDoctypeDeclHandler = forbid
        parser.EntityDeclHandler = forbid
        parser.ExternalEntityRefHandler = forbid
        count = 0
        try:
            while block := source.read(self.limits.chunk_bytes):
                count += len(block)
                if metadata and count > self.limits.metadata_bytes:
                    raise ValueError("streaming workbook metadata byte limit")
                parser.Parse(block, False)
            parser.Parse(b"", True)
        except expat.ExpatError as error:
            raise ValueError("streaming workbook XML malformed") from error
        return records


def _worksheet_target(target: str) -> str:
    value = PurePosixPath(target)
    if (
        not target
        or "\\" in target
        or value.is_absolute()
        or ".." in value.parts
    ):
        raise ValueError("streaming workbook relationship invalid")
    path = PurePosixPath("xl") / value
    if path.parts[:2] != ("xl", "worksheets") or path.suffix != ".xml":
        raise ValueError("streaming workbook relationship invalid")
    return str(path)


def validate_streaming_workbook(
    path: Path, reference: dict[str, Any]
) -> dict[str, Any]:
    """Verify ZIP integrity then stream selected sheets without interpretation."""
    if not reference["path"].endswith(".xlsx"):
        raise ValueError("streaming workbook format invalid")
    receipt = verify_zip_file(
        path,
        expected_sha256=reference["sha256"],
        expected_size=reference["byte_count"],
        policy=ARCHIVE_POLICY,
    )
    budget = XmlBudget(XmlLimits())
    with ZipFile(path) as archive:
        sheets = _package(archive, budget)
        for sheet in sheets:
            with archive.open(sheet) as source:
                budget.parse(source, f"{MAIN}}}worksheet")
    inventory = [(m.path, m.sha256, m.size_bytes) for m in receipt.members]
    return {
        "format": "xlsx",
        "check_profile": PROFILE,
        "member_count": len(receipt.members),
        "expanded_bytes": receipt.total_uncompressed_bytes,
        "member_inventory_sha256": hashlib.sha256(
            json.dumps(inventory, separators=(",", ":")).encode()
        ).hexdigest(),
        "worksheet_count": len(sheets),
        "xml_element_count": budget.elements,
        "limits": streaming_limits(),
    }


def _package(archive: ZipFile, budget: XmlBudget) -> list[str]:
    try:
        for member in (
            "[Content_Types].xml",
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
        ):
            if archive.getinfo(member).file_size > budget.limits.metadata_bytes:
                raise ValueError("streaming workbook metadata byte limit")
        with archive.open("[Content_Types].xml") as source:
            budget.parse(source, f"{TYPES}}}Types", metadata=True)
        with archive.open("xl/workbook.xml") as source:
            sheets = budget.parse(
                source,
                f"{MAIN}}}workbook",
                metadata=True,
                collect=f"{MAIN}}}sheet",
                collect_depth=3,
            )
        with archive.open("xl/_rels/workbook.xml.rels") as source:
            relationships = budget.parse(
                source,
                f"{REL}}}Relationships",
                metadata=True,
                collect=f"{REL}}}Relationship",
            )
        targets: dict[str, str] = {}
        identifiers: set[str] = set()
        for row in relationships:
            identifier = row.get("Id", "")
            if not identifier or identifier in identifiers:
                raise ValueError("streaming workbook relationship invalid")
            identifiers.add(identifier)
            if row.get("Type") == f"{OFFICE}/worksheet":
                if row.get("TargetMode", "Internal") != "Internal":
                    raise ValueError("streaming workbook relationship invalid")
                target = _worksheet_target(row.get("Target", ""))
                archive.getinfo(target)
                targets[identifier] = target
        selected = [targets[row[f"{OFFICE}}}id"]] for row in sheets]
        if not selected or len(selected) != len(set(selected)):
            raise ValueError("streaming workbook relationship invalid")
    except KeyError as error:
        raise ValueError(
            "streaming workbook required member missing"
        ) from error
    return selected


def streaming_limits() -> dict[str, int | float]:
    """Return fixed public-safe limits for successful or failed receipts."""
    limits = XmlLimits()
    return {
        "archive_bytes": ARCHIVE_POLICY.max_archive_bytes,
        "entries": ARCHIVE_POLICY.max_entries,
        "member_bytes": ARCHIVE_POLICY.max_entry_uncompressed_bytes,
        "expanded_bytes": ARCHIVE_POLICY.max_total_uncompressed_bytes,
        "ratio": ARCHIVE_POLICY.max_decompression_ratio,
        "path_depth": ARCHIVE_POLICY.max_path_depth,
        "chunk_bytes": MIB,
        "metadata_bytes": limits.metadata_bytes,
        "xml_depth": limits.depth,
        "xml_elements": limits.elements,
        "xml_text_bytes": limits.text_bytes,
    }
