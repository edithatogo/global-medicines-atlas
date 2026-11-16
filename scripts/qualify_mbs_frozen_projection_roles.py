"""Qualify retained role metadata for four frozen MBS projections.

Reads bound repository metadata and fixed producer-code blobs only. The v1
vocabulary cannot identify a rebuildable Bronze projection; a source-side v1
receipt is checked separately and is not presented as projection conformance.
No source or projection payloads are read and no admission is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed Git objects
from pathlib import Path
from typing import Any

import scripts.prepare_mbs_august_projection_admission as preparation
import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_august_projection_field_lineage as lineage
import scripts.qualify_mbs_august_projection_replay as replay
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = (
    "quality/qualifications/australian-mbs-frozen-projection-roles-20261116"
)
REPORT = f"{DIRECTORY}/role-assessment.json"
V1 = "quality/qualifications/australian-mbs-frozen-raw-lineage-20261115/v1-conformance.json"
V1_SHA = "288072cbfbbaee7efe4f35d8ed84487233da9dc025b5099f6091696456d1921c"
V1_SCHEMA = "contracts/medallion/v1/medallion-conformance.schema.json"
V1_SCHEMA_SHA = (
    "4c1ee81b026c64cf8f962d602cd64441a4a023c132346349c8b27dab0981f10e"
)
V3_SCHEMA = "contracts/medallion/v3/backfill-replay.schema.json"
V3_SCHEMA_SHA = (
    "5d0f472b124701ef66dcc1a5c39670826b8e95e5faf576cc394a3cd22df9419c"
)
PBS_BUILD = "quality/qualifications/pbs-independent-pipeline-builds-20261029/reconciliation.json"
PBS_BUILD_SHA = (
    "2d85ee0db7a19b3276da9baaaee9389558d09c87c43a0c57f68c5f31581ebaf8"
)
PBS_READY = (
    "quality/qualifications/pbs-reproduced-v4-evidence-readiness-20261029.json"
)
PBS_READY_SHA = (
    "d581fb505eca81ea2e984941d53c57218bbafcfc9c2de23a6718caf32ea01946"
)
PBS_CONTEXT = (
    "quality/qualifications/australian-pbs-schema-privacy-context-20261115.json"
)
PBS_CONTEXT_SHA = (
    "4a629204fc3810ea8e3d3de5e29f304e8cdecaf9ecbb4889ece6ca43db360209"
)
PBS_COMMIT = "c0f17f86f5d4f9a21efc28181786201005c369da"
PBS_CODE = {
    "src/global_medicines_atlas/pbs_value_package_v2.py": "7a6856ec17472022077360ce0e00a5d179a42609680237c5e9f137f06c836e4b",
    "src/global_medicines_atlas/pbs_xml_slots.py": "e689561f81bc476e57741e7f90afd0743ed064cbec297babdd59fd11ca38d326",
}
TRANSITIONS = {
    ("bronze_b0", "bronze_b1"),
    ("bronze_b1", "bronze_b2"),
    ("bronze_b1", "silver"),
    ("bronze_b2", "silver"),
    ("silver", "gold"),
    ("gold", "platinum"),
}


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def serialized(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def checked_json(root: Path, name: str, digest: str) -> dict[str, Any]:
    return bounded.read_bound_metadata(root, name, digest)


def checked_schema(root: Path, name: str, digest: str) -> dict[str, Any]:
    raw = (root / name).read_bytes()
    require(sha(raw) == digest, "schema digest differs")
    return json.loads(raw)


def semantic_errors(document: dict[str, Any]) -> list[str]:
    """Check v1 promotion semantics as well as its structural schema."""
    artifacts = {row["artifact_id"]: row for row in document["artifacts"]}
    errors: list[str] = []
    if len(artifacts) != len(document["artifacts"]):
        errors.append("duplicate_artifact")
    for decision in document["promotion_decisions"]:
        subject = artifacts.get(decision["subject_artifact_id"])
        if (decision["from_layer"], decision["to_layer"]) not in TRANSITIONS:
            errors.append("layer_skip")
        if subject is None:
            errors.append("unknown_subject")
            continue
        if subject["layer"] != decision["to_layer"]:
            errors.append("target_layer_mismatch")
        if set(subject["lineage"]["input_sha256"]) != set(
            decision["input_sha256"]
        ):
            errors.append("lineage_checksum_mismatch")
        if decision["status"] == "approved" and (
            set(decision["required_gate_ids"])
            - set(decision["passed_gate_ids"])
            or decision["rights_decision"]["status"] != "approved"
            or subject["promotion_status"] != "approved_within_scope"
        ):
            errors.append("approval_gate_missing")
    return errors


def projection_v1_errors(
    document: dict[str, Any], projection_path: str
) -> list[str]:
    """Fail closed when v1 alone is asked to qualify a Bronze projection."""
    errors = semantic_errors(document)
    matches = [
        artifact
        for artifact in document["artifacts"]
        if artifact["artifact_id"] == projection_path
        or artifact["artifact_id"].endswith(":" + projection_path)
    ]
    if not matches:
        errors.append("projection_subject_absent")
    elif len(matches) != 1:
        errors.append("projection_subject_ambiguous")
    elif matches[0]["layer"] == "bronze_b2":
        errors.append("v1_bronze_b2_lacks_representation_discriminator")
    else:
        errors.append("bronze_projection_layer_unrepresentable_in_v1")
    return errors


def check_code(root: Path, commit: str, files: dict[str, str]) -> None:
    git = shutil.which("git")
    require(git is not None, "Git is unavailable")
    for name, digest in files.items():
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed commit/path
            [str(git), "show", f"{commit}:{name}"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        require(sha(result.stdout) == digest, "producer code digest differs")


def pbs_assessment(root: Path) -> dict[str, Any]:
    """Relate the exact existing PBS output to its retained producer and schema."""
    build = checked_json(root, PBS_BUILD, PBS_BUILD_SHA)
    ready = checked_json(root, PBS_READY, PBS_READY_SHA)
    context = checked_json(root, PBS_CONTEXT, PBS_CONTEXT_SHA)
    package = build["package"]
    member = package["member_binding"]["member_payload"]
    require(
        build["workflow_commit"] == PBS_COMMIT
        and package["output_id"] == ready["output"]["id"]
        and package["parquet"]["sha256"] == ready["output"]["parquet_sha256"]
        and package["parquet"]["bytes"] == ready["output"]["parquet_bytes"]
        and member["sha256"]
        == ready["output"]["source_member_sha256"]
        == context["april_2026"]["member_sha256"]
        and "value" in package["native_core_keys"]
        and build["independent_algorithm"] is False
        and ready["boundaries"]["v4_admitted"] is False,
        "PBS output or source identity differs",
    )
    check_code(root, PBS_COMMIT, PBS_CODE)
    return {
        "output_id": ready["output"]["id"],
        "output_sha256": ready["output"]["parquet_sha256"],
        "source_member_sha256": member["sha256"],
        "producer_commit": PBS_COMMIT,
        "producer_code_sha256": PBS_CODE,
        "retained_native_core_includes_value": True,
        "schema_paths": context["april_2026"]["member_schema_paths"],
        "privacy": "unknown_output_values_not_screened",
        "finding": "native_values_preserved_not_deidentified_by_field_names",
        "applies_to": "exact_reproduced_silver_output_only",
        "admission": "not_performed",
    }


def build(root: Path = ROOT) -> dict[str, bytes]:  # ruff: ignore[too-many-locals] -- separate identity and evidence gates
    """Validate exact identities and reconstruct only metadata plans."""
    evidence = preparation.load(root)
    preparation.reconcile(evidence)
    vocabulary, crosswalk = lineage.build(root)
    require(
        serialized(vocabulary) == (root / lineage.OUTPUT).read_bytes(),
        "v2 bytes differ",
    )
    v2_schema = checked_schema(root, lineage.SCHEMA, lineage.SCHEMA_SHA)
    Draft202012Validator(v2_schema).validate(vocabulary)  # pyright: ignore[reportUnknownMemberType]
    v1 = checked_json(root, V1, V1_SHA)
    Draft202012Validator(
        checked_schema(root, V1_SCHEMA, V1_SCHEMA_SHA)
    ).validate(v1)  # pyright: ignore[reportUnknownMemberType]
    errors = semantic_errors(v1)
    require(
        errors == ["target_layer_mismatch"] * 3,
        "historical v1 semantic result differs",
    )
    require(
        "projection"
        not in checked_schema(root, V1_SCHEMA, V1_SCHEMA_SHA)["$defs"]["layer"][
            "enum"
        ],
        "v1 projection limitation differs",
    )
    checked_schema(root, V3_SCHEMA, V3_SCHEMA_SHA)
    plans = {row["path"]: row for row in evidence["replay"]["objects"]}
    sources = replay._sources(root)  # pyright: ignore[reportPrivateUsage]
    outputs: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    for row in crosswalk["objects"]:
        if not row["frozen_member"]:
            continue
        matches = [
            name
            for name in ("6bc9", "99fa")
            if lineage.PRODUCERS[name]["id"] in row["path"]
        ]
        require(
            len(matches) == 1 and row["revision"] == lineage.FROZEN_REVISION,
            "frozen identity differs",
        )
        name = matches[0]
        producer = lineage.PRODUCERS[name]
        check_code(root, str(producer["commit"]), lineage.code_hashes(name))
        actual = [
            record
            for record in vocabulary["records"]
            if record["output_dataset"] == row["path"]
        ]
        expected = lineage._records(  # pyright: ignore[reportPrivateUsage]
            row, producer, row["rights_evidence"]["sha256"]
        )
        require(
            actual == expected and len(actual) == lineage.RECORDS_PER_OBJECT,
            "v2 record bindings differ",
        )
        packet = replay._plan(  # pyright: ignore[reportPrivateUsage]
            root, row, sources[name], preparation.INPUTS["v2"][1]
        )
        registration = replay._register(packet["plan"], packet["metadata"])  # pyright: ignore[reportPrivateUsage]
        existing = plans[row["path"]]
        raw = serialized(packet["plan"])
        require(
            sha(raw) == existing["plan"]["sha256"]
            and replay._hash(registration) == existing["registration_sha256"]  # pyright: ignore[reportPrivateUsage]
            and all(existing[key] == row[key] for key in preparation.IDENTITY),
            "v3 plan or object identity differs",
        )
        rows.append({
            **{key: row[key] for key in preparation.IDENTITY},
            "producer_commit": producer["commit"],
            "source_acquisition_id": sources[name]["acquisition_id"],
            "v1": {
                "status": "blocked_no_projection_representation_in_v1",
                "errors": projection_v1_errors(v1, row["path"]),
            },
            "v2": {
                "path": lineage.OUTPUT,
                "sha256": preparation.INPUTS["v2"][1],
                "matching_records": len(actual),
            },
            "v3": {
                "replay_report_path": replay.REPORT,
                "replay_report_sha256": preparation.INPUTS["replay"][1],
                "reconstructed_plan_sha256": sha(raw),
                "plan_bytes_retained": False,
                "scope": "metadata_registration_only",
            },
            "privacy": "unknown_output_values_not_screened",
            "output_text_preserved_without_redaction": True,
            "admission": "not_performed",
        })
    require(
        len(rows) == preparation.FROZEN_COUNT
        and len({row["path"] for row in rows}) == preparation.FROZEN_COUNT,
        "frozen object count differs",
    )
    report = {
        "schema_id": "global-medicines-atlas.frozen-mbs-projection-role-assessment",
        "schema_version": 1,
        "recorded_on": "2026-11-16",
        "v1_source_receipt": {
            "path": V1,
            "sha256": V1_SHA,
            "schema_valid": True,
            "semantic_errors": errors,
            "projection_subject": False,
        },
        "v1_limit": "Pinned v1 does not distinguish B2 raw from a rebuildable projection or express B2-to-B2 production.",
        "objects": rows,
        "pbs_reproduced_silver": pbs_assessment(root),
        "boundaries": {
            "source_or_projection_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_acquired_or_published": False,
            "v4_admission_or_consumer_canary": False,
            "output_privacy_cleared": False,
        },
    }
    outputs[REPORT] = serialized(report)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, raw in build().items():
        path = ROOT / name
        if args.check:
            require(
                path.is_file() and path.read_bytes() == raw, f"stale: {name}"
            )
        else:
            require(
                not path.exists() or path.read_bytes() == raw,
                f"immutable conflict: {name}",
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    print(
        "Four v2 bindings and metadata-only v3 plans checked; v1 and privacy remain blocked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
