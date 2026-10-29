"""Direct historical PBS value candidates without intermediate Arrow tables.

The existing parser, lineage validation, mappings, entity construction and value
rules remain authoritative. Only the transport between these layers changes.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import chain, groupby
from typing import Any

import pyarrow as pa

from . import pbs_entities as entities
from .pbs_domain import (  # pyright: ignore[reportPrivateUsage] -- internal validated producer composition
    _mapping,  # pyright: ignore[reportPrivateUsage] -- shared internal mapping
    pbs_domain_schema,
)
from .pbs_historical_silver import (
    _schema as historical_schema,  # pyright: ignore[reportPrivateUsage] -- preserve complete existing schema
)
from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
)
from .pbs_native_values import (  # pyright: ignore[reportPrivateUsage] -- existing conversion rules
    _values,  # pyright: ignore[reportPrivateUsage] -- shared internal conversion
    pbs_value_schema,
)
from .pbs_silver import MAX_BATCH_ROWS
from .pbs_xml_slots import iter_pbs_xml_slots
from .receipts import SourceReceipt


def iter_direct_historical_value_batches(
    archive_payload: bytes,
    member_payload: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Yield the complete existing value schema from validated native slots.

    All native fields and constant provenance survive intact. Element field and
    encoded-byte limits and entity batch limits are inherited unchanged. This
    removes intermediate Arrow materializations, not independent source checks.
    No source meanings, release rights or admissions are qualified here.
    """
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("PBS historical batch size must be between 1 and 4096")
    if not isinstance(parent, SourceReceipt) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance] -- runtime boundary
        binding, PbsXmlMemberBinding
    ):  # pyright: ignore[reportUnnecessaryIsInstance] -- runtime boundary
        raise TypeError("historical parent receipt and member binding required")
    parent = SourceReceipt.model_validate(parent.model_dump())
    binding = validate_pbs_xml_member_binding(
        binding, archive_payload, member_payload, parent
    )
    schema = pbs_value_schema(
        entities._schema(pbs_domain_schema(historical_schema(parent, binding)))  # pyright: ignore[reportPrivateUsage] -- shared exact schema
    )  # pyright: ignore[reportPrivateUsage] -- reuse exact internal entity schema
    bound = {
        "source_id": binding.source.source_id,
        "source_sha256": binding.member_payload.sha256,
        "schema_era": binding.source.catalog_version,
        "receipt_sha256": binding.parent_receipt_sha256,
        "member_binding_sha256": binding.digest(),
        "archive_sha256": binding.archive_payload.sha256,
        "member_path": binding.member_path,
    }
    rows: list[dict[str, Any]] = []
    batch_bytes = 0
    slots = enumerate(iter_pbs_xml_slots(member_payload))
    for _, group in groupby(slots, key=lambda pair: pair[1].record_id):
        first_ordinal, first = next(group)
        mapping = _mapping({
            "record_id": first.record_id,
            "source_sha256": binding.member_payload.sha256,
        })
        fields: list[dict[str, Any]] = []
        field_bytes = 0
        for ordinal, slot in chain(((first_ordinal, first),), group):
            field = {
                **bound,
                "source_field_id": f"{binding.member_payload.sha256}:{slot.path}",
                "source_ordinal": ordinal,
                "record_id": slot.record_id,
                "path": slot.path,
                "schema_path": slot.schema_path,
                "value": slot.value,
                "state": "null" if slot.value is None else "value",
                **mapping,
            }
            field_bytes += entities._encoded_size(field)  # pyright: ignore[reportPrivateUsage] -- exact existing byte accounting
            if (
                len(fields) >= entities.MAX_ELEMENT_FIELDS
                or field_bytes > entities.MAX_ELEMENT_BYTES
            ):
                raise ValueError("PBS entity element exceeds field/byte limit")
            fields.append(field)
        row = entities._row(fields)  # pyright: ignore[reportPrivateUsage] -- exact existing entity projection
        size = (
            entities._encoded_size({**row, "native_fields": []})  # pyright: ignore[reportPrivateUsage] -- shared byte accounting
            + field_bytes
            + len(fields)
            - 1
        )  # pyright: ignore[reportPrivateUsage] -- exact existing entity byte measure
        if size > entities.MAX_BATCH_BYTES:
            raise ValueError("PBS entity exceeds batch byte limit")
        if rows and (
            len(rows) >= rows_per_batch
            or batch_bytes + size > entities.MAX_BATCH_BYTES
        ):
            yield pa.RecordBatch.from_pylist(rows, schema=schema)
            rows, batch_bytes = [], 0
        rows.append({**row, **_values(row)})
        batch_bytes += size
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=schema)
