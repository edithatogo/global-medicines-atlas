"""Reproduce exact Q1 category and decimal diagnostics without data rows."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

if __package__:
    from scripts import qualify_mbs_q1hr_context_measure_diagnostics as context
else:
    import qualify_mbs_q1hr_context_measure_diagnostics as context

COMMIT_LENGTH = 40
Row = context.Row


def diagnose(workbook: list[Row], csv_rows: list[Row]) -> dict[str, object]:
    """Exclude ambiguous keys and count only finite paired measures."""
    left: dict[tuple[str, ...], list[Row]] = defaultdict(list)
    right: dict[tuple[str, ...], list[Row]] = defaultdict(list)
    categories: Counter[str] = Counter()
    for row in workbook:
        left[context.row_key(row)].append(row)
        year = context.finite_number(row[0])
        if year is None or year != year.to_integral_value():
            continue
        age = row[4]
        categories["native_unknown" if age == "Unknown" else "other"] += 1
    for row in csv_rows:
        right[context.row_key(row)].append(row)
    shared = left.keys() & right.keys()
    counts: Counter[str] = Counter()
    rounding: Counter[str] = Counter()
    for key in shared:
        if len(left[key]) != 1 or len(right[key]) != 1:
            counts["ambiguous_keys_excluded"] += 1
            continue
        counts["unambiguous_pairs"] += 1
        a = context.finite_number(left[key][0][7])
        b = context.finite_number(right[key][0][7])
        if a is None or b is None:
            counts["nonnumeric_pairs_excluded"] += 1
            continue
        counts["numeric_pairs"] += 1
        counts["equal" if a == b else "lower" if a < b else "higher"] += 1
        for places in range(7):
            quantum = Decimal(10) ** -places
            for mode in ("ROUND_DOWN", "ROUND_HALF_UP"):
                name = f"{mode}_{places}"
                rounding.setdefault(name, 0)
                try:
                    rounding[name] += a == b.quantize(quantum, rounding=mode)
                except InvalidOperation:
                    counts["unquantizable_operations"] += 1
    return {
        "full_key_counts": dict(sorted(counts.items())),
        "workbook_age_row_counts": dict(sorted(categories.items())),
        "workbook_equals_rounded_csv": dict(sorted(rounding.items())),
        "native_unknown_category": {
            "marker": "Unknown",
            "observed": categories["native_unknown"] > 0,
            "suppression_relationship_established": False,
            "numeric_bounds": None,
            "cause_established": False,
            "csv_equivalence_established": False,
        },
    }


def qualify(exact_commit: str) -> dict[str, object]:
    """Read only pinned objects on the requested main Actions commit."""
    if not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY")
        == "edithatogo/global-medicines-atlas"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and len(exact_commit) == COMMIT_LENGTH
        and all(char in "0123456789abcdef" for char in exact_commit)
        and os.environ.get("GITHUB_SHA") == exact_commit
    ):
        raise ValueError("Qualification requires exact main Actions commit")
    policy = context.AcquisitionPolicy(
        allowed_hosts=context.HOSTS,
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
        transport=context.BoundIPAddressTransport(policy=policy),
    ) as client:
        workbook = context.workbook_rows(
            context.fetch_exact_source_bytes(client, context.OBJECTS[0])
        )
        csv_rows = context.csv_rows(
            context.fetch_exact_source_bytes(client, context.OBJECTS[1])
        )
    if (len(workbook), len(csv_rows)) != (
        context.EXPECTED_WORKBOOK_ROWS,
        context.EXPECTED_CSV_ROWS,
    ):
        raise ValueError("Pinned row denominators differ")
    return {
        "schema_id": "global-medicines-atlas.q1-source-meaning-diagnostics",
        "schema_version": 1,
        "workflow_commit": exact_commit,
        "source": {
            "dataset": context.DATASET,
            "revision": context.REVISION,
            "objects": context.OBJECTS,
        },
        "results": diagnose(workbook, csv_rows),
        "boundaries": {
            "benefit_calculation_resolved": False,
            "source_rows_emitted": False,
            "source_bytes_persisted": False,
            "silver_promoted": False,
            "new_sources_added": False,
        },
    }


def main() -> None:
    """Write aggregate diagnostics to the requested artifact path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = qualify(args.exact_commit)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.check:
        if args.output.read_text() != payload:
            raise SystemExit("Q1 source meaning diagnostic is stale")
    else:
        args.output.write_text(payload)


if __name__ == "__main__":
    main()
