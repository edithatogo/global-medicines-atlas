"""Inspect a locally prepared PBS v3 archive without network acquisition."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import]
    ElementTree as ET,
)

from global_medicines_atlas.adapters.au_pbs import (
    PBS_ARCHIVE_POLICY,
    PBS_V3_NAMESPACE,
    PBS_XML_POLICY,
    inspect_pbs_v3_tags,
    parse_pbs_v3_archive,
)
from global_medicines_atlas.parser_safety import parse_xml

MAX_ITEMS = 1000
MAX_TAGS = 4096
MAX_ARCHIVE_BYTES = PBS_ARCHIVE_POLICY.max_archive_bytes
MAX_XML_OUTPUT_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 4 * 1024 * 1024


def main() -> int:
    """Print bounded, source-native tag and receipt information as JSON."""
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--max-tags", type=int, default=128)
    parser.add_argument("--max-items", "--max_items", type=int, default=5)
    parser.add_argument("--first-item-xml", action="store_true")
    arguments = parser.parse_args()
    if not 1 <= arguments.max_items <= MAX_ITEMS:
        parser.error("--max-items must be between 1 and 1000")
    if not 1 <= arguments.max_tags <= MAX_TAGS:
        parser.error("--max-tags must be between 1 and 4096")
    with arguments.archive.open("rb") as stream:
        payload = stream.read(MAX_ARCHIVE_BYTES + 1)
    if len(payload) > MAX_ARCHIVE_BYTES:
        parser.error("archive exceeds the PBS archive byte limit")
    result = parse_pbs_v3_archive(payload)
    # Finish tag sampling before retaining the optional first-item tree.
    tags = inspect_pbs_v3_tags(result.xml_payload, max_tags=arguments.max_tags)
    first_item_xml = None
    if arguments.first_item_xml:
        root = parse_xml(result.xml_payload, policy=PBS_XML_POLICY)
        first = next(root.iter(f"{{{PBS_V3_NAMESPACE}}}pharmaceutical-item"))
        first_item_xml = ET.tostring(first, encoding="unicode")
        if len(first_item_xml.encode()) > MAX_XML_OUTPUT_BYTES:
            parser.error("first-item XML projection exceeds 1 MiB")
    output = json.dumps(
        {
            "archive_sha256": result.archive_sha256,
            "member": {
                "path": result.member.path,
                "sha256": result.member.sha256,
                "size_bytes": result.member.size_bytes,
            },
            "namespace_uri": result.namespace_uri,
            "effective_date": result.effective_date,
            "record_count": len(result.records),
            "items": [
                asdict(item) for item in result.records[: arguments.max_items]
            ],
            "first_item_xml_projection": first_item_xml,
            "tags": tags,
        },
        sort_keys=True,
    )
    if len(output.encode()) > MAX_OUTPUT_BYTES:
        parser.error("inspection JSON exceeds 4 MiB")
    print(output)
    return 0


if __name__ == "__main__":  # pragma: no cover - main tested directly
    raise SystemExit(main())
