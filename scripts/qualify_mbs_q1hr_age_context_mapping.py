#!/usr/bin/env python3
"""Measure candidate Q1 HR age-label mappings from shared row context.

The qualification emits only aggregate counts and category digests. It cannot
establish semantic category equivalence or authorize a Silver transformation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from qualify_mbs_q1hr_benefit_scale_comparison import (
    DATASET,
    EXPECTED_CSV_ROWS,
    EXPECTED_WORKBOOK_ROWS,
    OBJECTS,
    REVISION,
    _fetch_exact,  # ruff: ignore[import-private-name] -- pinned in-memory fetch helper
    csv_rows,
    workbook_rows,
)

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(
    "quality/qualifications/"
    "australian-mbs-demographics-q1hr-age-context-mapping-20261021.json"
)
CONTEXT_COLUMNS = (0, 1, 2, 3, 5, 6)
AGE_COLUMN = 4
NUMERIC_CONTEXT_COLUMNS = frozenset({0, 1, 6})


def _normalize(value: str | None, column: int) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if column in NUMERIC_CONTEXT_COLUMNS:
        try:
            number = Decimal(normalized)
            if number.is_finite():
                return str(number.normalize())
        except InvalidOperation:
            pass
    return normalized.translate(
        str.maketrans({"\u2013": "-", "\u2014": "-", "\u2212": "-"})
    )


def _row_context(row: tuple[str | None, ...]) -> tuple[str, ...]:
    return tuple(_normalize(row[column], column) for column in CONTEXT_COLUMNS)


def _candidate_relationships(
    workbook: list[tuple[str | None, ...]],
    csv_values: list[tuple[str | None, ...]],
) -> dict[str, object]:
    workbook_by_context: dict[tuple[str, ...], list[str]] = defaultdict(list)
    csv_by_context: dict[tuple[str, ...], list[str]] = defaultdict(list)
    workbook_categories: set[str] = set()
    csv_categories: set[str] = set()
    for row in workbook:
        age = _normalize(row[AGE_COLUMN], AGE_COLUMN)
        workbook_categories.add(age)
        workbook_by_context[_row_context(row)].append(age)
    for row in csv_values:
        age = _normalize(row[AGE_COLUMN], AGE_COLUMN)
        csv_categories.add(age)
        csv_by_context[_row_context(row)].append(age)

    shared_keys = workbook_by_context.keys() & csv_by_context.keys()
    exact_context_occurrences = sum(
        min(len(workbook_by_context[key]), len(csv_by_context[key]))
        for key in shared_keys
    )
    unique_pairs: Counter[tuple[str, str]] = Counter()
    unambiguous_context_count = 0
    ambiguous_context_count = 0
    for key in shared_keys:
        left = workbook_by_context[key]
        right = csv_by_context[key]
        if len(left) == len(right) == 1:
            unique_pairs[left[0], right[0]] += 1
            unambiguous_context_count += 1
        else:
            ambiguous_context_count += 1

    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    support_by_source: Counter[str] = Counter()
    for (left, right), count in unique_pairs.items():
        outgoing[left].add(right)
        incoming[right].add(left)
        support_by_source[left] += count
    one_to_one_pairs = sum(
        1
        for targets in outgoing.values()
        if len(targets) == 1 and len(incoming[next(iter(targets))]) == 1
    )
    category_digests = sorted(
        hashlib.sha256(label.encode("utf-8")).hexdigest()[:16]
        for label in workbook_categories | csv_categories
    )
    return {
        "workbook_unique_age_categories": len(workbook_categories),
        "csv_unique_age_categories": len(csv_categories),
        "category_digest_count": len(category_digests),
        "category_digests_sha256": hashlib.sha256(
            "\n".join(category_digests).encode("ascii")
        ).hexdigest(),
        "workbook_unique_context_keys": len(workbook_by_context),
        "csv_unique_context_keys": len(csv_by_context),
        "shared_context_keys": len(shared_keys),
        "shared_context_occurrences": exact_context_occurrences,
        "unambiguous_single_row_contexts": unambiguous_context_count,
        "ambiguous_or_repeated_contexts": ambiguous_context_count,
        "unique_age_category_pairs_from_unambiguous_contexts": len(
            unique_pairs
        ),
        "one_to_one_category_pairs": one_to_one_pairs,
        "source_categories_with_multiple_targets": sum(
            len(targets) > 1 for targets in outgoing.values()
        ),
        "target_categories_with_multiple_sources": sum(
            len(sources) > 1 for sources in incoming.values()
        ),
        "maximum_unambiguous_support_for_one_source_category": max(
            support_by_source.values(), default=0
        ),
        "source_values_or_category_labels_emitted": False,
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
        follow_redirects=True,
        timeout=httpx.Timeout(120),
        trust_env=False,
        max_redirects=policy.max_redirects,
        transport=BoundIPAddressTransport(policy=policy),
    ) as client:
        workbook_payload = _fetch_exact(client, OBJECTS[0])
        csv_payload = _fetch_exact(client, OBJECTS[1])
    workbook = workbook_rows(workbook_payload)
    csv_values = csv_rows(csv_payload)
    if (
        len(workbook) != EXPECTED_WORKBOOK_ROWS
        or len(csv_values) != EXPECTED_CSV_ROWS
    ):
        raise ValueError(
            "Pinned object row counts differ from the qualified layout"
        )
    return {
        "schema_id": "global-medicines-atlas.mbs-demographics-q1hr-age-context-mapping",
        "schema_version": 1,
        "source": {
            "dataset": DATASET,
            "revision": REVISION,
            "objects": list(OBJECTS),
            "source_bytes_persisted": False,
        },
        "method": {
            "context_fields": [
                "Year",
                "Month",
                "Item_Number",
                "State",
                "Gender",
                "Services",
            ],
            "age_field": "Age_Range",
            "normalization": "NFKC, trim, casefold; numeric canonicalization for year/month/services; Unicode dash normalization",
            "candidate_pairs": "Only one-to-one contexts with one row in each object; repeated contexts are counted as ambiguous and excluded",
        },
        "results": _candidate_relationships(workbook, csv_values),
        "interpretation": (
            "Shared row context can suggest a candidate label crosswalk only. "
            "Context co-occurrence is not source-defined category semantics, "
            "record equivalence, or approval to transform Silver data."
        ),
        "boundaries": {
            "new_sources_added": False,
            "source_values_emitted_or_retained": False,
            "semantic_equivalence_established": False,
            "silver_projection_created": False,
            "admission_or_canary_performed": False,
            "public_dataset_mutated": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = (
        json.dumps(qualify(), sort_keys=True, separators=(",", ":")) + "\n"
    )
    output = args.output.expanduser()
    if args.check:
        if (
            not output.is_file()
            or output.read_text(encoding="utf-8") != expected
        ):
            raise SystemExit(f"Q1 HR age-context report is stale: {output}")
        print("Q1 HR age-context mapping report passed")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(expected, encoding="utf-8")
    print(
        f"wrote {output} sha256={hashlib.sha256(expected.encode()).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
