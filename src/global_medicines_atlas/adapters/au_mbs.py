"""Source-faithful Australian Medicare Benefits Schedule XML adapter."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, cast
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import]
    ElementTree as ET,
)

from pydantic import Field, model_validator

from ..models import FrozenModel, Provenance
from ..parser_safety import ParserPolicy, iter_xml_events, parse_xml
from ..receipts import SourceReceipt
from ._receipt import provenance_from_receipt

SOURCE_ID = "au-mbs"
LEGACY_MBS_BYTES = 8_194_522
LEGACY_MBS_RECORDS = 5_989
LEGACY_MBS_SHA256 = (
    "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
)
LEGACY_FIELD_COUNT_DISTRIBUTION = {34: 75, 35: 1_051, 36: 4_132, 37: 731}
MBS_NATIVE_FIELDS = (
    "Anaes",
    "AnaesChange",
    "BasicUnits",
    "Benefit100",
    "Benefit75",
    "Benefit85",
    "BenefitStartDate",
    "BenefitType",
    "Category",
    "DerivedFee",
    "DerivedFeeStartDate",
    "Description",
    "DescriptionStartDate",
    "DescriptorChange",
    "EMSNCap",
    "EMSNChange",
    "EMSNChangeDate",
    "EMSNDescription",
    "EMSNEndDate",
    "EMSNFixedCapAmount",
    "EMSNMaximumCap",
    "EMSNPercentageCap",
    "EMSNStartDate",
    "FeeChange",
    "FeeStartDate",
    "FeeType",
    "Group",
    "ItemChange",
    "ItemEndDate",
    "ItemNum",
    "ItemStartDate",
    "ItemType",
    "NewItem",
    "ProviderType",
    "QFEEndDate",
    "QFEStartDate",
    "ScheduleFee",
    "SubGroup",
    "SubHeading",
    "SubItemNum",
)
_NATIVE_FIELD_SET = frozenset(MBS_NATIVE_FIELDS)
_MBS_POLICY = ParserPolicy(
    max_bytes=9_000_000,
    max_xml_depth=8,
    max_xml_elements=300_000,
    max_xml_text_bytes=9_000_000,
)


class MbsNativeField(FrozenModel):
    """One field exactly as represented in a source ``Data`` element."""

    name: str = Field(min_length=1)
    value: str | None


class MbsSourceRecord(FrozenModel):
    """Independent MBS service-benefit evidence, never a medicine assertion."""

    source_record_id: str = Field(min_length=1)
    source_ordinal: int = Field(ge=0)
    fields: tuple[MbsNativeField, ...] = Field(min_length=1)
    provenance: Provenance

    @model_validator(mode="after")
    def native_field_names_are_unique(self) -> MbsSourceRecord:
        names = tuple(field.name for field in self.fields)
        if len(names) != len(set(names)):
            raise ValueError("MBS record contains a duplicate native field")
        return self

    def value(self, name: str) -> str | None:
        """Return the source value without harmonising its type or semantics."""
        return next(
            (field.value for field in self.fields if field.name == name),
            None,
        )


class MbsSourceBatch(FrozenModel):
    """Receipt-bound collection of source-faithful MBS records."""

    source_id: Literal["au-mbs"] = SOURCE_ID
    schema_era: str = Field(min_length=1)
    observed_fields: tuple[str, ...] = Field(min_length=1)
    missing_native_fields: tuple[str, ...]
    records: tuple[MbsSourceRecord, ...] = Field(min_length=1)
    provenance: Provenance

    @property
    def record_count(self) -> int:
        """Return the exact parsed ``Data`` denominator."""
        return len(self.records)


@dataclass(frozen=True, slots=True)
class MbsSourceStreamMetadata:
    """Denominators and provenance validated before streaming Silver rows."""

    schema_era: str
    observed_fields: tuple[str, ...]
    missing_native_fields: tuple[str, ...]
    record_count: int
    provenance: Provenance


def _native_fields(element: ET.Element) -> tuple[MbsNativeField, ...]:
    # ``parse_xml`` returns Element objects; this helper stays local so the
    # public model never exposes mutable ElementTree nodes.
    children = list(element)
    fields: list[MbsNativeField] = []
    seen: set[str] = set()
    for child in children:
        name = child.tag.split("}")[-1]
        if name not in _NATIVE_FIELD_SET:
            raise ValueError(f"MBS Data contains unknown native field {name!r}")
        if name in seen:
            raise ValueError(
                f"MBS Data contains duplicate native field {name!r}"
            )
        if list(child):
            raise ValueError(f"MBS native field {name!r} must not be nested")
        seen.add(name)
        fields.append(MbsNativeField(name=name, value=child.text or None))
    return tuple(fields)


def _required_identity_value(
    fields: tuple[MbsNativeField, ...],
    name: str,
) -> str:
    value = next((field.value for field in fields if field.name == name), None)
    if value is None or not value.strip():
        raise ValueError(f"MBS Data is missing required identity field {name}")
    return value.strip()


def _iter_mbs_data_elements(
    payload: bytes,
) -> Iterator[ET.Element]:
    """Yield direct MBS Data records and detach each completed subtree."""
    root: ET.Element | None = None
    record_count = 0
    for event, element, parent in iter_xml_events(payload, policy=_MBS_POLICY):
        if event == "start":
            if parent is None:
                root = element
                root_name = root.tag.split("}")[-1]
                if root_name != "MBS_XML":
                    raise ValueError(
                        f"MBS XML root must be 'MBS_XML', got {root_name!r}"
                    )
            elif parent is root and element.tag != "Data":
                raise ValueError(
                    "MBS_XML contains an unexpected non-Data element"
                )
        elif parent is root:
            record_count += 1
            yield element
            element.clear()
            cast("ET.Element", parent).remove(element)
    if record_count == 0:
        raise ValueError("MBS_XML contains no Data records")


def inspect_mbs_source_xml_stream(
    payload: bytes,
    receipt: SourceReceipt,
) -> MbsSourceStreamMetadata:
    """Validate the complete MBS document without retaining its record tree."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=SOURCE_ID,
        jurisdiction="AUS",
        transformation="au-mbs-source-xml-v1",
    )
    observed: set[str] = set()
    record_count = 0
    for element in _iter_mbs_data_elements(payload):
        fields = _native_fields(element)
        _required_identity_value(fields, "ItemNum")
        record_count += 1
        observed.update(field.name for field in fields)
    observed_fields = tuple(sorted(observed))
    return MbsSourceStreamMetadata(
        schema_era=receipt.source.catalog_version,
        observed_fields=observed_fields,
        missing_native_fields=tuple(
            field for field in MBS_NATIVE_FIELDS if field not in observed
        ),
        record_count=record_count,
        provenance=provenance,
    )


def iter_mbs_source_xml_records(
    payload: bytes,
    metadata: MbsSourceStreamMetadata,
) -> Iterator[MbsSourceRecord]:
    """Stream validated source records without building a batch-sized tree."""
    if (
        metadata.provenance.source_sha256 is None
        or hashlib.sha256(payload).hexdigest()
        != metadata.provenance.source_sha256
    ):
        raise ValueError(
            "MBS stream payload differs from inspected source bytes"
        )
    for ordinal, element in enumerate(_iter_mbs_data_elements(payload)):
        fields = _native_fields(element)
        item = _required_identity_value(fields, "ItemNum")
        sub_item = next(
            (
                field.value or ""
                for field in fields
                if field.name == "SubItemNum"
            ),
            "",
        ).strip()
        start = next(
            (
                field.value or ""
                for field in fields
                if field.name == "ItemStartDate"
            ),
            "",
        ).strip()
        yield MbsSourceRecord(
            source_record_id=(
                f"{SOURCE_ID}:{item}:{sub_item}:{start}:{ordinal}"
            ),
            source_ordinal=ordinal,
            fields=fields,
            provenance=metadata.provenance,
        )


def parse_mbs_source_xml(
    payload: bytes,
    receipt: SourceReceipt,
) -> MbsSourceBatch:
    """Parse MBS ``Data`` rows without projecting medicine assertions."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=SOURCE_ID,
        jurisdiction="AUS",
        transformation="au-mbs-source-xml-v1",
    )
    root = parse_xml(payload, policy=_MBS_POLICY)
    root_name = root.tag.split("}")[-1]
    if root_name != "MBS_XML":
        raise ValueError(f"MBS XML root must be 'MBS_XML', got {root_name!r}")
    data_elements = tuple(root.findall("./Data"))
    if not data_elements:
        raise ValueError("MBS_XML contains no Data records")
    if len(data_elements) != len(root):
        raise ValueError("MBS_XML contains an unexpected non-Data element")

    records: list[MbsSourceRecord] = []
    observed: set[str] = set()
    for ordinal, element in enumerate(data_elements):
        fields = _native_fields(element)
        observed.update(field.name for field in fields)
        item = _required_identity_value(fields, "ItemNum")
        sub_item = next(
            (
                field.value or ""
                for field in fields
                if field.name == "SubItemNum"
            ),
            "",
        ).strip()
        start = next(
            (
                field.value or ""
                for field in fields
                if field.name == "ItemStartDate"
            ),
            "",
        ).strip()
        records.append(
            MbsSourceRecord(
                source_record_id=(
                    f"{SOURCE_ID}:{item}:{sub_item}:{start}:{ordinal}"
                ),
                source_ordinal=ordinal,
                fields=fields,
                provenance=provenance,
            )
        )
    observed_fields = tuple(sorted(observed))
    return MbsSourceBatch(
        schema_era=receipt.source.catalog_version,
        observed_fields=observed_fields,
        missing_native_fields=tuple(
            field for field in MBS_NATIVE_FIELDS if field not in observed
        ),
        records=tuple(records),
        provenance=provenance,
    )


def qualify_legacy_mbs_xml(
    payload: bytes,
    receipt: SourceReceipt,
) -> MbsSourceBatch:
    """Qualify the exact July 2025 donor payload and its schema denominator."""
    if len(payload) != LEGACY_MBS_BYTES or not receipt.payload.matches(payload):
        raise ValueError("payload is not the exact July 2025 MBS payload")
    if receipt.payload.sha256 != LEGACY_MBS_SHA256:
        raise ValueError("payload is not the exact July 2025 MBS payload")
    batch = parse_mbs_source_xml(payload, receipt)
    if batch.record_count != LEGACY_MBS_RECORDS:
        raise ValueError("July 2025 MBS record denominator differs")
    if batch.observed_fields != MBS_NATIVE_FIELDS:
        raise ValueError("July 2025 MBS native field denominator differs")
    distribution = Counter(len(record.fields) for record in batch.records)
    if dict(distribution) != LEGACY_FIELD_COUNT_DISTRIBUTION:
        raise ValueError("July 2025 MBS field-count distribution differs")
    return batch
