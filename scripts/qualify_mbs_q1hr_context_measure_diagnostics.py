"""Diagnose Q1 HR residual rows and measures using exact shared row keys.

Only aggregates leave memory. This does not assign measure or category meaning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from scripts import qualify_mbs_q1hr_age_context_mapping as context_mapping
from scripts.qualify_mbs_q1hr_benefit_scale_comparison import (
    DATASET,
    EXPECTED_CSV_ROWS,
    EXPECTED_WORKBOOK_ROWS,
    OBJECTS,
    REVISION,
    SCALE_FACTORS,
    csv_rows,
    fetch_exact_source_bytes,
    workbook_rows,
)

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "quality/qualifications/australian-mbs-demographics-q1hr-context-measure-diagnostics-20261021.json"
)
FIELDS = (
    "Year",
    "Month",
    "Item_Number",
    "State",
    "Age_Range",
    "Gender",
    "Services",
    "Benefits",
)
type Row = tuple[str | None, ...]


def _number(value: str | None) -> Decimal | None:
    try:
        parsed = Decimal(value or "")
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _key(row: Row) -> tuple[str, ...]:
    if len(row) != len(FIELDS):
        raise ValueError("Expected exactly eight source columns")
    age = context_mapping.normalize_context_value(row[4], 4)
    unquoted = context_mapping.unquote_balanced(age)
    return (
        *context_mapping.row_context(row),
        age if unquoted is None else unquoted,
    )


def _accumulate_precision(
    a: Decimal, b: Decimal, decimal_agreement: Counter[str]
) -> None:
    """Count numeric agreement without assigning a measure unit or meaning."""
    difference = abs(a - b)
    for bound in ("0.000000001", "0.005", "0.01"):
        if difference <= Decimal(bound):
            decimal_agreement[f"absolute_difference_le_{bound}"] += 1
    if difference > Decimal("0.01"):
        decimal_agreement["absolute_difference_gt_0.01"] += 1
    try:
        if a.quantize(Decimal("0.01")) == b.quantize(Decimal("0.01")):
            decimal_agreement["rounded_2_decimal_places"] += 1
    except InvalidOperation:
        decimal_agreement["unquantizable_pairs"] += 1


def diagnose(workbook: list[Row], csv_values: list[Row]) -> dict[str, object]:
    """Compare only unambiguous full keys; classify unmatched rows by shape."""
    left: dict[tuple[str, ...], list[Row]] = defaultdict(list)
    right: dict[tuple[str, ...], list[Row]] = defaultdict(list)
    for row in workbook:
        left[_key(row)].append(row)
    for row in csv_values:
        right[_key(row)].append(row)
    shared = left.keys() & right.keys()
    unique = {key for key in shared if len(left[key]) == len(right[key]) == 1}
    scales: Counter[str] = Counter(dict.fromkeys(SCALE_FACTORS, 0))
    numeric_pairs = 0
    decimal_agreement: Counter[str] = Counter({
        "rounded_2_decimal_places": 0,
        "absolute_difference_le_0.000000001": 0,
        "absolute_difference_le_0.005": 0,
        "absolute_difference_le_0.01": 0,
        "absolute_difference_gt_0.01": 0,
        "unquantizable_pairs": 0,
    })
    for key in unique:
        a, b = _number(left[key][0][7]), _number(right[key][0][7])
        if a is None or b is None:
            continue
        numeric_pairs += 1
        _accumulate_precision(a, b, decimal_agreement)
        for name, factor in SCALE_FACTORS.items():
            if a * factor == b:
                scales[name] += 1
    residuals = [row for key in left.keys() - right.keys() for row in left[key]]
    shapes: dict[str, dict[str, int]] = {}
    for column, field in enumerate(FIELDS):
        counts: Counter[str] = Counter()
        for row in residuals:
            value = row[column]
            kind = (
                "missing"
                if value is None or not value.strip()
                else (
                    "finite_numeric" if _number(value) is not None else "text"
                )
            )
            counts[kind] += 1
        shapes[field] = dict(sorted(counts.items()))
    return {
        "workbook_rows": len(workbook),
        "csv_rows": len(csv_values),
        "shared_full_keys": len(shared),
        "unambiguous_full_key_pairs": len(unique),
        "ambiguous_shared_full_keys_excluded": len(shared - unique),
        "shared_keys_with_multiplicity_mismatch": sum(
            len(left[key]) != len(right[key]) for key in shared
        ),
        "unambiguous_numeric_benefit_pairs": numeric_pairs,
        "exact_numeric_matches_by_fixed_scale": dict(scales),
        "numeric_precision_diagnostics": dict(decimal_agreement),
        "workbook_only_full_keys": len(left.keys() - right.keys()),
        "workbook_only_rows": len(residuals),
        "csv_only_full_keys": len(right.keys() - left.keys()),
        "csv_only_rows": sum(
            len(right[key]) for key in right.keys() - left.keys()
        ),
        "workbook_only_row_field_shapes": shapes,
        "workbook_only_rows_with_all_context_fields_missing": sum(
            all(not (value or "").strip() for value in row[:7])
            for row in residuals
        ),
    }


def qualify() -> dict[str, object]:
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=120,
        max_bytes=25_000_000,
        max_attempts=1,
        max_redirects=3,
    )
    with httpx.Client(
        timeout=120,
        trust_env=False,
        follow_redirects=True,
        max_redirects=3,
        transport=BoundIPAddressTransport(policy=policy),
    ) as client:
        workbook = workbook_rows(fetch_exact_source_bytes(client, OBJECTS[0]))
        csv_values = csv_rows(fetch_exact_source_bytes(client, OBJECTS[1]))
    if (
        len(workbook) != EXPECTED_WORKBOOK_ROWS
        or len(csv_values) != EXPECTED_CSV_ROWS
    ):
        raise ValueError("Pinned source row count changed")
    return {
        "schema_id": "global-medicines-atlas.mbs-q1hr-context-measure-diagnostics",
        "schema_version": 1,
        "source": {
            "dataset": DATASET,
            "revision": REVISION,
            "objects": list(OBJECTS),
        },
        "method": "Join full source context and normalized literal age label; exclude repeated keys; compare finite Decimal values exactly",
        "results": diagnose(workbook, csv_values),
        "boundaries": {
            "new_sources_added": False,
            "source_values_emitted_or_retained": False,
            "source_bytes_persisted": False,
            "category_or_benefit_semantics_qualified": False,
            "silver_projection_created": False,
            "public_release_performed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = (json.dumps(qualify(), sort_keys=True, indent=2) + "\n").encode()
    if args.check:
        if args.output.read_bytes() != payload:
            raise SystemExit("Context/measure diagnostics are stale")
    else:
        args.output.write_bytes(payload)
    print(hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    main()
