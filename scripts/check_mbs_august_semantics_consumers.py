"""Check retained August MBS field profiles and offline consumer isolation.

This reads pinned, value-free metadata only. Synthetic probes are never real
contracts, admissions, payload canaries, or evidence of semantic acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

import scripts.check_mbs_august_projection_consumers as probes
import scripts.prepare_mbs_august_projection_admission as preparation
import scripts.qualify_australian_existing_derived_gates as derived
import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_august_projection_field_lineage as lineage
import scripts.qualify_mbs_july_frozen_v4 as existing

from global_medicines_atlas.australian_source_contracts import (
    mbs_field_contracts,
)
from global_medicines_atlas.federation_identity import AdmissionRecord

ROOT = Path(__file__).resolve().parents[1]
Q = "quality/qualifications/"
OUTPUT = Q + "australian-mbs-august-bounded-semantics-consumers-20261116.json"
INPUTS = {
    "baseline": (
        Q + "mbs-source-era-candidate-2026-08-01-presence-baseline.json",
        "5af143a416918113ebb4dc2a625c3a14ab66015d413f7c7de92ee13a3995f181",
    ),
    "dmy": lineage.INPUTS["profile"],
    "history": (
        Q + "australian-mbs-field-guide-semantic-history-20261018.json",
        "4140b659a21ad62937dfa02ec9d1c9116ea836ef911a1127abc9e711f7f5ef73",
    ),
    "preparation": (
        preparation.OUTPUT,
        "1aee87122b0062e297645480312c4462aa1f097e0c866c2f9bb672c3ef673ecf",
    ),
    "prior_admission": derived.INPUTS["consumer_receipt"],
}
CHANGED_DATE_FIELDS = 6
PRIOR_ADMISSIONS = 6


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _ref(name: str) -> dict[str, str]:
    path, digest = INPUTS[name]
    return {"path": path, "sha256": digest}


def load(root: Path = ROOT) -> dict[str, Any]:
    """Load only the fixed, digest-bound metadata and status note."""
    evidence = {
        name: bounded.read_bound_metadata(root, *ref)
        for name, ref in INPUTS.items()
    }
    evidence["projection"] = preparation.load(root)
    status = (root / lineage.STATUS).read_bytes()
    _require(
        hashlib.sha256(status).hexdigest() == lineage.STATUS_SHA,
        "semantic status note differs",
    )
    return evidence


def _fields(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = profile["field_presence_diagnostics"]
    result = {row["native_field"]: row for row in rows}
    _require(
        len(rows) == len(result) == lineage.FIELD_COUNT, "profile fields differ"
    )
    return result


def _counts(row: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    rows, present, null = (
        row[key] for key in ("rows", "source_present", "source_null")
    )
    _require(
        all(type(value) is int for value in (rows, present, null))
        and rows == lineage.SOURCE_RECORDS
        and 0 <= null <= present <= rows
        and row["presence_state_mismatches"] == 0
        and row["requiredness_accepted"] is False,
        "presence evidence differs",
    )
    states = {
        "missing_field": rows - present,
        "null": null,
        "value": present - null,
    }
    states = {key: value for key, value in states.items() if value}
    _require(row["projected_states"] == states, "native presence states differ")
    raw_conversions: object = row["conversion_status_counts"]
    _require(isinstance(raw_conversions, dict), "conversion totals differ")
    conversions = cast("dict[str, int]", raw_conversions)
    _require(
        set(conversions)
        <= {
            "missing_field",
            "null",
            "converted",
            "preserved",
            "unsupported_format",
        }
        and all(
            type(value) is int and value > 0 for value in conversions.values()
        )
        and sum(conversions.values()) == rows
        and conversions.get("missing_field", 0) == rows - present
        and conversions.get("null", 0) == null,
        "conversion totals differ",
    )
    return states, conversions


def reconcile(evidence: dict[str, Any]) -> dict[str, Any]:  # ruff: ignore[too-many-locals] -- retain independent profile checks
    """Compare the two historical aggregate profiles without interpreting values."""
    prep = preparation.reconcile(evidence["projection"])
    _require(prep == evidence["preparation"], "preparation evidence differs")
    baseline, dmy = evidence["baseline"], evidence["dmy"]
    for profile in (baseline, dmy):
        qualification = profile["qualification"]
        _require(
            profile["status"] == "candidate_only"
            and profile["official_release_sha256"]
            == qualification["source_sha256"]
            == lineage.SOURCE_SHA
            and profile["official_release_byte_count"]
            == qualification["source_byte_count"]
            == lineage.SOURCE_BYTES
            and qualification["source_record_count"] == lineage.SOURCE_RECORDS
            and profile["source_presence_projection_alignment"] == "matched"
            and profile["historical_semantic_parity_accepted"] is False
            and profile["m109_accepted"] is False
            and profile["public_v4_admission"] is False,
            "source profile identity differs",
        )
    _require(
        baseline["qualification"]["date_format"] is None
        and baseline["field_semantics_accepted"] is False
        and dmy["qualification"]["date_format"] == "mbs-dmy"
        and dmy["field_semantics_accepted"] is True,
        "historical profile status differs",
    )
    history = evidence["history"]
    conflicts = sorted(row["field"] for row in history["field_comparisons"])
    _require(
        conflicts == ["EMSNCap", "ItemChange"]
        and history["unresolved_history"]["release_semantics_qualified"]
        is False
        and history["qualification_boundaries"]["semantic_promotion"] is False,
        "semantic history differs",
    )
    contracts = {item.native_name: item for item in mbs_field_contracts()}
    first, second = _fields(baseline), _fields(dmy)
    _require(
        set(first) == set(second) == set(contracts), "native field set differs"
    )
    output: list[str] = []
    date_changes = changed_fields = 0
    baseline_totals: Counter[str] = Counter()
    dmy_totals: Counter[str] = Counter()
    for name in sorted(contracts):
        before, after = first[name], second[name]
        before_states, before_statuses = _counts(before)
        after_states, after_statuses = _counts(after)
        contract = contracts[name]
        _require(
            before_states == after_states
            and before["target_table"]
            == after["target_table"]
            == contract.target_table,
            "field profile alignment differs",
        )
        expected = dict(before_statuses)
        changed = expected.pop("unsupported_format", 0)
        if changed:
            _require(
                contract.value_type == "source_date",
                "non-date conversion differs",
            )
            expected["converted"] = expected.get("converted", 0) + changed
            changed_fields += 1
            date_changes += changed
        _require(expected == after_statuses, "date profile conversion differs")
        baseline_totals.update(before_statuses)
        dmy_totals.update(after_statuses)
        output.append(name)
    _require(
        date_changes > 0
        and date_changes == baseline_totals.get("unsupported_format", 0)
        and changed_fields == CHANGED_DATE_FIELDS,
        "date profile denominator differs",
    )
    for profile, totals in ((baseline, baseline_totals), (dmy, dmy_totals)):
        quality = profile["qualification"]["quality"]
        by_status = {row["status"]: row["count"] for row in quality}
        _require(
            len(by_status) == len(quality) and by_status == totals,
            "aggregate quality totals differ",
        )
    records = evidence["projection"]["v2"]["records"]
    fields = set(contracts)
    for item in prep["objects"]:
        mapped = [
            record
            for record in records
            if record["output_dataset"] == item["path"]
            and record["output_field"] in {"fields[].name", "fields[].value"}
        ]
        observed = Counter(
            (
                record["source_field"],
                record["output_field"],
                record["transformation_id"],
            )
            for record in mapped
        )
        expected_records = Counter(
            (f"/MBS_XML/Data/{name}", field, transformation)
            for name in fields
            for field, transformation in (
                ("fields[].name", "au-mbs-bronze:xml-child-local-name"),
                ("fields[].value", "au-mbs-bronze:xml-child-text-or-null"),
            )
        )
        _require(
            observed == expected_records
            and all(
                record["output_sha256"] == item["sha256"]
                and record["input_sha256"] == lineage.SOURCE_SHA
                for record in mapped
            ),
            "projection field mapping differs",
        )
    prior = evidence["prior_admission"]
    admissions = [
        AdmissionRecord.model_validate(row["admission_record"])
        for row in prior["objects"]
    ]
    _require(
        prior["status"] == "passed"
        and prior["verified_object_count"]
        == len(admissions)
        == PRIOR_ADMISSIONS
        and len({record.contract_sha256 for record in admissions})
        == PRIOR_ADMISSIONS
        and all(
            record.evidence_kind == "live"
            and record.layer == "silver"
            and record.dataset == lineage.DATASET
            and record.revision == derived.SILVER_REVISION
            and record.schema_sha256 == existing.SCHEMA_SHA
            for record in admissions
        ),
        "prior admission scope differs",
    )
    return {
        "source_sha256": lineage.SOURCE_SHA,
        "native_fields": len(output),
        "changed_date_fields": changed_fields,
        "aggregate_date_conversion_accounting": "matched",
        "field_semantics_accepted": False,
        "historical_dmy_acceptance_flag": "superseded_by_status_note",
        "unresolved_conflicts": conflicts,
        "checked_native_fields": output,
        "evidence_scope": "source_and_candidate_silver_profiles_not_eight_bronze_payload_profiles",
    }


def _consumer_checks(evidence: dict[str, Any], root: Path) -> dict[str, Any]:
    rows = evidence["projection"]["lineage"]["objects"]
    plans = {
        item["path"]: item
        for item in evidence["projection"]["replay"]["objects"]
    }
    admissions = tuple(
        AdmissionRecord.model_validate(item["admission_record"])
        for item in evidence["prior_admission"]["objects"]
    )
    schema = (root / existing.SCHEMA).read_bytes()
    results: list[dict[str, Any]] = []
    for item in rows:
        raw = probes._probe(  # pyright: ignore[reportPrivateUsage] -- reuse synthetic-only probe
            root,
            item,
            plans[item["path"]],
            preparation.INPUTS["v2"][1],
            preparation.INPUTS["replay"][1],
        )
        rekeyed = admissions[0].model_copy(
            update={"contract_sha256": hashlib.sha256(raw).hexdigest()}
        )
        for allowed, message in (
            (admissions, "contract is not independently admitted"),
            ((rekeyed,), "contract identity differs from admission record"),
        ):
            with probes._NoNetworkReader(  # pyright: ignore[reportPrivateUsage] -- fail before remote I/O
                schema=schema, admission_records=allowed
            ) as reader:
                try:
                    with reader.open(raw):
                        raise AssertionError(
                            "unadmitted synthetic projection opened"
                        )
                except ValueError as exc:
                    _require(
                        str(exc) == message and reader.cached_bytes == 0,
                        "consumer refusal differs",
                    )
        results.append({
            "dataset": item["dataset"],
            "path": item["path"],
            "revision": item["revision"],
            "sha256": item["sha256"],
            "byte_count": item["byte_count"],
            "prior_silver_admissions_rejected": True,
            "rekeyed_silver_identity_rejected": True,
        })
    _require(len(results) == lineage.OBJECT_COUNT, "consumer cohort differs")
    return {
        "prior_silver_admission_count": len(admissions),
        "prior_silver_revision": derived.SILVER_REVISION,
        "probe_kind": "synthetic_identity_only",
        "rekeying_scope": "in_memory_negative_test_not_admission",
        "objects": results,
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    evidence = load(root)
    semantics = reconcile(evidence)
    return {
        "schema_id": "global-medicines-atlas.mbs-august-bounded-semantics-consumers",
        "schema_version": 1,
        "recorded_on": "2026-11-16",
        "inputs": {name: _ref(name) for name in INPUTS}
        | {
            "semantic_status": {
                "path": lineage.STATUS,
                "sha256": lineage.STATUS_SHA,
            }
        },
        "semantics": semantics,
        "consumers": _consumer_checks(evidence, root),
        "boundaries": {
            "source_or_projection_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_acquired_or_published": False,
            "field_semantics_accepted": False,
            "rights_or_privacy_decision_changed": False,
            "actual_admission_or_payload_consumer_canary": False,
            "independent_recovery_established": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), sort_keys=True, indent=2) + "\n").encode()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == raw,
            "bounded check report differs",
        )
    else:
        path.write_bytes(raw)
    print("Checked 40 field profiles and eight offline consumer identities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
