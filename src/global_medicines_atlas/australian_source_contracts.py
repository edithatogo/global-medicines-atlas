"""Loss-aware native field denominators for Australian Silver contracts.

These inventories are source projections, not Silver promotion or publication
receipts. They retain all native values before later typed harmonisation.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable, Iterator
from typing import Literal
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import]
    ElementTree as ET,
)

from pydantic import Field, model_validator

from .adapters._receipt import provenance_from_receipt
from .adapters.au_mbs import MBS_NATIVE_FIELDS, MbsSourceBatch
from .adapters.au_mbs_workbook import MbsWorkbookBatch
from .adapters.au_pbs import PBS_V3_NAMESPACE, PBS_XML_POLICY
from .models import FrozenModel, Provenance
from .parser_safety import parse_xml
from .receipts import SourceReceipt

SourceId = Literal["au-mbs", "au-mbs-p7-legacy-workbook", "au-pbs"]
ValueState = Literal["missing_field", "null", "value"]
ValueType = Literal[
    "identifier",
    "source_code",
    "source_text",
    "source_date",
    "aud_decimal",
    "decimal",
    "percentage",
]
TargetTable = Literal[
    "services",
    "hierarchy",
    "descriptions",
    "fees",
    "benefits",
    "caps",
]


class AustralianTableContract(FrozenModel):
    """Prevent native table identity from silently becoming another claim."""

    schema_version: Literal["1.0"] = "1.0"
    source_id: SourceId
    subject_kind: Literal["service", "pbs_item", "terminology_reference"]
    dimension: Literal["service_benefit", "funding", "formulary", "terminology"]
    mapping_status: Literal["source_native"] = "source_native"
    absence_interpretation: Literal["unknown"] = "unknown"

    @model_validator(mode="after")
    def dimensions_match_source(self) -> AustralianTableContract:
        allowed = (
            {("service", "service_benefit")}
            if self.source_id != "au-pbs"
            else {
                ("pbs_item", "funding"),
                ("pbs_item", "formulary"),
                ("terminology_reference", "terminology"),
            }
        )
        if (self.subject_kind, self.dimension) not in allowed:
            raise ValueError("table subject/dimension does not match source")
        return self


class MbsFieldContract(FrozenModel):
    """One native MBS field and its intended typed Silver destination."""

    native_name: str = Field(min_length=1)
    target_table: TargetTable
    value_type: ValueType

    @model_validator(mode="after")
    def mapping_matches_native_field(self) -> MbsFieldContract:
        if _MBS_FIELDS.get(self.native_name) != (
            self.target_table,
            self.value_type,
        ):
            raise ValueError("native MBS field mapping differs from contract")
        return self


# Types describe the later conversion contract; no source value is converted
# or interpreted here. In particular DerivedFee remains an expression/text.
_MBS_FIELDS: dict[str, tuple[TargetTable, ValueType]] = {
    "Anaes": ("services", "source_code"),
    "AnaesChange": ("services", "source_code"),
    "BasicUnits": ("services", "decimal"),
    "Benefit100": ("benefits", "aud_decimal"),
    "Benefit75": ("benefits", "aud_decimal"),
    "Benefit85": ("benefits", "aud_decimal"),
    "BenefitStartDate": ("benefits", "source_date"),
    "BenefitType": ("benefits", "source_code"),
    "Category": ("hierarchy", "source_code"),
    "DerivedFee": ("fees", "source_text"),
    "DerivedFeeStartDate": ("fees", "source_date"),
    "Description": ("descriptions", "source_text"),
    "DescriptionStartDate": ("descriptions", "source_date"),
    "DescriptorChange": ("descriptions", "source_code"),
    "EMSNCap": ("caps", "source_code"),
    "EMSNChange": ("caps", "source_code"),
    "EMSNChangeDate": ("caps", "source_date"),
    "EMSNDescription": ("caps", "source_text"),
    "EMSNEndDate": ("caps", "source_date"),
    "EMSNFixedCapAmount": ("caps", "aud_decimal"),
    "EMSNMaximumCap": ("caps", "aud_decimal"),
    "EMSNPercentageCap": ("caps", "percentage"),
    "EMSNStartDate": ("caps", "source_date"),
    "FeeChange": ("fees", "source_code"),
    "FeeStartDate": ("fees", "source_date"),
    "FeeType": ("fees", "source_code"),
    "Group": ("hierarchy", "source_code"),
    "ItemChange": ("services", "source_code"),
    "ItemEndDate": ("services", "source_date"),
    "ItemNum": ("services", "identifier"),
    "ItemStartDate": ("services", "source_date"),
    "ItemType": ("services", "source_code"),
    "NewItem": ("services", "source_code"),
    "ProviderType": ("services", "source_code"),
    "QFEEndDate": ("services", "source_date"),
    "QFEStartDate": ("services", "source_date"),
    "ScheduleFee": ("fees", "aud_decimal"),
    "SubGroup": ("hierarchy", "source_code"),
    "SubHeading": ("hierarchy", "source_code"),
    "SubItemNum": ("services", "identifier"),
}


def mbs_field_contracts() -> tuple[MbsFieldContract, ...]:
    """Return a complete, ordered, explicit mapping of all native MBS fields."""
    if set(_MBS_FIELDS) != set(MBS_NATIVE_FIELDS):
        raise ValueError("MBS field contract denominator differs from adapter")
    return tuple(
        MbsFieldContract(
            native_name=name,
            target_table=_MBS_FIELDS[name][0],
            value_type=_MBS_FIELDS[name][1],
        )
        for name in MBS_NATIVE_FIELDS
    )


class SourceFieldBinding(FrozenModel):
    """Immutable source identity for a native projection, not a rights grant."""

    source_id: SourceId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_era: str = Field(min_length=1)


class NativeFieldOccurrence(SourceFieldBinding):
    """A value/state and address within one source-native record."""

    record_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    schema_path: str = Field(min_length=1)
    value: str | None
    state: ValueState

    @model_validator(mode="after")
    def state_matches_value(self) -> NativeFieldOccurrence:
        if (self.state == "value") != (self.value is not None):
            raise ValueError("native value and state disagree")
        return self


class NativeFieldCount(FrozenModel):
    """Denominator for one native schema path, including missing/null slots."""

    schema_path: str
    missing_count: int = Field(ge=0)
    null_count: int = Field(ge=0)
    value_count: int = Field(ge=0)


class NativeFieldCoverage(SourceFieldBinding):
    """Content-bound structural coverage; not evidence of current coverage."""

    schema_version: Literal["1.0"] = "1.0"
    record_count: int = Field(ge=1)
    fields: tuple[NativeFieldCount, ...] = Field(min_length=1)
    denominator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def denominators_are_consistent(self) -> NativeFieldCoverage:
        paths = tuple(field.schema_path for field in self.fields)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("coverage paths must be sorted and unique")
        if any(
            field.missing_count + field.null_count + field.value_count == 0
            for field in self.fields
        ):
            raise ValueError("coverage field denominator must be non-empty")
        if self.record_count > self.occurrence_count:
            raise ValueError(
                "record denominator exceeds occurrence denominator"
            )
        return self

    @property
    def field_count(self) -> int:
        """Return the number of distinct native schema paths."""
        return len(self.fields)

    @property
    def missing_count(self) -> int:
        """Return absent expected native field slots."""
        return sum(field.missing_count for field in self.fields)

    @property
    def null_count(self) -> int:
        """Return present native slots with a null value."""
        return sum(field.null_count for field in self.fields)

    @property
    def value_count(self) -> int:
        """Return present native slots with a value, including empty strings."""
        return sum(field.value_count for field in self.fields)

    @property
    def occurrence_count(self) -> int:
        """Return all observed and expected-missing slots."""
        return self.missing_count + self.null_count + self.value_count


def _binding(provenance: Provenance, schema_era: str) -> SourceFieldBinding:
    return SourceFieldBinding.model_validate({
        "source_id": provenance.source_id,
        "source_sha256": provenance.source_sha256,
        "schema_era": schema_era,
    })


def _field(
    binding: SourceFieldBinding,
    record_id: str,
    path: str,
    schema_path: str,
    value: str | None,
    *,
    present: bool = True,
) -> NativeFieldOccurrence:
    return NativeFieldOccurrence(
        source_id=binding.source_id,
        source_sha256=binding.source_sha256,
        schema_era=binding.schema_era,
        record_id=record_id,
        path=path,
        schema_path=schema_path,
        value=value,
        state="missing_field"
        if not present
        else "null"
        if value is None
        else "value",
    )


def mbs_native_fields(batch: MbsSourceBatch) -> Iterator[NativeFieldOccurrence]:
    """Yield all 40 expected fields for each bounded native MBS record."""
    batch = MbsSourceBatch.model_validate(batch.model_dump())
    if batch.provenance.source_id != batch.source_id:
        raise ValueError("MBS source/provenance mismatch")
    binding = _binding(batch.provenance, batch.schema_era)
    contracts = mbs_field_contracts()
    for record in batch.records:
        if record.provenance != batch.provenance:
            raise ValueError("MBS record/provenance mismatch")
        values = {field.name: field.value for field in record.fields}
        if set(values) - set(MBS_NATIVE_FIELDS):
            raise ValueError("MBS native field is not covered by the contract")
        for contract in contracts:
            name = contract.native_name
            path = f"/MBS_XML/Data/{name}"
            yield _field(
                binding,
                record.source_record_id,
                path,
                path,
                values.get(name),
                present=name in values,
            )


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def workbook_native_fields(
    batch: MbsWorkbookBatch,
) -> Iterator[NativeFieldOccurrence]:
    """Yield every sheet/cell property without calculating formulas or dates."""
    batch = MbsWorkbookBatch.model_validate(batch.model_dump())
    if batch.provenance.source_id != batch.source_id:
        raise ValueError("workbook source/provenance mismatch")
    binding = _binding(batch.provenance, batch.schema_era)
    paths: set[str] = set()
    for sheet in batch.sheets:
        if sheet.path in paths:
            raise ValueError("duplicate workbook sheet path")
        paths.add(sheet.path)
        prefix = f"/sheets/{_pointer(sheet.path)}"
        for name, value in (
            ("name", sheet.name),
            ("relationship_id", sheet.relationship_id),
            ("path", sheet.path),
            ("dimension", sheet.dimension),
        ):
            path = f"{prefix}/{name}"
            yield _field(binding, sheet.path, path, path, value)
        for cell in sheet.cells:
            match = re.fullmatch(r"([A-Z]+)[1-9][0-9]*", cell.coordinate)
            if match is None:
                raise ValueError("invalid workbook cell coordinate")
            for name, value in (
                ("coordinate", cell.coordinate),
                ("cell_type", cell.cell_type),
                (
                    "style_index",
                    str(cell.style_index)
                    if cell.style_index is not None
                    else None,
                ),
                ("formula", cell.formula),
                ("raw_value", cell.raw_value),
                ("display_value", cell.display_value),
            ):
                yield _field(
                    binding,
                    f"{sheet.path}#{cell.coordinate}",
                    f"{prefix}/cells/{cell.coordinate}/{name}",
                    f"{prefix}/columns/{match.group(1)}/{name}",
                    value,
                )


def _xml_fields(
    element: ET.Element,
    binding: SourceFieldBinding,
    record_id: str,
    schema_path: str,
) -> Iterator[NativeFieldOccurrence]:
    for name, value in (("text", element.text), ("tail", element.tail)):
        yield _field(
            binding,
            record_id,
            f"{record_id}/{name}",
            f"{schema_path}/{name}",
            value,
        )
    for name, value in sorted(element.attrib.items()):
        slot = f"attributes/{_pointer(name)}"
        yield _field(
            binding,
            record_id,
            f"{record_id}/{slot}",
            f"{schema_path}/{slot}",
            value,
        )
    counts: Counter[str] = Counter()
    for child in element:
        counts[child.tag] += 1
        name = _pointer(child.tag)
        yield from _xml_fields(
            child,
            binding,
            f"{record_id}/{name}/{counts[child.tag]}",
            f"{schema_path}/{name}",
        )


def pbs_native_fields(
    payload: bytes, receipt: SourceReceipt
) -> Iterator[NativeFieldOccurrence]:
    """Yield every PBS element/text/tail/attribute, including unknown fields.

    The shared bounded parser protects the XML envelope. Native inventory is
    deliberately broader than the selected pharmaceutical-item projection.
    """
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id="au-pbs",
        jurisdiction="AUS",
        transformation="australian-native-field-inventory-v1",
    )
    binding = _binding(provenance, receipt.source.catalog_version)
    root = parse_xml(payload, policy=PBS_XML_POLICY)
    if root.tag not in {
        f"{{{PBS_V3_NAMESPACE}}}root",
        f"{{{PBS_V3_NAMESPACE}}}schedule",
    }:
        raise ValueError("PBS namespace/root does not match source contract")
    path = f"/{_pointer(root.tag)}"
    yield from _xml_fields(root, binding, f"{path}/1", path)


def summarize_native_fields(
    fields: Iterable[NativeFieldOccurrence],
) -> NativeFieldCoverage:
    """Hash ordered slots and summarize exact field/state denominators.

    Values are consumed incrementally. Identity sets detect duplicates and
    retain the input's native record denominator; callers must use bounded
    source inputs. This receipt alone does not establish acquisition or rights.
    """
    binding: SourceFieldBinding | None = None
    seen: set[tuple[str, str]] = set()
    records: set[str] = set()
    counts: dict[str, Counter[str]] = {}
    digest = hashlib.sha256()
    for supplied in fields:
        field = NativeFieldOccurrence.model_validate(supplied.model_dump())
        current = SourceFieldBinding(
            source_id=field.source_id,
            source_sha256=field.source_sha256,
            schema_era=field.schema_era,
        )
        if binding is not None and current != binding:
            raise ValueError("native field source bindings differ")
        binding = current
        key = (field.record_id, field.path)
        if key in seen:
            raise ValueError("duplicate native field identity")
        seen.add(key)
        records.add(field.record_id)
        counts.setdefault(field.schema_path, Counter())[field.state] += 1
        digest.update(field.model_dump_json().encode())
        digest.update(b"\n")
    if binding is None:
        raise ValueError("native field denominator is empty")
    return NativeFieldCoverage(
        source_id=binding.source_id,
        source_sha256=binding.source_sha256,
        schema_era=binding.schema_era,
        record_count=len(records),
        denominator_sha256=digest.hexdigest(),
        fields=tuple(
            NativeFieldCount(
                schema_path=path,
                missing_count=count["missing_field"],
                null_count=count["null"],
                value_count=count["value"],
            )
            for path, count in sorted(counts.items())
        ),
    )
