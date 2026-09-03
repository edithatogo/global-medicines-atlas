"""Fail-closed contracts for remote-query and Xet frontier experiments."""

import copy
import hashlib
import json
from typing import Any

import pytest
from pydantic import ValidationError

from global_medicines_atlas.frontier_remote_query import (
    RemoteQueryQualification,
    XetRestoreQualification,
)

SHA = "a" * 64
REVISION = "b" * 40


def query_identity() -> dict[str, Any]:
    query: dict[str, Any] = {
        "query_id": "pbs-example-funded-items-v1",
        "predicate": "schedule_code = 'GE' AND benefit_amount > 0",
        "projected_columns": ["item_code", "benefit_amount"],
        "order_by": ["item_code"],
        "limit": 100,
    }
    encoded = json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
    query["canonical_sha256"] = hashlib.sha256(encoded).hexdigest()
    return query


def query_document() -> dict[str, Any]:
    query = query_identity()
    observations: list[dict[str, Any]] = [
        {
            "engine": engine,
            "scenario": scenario,
            "outcome": {
                "interrupted_resume": "resumed",
                "offline": "offline_rejected",
            }.get(scenario, "passed"),
            "query_sha256": query["canonical_sha256"],
            "result_sha256": None if scenario == "offline" else SHA,
            "request_count": 0 if scenario == "offline" else 2,
            "transferred_bytes": 0 if scenario == "offline" else 512,
            "peak_memory_bytes": 1024,
            "cache_bytes": 0 if scenario in {"cold", "offline"} else 128,
            "scanned_rows": 0 if scenario == "offline" else 100,
            "returned_rows": 0 if scenario == "offline" else 25,
            "interrupted_after_bytes": (
                256 if scenario == "interrupted_resume" else None
            ),
            "resumed_from_byte": (
                256 if scenario == "interrupted_resume" else None
            ),
            "latency_ns": 1000,
        }
        for engine in ("python_fallback", "duckdb", "polars", "arrow")
        for scenario in (
            "cold",
            "warm",
            "concurrent",
            "interrupted_resume",
            "offline",
        )
    ]
    return {
        "schema_id": "global-medicines-atlas.frontier-remote-query",
        "schema_version": 1,
        "public_object": {
            "dataset": "edithatogo/australian-pbs-source-archive",
            "revision": REVISION,
            "path": "silver/example.parquet",
            "sha256": SHA,
            "byte_count": 2048,
            "anonymously_verified": True,
        },
        "profile": {
            "maximum_rows": 100,
            "maximum_source_bytes": 4096,
            "maximum_requests": 8,
            "maximum_memory_bytes": 8192,
            "maximum_cache_bytes": 1024,
        },
        "query": query,
        "expected_result_sha256": SHA,
        "observations": observations,
        "production_dependency_adopted": False,
        "technology_promotion_claimed": False,
    }


def xet_document() -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    for index in range(2):
        digest = f"{index + 1:064x}"
        objects.append({
            "dataset": "edithatogo/australian-pbs-source-archive",
            "revision": f"{index + 1:040x}",
            "path": f"bronze/release-{index}.zip",
            "sha256": digest,
            "byte_count": 2048 + index,
            "anonymously_verified": True,
            "restored_sha256": digest,
            "request_count": 2,
            "transferred_bytes": 1024,
            "reused_chunk_count": index,
            "new_chunk_count": 2 - index,
        })
    return {
        "schema_id": "global-medicines-atlas.frontier-xet-restore",
        "schema_version": 1,
        "objects": objects,
        "source_identity_basis": "per_object_sha256",
        "chunk_identity_is_evidence_truth": False,
        "production_dependency_adopted": False,
        "technology_promotion_claimed": False,
    }


def test_complete_remote_query_matrix_preserves_parity_and_bounds() -> None:
    report = RemoteQueryQualification.model_validate(query_document())
    assert len(report.observations) == 20
    assert {item.engine for item in report.observations} == {
        "python_fallback",
        "duckdb",
        "polars",
        "arrow",
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("request_count", 9, "request bound"),
        ("transferred_bytes", 4097, "source-byte bound"),
        ("peak_memory_bytes", 8193, "memory bound"),
        ("cache_bytes", 1025, "cache bound"),
        ("scanned_rows", 101, "row bound"),
        ("returned_rows", 101, "row bound"),
    ],
)
def test_remote_query_resource_bounds_fail_closed(
    field: str, value: int, message: str
) -> None:
    raw = query_document()
    raw["observations"][0][field] = value
    if field == "returned_rows":
        raw["observations"][0]["scanned_rows"] = value
    with pytest.raises(ValidationError, match=message):
        RemoteQueryQualification.model_validate(raw)


def test_remote_query_requires_complete_engine_scenario_denominator() -> None:
    raw = query_document()
    raw["observations"].pop()
    with pytest.raises(ValidationError, match="engine/scenario denominator"):
        RemoteQueryQualification.model_validate(raw)


def test_remote_query_binds_exact_query_and_each_observation() -> None:
    raw = query_document()
    raw["query"]["predicate"] = "schedule_code = 'DIFFERENT'"
    with pytest.raises(ValidationError, match="canonical identity"):
        RemoteQueryQualification.model_validate(raw)

    raw = query_document()
    raw["observations"][0]["query_sha256"] = "c" * 64
    with pytest.raises(ValidationError, match="observation identity"):
        RemoteQueryQualification.model_validate(raw)

    raw = query_document()
    raw["query"]["limit"] = 101
    raw["query"] = query_identity() | {"limit": 101}
    encoded = json.dumps(
        {
            key: value
            for key, value in raw["query"].items()
            if key != "canonical_sha256"
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    raw["query"]["canonical_sha256"] = hashlib.sha256(encoded).hexdigest()
    with pytest.raises(ValidationError, match="limit exceeds row bound"):
        RemoteQueryQualification.model_validate(raw)

    for field in ("projected_columns", "order_by"):
        raw = query_document()
        raw["query"][field] = ["item_code", "item_code"]
        encoded = json.dumps(
            {
                key: value
                for key, value in raw["query"].items()
                if key != "canonical_sha256"
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        raw["query"]["canonical_sha256"] = hashlib.sha256(encoded).hexdigest()
        with pytest.raises(ValidationError, match="columns repeat"):
            RemoteQueryQualification.model_validate(raw)


def test_remote_query_rejects_parity_and_failure_semantic_drift() -> None:
    raw = query_document()
    raw["observations"][0]["result_sha256"] = "c" * 64
    with pytest.raises(ValidationError, match="result parity"):
        RemoteQueryQualification.model_validate(raw)

    raw = query_document()
    offline = next(
        item for item in raw["observations"] if item["scenario"] == "offline"
    )
    offline["request_count"] = 1
    with pytest.raises(ValidationError, match="offline observation"):
        RemoteQueryQualification.model_validate(raw)

    raw = query_document()
    interrupted = next(
        item
        for item in raw["observations"]
        if item["scenario"] == "interrupted_resume"
    )
    interrupted["result_sha256"] = None
    with pytest.raises(ValidationError, match="must resume exactly"):
        RemoteQueryQualification.model_validate(raw)

    raw = query_document()
    interrupted = next(
        item
        for item in raw["observations"]
        if item["scenario"] == "interrupted_resume"
    )
    interrupted["resumed_from_byte"] = 128
    with pytest.raises(ValidationError, match="must resume exactly"):
        RemoteQueryQualification.model_validate(raw)

    raw = query_document()
    warm = next(
        item for item in raw["observations"] if item["scenario"] == "warm"
    )
    warm["resumed_from_byte"] = 1
    with pytest.raises(ValidationError, match="has resume offsets"):
        RemoteQueryQualification.model_validate(raw)

    raw = query_document()
    raw["observations"][0]["returned_rows"] = 101
    raw["profile"]["maximum_rows"] = 200
    with pytest.raises(ValidationError, match="returned rows exceed"):
        RemoteQueryQualification.model_validate(raw)

    raw = query_document()
    cold = next(
        item for item in raw["observations"] if item["scenario"] == "cold"
    )
    cold["result_sha256"] = None
    with pytest.raises(ValidationError, match="must pass with a result"):
        RemoteQueryQualification.model_validate(raw)


def test_remote_query_requires_exact_anonymous_object_identity() -> None:
    raw = query_document()
    raw["public_object"]["anonymously_verified"] = False
    with pytest.raises(ValidationError, match="anonymous verification"):
        RemoteQueryQualification.model_validate(raw)


def test_xet_restore_keeps_chunk_reuse_separate_from_source_identity() -> None:
    report = XetRestoreQualification.model_validate(xet_document())
    assert len(report.objects) == 2
    assert report.chunk_identity_is_evidence_truth is False


def test_xet_restore_rejects_digest_or_revision_denominator_drift() -> None:
    raw = xet_document()
    raw["objects"][0]["restored_sha256"] = "f" * 64
    with pytest.raises(ValidationError, match="restored digest"):
        XetRestoreQualification.model_validate(raw)

    raw = xet_document()
    raw["objects"][1] = copy.deepcopy(raw["objects"][0])
    with pytest.raises(ValidationError, match="two exact revisions"):
        XetRestoreQualification.model_validate(raw)

    raw = xet_document()
    raw["objects"][0]["reused_chunk_count"] = 0
    raw["objects"][0]["new_chunk_count"] = 0
    with pytest.raises(ValidationError, match="chunk denominator"):
        XetRestoreQualification.model_validate(raw)
