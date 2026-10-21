"""Exact-source structural roles from the qualified April PBS path inventory.

Roles describe native structure only. They establish no payable amount,
reference resolution, clinical meaning, current status or cross-era equivalence.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import pyarrow as pa

from .pbs_historical_silver import iter_pbs_historical_silver_batches
from .pbs_member_identity import PbsXmlMemberBinding
from .receipts import SourceReceipt

INVENTORY = "quality/qualifications/pbs-schema-paths-20261022-39667604237.json"
INVENTORY_SHA256 = (
    "6da85f3e3526a52dca7b0f41206b5ec1afde854f89d858ae659867827219408b"
)
MEMBER_SHA256 = (
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
)
PBS = "{http://schema.pbs.gov.au/}"
EXPECTED_FIELDS = 18208758
EXPECTED_PATHS = 5163


def _entity_path(path: str) -> str:
    if "/attributes/" in path:
        return path.split("/attributes/", 1)[0]
    if path.endswith(("/text", "/tail")):
        return path.rsplit("/", 1)[0]
    raise ValueError("PBS observed native slot path differs")


def _names(path: str) -> tuple[str, ...]:
    return tuple(
        part.replace("~1", "/").replace("~0", "~")
        for part in path.split("/")[1:]
    )


def _role(path: str) -> str:  # ruff: ignore[too-many-return-statements] -- explicit native structural precedence
    names = _names(path)
    if names[:1] != (PBS + "root",):
        return "unmapped"
    if len(names) == 1 or names[1] == PBS + "info":
        return "schedules"
    branch = names[1]
    if branch == PBS + "previous-list":
        return "historical_records"
    if PBS + "drug-references-list" in names:
        return "references"
    if names[-1] == PBS + "amount" and PBS + "price" in names:
        return "prices"
    families = {
        PBS + "prescribing-texts-list": "restrictions",
        PBS + "drugs-list": "products",
        PBS + "pharmaceutical-items-list": "items",
        PBS + "organisations-list": "organisations",
        "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF": "vocabulary_metadata",
    }
    if branch in families:
        return families[branch]
    if branch == PBS + "schedule":
        if PBS + "price" in names:
            return "pricing_components"
        if PBS + "prescribing-rule" in names:
            return "prescribing_rules"
        return "schedules"
    return "unmapped"


@dataclass(frozen=True)
class ObservedDomainProfile:
    """Read-only exact-path allowlist, never a licence or semantic approval."""

    member_sha256: str
    native_fields: int
    roles: Mapping[str, str]
    field_counts: Mapping[str, int]

    def mapping(
        self, member_sha256: str, schema_path: str, record_id: str
    ) -> dict[str, str | None]:
        """Return source structure only after exact member/path checks."""
        if member_sha256 != self.member_sha256:
            raise ValueError("PBS observed profile member identity differs")
        path = _entity_path(schema_path)
        role = self.roles.get(path, "unmapped")
        item_id = None
        if role != "unmapped":
            parts = record_id.split("/")
            if "/" + "/".join(parts[1::2]) != path:
                raise ValueError(
                    "PBS observed schema and occurrence paths differ"
                )
            names = _names(path)
            if names[:3] == (
                PBS + "root",
                PBS + "pharmaceutical-items-list",
                PBS + "pharmaceutical-item",
            ):
                item_id = f"{member_sha256}:{'/'.join(parts[:7])}"
        return {
            "mapping_target": role,
            "mapping_status": "unmapped"
            if role == "unmapped"
            else "source_structure",
            "item_occurrence_id": item_id,
        }


def load_observed_profile(root: Path) -> ObservedDomainProfile:
    """Load only the exact aggregate inventory qualified by run 39667604237."""
    payload = (root / INVENTORY).read_bytes()
    if hashlib.sha256(payload).hexdigest() != INVENTORY_SHA256:
        raise ValueError("PBS observed profile inventory digest differs")
    report = json.loads(payload)
    if (
        report["member_sha256"] != MEMBER_SHA256
        or report["native_fields"] != EXPECTED_FIELDS
        or len(report["paths"]) != EXPECTED_PATHS
    ):
        raise ValueError("PBS observed profile source denominator differs")
    roles: dict[str, str] = {}
    counts: Counter[str] = Counter()
    for row in report["paths"]:
        path = _entity_path(row["schema_path"])
        role = _role(path)
        roles[path] = role
        counts[role] += row["native_fields"]
    if sum(counts.values()) != report["native_fields"]:
        raise ValueError("PBS observed profile field coverage differs")
    return ObservedDomainProfile(
        MEMBER_SHA256,
        report["native_fields"],
        MappingProxyType(roles),
        MappingProxyType(dict(counts)),
    )


def iter_observed_historical_domain_batches(
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    profile: ObservedDomainProfile,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Add explicit structural roles while retaining original native buffers.

    This opt-in candidate uses the native producer's full identity, parsing and
    batch bounds. Unknown paths remain visible. It performs no joins, value
    interpretation, reference resolution, acquisition, admission or publication.
    """
    if binding.member_payload.sha256 != profile.member_sha256:
        raise ValueError("PBS observed profile member identity differs")
    for batch in iter_pbs_historical_silver_batches(
        archive, member, parent, binding, rows_per_batch=rows_per_batch
    ):
        columns = {
            name: cast(
                "list[str]",
                cast("pa.StringArray", batch.column(name)).to_pylist(),
            )
            for name in ("source_sha256", "schema_path", "record_id")
        }
        mappings = list(
            map(
                profile.mapping,
                columns["source_sha256"],
                columns["schema_path"],
                columns["record_id"],
                strict=True,
            )
        )
        schema = batch.schema
        additions: list[pa.Array[Any]] = []
        for name in ("mapping_target", "mapping_status", "item_occurrence_id"):
            field = pa.field(
                name, pa.string(), nullable=name == "item_occurrence_id"
            )
            schema = schema.append(field)  # pyright: ignore[reportUnknownMemberType] -- Arrow schema append stub
            additions.append(
                pa.array([row[name] for row in mappings], type=field.type)
            )
        metadata = dict(schema.metadata or {})
        metadata.update({
            b"mapping_profile": b"pbs-observed-april-2026-structural-v1",
            b"inventory_sha256": INVENTORY_SHA256.encode(),
            b"domain_semantics_qualified": b"false",
        })
        schema = schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType] -- Arrow schema metadata stub
        yield pa.RecordBatch.from_arrays(  # pyright: ignore[reportUnknownMemberType] -- Arrow constructor stub
            [
                *[
                    cast("pa.Array[Any]", batch.column(index))
                    for index in range(batch.num_columns)
                ],
                *additions,
            ],
            schema=schema,
        )
