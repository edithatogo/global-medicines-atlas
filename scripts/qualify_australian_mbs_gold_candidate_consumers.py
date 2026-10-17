"""Qualify all current consumers of the pinned MBS Gold edge candidate."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq
from qualify_australian_mbs_gold_real_silver import (
    ADMISSION_PATH,
    ROOT,
    SEMANTIC_PATH,
    _read_json,  # ruff: ignore[import-private-name] -- reuse qualifier  # pyright: ignore[reportPrivateUsage]
)
from qualify_australian_mbs_gold_real_silver import (
    OUTPUT_PATH as QUALIFICATION_PATH,
)

from global_medicines_atlas.atlas_browser_qualification import (
    qualify_candidate_atlas_browser,
)
from global_medicines_atlas.mbs_gold_consumer_qualification import (
    qualify_consumers,
)
from global_medicines_atlas.platinum_query import (
    DuckDBQueryAdapter,
    Operator,
    PolarsQueryAdapter,
    QueryFilter,
    QuerySpec,
    Scalar,
)
from global_medicines_atlas.platinum_resolver import ProductRead

V4_USE_AUTHORIZATION_PATH = Path(
    "quality/qualifications/"
    "australian-mbs-v4-candidate-use-authorization-20261017.json"
)
MBS_V4_MANIFEST_PATH = Path(
    "quality/qualifications/australian-mbs-v4-candidate-2025-07/manifest.json"
)
MBS_V4_QUALIFICATION_PATH = Path(
    "quality/qualifications/australian-mbs-v4-candidate-2025-07/qualification.json"
)
SOURCE_CANDIDATE_REPORT_PATH = Path(
    "quality/qualifications/"
    "australian-mbs-silver-candidate-qualification-20261017-8c0090db.json"
)
EXPECTED_V4_OBJECT_COUNT = 6
EXPECTED_RECORD_COUNT = 5989
WORKFLOW_PATH = (
    ".github/workflows/australian-mbs-gold-candidate-consumer-qualification.yml"
)
REPOSITORY = "edithatogo/global-medicines-atlas"
MBS_DATASET = "edithatogo/australian-mbs-source-archive"
SCALAR_DECIMAL_COLUMN = "benefit__Benefit100__typed_value"
SCALAR_DATE_COLUMN = "benefit__BenefitStartDate__typed_value"


def qualify_candidate_scalar_queries(
    scalar_path: Path, qualification: dict[str, Any]
) -> dict[str, object]:
    """Run value-free exact decimal/date engine canaries on candidate bytes."""
    if not scalar_path.is_file():
        raise ValueError("candidate scalar Parquet is missing")
    payload = scalar_path.read_bytes()
    if not payload:
        raise ValueError("candidate scalar Parquet is empty")
    parquet_module: Any = pq
    read_table: Any = parquet_module.read_table
    table = cast("pa.Table", read_table(io.BytesIO(payload)))
    metadata = table.schema.metadata or {}
    expected = {
        b"schema_name": b"global-medicines-atlas.mbs-gold-scalar-candidate",
        b"schema_version": b"1",
        b"qualification": b"candidate_only",
        b"consumer_admission": b"not_performed",
        b"graph_sha256": str(qualification["graph"]["graph_sha256"]).encode(),
        b"source_receipt_sha256": str(
            qualification["graph"]["source_receipt_sha256"]
        ).encode(),
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("candidate scalar metadata differs from qualification")
    if not table.num_rows:
        raise ValueError("candidate scalar has no source-record rows")

    query_cases: dict[str, object] = {}
    query_specs: tuple[tuple[str, str, Operator, Decimal | date], ...] = (
        ("decimal", SCALAR_DECIMAL_COLUMN, ">", Decimal("10.00")),
        ("date", SCALAR_DATE_COLUMN, ">=", date(2025, 8, 1)),
    )
    for case, column, operator, value in query_specs:
        spec = QuerySpec(
            columns=("source_ordinal",),
            filters=(QueryFilter(column, operator, value),),
            limit=1000,
        )
        engine_rows: dict[str, tuple[dict[str, Scalar], ...]] = {}
        for adapter in (DuckDBQueryAdapter(), PolarsQueryAdapter()):
            stream = io.BytesIO(payload)
            read = cast(
                "ProductRead",
                SimpleNamespace(verified=SimpleNamespace(stream=stream)),
            )
            engine_rows[adapter.name] = adapter.execute(read, spec)
        if engine_rows["duckdb"] != engine_rows["polars"]:
            raise ValueError(f"candidate scalar {case} engine parity failed")
        query_cases[case] = {
            "engines": ["duckdb", "polars"],
            "returned_rows": len(engine_rows["duckdb"]),
            "row_limit": spec.limit,
            "parity": True,
        }
    return {
        "candidate_only": True,
        "consumer_admission_performed": False,
        "row_count": table.num_rows,
        "parquet_sha256": hashlib.sha256(payload).hexdigest(),
        "query_cases": query_cases,
    }


def candidate_v4_use_binding(
    admission: dict[str, Any],
    authorization: dict[str, Any],
    authorization_sha256: str,
) -> dict[str, object]:
    """Bind the maintainer's exact six-object candidate-use scope."""
    expected_authorization_keys = {
        "schema_id",
        "schema_version",
        "decision",
        "decision_by",
        "recorded_at",
        "source_identity",
        "dataset_identity",
        "scope",
        "authorized_objects",
        "boundaries",
    }

    if (
        authorization.get("schema_id")
        != "global-medicines-atlas.australian-mbs-v4-candidate-use-authorization"
        or authorization.get("schema_version") != 1
        or set(authorization) != expected_authorization_keys
    ):
        raise ValueError("candidate v4 authorization contract changed")
    if authorization.get("decision") != (
        "Authorize the exact six for candidate v4 qualification"
    ):
        raise ValueError("candidate v4 authorization decision is missing")
    if authorization.get("decision_by") != "maintainer":
        raise ValueError("candidate v4 authorization is not maintainer-issued")
    expected_scope = (
        "exact_six_july_2025_mbs_v3_silver_objects_for_candidate_v4_"
        "qualification_and_consumer_canaries"
    )
    if authorization.get("scope") != expected_scope:
        raise ValueError("candidate v4 authorization scope changed")
    source = admission.get("source_identity")
    public = admission.get("public_dataset_identity")
    if not isinstance(source, dict) or not isinstance(public, dict):
        raise TypeError("Silver admission identity is incomplete")
    source = cast("dict[str, Any]", source)
    public = cast("dict[str, Any]", public)
    if authorization.get("source_identity") != {
        "source_id": source.get("source_id"),
        "schema_era": source.get("schema_era"),
        "source_sha256": source.get("source_sha256"),
    }:
        raise ValueError("authorization source identity differs from admission")
    authorized_dataset = authorization.get("dataset_identity")
    if authorized_dataset != {
        "dataset": public.get("dataset"),
        "revision": public.get("current_revision"),
        "manifest_sha256": public.get("manifest_sha256"),
        "candidate_only": True,
    }:
        raise ValueError(
            "authorization dataset identity differs from admission"
        )
    tables = admission.get("tables")
    objects = authorization.get("authorized_objects")
    if not isinstance(tables, list) or not isinstance(objects, list):
        raise TypeError("authorization object list is missing")
    untyped_tables = cast("list[object]", tables)
    untyped_objects = cast("list[object]", objects)
    if any(not isinstance(item, dict) for item in untyped_tables) or any(
        not isinstance(item, dict) for item in untyped_objects
    ):
        raise TypeError("authorization contains an invalid object identity")
    table_records = cast("list[dict[str, Any]]", tables)
    authorized_objects = cast("list[dict[str, Any]]", objects)
    expected_objects = sorted(
        [
            {
                "name": item.get("name"),
                "path": item.get("path"),
                "sha256": item.get("sha256"),
                "byte_count": item.get("byte_count"),
            }
            for item in table_records
        ],
        key=lambda item: str(item["name"]),
    )
    actual_objects = sorted(
        authorized_objects, key=lambda item: str(item.get("name"))
    )
    if (
        len(expected_objects) != EXPECTED_V4_OBJECT_COUNT
        or actual_objects != expected_objects
    ):
        raise ValueError(
            "authorization must match the exact six Silver objects"
        )
    expected_boundaries = {
        "candidate_v4_qualification": True,
        "candidate_consumer_canaries": True,
        "public_release_or_publication": False,
        "production_admission_or_promotion": False,
        "new_rights_or_licensing_conclusion": False,
        "m110_gold_review_or_acceptance": False,
        "m112_federation_acceptance": False,
        "source_coverage_expansion": False,
    }
    if authorization.get("boundaries") != expected_boundaries:
        raise ValueError("candidate v4 authorization boundaries changed")
    return {
        "path": V4_USE_AUTHORIZATION_PATH.as_posix(),
        "sha256": authorization_sha256,
        "scope": expected_scope,
        "authorized_object_count": EXPECTED_V4_OBJECT_COUNT,
        "candidate_only": True,
    }


def _named_rows(value: object, name: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list) or any(
        not isinstance(row, dict) for row in cast("list[object]", value)
    ):
        raise TypeError(f"{name} table inventory is invalid")
    rows = cast("list[dict[str, Any]]", value)
    if len(rows) != EXPECTED_V4_OBJECT_COUNT:
        raise ValueError(f"{name} must contain exactly six tables")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(
            row.get(
                "name",
                row.get(
                    "table",
                    Path(str(row.get("path", ""))).name.removesuffix(
                        ".parquet"
                    ),
                ),
            )
        )
        if key in result:
            raise ValueError(f"{name} contains duplicate table identities")
        result[key] = row
    return result


def _manifest_role_objects(
    manifest: dict[str, Any], role: str
) -> list[dict[str, Any]]:
    value = manifest.get("objects")
    if not isinstance(value, list):
        raise TypeError("MBS v4 manifest object inventory is missing")
    result: list[dict[str, Any]] = []
    for item in cast("list[object]", value):
        if isinstance(item, dict):
            row = cast("dict[str, Any]", item)
            if row.get("role") == role:
                result.append(row)
    return result


def _one_table_lineage(
    name: str,
    authorized: dict[str, Any],
    admission: dict[str, Any],
    semantic: dict[str, Any],
    manifest: dict[str, Any],
    qualification: dict[str, Any],
) -> dict[str, object]:
    identity = {
        "path": manifest.get("path"),
        "sha256": manifest.get("sha256"),
        "byte_count": manifest.get("byte_count"),
    }
    input_identities_match = all(
        {
            "path": row.get("path"),
            "sha256": row.get("sha256"),
            "byte_count": row.get("byte_count"),
        }
        == identity
        for row in (admission, semantic)
    )
    qualification_matches = all((
        qualification.get("row_count") == EXPECTED_RECORD_COUNT,
        semantic.get("row_count") == EXPECTED_RECORD_COUNT,
        qualification.get("field_count")
        == len(semantic.get("native_fields", [])),
        bool(
            re.fullmatch(
                r"[0-9a-f]{64}", str(qualification.get("lineage_sha256"))
            )
        ),
    ))
    if authorized != {"name": name, **identity} or not input_identities_match:
        raise ValueError(f"MBS v4 table identity differs for {name}")
    if not qualification_matches:
        raise ValueError(f"MBS v4 table lineage differs for {name}")
    return {
        "name": name,
        **identity,
        "row_count": EXPECTED_RECORD_COUNT,
        "field_count": qualification["field_count"],
        "field_occurrence_count": qualification["field_occurrence_count"],
        "lineage_sha256": qualification["lineage_sha256"],
    }


def _candidate_table_lineage(
    authorization: dict[str, Any],
    admission: dict[str, Any],
    semantic: dict[str, Any],
    manifest: dict[str, Any],
    qualification: dict[str, Any],
) -> list[dict[str, object]]:
    authorized = _named_rows(
        authorization.get("authorized_objects"), "authorization"
    )
    admitted = _named_rows(admission.get("tables"), "admission")
    semantic_tables = _named_rows(semantic.get("tables"), "semantic manifest")
    object_rows = _manifest_role_objects(
        manifest, "source_faithful_silver_table"
    )
    objects = _named_rows(object_rows, "MBS v4 manifest")
    qualification_tables = _named_rows(
        qualification.get("tables"), "MBS v4 qualification"
    )
    inventories = (
        authorized,
        admitted,
        semantic_tables,
        objects,
        qualification_tables,
    )
    if any(rows.keys() != authorized.keys() for rows in inventories[1:]):
        raise ValueError("MBS v4 lineage table denominators differ")

    return [
        _one_table_lineage(
            name,
            authorized[name],
            admitted[name],
            semantic_tables[name],
            objects[name],
            qualification_tables[name],
        )
        for name in sorted(authorized)
    ]


def _candidate_source_receipt(
    manifest: dict[str, Any], qualification: dict[str, Any]
) -> dict[str, object]:
    receipts = _manifest_role_objects(manifest, "b1_source_receipt")
    if len(receipts) != 1:
        raise ValueError("MBS v4 manifest must bind one B1 source receipt")
    receipt = receipts[0]
    if not all((
        receipt.get("path") == "silver/mbs/v4/2025-07-v3/source-receipt.json",
        bool(re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("sha256")))),
        type(receipt.get("byte_count")) is int,
        receipt.get("byte_count", 0) > 0,
    )):
        raise ValueError("MBS v4 B1 source receipt identity is invalid")
    if qualification.get("receipt_sha256") != manifest.get("source", {}).get(
        "receipt_sha256"
    ):
        raise ValueError("MBS source receipt lineage differs")
    return {
        "source_receipt_sha256": qualification["receipt_sha256"],
        "source_receipt_object": {
            "path": receipt["path"],
            "sha256": receipt["sha256"],
            "byte_count": receipt["byte_count"],
        },
    }


def candidate_v4_lineage_binding(
    admission: dict[str, Any],
    semantic: dict[str, Any],
    authorization: dict[str, Any],
    manifest: dict[str, Any],
    qualification: dict[str, Any],
    source_report: dict[str, Any],
) -> dict[str, object]:
    """Bind the authorized six v4 tables to the existing M-112 lineage chain.

    This is a candidate qualification only. It neither changes the M-112
    denominator nor upgrades the per-object rights/admission gates.
    """
    candidate_state_matches = all((
        manifest.get("candidate_only") is True,
        manifest.get("qualification_sha256")
        == qualification.get("qualification_sha256"),
        source_report.get("source_bytes_retained") is False,
        source_report.get("publication_performed") is False,
        source_report.get("current_blockers") == [],
        qualification.get("promotion_status") == "candidate_only",
        qualification.get("blockers") == ["public_v4_identity_unverified"],
        "public_v4_identity_unverified"
        in source_report.get("resolved_blockers", []),
    ))
    if not candidate_state_matches:
        raise ValueError("MBS v4 candidate qualification boundary changed")
    public_identity = admission.get("public_dataset_identity")
    semantic_identity = semantic.get("public_dataset_identity")
    source_identity = admission.get("source_identity")
    report_identity = source_report.get("public_v4_identity")
    if not all(
        isinstance(value, dict)
        for value in (
            public_identity,
            semantic_identity,
            source_identity,
            report_identity,
        )
    ):
        raise TypeError("MBS candidate lineage identity is incomplete")
    public_identity = cast("dict[str, Any]", public_identity)
    semantic_identity = cast("dict[str, Any]", semantic_identity)
    source_identity = cast("dict[str, Any]", source_identity)
    report_identity = cast("dict[str, Any]", report_identity)
    dataset = manifest.get("dataset")
    revision = report_identity.get("current_revision")
    manifest_sha256 = _sha256(ROOT / MBS_V4_MANIFEST_PATH)
    identities_match = all((
        dataset == MBS_DATASET,
        public_identity.get("dataset") == dataset,
        semantic_identity.get("dataset") == dataset,
        public_identity.get("current_revision") == revision,
        semantic_identity.get("current_revision") == revision,
        public_identity.get("manifest_sha256") == manifest_sha256,
        semantic_identity.get("manifest_sha256") == manifest_sha256,
        report_identity.get("manifest_sha256") == manifest_sha256,
        report_identity.get("candidate_only") is True,
        report_identity.get("status") == "verified",
    ))
    if not identities_match:
        raise ValueError("MBS v4 candidate lineage identity differs")
    if authorization.get("dataset_identity") != {
        "dataset": dataset,
        "revision": revision,
        "manifest_sha256": manifest_sha256,
        "candidate_only": True,
    }:
        raise ValueError("authorization does not bind current MBS v4 identity")
    table_lineage = _candidate_table_lineage(
        authorization, admission, semantic, manifest, qualification
    )
    source_receipt = _candidate_source_receipt(manifest, qualification)
    if not all((
        qualification.get("source_sha256")
        == source_identity.get("source_sha256"),
        qualification.get("source_id") == source_identity.get("source_id"),
        source_identity.get("schema_era") == qualification.get("schema_era"),
    )):
        raise ValueError("MBS source receipt lineage differs")
    return {
        "status": "verified_candidate_source_faithful_silver_lineage",
        "candidate_only": True,
        "dataset": dataset,
        "revision": revision,
        "manifest_sha256": manifest_sha256,
        "source": {
            "source_id": source_identity["source_id"],
            "schema_era": source_identity["schema_era"],
            "source_sha256": source_identity["source_sha256"],
            **source_receipt,
        },
        "admission_path": ADMISSION_PATH.as_posix(),
        "admission_sha256": _sha256(ROOT / ADMISSION_PATH),
        "semantic_manifest_path": SEMANTIC_PATH.as_posix(),
        "semantic_manifest_sha256": _sha256(ROOT / SEMANTIC_PATH),
        "source_candidate_report_path": SOURCE_CANDIDATE_REPORT_PATH.as_posix(),
        "source_candidate_report_sha256": _sha256(
            ROOT / SOURCE_CANDIDATE_REPORT_PATH
        ),
        "tables": table_lineage,
        "boundaries": {
            "source_values_included": False,
            "source_bytes_retained": False,
            "public_dataset_mutation": False,
            "production_admission_or_promotion": False,
            "new_rights_or_licensing_conclusion": False,
            "m110_gold_review_or_acceptance": False,
            "m112_federation_acceptance": False,
            "source_coverage_expansion": False,
        },
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hosted_workflow_binding(
    *, commit: str, repository: str, run_id: str, run_attempt: str
) -> dict[str, object]:
    """Bind the aggregate receipt to the exact protected qualification run."""
    if repository != REPOSITORY or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("hosted qualification repository or commit is invalid")
    if not run_id.isdecimal() or int(run_id) < 1:
        raise ValueError("hosted qualification run ID is invalid")
    if not run_attempt.isdecimal() or int(run_attempt) < 1:
        raise ValueError("hosted qualification run attempt is invalid")
    return {
        "repository": repository,
        "workflow": WORKFLOW_PATH,
        "commit": commit,
        "run_id": int(run_id),
        "run_attempt": int(run_attempt),
        "run_url": f"https://github.com/{repository}/actions/runs/{run_id}",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edge-file", required=True, type=Path)
    parser.add_argument("--scalar-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workflow-commit", required=True)
    parser.add_argument("--workflow-repository", required=True)
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--workflow-run-attempt", required=True)
    args = parser.parse_args(argv)
    output = args.output.expanduser()
    qualification: dict[str, Any] = _read_json(QUALIFICATION_PATH)
    authorization = _read_json(V4_USE_AUTHORIZATION_PATH)
    admission = _read_json(ADMISSION_PATH)
    semantic = _read_json(SEMANTIC_PATH)
    v4_manifest = _read_json(MBS_V4_MANIFEST_PATH)
    v4_qualification = _read_json(MBS_V4_QUALIFICATION_PATH)
    source_report = _read_json(SOURCE_CANDIDATE_REPORT_PATH)
    authorization_binding = candidate_v4_use_binding(
        admission,
        authorization,
        _sha256(ROOT / V4_USE_AUTHORIZATION_PATH),
    )
    lineage_binding = candidate_v4_lineage_binding(
        admission,
        semantic,
        authorization,
        v4_manifest,
        v4_qualification["qualification"],
        source_report,
    )
    receipt = qualify_consumers(
        args.edge_file.expanduser(),
        qualification,
        expected_bindings={
            "input_admission_sha256": _sha256(ROOT / ADMISSION_PATH),
            "input_semantic_manifest_sha256": _sha256(ROOT / SEMANTIC_PATH),
            "graph_sha256": cast("str", qualification["graph"]["graph_sha256"]),
        },
        browser_qualifier=qualify_candidate_atlas_browser,
    )
    receipt["candidate_v4_use_authorization"] = authorization_binding
    receipt["candidate_v4_source_lineage"] = lineage_binding
    receipt["candidate_scalar_query_canary"] = qualify_candidate_scalar_queries(
        args.scalar_file.expanduser(), qualification
    )
    receipt["hosted_workflow"] = hosted_workflow_binding(
        commit=args.workflow_commit,
        repository=args.workflow_repository,
        run_id=args.workflow_run_id,
        run_attempt=args.workflow_run_attempt,
    )
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        stream.write("\n")
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
