"""Candidate-only mappings from the qualified legacy workbook profile to XML.

The workbook and XML are independent source artefacts.  Exact header spelling
allows a structural mapping, but does not prove that values have identical
meaning across releases.  Legacy annotations remain source-only assertions.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Literal, cast

from pydantic import ConfigDict, Field, model_validator

from .australian_source_contracts import mbs_field_contracts
from .mbs_historical_comparison import MbsComparisonCohort, MbsNativeKey
from .mbs_workbook_domain import (
    LEGACY_SHEET_PROFILES,
    iter_workbook_domain_batches,
)
from .models import FrozenModel
from .receipts import EvidenceClass, SourceReceipt


class MbsWorkbookXmlFieldMapping(FrozenModel):
    """One exhaustive legacy header disposition."""

    workbook_native_header: str = Field(min_length=1)
    xml_native_name: str | None = None
    disposition: Literal["exact_native_header", "legacy_annotation_only"]

    @model_validator(mode="after")
    def target_matches_disposition(self) -> MbsWorkbookXmlFieldMapping:
        if (self.disposition == "exact_native_header") != (
            self.xml_native_name is not None
        ):
            raise ValueError("workbook/XML mapping disposition differs")
        if self.xml_native_name is not None and (
            self.xml_native_name != self.workbook_native_header
        ):
            raise ValueError(
                "workbook/XML exact mapping renamed a native field"
            )
        return self


class MbsWorkbookXmlSchemaMapping(FrozenModel):
    """Content-bound mapping for the qualified P7 header profile."""

    schema_id: Literal["global-medicines-atlas.mbs-workbook-xml-mapping"] = (
        "global-medicines-atlas.mbs-workbook-xml-mapping"
    )
    schema_version: Literal[1] = 1
    workbook_source_id: Literal["au-mbs-p7-legacy-workbook"] = (
        "au-mbs-p7-legacy-workbook"
    )
    xml_source_id: Literal["au-mbs"] = "au-mbs"
    workbook_schema_era: Literal["mbs-p7-2024-07-headers-v1"] = (
        "mbs-p7-2024-07-headers-v1"
    )
    xml_schema_era: str = Field(min_length=1)
    fields: tuple[MbsWorkbookXmlFieldMapping, ...]
    mapping_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exhaustive_and_bound(self) -> MbsWorkbookXmlSchemaMapping:
        if (
            not self.xml_schema_era.strip()
            or self.xml_schema_era.strip() != self.xml_schema_era
        ):
            raise ValueError("XML schema era must be nonblank and unpadded")
        if self.fields != _expected_fields():
            raise ValueError("workbook/XML field mapping differs")
        if self.mapping_sha256 != _digest(self, "mapping_sha256"):
            raise ValueError("workbook/XML mapping digest differs")
        return self


class MbsWorkbookXmlCandidateMatch(FrozenModel):
    """A source-addressed workbook row's literal XML-key match result."""

    workbook_occurrence_id: str = Field(min_length=1)
    sheet_name: str = Field(min_length=1)
    row_index: int = Field(strict=True, ge=2)
    item_num: str
    sub_item_state: Literal["missing", "null", "value"]
    sub_item_value: str | None = None
    xml_native_id: str
    match_status: Literal[
        "matched_once",
        "not_observed_complete_cohort",
        "outside_selection_unknown",
    ]

    @model_validator(mode="after")
    def key_is_bound(self) -> MbsWorkbookXmlCandidateMatch:
        key = MbsNativeKey(
            item_num=self.item_num,
            sub_item_state=self.sub_item_state,
            sub_item_value=self.sub_item_value,
        )
        if self.xml_native_id != key.content_id():
            raise ValueError("workbook/XML candidate key differs")
        return self


class MbsWorkbookXmlCandidateReport(FrozenModel):
    """Deterministic structural comparison; never real-source qualification."""

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal[
        "global-medicines-atlas.mbs-workbook-xml-candidate-report"
    ] = "global-medicines-atlas.mbs-workbook-xml-candidate-report"
    schema_version: Literal[1] = 1
    qualification: Literal["fixture_candidate_only"] = "fixture_candidate_only"
    absence_interpretation: Literal["unknown"] = "unknown"
    semantic_equivalence_asserted: Literal[False] = False
    publication_performed: Literal[False] = False
    evidence_class: Literal["synthetic"] = "synthetic"
    workbook_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workbook_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mapping: MbsWorkbookXmlSchemaMapping
    xml: MbsComparisonCohort
    matches: tuple[MbsWorkbookXmlCandidateMatch, ...]
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def consistent_and_bound(self) -> MbsWorkbookXmlCandidateReport:
        if self.xml.snapshot.schema_era != self.mapping.xml_schema_era:
            raise ValueError("candidate XML era differs from mapping")
        if self.xml.evidence_class != "synthetic":
            raise ValueError("candidate report requires synthetic XML evidence")
        counts = Counter(row.native_id for row in self.xml.snapshot.rows)
        if any(
            match.match_status
            != (
                "matched_once"
                if counts[match.xml_native_id] == 1
                else "outside_selection_unknown"
                if self.xml.omitted_record_count > 0
                else "not_observed_complete_cohort"
            )
            for match in self.matches
        ):
            raise ValueError("workbook/XML match status differs")
        if (
            tuple(
                sorted(self.matches, key=lambda row: row.workbook_occurrence_id)
            )
            != self.matches
        ):
            raise ValueError("workbook/XML matches are not deterministic")
        if self.report_sha256 != _digest(self, "report_sha256"):
            raise ValueError("workbook/XML report digest differs")
        return self


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def _digest(model: FrozenModel, field: str) -> str:
    return hashlib.sha256(
        _canonical(
            model.model_dump(exclude={field}, exclude_computed_fields=True)
        )
    ).hexdigest()


def _expected_fields() -> tuple[MbsWorkbookXmlFieldMapping, ...]:
    xml_names = {field.native_name for field in mbs_field_contracts()}
    headers = sorted({
        header
        for _, _, profile in LEGACY_SHEET_PROFILES
        for _, header in profile
    })
    return tuple(
        MbsWorkbookXmlFieldMapping(
            workbook_native_header=header,
            xml_native_name=header if header in xml_names else None,
            disposition="exact_native_header"
            if header in xml_names
            else "legacy_annotation_only",
        )
        for header in headers
    )


def declare_mbs_workbook_xml_mapping(
    *, xml_schema_era: str
) -> MbsWorkbookXmlSchemaMapping:
    """Declare the exhaustive qualified-header mapping without semantic promotion."""
    fields = _expected_fields()
    provisional = MbsWorkbookXmlSchemaMapping.model_construct(
        xml_schema_era=xml_schema_era, fields=fields, mapping_sha256="0" * 64
    )
    return MbsWorkbookXmlSchemaMapping(
        xml_schema_era=xml_schema_era,
        fields=fields,
        mapping_sha256=_digest(provisional, "mapping_sha256"),
    )


def build_mbs_workbook_xml_candidate_report(  # ruff: ignore[too-many-locals]
    workbook_payload: bytes,
    workbook_receipt: SourceReceipt,
    xml: MbsComparisonCohort,
    mapping: MbsWorkbookXmlSchemaMapping,
) -> MbsWorkbookXmlCandidateReport:
    """Compare literal workbook row keys with an existing XML candidate cohort."""
    workbook_receipt = SourceReceipt.model_validate(
        workbook_receipt.model_dump()
    )
    xml = MbsComparisonCohort.model_validate(xml.model_dump())
    mapping = MbsWorkbookXmlSchemaMapping.model_validate(mapping.model_dump())
    if workbook_receipt.evidence_class is not EvidenceClass.SYNTHETIC:
        raise ValueError(
            "candidate report requires synthetic workbook evidence"
        )
    if xml.evidence_class != "synthetic":
        raise ValueError("candidate report requires synthetic XML evidence")
    grouped: dict[tuple[str, int], dict[str, object]] = {}
    for batch in iter_workbook_domain_batches(
        workbook_payload, workbook_receipt
    ):
        for cell in batch.to_pylist():
            if cell["row_kind"] != "data_candidate":
                continue
            grouped.setdefault((cell["sheet_path"], cell["row_index"]), cell)
            if cell["native_header"] in {"ItemNum", "SubItemNum"}:
                grouped[cell["sheet_path"], cell["row_index"]][
                    cell["native_header"]
                ] = cell
    matches: list[MbsWorkbookXmlCandidateMatch] = []
    for (path, row_index), row in grouped.items():
        item = row.get("ItemNum")
        if not isinstance(item, dict):
            continue
        item_value = cast("dict[str, object]", item).get("display_value")
        if not isinstance(item_value, str):
            continue
        sub = row.get("SubItemNum")
        observed_sub = (
            cast("dict[str, object]", sub).get("display_value")
            if isinstance(sub, dict)
            else None
        )
        sub_value = observed_sub if isinstance(observed_sub, str) else None
        sub_state: Literal["missing", "null", "value"] = (
            "missing"
            if not isinstance(sub, dict)
            else "null"
            if sub_value is None
            else "value"
        )
        key = MbsNativeKey(
            item_num=item_value,
            sub_item_state=sub_state,
            sub_item_value=sub_value,
        )
        counts = Counter(native.native_id for native in xml.snapshot.rows)
        observed = counts[key.content_id()] == 1
        matches.append(
            MbsWorkbookXmlCandidateMatch(
                workbook_occurrence_id=f"{workbook_receipt.payload.sha256}:{path}#row={row_index}",
                sheet_name=str(row["sheet_name"]),
                row_index=row_index,
                item_num=item_value,
                sub_item_state=sub_state,
                sub_item_value=sub_value,
                xml_native_id=key.content_id(),
                match_status="matched_once"
                if observed
                else "outside_selection_unknown"
                if xml.omitted_record_count > 0
                else "not_observed_complete_cohort",
            )
        )
    matches_tuple = tuple(
        sorted(matches, key=lambda row: row.workbook_occurrence_id)
    )
    provisional = MbsWorkbookXmlCandidateReport.model_construct(
        workbook_source_sha256=workbook_receipt.payload.sha256,
        workbook_receipt_sha256=workbook_receipt.digest(),
        mapping=mapping,
        xml=xml,
        matches=matches_tuple,
        report_sha256="0" * 64,
    )
    return MbsWorkbookXmlCandidateReport(
        workbook_source_sha256=workbook_receipt.payload.sha256,
        workbook_receipt_sha256=workbook_receipt.digest(),
        mapping=mapping,
        xml=xml,
        matches=matches_tuple,
        report_sha256=_digest(provisional, "report_sha256"),
    )
