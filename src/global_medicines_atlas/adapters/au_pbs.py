"""Australian Pharmaceutical Benefits Scheme funding XML adapter."""

from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import dataclass
from io import BytesIO
from itertools import islice
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import]
    ElementTree as ET,
)
from zipfile import ZipFile

import pyarrow as pa
import pyarrow.parquet as pq

from ..archive_safety import ArchivePolicy, ExtractedMember, inspect_zip
from ..models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    Identifier,
    MedicineConcept,
    StatusAssertion,
)
from ..parser_safety import ParserPolicy, parse_xml
from ..receipts import SourceReceipt
from ._receipt import provenance_from_receipt

SOURCE_ID = "au-pbs"
MAX_FIXTURE_BYTES = 1_000_000
PBS_V3_NAMESPACE = "http://schema.pbs.gov.au/"
DOCBOOK_NAMESPACE = "http://docbook.org/ns/docbook"
RDF_NAMESPACE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
DCTERMS_NAMESPACE = "http://purl.org/dc/terms/"
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
PBS_ARCHIVE_POLICY = ArchivePolicy(
    max_archive_bytes=256 * 1024 * 1024,
    max_entries=64,
    max_entry_uncompressed_bytes=512 * 1024 * 1024,
    max_total_uncompressed_bytes=768 * 1024 * 1024,
    max_decompression_ratio=200,
)
PBS_XML_POLICY = ParserPolicy(
    max_bytes=PBS_ARCHIVE_POLICY.max_entry_uncompressed_bytes,
    max_xml_depth=128,
    # The official April 2026 v3 schedule exceeds twenty million structural
    # elements. Keep a source-specific finite ceiling within the bounded
    # 512 MiB member envelope rather than weakening the shared parser policy.
    max_xml_elements=50_000_000,
    max_xml_text_bytes=384 * 1024 * 1024,
)


@dataclass(frozen=True, slots=True)
class PbsV3Record:
    """Source-native identity and classification fields from one PBS item."""

    item_code: str
    product_name: str
    amt_references: tuple[tuple[str, str | None], ...]
    atc_codes: tuple[str, ...]
    restrictions: tuple[str, ...]
    restriction_effective_dates: tuple[str | None, ...]
    projected_item_sha256: str


@dataclass(frozen=True, slots=True)
class PbsV3Archive:
    """Immutable archive/member receipt plus parsed source-native records."""

    archive_sha256: str
    member: ExtractedMember
    namespace_uri: str
    effective_date: str | None
    records: tuple[PbsV3Record, ...]
    xml_payload: bytes


PBS_V3_SOURCE_SCHEMA = pa.schema([
    pa.field("item_code", pa.string(), nullable=False),
    pa.field("product_name", pa.string(), nullable=False),
    pa.field("amt_codes", pa.list_(pa.string()), nullable=False),
    pa.field(
        "amt_resources",
        pa.list_(pa.field("item", pa.string(), nullable=True)),
        nullable=False,
    ),
    pa.field("atc_codes", pa.list_(pa.string()), nullable=False),
    pa.field("restrictions", pa.list_(pa.string()), nullable=False),
    pa.field("restriction_effective_dates", pa.list_(pa.string())),
    pa.field("projected_item_sha256", pa.string(), nullable=False),
])


def read_pbs_v3_member(payload: bytes) -> tuple[ExtractedMember, bytes]:
    """Read the single schedule member under existing ZIP safety bounds.

    This byte-level operation does not parse item records, admit the archive,
    establish source identity or write extracted bytes to the filesystem.
    """
    inspect_zip(payload, PBS_ARCHIVE_POLICY)
    with ZipFile(BytesIO(payload)) as archive:
        matches = [
            info
            for info in archive.infolist()
            if not info.is_dir()
            and fnmatch.fnmatch(
                info.filename.rsplit("/", 1)[-1].casefold(), "sch-*.xml"
            )
        ]
        if len(matches) != 1:
            raise ValueError(
                "PBS archive must contain exactly one schedule XML"
            )
        info = matches[0]
        xml_payload = archive.read(info)
        if len(xml_payload) != info.file_size:
            raise ValueError("PBS member size does not match ZIP directory")
    return (
        ExtractedMember(
            path=info.filename,
            sha256=hashlib.sha256(xml_payload).hexdigest(),
            size_bytes=len(xml_payload),
        ),
        xml_payload,
    )


def parse_pbs_v3_archive(payload: bytes) -> PbsV3Archive:
    """Validate a PBS ZIP and parse its single v3 schedule member."""
    member, xml_payload = read_pbs_v3_member(payload)

    try:
        root = parse_xml(xml_payload, policy=PBS_XML_POLICY)
    except ValueError as error:
        raise ValueError("schedule member is not valid PBS XML") from error
    namespace = _namespace(root.tag)
    if namespace != PBS_V3_NAMESPACE:
        raise ValueError(f"PBS namespace drift: {namespace or 'missing'}")
    allowed_roots = {
        f"{{{PBS_V3_NAMESPACE}}}root",
        f"{{{PBS_V3_NAMESPACE}}}schedule",
    }
    if root.tag not in allowed_roots:
        raise ValueError(f"PBS root drift: {root.tag}")
    records = tuple(
        _pbs_v3_record(item)
        for item in root.iter(f"{{{PBS_V3_NAMESPACE}}}pharmaceutical-item")
    )
    if not records:
        raise ValueError("PBS schedule contains no pharmaceutical items")
    item_codes = [record.item_code for record in records]
    if len(item_codes) != len(set(item_codes)):
        raise ValueError("PBS schedule contains duplicate item identity")
    return PbsV3Archive(
        archive_sha256=hashlib.sha256(payload).hexdigest(),
        member=member,
        namespace_uri=namespace,
        effective_date=_publication_date(root),
        records=records,
        xml_payload=xml_payload,
    )


def inspect_pbs_v3_tags(
    payload: bytes, *, max_tags: int = 128
) -> tuple[str, ...]:
    """Return a bounded preorder tag sample from admitted PBS XML."""
    if max_tags < 1:
        raise ValueError("max_tags must be positive")
    root = parse_xml(payload, policy=PBS_XML_POLICY)
    return tuple(element.tag for element in islice(root.iter(), max_tags))


def pbs_v3_source_parquet(records: tuple[PbsV3Record, ...]) -> bytes:
    """Build deterministic source-faithful Parquet for admitted PBS records."""
    rows = [
        {
            "item_code": record.item_code,
            "product_name": record.product_name,
            "amt_codes": [code for code, _ in record.amt_references],
            "amt_resources": [
                resource for _, resource in record.amt_references
            ],
            "atc_codes": list(record.atc_codes),
            "restrictions": list(record.restrictions),
            "restriction_effective_dates": list(
                record.restriction_effective_dates
            ),
            "projected_item_sha256": record.projected_item_sha256,
        }
        for record in records
    ]
    output = BytesIO()
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        pa.Table.from_pylist(rows, schema=PBS_V3_SOURCE_SCHEMA),
        output,
        compression="zstd",
        version="2.6",
        write_statistics=True,
    )
    return output.getvalue()


def _namespace(tag: str) -> str:
    if not tag.startswith("{") or "}" not in tag:
        return ""
    return tag[1:].split("}", 1)[0]


def _publication_date(root: ET.Element) -> str | None:
    declared = root.get("effective-date")
    if declared:
        return declared
    return root.findtext(
        f"./{{{PBS_V3_NAMESPACE}}}info/{{{DCTERMS_NAMESPACE}}}valid"
    )


def _pbs_v3_record(item: ET.Element) -> PbsV3Record:
    item_code = (item.get(f"{{{XML_NAMESPACE}}}id") or "").strip()
    if not item_code:
        raise ValueError("Missing required PBS XML field: xml:id")
    name = _required_text(
        item,
        f"./{{{PBS_V3_NAMESPACE}}}block-container/{{{DOCBOOK_NAMESPACE}}}para",
    )
    reference_path = (
        f"./{{{PBS_V3_NAMESPACE}}}drug-references-list/"
        f"{{{PBS_V3_NAMESPACE}}}mp-reference/"
        f"{{{PBS_V3_NAMESPACE}}}code"
    )
    amt_references = [
        (value, code.get(f"{{{RDF_NAMESPACE}}}resource"))
        for code in item.findall(reference_path)
        if (value := (code.text or "").strip())
    ]
    atc_codes = tuple(
        value
        for code in item.iter(f"{{{PBS_V3_NAMESPACE}}}code")
        if code.get("type") == "ATC" and (value := (code.text or "").strip())
    )
    restriction_nodes = tuple(item.iter(f"{{{PBS_V3_NAMESPACE}}}restriction"))
    restriction_rows = tuple(
        (value, node.get("effective-date"))
        for node in restriction_nodes
        if (value := " ".join("".join(node.itertext()).split()))
    )
    return PbsV3Record(
        item_code=item_code,
        product_name=name,
        amt_references=tuple(amt_references),
        atc_codes=atc_codes,
        restrictions=tuple(value for value, _ in restriction_rows),
        restriction_effective_dates=tuple(
            effective_date for _, effective_date in restriction_rows
        ),
        projected_item_sha256=hashlib.sha256(
            ET.tostring(item, encoding="utf-8")
        ).hexdigest(),
    )


def project_pbs_xml(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project listed items from a minimal PBS XML schedule."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=SOURCE_ID,
        jurisdiction="AUS",
        transformation="au-pbs-xml-v1",
    )
    root = _fixture_xml(payload)
    records: list[CanonicalMedicineRecord] = []
    for item in root.findall(".//item"):
        item_code = _required_text(item, "item-code")
        name = _required_text(item, "product-name")
        status = _required_text(item, "listing-status")
        restrictions = tuple(
            text
            for node in item.findall("./restrictions/restriction")
            if (text := (node.text or "").strip())
        )
        concept_id = f"au-pbs:{item_code}"
        records.append(
            CanonicalMedicineRecord(
                concept=MedicineConcept(
                    concept_id=concept_id,
                    jurisdiction="AUS",
                    level="presentation",
                    preferred_name=name,
                    identifiers=(
                        Identifier(
                            system="https://www.pbs.gov.au/medicine/item/",
                            value=item_code,
                            identifier_type="pbs-item-code",
                        ),
                    ),
                ),
                assertions=(
                    StatusAssertion(
                        assertion_id=f"{concept_id}:funding",
                        concept_id=concept_id,
                        jurisdiction="AUS",
                        kind=AssertionKind.FUNDING,
                        authority="Department of Health, Disability and Ageing",
                        status_code=_status_code(status),
                        evidence_status=(
                            EvidenceStatus.CONFIRMED
                            if receipt.satisfies_live_gate
                            else EvidenceStatus.UNKNOWN
                        ),
                        restrictions=restrictions,
                        provenance=provenance,
                    ),
                ),
                provenance=(provenance,),
            )
        )
    return tuple(sorted(records, key=lambda record: record.concept.concept_id))


def _fixture_xml(payload: bytes) -> ET.Element:
    return parse_xml(
        payload,
        policy=ParserPolicy(max_bytes=MAX_FIXTURE_BYTES),
    )


def _required_text(parent: ET.Element, path: str) -> str:
    value = parent.findtext(path, default="").strip()
    if not value:
        raise ValueError(f"Missing required PBS XML field: {path}")
    return value


def _status_code(value: str) -> str:
    return "-".join(value.casefold().split())
