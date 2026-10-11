"""Source-unbound PBS XML slots; callers must separately validate provenance."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import] -- bounded parser below
    ElementTree as ET,
)

from .adapters.au_pbs import PBS_V3_NAMESPACE, PBS_XML_POLICY
from .parser_safety import iter_xml_events


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
    yield from _own_slots(element, record_id, schema_path)
    counts: Counter[str] = Counter()
    for child in element:
        counts[child.tag] += 1
        name = _pointer(child.tag)
        yield from _slots(
            child,
            f"{record_id}/{name}/{counts[child.tag]}",
            f"{schema_path}/{name}",
        )


def _own_slots(
    element: ET.Element, record_id: str, schema_path: str
) -> Iterator[PbsXmlSlot]:
    """Yield an element's own slots without traversing its children."""
    for name, value in (("text", element.text), ("tail", element.tail)):
        yield PbsXmlSlot(
            record_id, f"{record_id}/{name}", f"{schema_path}/{name}", value
        )
    for name, value in sorted(element.attrib.items()):
        slot = f"attributes/{_pointer(name)}"
        yield PbsXmlSlot(
            record_id, f"{record_id}/{slot}", f"{schema_path}/{slot}", value
        )


def _iter_pbs_xml_slots_once(
    payload: bytes,
) -> Iterator[PbsXmlSlot]:
    """Walk a checked document and detach completed direct-root children."""
    root: ET.Element | None = None
    root_record_id = ""
    root_schema_path = ""
    root_slots_emitted = False
    sibling_counts: Counter[str] = Counter()
    current_child: tuple[ET.Element, str, str] | None = None
    pending_child: tuple[ET.Element, str, str] | None = None

    for event, element, parent in iter_xml_events(
        payload, policy=PBS_XML_POLICY
    ):
        if event == "start" and parent is None:
            if element.tag not in {
                f"{{{PBS_V3_NAMESPACE}}}root",
                f"{{{PBS_V3_NAMESPACE}}}schedule",
            }:
                raise ValueError(
                    "PBS namespace/root does not match source contract"
                )
            root = element
            root_schema_path = f"/{_pointer(root.tag)}"
            root_record_id = f"{root_schema_path}/1"
            continue

        if root is None:
            raise ValueError("PBS XML has no document root")

        if event == "start" and parent is root:
            # The previous child's tail is complete before the next direct
            # child starts. Emit it before this sibling to preserve the
            # original depth-first source order, then detach the old subtree.
            if pending_child is not None:
                child, record_id, schema_path = pending_child
                yield from _slots(child, record_id, schema_path)
                child.clear()
                root.remove(child)
                pending_child = None

            if not root_slots_emitted:
                yield from _own_slots(root, root_record_id, root_schema_path)
                root_slots_emitted = True

            sibling_counts[element.tag] += 1
            name = _pointer(element.tag)
            current_child = (
                element,
                f"{root_record_id}/{name}/{sibling_counts[element.tag]}",
                f"{root_schema_path}/{name}",
            )
        elif event == "end" and parent is root:
            if current_child is None or current_child[0] is not element:
                raise ValueError("PBS XML child structure is inconsistent")
            pending_child = current_child
            current_child = None
        elif event == "end" and element is root:
            if pending_child is not None:
                child, record_id, schema_path = pending_child
                yield from _slots(child, record_id, schema_path)
                child.clear()
                root.remove(child)
                pending_child = None
            if not root_slots_emitted:
                yield from _own_slots(root, root_record_id, root_schema_path)
            root_slots_emitted = True


def iter_pbs_xml_slots(payload: bytes) -> Iterator[PbsXmlSlot]:
    """Stream checked root subtrees into ordered slots without source identity.

    A full no-output pass validates well-formedness and parser limits before
    any slot is yielded. The output pass detaches completed direct children of
    the root. Retained tree state is bounded by the current parser input chunk
    and the largest direct-root child subtree; a single large wrapper can
    therefore still approach the document limit. This cannot establish
    receipt lineage or admission. Unknown fields, duplicate occurrences and
    empty text/tail slots survive.
    """
    # iter_xml_events completes its no-tree safety preflight before yielding
    # the first event, so malformed or oversized XML cannot produce partial
    # native rows.
    yield from _iter_pbs_xml_slots_once(payload)
