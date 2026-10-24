"""Value-free crosswalk between PBS date roles and direct restriction paths."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx
    import pyarrow as pa

from .pbs_dates import iter_pbs_date_batches
from .pbs_historical_projections import iter_pbs_historical_entity_batches
from .pbs_historical_qualification import (
    _date_batches,  # pyright: ignore[reportPrivateUsage]
    _denominator,  # pyright: ignore[reportPrivateUsage]
)
from .pbs_hosted_qualification import (
    DATASET,
    MAX_REPORT_BYTES,
    REVISION,
    _RetryBudget,  # pyright: ignore[reportPrivateUsage]
    _verified_inputs,  # pyright: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    from .receipts import SourceReceipt

_RESTRICTION_DATE_PATH = (
    "/{http:~1~1schema.pbs.gov.au~1}root"
    "/{http:~1~1schema.pbs.gov.au~1}prescribing-texts-list"
    "/{http:~1~1schema.pbs.gov.au~1}restriction"
    "/{http:~1~1schema.pbs.gov.au~1}effective"
    "/{http:~1~1schema.pbs.gov.au~1}date/text"
)
_MAX_IDENTITIES = 100_000
_EXPECTED_RESTRICTION_FIELDS = 3028
_EXPECTED_ITEM_DATE_FIELDS = 2798
_EXPECTED_UNMATCHED_DATE_FIELDS = (
    _EXPECTED_RESTRICTION_FIELDS + _EXPECTED_ITEM_DATE_FIELDS
)


def _identity_digest(values: set[str]) -> str:
    encoded = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def reconcile_pbs_date_occurrences(
    batches: Iterable[pa.RecordBatch],
) -> dict[str, Any]:
    """Compare exact native field identities without retaining their values.

    The direct restriction path and item date profile are counted as separate
    sets. Only digests of their source-field identities leave this function;
    native values and field paths are never included in the result.
    """
    restriction_ids: set[str] = set()
    item_date_ids: set[str] = set()
    missing_date_role_slots = 0
    for batch in batches:
        for row in batch.to_pylist():
            role = row["date_role"]
            source_field_id = row["date_source_field_id"]
            if role == "pbs_effective_date":
                if source_field_id is not None:
                    item_date_ids.add(source_field_id)
                else:
                    missing_date_role_slots += 1
            for field in row["native_fields"]:
                if field["schema_path"] == _RESTRICTION_DATE_PATH:
                    field_id = field["source_field_id"]
                    if field_id in restriction_ids:
                        continue
                    restriction_ids.add(field_id)
            if len(restriction_ids) + len(item_date_ids) > _MAX_IDENTITIES:
                raise ValueError("PBS date occurrence identity limit exceeded")

    overlap = restriction_ids & item_date_ids
    restriction_only = restriction_ids - item_date_ids
    item_only = item_date_ids - restriction_ids
    complete = (
        len(restriction_ids) == _EXPECTED_RESTRICTION_FIELDS
        and len(item_date_ids) == _EXPECTED_ITEM_DATE_FIELDS
        and not overlap
    )
    return {
        "schema_id": "global-medicines-atlas.pbs-date-occurrence-crosswalk",
        "schema_version": 1,
        "status": (
            "reconciled_by_exact_occurrence_identity"
            if complete
            else "unresolved_incomplete_or_nonmatching_denominators"
        ),
        "occurrence_sets": {
            "restriction_effective_date_path": {
                "role": "restriction_effective_date_path",
                "fields": len(restriction_ids),
                "identity_set_sha256": _identity_digest(restriction_ids),
            },
            "item_effective_date_profile": {
                "role": "pbs_effective_date",
                "fields": len(item_date_ids),
                "identity_set_sha256": _identity_digest(item_date_ids),
            },
        },
        "join": {
            "identity": "source_field_id_exact_match",
            "overlap_fields": len(overlap),
            "restriction_only_fields": len(restriction_only),
            "item_profile_only_fields": len(item_only),
            "unmatched_total": len(restriction_only) + len(item_only),
            "identity_set_sha256": _identity_digest(overlap),
        },
        "date_role_slots_without_source_field": missing_date_role_slots,
        "limits": [
            "identity crosswalk only; it does not qualify date meaning or values",
            "unmatched fields are distinct exact paths, not missing data",
            "identity digests are deterministic and are not anonymization",
        ],
        "source_values_emitted": False,
    }


def build_pbs_date_occurrence_crosswalk(
    payload: bytes,
    receipt: SourceReceipt,
) -> dict[str, Any]:
    """Build a crosswalk from one receipt-bound PBS source member."""
    batches = iter_pbs_date_batches(payload, receipt)
    return reconcile_pbs_date_occurrences(batches)


def run_hosted_date_occurrence_reconciliation(
    exact_commit: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Reconcile exact date-field identities from the pinned PBS archive."""
    retry = _RetryBudget()
    inputs = _verified_inputs(
        exact_commit, transport=transport, retry=retry
    )
    denominator = _denominator(inputs.xml)
    entities = iter_pbs_historical_entity_batches(
        inputs.archive, inputs.xml, inputs.parent, inputs.binding
    )
    crosswalk = reconcile_pbs_date_occurrences(
        _date_batches(entities, None, 1024)
    )
    occurrence_sets = crosswalk["occurrence_sets"]
    if (
        occurrence_sets["restriction_effective_date_path"]["fields"]
        != _EXPECTED_RESTRICTION_FIELDS
        or occurrence_sets["item_effective_date_profile"]["fields"]
        != _EXPECTED_ITEM_DATE_FIELDS
        or crosswalk["join"]["overlap_fields"] != 0
        or crosswalk["join"]["unmatched_total"]
        != _EXPECTED_UNMATCHED_DATE_FIELDS
        or crosswalk["status"] != "reconciled_by_exact_occurrence_identity"
    ):
        raise ValueError("PBS date occurrence denominators differ")
    report = {
        "schema_version": 1,
        "status": "passed",
        **inputs.context,
        "dataset": DATASET,
        "revision": REVISION,
        "source": {
            "member_path": inputs.binding.member_path,
            "member_sha256": inputs.binding.member_payload.sha256,
            "archive_sha256": inputs.binding.archive_payload.sha256,
            "native_digest": denominator["native_digest"],
            "native_fields": denominator["native_fields"],
            "member_binding_sha256": inputs.binding.digest(),
            "parent_receipt_sha256": inputs.binding.parent_receipt_sha256,
        },
        "crosswalk": crosswalk,
        "publication_performed": False,
        "source_values_emitted": False,
    }
    if len(json.dumps(report, sort_keys=True).encode()) > MAX_REPORT_BYTES:
        raise ValueError("PBS date occurrence report exceeds byte limit")
    return report
