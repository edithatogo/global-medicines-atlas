"""Qualify MBS Gold candidate edges from exact admitted public Silver Parquet."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from jsonschema import Draft202012Validator, FormatChecker

from global_medicines_atlas.mbs_gold_graph import (
    MbsGoldAdmittedSilverInput,
    build_mbs_gold_graph_from_admitted_silver,
)
from global_medicines_atlas.receipts import RightsState

ROOT = Path(__file__).resolve().parents[1]
ADMISSION_PATH = Path(
    "quality/qualifications/australian-mbs-silver-admission-20261017.json"
)
ADMISSION_SCHEMA_PATH = Path("schemas/australian-mbs-silver-admission-v1.json")
SEMANTIC_PATH = Path(
    "quality/qualifications/australian-mbs-silver-semantic-manifest-20261017.json"
)
PARITY_PATH = Path(
    "quality/qualifications/mbs-source-silver-tables-parity-2025-07-v3.json"
)
OUTPUT_PATH = Path(
    "quality/qualifications/australian-mbs-gold-real-silver-qualification-20261017.json"
)
SCHEMA_PATH = Path(
    "schemas/australian-mbs-gold-real-silver-qualification-v1.json"
)
IMPLEMENTATION_PATHS = (
    Path("scripts/qualify_australian_mbs_gold_real_silver.py"),
    Path("src/global_medicines_atlas/mbs_gold_graph.py"),
    Path("schemas/australian-mbs-gold-real-silver-qualification-v1.json"),
    Path("schemas/australian-mbs-silver-admission-v1.json"),
    Path("schemas/australian-mbs-silver-semantic-manifest-v1.json"),
)
EXPECTED_TABLES = (
    "benefits",
    "caps",
    "descriptions",
    "fees",
    "hierarchy",
    "services",
)
EXPECTED_NATIVE_FIELD_COUNT = 40


def _read_json(path: Path) -> dict[str, Any]:
    value: Any = json.loads((ROOT / path).read_bytes())
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def _implementation_fingerprints() -> list[dict[str, str]]:
    return [
        {"path": str(path), "sha256": _sha256((ROOT / path).read_bytes())}
        for path in IMPLEMENTATION_PATHS
    ]


def _check_json_schema(schema: dict[str, Any]) -> None:
    validator_type: Any = Draft202012Validator
    validator_type.check_schema(schema)


def _validate_json_schema(
    schema: dict[str, Any], instance: dict[str, Any]
) -> None:
    validator_type: Any = Draft202012Validator
    validator_type(schema, format_checker=FormatChecker()).validate(instance)


def _load_verified_inputs() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    admission = _read_json(ADMISSION_PATH)
    semantic = _read_json(SEMANTIC_PATH)
    parity = _read_json(PARITY_PATH)
    admission_schema = _read_json(ADMISSION_SCHEMA_PATH)
    schema = _read_json(SCHEMA_PATH)
    _check_json_schema(admission_schema)
    _check_json_schema(schema)
    _validate_json_schema(admission_schema, admission)
    semantic_schema = _read_json(
        Path("schemas/australian-mbs-silver-semantic-manifest-v1.json")
    )
    _check_json_schema(semantic_schema)
    _validate_json_schema(semantic_schema, semantic)
    if admission["semantic_manifest"]["sha256"] != _sha256(
        (ROOT / SEMANTIC_PATH).read_bytes()
    ):
        raise ValueError(
            "admission does not bind the exact semantic manifest bytes"
        )
    if admission["source_identity"] != semantic["source_identity"]:
        raise ValueError("admission and semantic source identities differ")
    if (
        admission["public_dataset_identity"]
        != semantic["public_dataset_identity"]
    ):
        raise ValueError("admission and semantic public identities differ")
    if admission["separation"]["M110_gold_graph_accepted"] is not False:
        raise ValueError("input admission already claims Gold graph acceptance")
    if admission["separation"]["public_dataset_mutation"] is not False:
        raise ValueError("input admission permits a public dataset mutation")
    if (
        parity["production_admission"] is not False
        or parity["rights_conclusion"] is not False
    ):
        raise ValueError(
            "historical parity receipt admission or rights boundary changed"
        )
    tables = semantic["tables"]
    if tuple(table["name"] for table in tables) != EXPECTED_TABLES:
        raise ValueError(
            "semantic manifest does not contain the exact six-table order"
        )
    if (
        len({
            field["native_name"]
            for table in tables
            for field in table["native_fields"]
        })
        != EXPECTED_NATIVE_FIELD_COUNT
    ):
        raise ValueError("semantic manifest does not bind all 40 native fields")
    return admission, semantic, parity, schema


def _download_objects(
    admission: dict[str, Any], semantic: dict[str, Any], parity: dict[str, Any]
) -> dict[str, pa.Table]:
    identity = admission["public_dataset_identity"]
    table_specs = {table["name"]: table for table in semantic["tables"]}
    parity_specs = {table["table"]: table for table in parity["tables"]}
    output: dict[str, pa.Table] = {}
    receipt_hashes: set[str] = set()
    retrieved_at_values: set[str] = set()
    source_hashes: set[str] = set()
    url_base = (
        f"https://huggingface.co/datasets/{identity['dataset']}/resolve/"
        f"{identity['current_revision']}/"
    )
    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        for name in EXPECTED_TABLES:
            spec = table_specs[name]
            parity_spec = parity_specs[name]
            if (
                spec["sha256"] != parity_spec["silver_object_sha256"]
                or spec["byte_count"] != parity_spec["silver_object_bytes"]
                or spec["row_count"] != parity_spec["row_count"]
            ):
                raise ValueError(
                    "semantic manifest table differs from parity evidence"
                )
            response = client.get(url_base + spec["path"])
            response.raise_for_status()
            data = response.content
            if (
                len(data) != spec["byte_count"]
                or _sha256(data) != spec["sha256"]
            ):
                raise ValueError(
                    f"public MBS Parquet identity mismatch: {name}"
                )
            parquet_module: Any = pq
            read_table: Any = parquet_module.read_table
            table = cast("pa.Table", read_table(pa.BufferReader(data)))
            if table.num_rows != spec["row_count"]:
                raise ValueError(
                    f"public MBS Parquet row count mismatch: {name}"
                )
            metadata = table.schema.metadata or {}
            if (
                metadata.get(b"schema_name")
                != f"global-medicines-atlas.mbs-silver.{name}".encode()
                or metadata.get(b"source_id") != b"au-mbs"
                or metadata.get(b"schema_era")
                != admission["source_identity"]["schema_era"].encode()
                or metadata.get(b"source_receipt_sha256")
                != parity["source_receipt_sha256"].encode()
            ):
                raise ValueError(
                    f"public MBS Parquet provenance mismatch: {name}"
                )
            row_source_values = table["source_sha256"].to_pylist()
            if any(not isinstance(value, str) for value in row_source_values):
                raise ValueError(
                    f"public MBS Parquet source digest is invalid: {name}"
                )
            row_source_hashes = {
                value for value in row_source_values if isinstance(value, str)
            }
            if row_source_hashes != {
                admission["source_identity"]["source_sha256"]
            }:
                raise ValueError(
                    f"public MBS Parquet source-row digest mismatch: {name}"
                )
            receipt_hashes.add(
                metadata.get(b"source_receipt_sha256", b"").decode()
            )
            retrieved_at_values.add(metadata.get(b"retrieved_at", b"").decode())
            source_hashes.update(row_source_hashes)
            output[name] = table
    if len(receipt_hashes) != 1 or "" in receipt_hashes:
        raise ValueError("MBS Silver tables do not share one source receipt")
    if len(retrieved_at_values) != 1 or "" in retrieved_at_values:
        raise ValueError("MBS Silver tables do not share one retrieval time")
    if source_hashes != {admission["source_identity"]["source_sha256"]}:
        raise ValueError(
            "MBS Silver tables do not share the admitted source digest"
        )
    return output


def build_qualification() -> dict[str, Any]:
    admission, semantic, parity, _ = _load_verified_inputs()
    tables = _download_objects(admission, semantic, parity)
    metadata = tables["services"].schema.metadata or {}
    effective_date = date.fromisoformat(
        admission["source_identity"]["effective_at"]
    )
    source = MbsGoldAdmittedSilverInput(
        source_sha256=admission["source_identity"]["source_sha256"],
        receipt_sha256=metadata[b"source_receipt_sha256"].decode(),
        catalog_version=admission["source_identity"]["schema_era"],
        source_record_count=admission["source_identity"]["source_record_count"],
        source_effective_date=effective_date,
        retrieved_at=datetime.fromisoformat(metadata[b"retrieved_at"].decode()),
        rights_state=RightsState(metadata[b"rights_state"].decode()),
        admission_sha256=_sha256((ROOT / ADMISSION_PATH).read_bytes()),
        semantic_manifest_sha256=_sha256((ROOT / SEMANTIC_PATH).read_bytes()),
    )
    graph = build_mbs_gold_graph_from_admitted_silver(
        tables["services"], tables["benefits"], source
    )
    negative_controls = _run_negative_controls(tables, source)
    return {
        "schema_id": "global-medicines-atlas.australian-mbs-gold-real-silver-qualification",
        "schema_version": 1,
        "status": "real_admitted_silver_graph_candidate_qualified_for_review",
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "requirement_id": "M-110",
        "implementation_fingerprints": _implementation_fingerprints(),
        "source_identity": admission["source_identity"],
        "public_dataset_identity": admission["public_dataset_identity"],
        "admission_receipt": {
            "path": str(ADMISSION_PATH),
            "sha256": source.admission_sha256,
            "semantic_manifest_sha256": source.semantic_manifest_sha256,
        },
        "verified_objects": [
            {
                "name": name,
                "path": next(
                    table["path"]
                    for table in semantic["tables"]
                    if table["name"] == name
                ),
                "sha256": next(
                    table["sha256"]
                    for table in semantic["tables"]
                    if table["name"] == name
                ),
                "byte_count": next(
                    table["byte_count"]
                    for table in semantic["tables"]
                    if table["name"] == name
                ),
                "row_count": tables[name].num_rows,
            }
            for name in EXPECTED_TABLES
        ],
        "graph": {
            "source_record_count": graph.source_record_count,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "graph_sha256": graph.graph_sha256,
            "candidate_schema_version": graph.schema_version,
            "source_receipt_sha256": source.receipt_sha256,
            "rights_state": source.rights_state.value,
            "source_retrieved_at": source.retrieved_at.isoformat(),
            "source_snapshot_effective_date": source.source_effective_date.isoformat(),
            "qualification": graph.qualification,
            "edge_kind": "source_record_has_benefit",
            "mapping_method": "source-explicit",
            "assertion_basis": "same_source_record",
            "temporal_basis": "source_snapshot_effective_date",
            "confidence": None,
            "confidence_calibration": "not_applicable_source_record",
            "review_state": "not_reviewed",
            "negative_control_outcome": "not_applicable",
            "inferred": False,
            "all_edges_same_record_bound": True,
            "all_nodes_preserve_native_field_states": True,
        },
        "negative_controls": negative_controls,
        "boundaries": {
            "public_candidate_promoted": False,
            "gold_graph_admission_performed": False,
            "graph_publication_performed": False,
            "source_payload_bytes_retained": False,
            "source_values_in_qualification": False,
            "m109_full_denominator_accepted": False,
            "m110_accepted": False,
            "m112_accepted": False,
            "patient_denominator_established": False,
            "pbs_or_clinical_equivalence_claimed": False,
        },
    }


def _run_negative_controls(
    tables: dict[str, pa.Table], source: MbsGoldAdmittedSilverInput
) -> dict[str, bool]:
    services = tables["services"]
    benefits = tables["benefits"]
    forged_source_id = "forged-unmatched-source-record"
    record_ids = benefits["source_record_id"].to_pylist()
    if not record_ids or not isinstance(record_ids[0], str):
        raise ValueError(
            "benefit table has no source record for negative control"
        )
    changed_ids = [forged_source_id, *record_ids[1:]]
    changed_benefits = benefits.set_column(
        benefits.schema.get_field_index("source_record_id"),
        cast("Any", benefits.schema).field("source_record_id"),
        pa.array(changed_ids, type=pa.string()),
    )
    try:
        build_mbs_gold_graph_from_admitted_silver(
            services, changed_benefits, source
        )
    except ValueError as error:
        if "row identities do not pair" not in str(error):
            raise
    else:
        raise ValueError("cross-record MBS graph negative control was accepted")

    forged_digest = "0" * 64
    changed_tables: list[pa.Table] = []
    for table, column in (
        (services, "source_sha256"),
        (benefits, "source_sha256"),
    ):
        values = [forged_digest] * table.num_rows
        index = table.schema.get_field_index(column)
        changed_tables.append(
            table.set_column(
                index,
                cast("Any", table.schema).field(index),
                pa.array(values, type=pa.string()),
            )
        )
    try:
        build_mbs_gold_graph_from_admitted_silver(
            changed_tables[0], changed_tables[1], source
        )
    except ValueError as error:
        if "row identity differs from admitted digests" not in str(error):
            raise
    else:
        raise ValueError("forged source digest negative control was accepted")

    try:
        build_mbs_gold_graph_from_admitted_silver(
            services,
            benefits,
            source.model_copy(update={"rights_state": RightsState.UNKNOWN}),
        )
    except ValueError as error:
        if "requires permitted" not in str(error):
            raise
    else:
        raise ValueError("unpermitted MBS source negative control was accepted")
    return {
        "cross_record_pairing_rejected": True,
        "forged_source_digest_rejected": True,
        "unpermitted_rights_rejected": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check stored value-free receipt and input bindings without downloading data",
    )
    args = parser.parse_args(argv)
    admission, semantic, _, schema = _load_verified_inputs()
    if args.check:
        current = _read_json(OUTPUT_PATH)
        _validate_json_schema(schema, current)
        expected_admission_hash = _sha256((ROOT / ADMISSION_PATH).read_bytes())
        expected_semantic_hash = _sha256((ROOT / SEMANTIC_PATH).read_bytes())
        expected_objects = [
            {
                "name": table["name"],
                "path": table["path"],
                "sha256": table["sha256"],
                "byte_count": table["byte_count"],
                "row_count": table["row_count"],
            }
            for table in semantic["tables"]
        ]
        expected_fingerprints = _implementation_fingerprints()
        expected_bindings = {
            "source_identity": admission["source_identity"],
            "public_dataset_identity": admission["public_dataset_identity"],
            "admission_receipt": {
                "path": str(ADMISSION_PATH),
                "sha256": expected_admission_hash,
                "semantic_manifest_sha256": expected_semantic_hash,
            },
            "verified_objects": expected_objects,
            "implementation_fingerprints": expected_fingerprints,
        }
        if any(
            current.get(name) != expected
            for name, expected in expected_bindings.items()
        ):
            raise SystemExit("real MBS Gold qualification is stale")
        print("real MBS Gold graph qualification checks passed")
        return 0
    qualification = build_qualification()
    _validate_json_schema(schema, qualification)
    (ROOT / OUTPUT_PATH).write_bytes(_canonical_bytes(qualification))
    print(
        f"qualified {qualification['graph']['edge_count']} real MBS same-record edges "
        "from the admitted July 2025 Silver tables"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
