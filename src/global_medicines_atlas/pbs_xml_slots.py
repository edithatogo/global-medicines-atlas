"""Source-unbound PBS XML slots; callers must separately validate provenance."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import] -- bounded parser below
    ElementTree as ET,
)

from .adapters.au_pbs import PBS_V3_NAMESPACE, PBS_XML_POLICY
from .parser_safety import parse_xml


@dataclass(frozen=True, slots=True)
class PbsXmlSlot:
    """One uninterpreted native slot; not a source or acquisition assertion."""

    record_id: str
    path: str
    schema_path: str
    value: str | None


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _slots(
    element: ET.Element, record_id: str, schema_path: str
) -> Iterator[PbsXmlSlot]:
    for name, value in (("text", element.text), ("tail", element.tail)):
        yield PbsXmlSlot(
            record_id, f"{record_id}/{name}", f"{schema_path}/{name}", value
        )
    for name, value in sorted(element.attrib.items()):
        slot = f"attributes/{_pointer(name)}"
        yield PbsXmlSlot(
            record_id, f"{record_id}/{slot}", f"{schema_path}/{slot}", value
        )
    counts: Counter[str] = Counter()
    for child in element:
        counts[child.tag] += 1
        name = _pointer(child.tag)
        yield from _slots(
            child,
            f"{record_id}/{name}/{counts[child.tag]}",
            f"{schema_path}/{name}",
        )


def iter_pbs_xml_slots(payload: bytes) -> Iterator[PbsXmlSlot]:
    """Parse bounded XML into ordered slots without inventing source identity.

    The parser retains a tree under the existing finite PBS envelope limits.
    This source-unbound iterator cannot establish receipt lineage or admission.
    Unknown fields, duplicate occurrences and empty text/tail slots survive.
    """
    root = parse_xml(payload, policy=PBS_XML_POLICY)
    if root.tag not in {
        f"{{{PBS_V3_NAMESPACE}}}root",
        f"{{{PBS_V3_NAMESPACE}}}schedule",
    }:
        raise ValueError("PBS namespace/root does not match source contract")
    path = f"/{_pointer(root.tag)}"
    yield from _slots(root, f"{path}/1", path)
