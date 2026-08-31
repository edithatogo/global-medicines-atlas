"""Pure receipt-bound MBS cohort candidates over a complete bounded XML scan.

No acquisition, date interpretation, Gold promotion or publication occurs here.
Completeness describes only an explicit native-key selection within the parsed
payload, not the MBS programme or all history. Comparison XML schema era is an
explicit caller declaration, separate from the receipt's source release label;
neither is independently qualified here. Tests use synthetic source bytes.
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from .adapters.au_mbs import MbsSourceRecord, parse_mbs_source_xml
from .australian_source_contracts import TargetTable, mbs_field_contracts
from .historical_comparison import (
    MAX_NATIVE_BYTES,
    MAX_ROWS,
    MAX_SNAPSHOT_FIELDS,
    NativeField,
    NativeIdentity,
    NativeRow,
    NativeSnapshot,
)
from .models import FrozenModel
from .receipts import AcquisitionStatus, EvidenceClass, SourceReceipt

IDENTITY_PROFILE = "mbs-item-subitem-literal-v1"
SELECTION_PROFILE = "mbs-native-keys-v1"
Cohort = Literal["synthetic", "legacy", "historical", "current"]
Ordinal = Annotated[int, Field(strict=True, ge=0)]


class MbsNativeKey(FrozenModel):
    """Exact source text/states, never stripped or coerced numeric identity."""

    model_config = ConfigDict(revalidate_instances="always")
    item_num: NativeIdentity
    sub_item_state: Literal["missing", "null", "value"]
    sub_item_value: str | None = Field(default=None, max_length=16384)

    @model_validator(mode="after")
    def valid_subitem_state(self) -> MbsNativeKey:
        if (self.sub_item_state == "value") != (
            self.sub_item_value is not None
        ):
            raise ValueError("subitem state and value disagree")
        return self

    def content_id(self) -> str:
        """Bind all literal key fields without delimiter collisions."""
        return "mbs-key:" + sha256(_canonical(self.model_dump())).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _scope(keys: tuple[MbsNativeKey, ...]) -> str:
    manifest = {
        "profile": SELECTION_PROFILE,
        "keys": [key.model_dump() for key in keys],
    }
    return f"{SELECTION_PROFILE}:" + sha256(_canonical(manifest)).hexdigest()


def _selection(keys: tuple[MbsNativeKey, ...]) -> tuple[MbsNativeKey, ...]:
    if not 1 <= len(keys) <= MAX_ROWS:
        raise ValueError("selection must contain between 1 and 4096 keys")
    validated = tuple(
        MbsNativeKey.model_validate(key.model_dump()) for key in keys
    )
    by_id = {key.content_id(): key for key in validated}
    if len(by_id) != len(validated):
        raise ValueError("selection contains duplicate keys")
    return tuple(by_id[key] for key in sorted(by_id))


class MbsComparisonCohort(FrozenModel):
    """Manifest-bound selection with full parsed and omitted denominators.

    Construction checks internal consistency, not source bytes. Only the
    producer binds supplied bytes to B1/B2. Catalog version is a declared source
    release label, not an XML schema era, immutable content revision or
    qualification receipt.
    """

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal["global-medicines-atlas.mbs-comparison-cohort"] = (
        "global-medicines-atlas.mbs-comparison-cohort"
    )
    schema_version: Literal[1] = 1
    qualification: Literal["source_native_candidate"] = (
        "source_native_candidate"
    )
    selected_native_keys: tuple[MbsNativeKey, ...] = Field(
        min_length=1, max_length=MAX_ROWS
    )
    snapshot: NativeSnapshot
    evidence_class: Literal["synthetic", "live"]
    source_record_count: int = Field(strict=True, ge=1, le=300000)
    omitted_record_count: int = Field(strict=True, ge=0, le=300000)
    source_ordinals: tuple[Ordinal, ...] = Field(max_length=MAX_ROWS)

    @model_validator(mode="after")
    def binds_selection(self) -> MbsComparisonCohort:
        keys = _selection(self.selected_native_keys)
        snapshot = self.snapshot
        if keys != self.selected_native_keys or snapshot.scope_id != _scope(
            keys
        ):
            raise ValueError("cohort selection identity mismatch")
        if (
            snapshot.source_id != "au-mbs"
            or snapshot.dimension != "service_benefit"
            or snapshot.identity_profile != IDENTITY_PROFILE
        ):
            raise ValueError("cohort source/profile mismatch")
        names = tuple(
            c.native_name
            for c in mbs_field_contracts()
            if c.target_table == snapshot.table
        )
        if not names:
            raise ValueError("unknown MBS comparison table")
        if (snapshot.cohort == "synthetic") != (
            self.evidence_class == "synthetic"
        ):
            raise ValueError("cohort evidence class mismatch")
        if any(
            tuple(field.name for field in row.fields) != names
            for row in snapshot.rows
        ):
            raise ValueError("cohort native fields differ from selected table")
        if not snapshot.complete or snapshot.declared_rows != len(
            snapshot.rows
        ):
            raise ValueError("selection denominator must be complete")
        if (
            self.source_record_count
            != len(snapshot.rows) + self.omitted_record_count
        ):
            raise ValueError("full source denominator mismatch")
        if len(self.source_ordinals) != len(snapshot.rows) or any(
            type(value) is not int for value in self.source_ordinals
        ):
            raise ValueError("source ordinal count/type mismatch")
        if tuple(
            sorted(set(self.source_ordinals))
        ) != self.source_ordinals or any(
            value < 0 or value >= self.source_record_count
            for value in self.source_ordinals
        ):
            raise ValueError("source ordinals must preserve source order")
        allowed = {key.content_id() for key in keys}
        if any(row.native_id not in allowed for row in snapshot.rows):
            raise ValueError("row is outside explicit selection")
        if any(
            row.occurrence_id.rsplit(":", 1)[-1] != str(ordinal)
            for row, ordinal in zip(
                snapshot.rows, self.source_ordinals, strict=True
            )
        ):
            raise ValueError("row occurrence does not match source ordinal")
        _check_native_rows(snapshot, self.source_ordinals, keys)
        return self


def _check_native_rows(
    snapshot: NativeSnapshot,
    ordinals: tuple[int, ...],
    keys: tuple[MbsNativeKey, ...],
) -> None:
    selected = {key.content_id(): key for key in keys}
    for row, ordinal in zip(snapshot.rows, ordinals, strict=True):
        key = selected[row.native_id]
        fields = {field.name: field for field in row.fields}
        expected = {
            "ItemNum": NativeField(
                name="ItemNum", state="value", value=key.item_num
            ),
            "SubItemNum": NativeField(
                name="SubItemNum",
                state=key.sub_item_state,
                value=key.sub_item_value,
            ),
        }
        if any(
            fields[name] != value
            for name, value in expected.items()
            if name in fields
        ):
            raise ValueError("native identity field differs from selected key")
        prefix = f"au-mbs:{key.item_num.strip()}:{(key.sub_item_value or '').strip()}:"
        if not row.occurrence_id.startswith(prefix):
            raise ValueError("row occurrence differs from native key")
        if "ItemStartDate" in fields:
            start = (fields["ItemStartDate"].value or "").strip()
            if row.occurrence_id != f"{prefix}{start}:{ordinal}":
                raise ValueError(
                    "row occurrence differs from native start text"
                )


def _key(record: MbsSourceRecord) -> MbsNativeKey:
    fields = {field.name: field.value for field in record.fields}
    item = fields["ItemNum"]
    if item is None:
        raise ValueError("MBS item identity is missing")
    value = fields.get("SubItemNum")
    return MbsNativeKey(
        item_num=item,
        sub_item_state="missing"
        if "SubItemNum" not in fields
        else "null"
        if value is None
        else "value",
        sub_item_value=value,
    )


def _fields(
    record: MbsSourceRecord, names: tuple[str, ...]
) -> tuple[NativeField, ...]:
    native = {field.name: field.value for field in record.fields}
    return tuple(
        NativeField(
            name=name,
            state="missing"
            if name not in native
            else "null"
            if native[name] is None
            else "value",
            value=native.get(name),
        )
        for name in names
    )


def _rows(
    records: tuple[MbsSourceRecord, ...],
    keys: tuple[MbsNativeKey, ...],
    names: tuple[str, ...],
) -> tuple[tuple[NativeRow, ...], tuple[int, ...]]:
    allowed = {key.content_id() for key in keys}
    rows: list[NativeRow] = []
    ordinals: list[int] = []
    size = 0
    for record in records:
        identity = _key(record).content_id()
        if identity not in allowed:
            continue
        if (
            len(rows) >= MAX_ROWS
            or (len(rows) + 1) * len(names) > MAX_SNAPSHOT_FIELDS
        ):
            raise ValueError("selected row/field limit exceeded")
        fields = _fields(record, names)
        size += len(identity.encode()) + len(record.source_record_id.encode())
        size += sum(
            len(field.name.encode()) + len((field.value or "").encode())
            for field in fields
        )
        if size > MAX_NATIVE_BYTES:
            raise ValueError("selected native byte limit exceeded")
        rows.append(
            NativeRow(
                native_id=identity,
                occurrence_id=record.source_record_id,
                fields=fields,
            )
        )
        ordinals.append(record.source_ordinal)
    return tuple(rows), tuple(ordinals)


def build_mbs_comparison_cohort(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    table: TargetTable,
    selected_native_keys: tuple[MbsNativeKey, ...],
    schema_era: str,
    expected_source_revision: str,
    cohort: Cohort | None = None,
) -> MbsComparisonCohort:
    """Fully scan receipt-matched XML, then select all requested occurrences.

    LIVE evidence requires an explicit non-synthetic cohort label. Neither that
    label nor the caller-declared schema era establishes real-source
    qualification or publication authority. The source revision must match the
    receipt's catalog version exactly. No date stripping or schema inference,
    retrieval or file writes are performed.
    """
    keys = _selection(selected_native_keys)
    names = tuple(
        c.native_name for c in mbs_field_contracts() if c.target_table == table
    )
    if not names:
        raise ValueError("unknown MBS comparison table")
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    if (
        receipt.evidence_class
        not in {EvidenceClass.SYNTHETIC, EvidenceClass.LIVE}
        or receipt.retrieval.status is not AcquisitionStatus.SUCCEEDED
    ):
        raise ValueError(
            "comparison producer requires successful synthetic or live evidence"
        )
    cohort = _cohort(receipt.evidence_class, cohort)
    if not schema_era.strip() or schema_era != schema_era.strip():
        raise ValueError("comparison schema era must be nonblank and unpadded")
    if (
        not expected_source_revision.strip()
        or expected_source_revision != expected_source_revision.strip()
        or expected_source_revision != receipt.source.catalog_version
    ):
        raise ValueError("receipt source revision mismatch")
    batch = parse_mbs_source_xml(payload, receipt)
    rows, ordinals = _rows(batch.records, keys, names)
    snapshot = NativeSnapshot(
        source_id=batch.source_id,
        table=table,
        dimension="service_benefit",
        schema_era=schema_era,
        identity_profile=IDENTITY_PROFILE,
        scope_id=_scope(keys),
        source_revision=receipt.source.catalog_version,
        source_path="/MBS_XML/Data",
        b1_sha256=receipt.digest(),
        b2_sha256=receipt.payload.sha256,
        observed_at=receipt.retrieval.retrieved_at,
        cohort=cohort,
        declared_rows=len(rows),
        complete=True,
        rows=rows,
    )
    return MbsComparisonCohort(
        selected_native_keys=keys,
        snapshot=snapshot,
        evidence_class="synthetic"
        if receipt.evidence_class is EvidenceClass.SYNTHETIC
        else "live",
        source_record_count=batch.record_count,
        omitted_record_count=batch.record_count - len(rows),
        source_ordinals=ordinals,
    )


def _cohort(evidence_class: EvidenceClass, cohort: Cohort | None) -> Cohort:
    if evidence_class is EvidenceClass.SYNTHETIC:
        if cohort not in {None, "synthetic"}:
            raise ValueError("synthetic evidence cannot claim a real cohort")
        return "synthetic"
    if cohort not in {"legacy", "historical", "current"}:
        raise ValueError("live evidence requires an explicit real cohort")
    return cohort
