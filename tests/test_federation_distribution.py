"""Synthetic denominator tests; no source bytes or publication authority."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from jsonschema import FormatChecker

from global_medicines_atlas.federation_distribution import (
    ProducedObject,
    reconcile_distribution,
)

ROOT = Path(__file__).resolve().parents[1] / "contracts/medallion/v4"
SCHEMA = (ROOT / "federation.schema.json").read_bytes()


def candidate(layer: str = "silver") -> tuple[ProducedObject, dict[str, Any]]:
    document = json.loads((ROOT / "fixtures/valid.json").read_bytes())
    document["source"].update(
        layer=layer,
        bronze_stratum="B2" if layer == "bronze" else None,
        representation="projection",
    )
    document["lineage"]["inputs"] = [document["verification"]["receipt"]]
    document["lineage"]["promotion_receipt"] = document["verification"][
        "receipt"
    ]
    obj = ProducedObject(
        producer_repository="example/producer",
        source_id="synthetic-mbs",
        acquisition_id="synthetic-acquisition",
        layer=layer,
        path="raw/synthetic.xml",
        sha256="d" * 64,
        byte_count=11,
        evidence_kind="synthetic",
    )
    return obj, document


def reconcile(
    objects: list[ProducedObject], documents: list[dict[str, Any]]
) -> Any:
    return reconcile_distribution(
        objects,
        [json.dumps(document).encode() for document in documents],
        schema=SCHEMA,
        destinations=dict.fromkeys(
            ("bronze", "silver", "gold", "platinum"), "example/synthetic-mbs"
        ),
    )


@pytest.mark.parametrize("layer", ["bronze", "silver", "gold", "platinum"])
def test_exact_object_has_one_immutable_destination(layer: str) -> None:
    obj, document = candidate(layer)
    bindings = reconcile([obj], [document])
    assert len(bindings) == 1
    assert bindings[0].object == obj
    assert bindings[0].revision == "a" * 40
    assert bindings[0].dataset == "example/synthetic-mbs"


@pytest.mark.parametrize(
    "mode", ["missing", "extra", "duplicate_object", "duplicate_contract"]
)
def test_denominator_must_match_exactly(mode: str) -> None:
    obj, document = candidate()
    objects = [] if mode == "extra" else [obj]
    documents = [] if mode == "missing" else [document]
    if mode == "duplicate_object":
        objects.append(obj)
    if mode == "duplicate_contract":
        documents.append(document)
    with pytest.raises(ValueError, match=r"empty|missing|duplicate"):
        reconcile(objects, documents)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sha256", "e" * 64),
        ("byte_count", 12),
        ("byte_count", True),
        ("evidence_kind", "live"),
        ("source_id", "different"),
        ("producer_repository", "different/producer"),
        ("layer", "gold"),
    ],
)
def test_object_identity_cannot_be_substituted(field: str, value: Any) -> None:
    obj, document = candidate()
    with pytest.raises(ValueError, match=r"mismatched|integer"):
        reconcile([replace(obj, **{field: value})], [document])


@pytest.mark.parametrize(
    ("group", "field", "value"),
    [
        ("location", "revision", "main"),
        ("location", "private", True),
        ("location", "gated", "auto"),
        ("location", "path", "../escape"),
        ("authority", "schema_sha256", "e" * 64),
        ("verification", "bytes", 12),
        ("source", "retrieved_at", "invalid"),
    ],
)
def test_unsafe_contract_is_rejected(
    group: str, field: str, value: Any
) -> None:
    obj, document = candidate()
    document[group][field] = value
    with pytest.raises(ValueError, match="invalid federation contract"):
        reconcile([obj], [document])


def test_destination_is_bound_to_caller_topology() -> None:
    obj, document = candidate()
    with pytest.raises(ValueError, match="destination"):
        reconcile_distribution(
            [obj],
            [json.dumps(document).encode()],
            schema=SCHEMA,
            destinations={"silver": "example/different"},
        )


def test_empty_inventory_cannot_claim_completion() -> None:
    with pytest.raises(ValueError, match="empty"):
        reconcile([], [])


def test_schema_bytes_are_pinned() -> None:
    obj, document = candidate()
    with pytest.raises(ValueError, match="schema"):
        reconcile_distribution(
            [obj],
            [json.dumps(document).encode()],
            schema=b"{}",
            destinations={},
        )


@pytest.mark.parametrize(
    "raw", [b"{}", b"null", b"invalid", b" " * (1024 * 1024 + 1)]
)
def test_malformed_or_oversized_document(raw: bytes) -> None:
    obj, _ = candidate()
    with pytest.raises(ValueError, match="contract"):
        reconcile_distribution([obj], [raw], schema=SCHEMA, destinations={})


def test_missing_format_plugins_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(FormatChecker, "checkers", {})
    obj, document = candidate()
    with pytest.raises(ValueError, match="format validators"):
        reconcile([obj], [document])


def test_raw_objects_and_replicas_are_not_primary_projections() -> None:
    obj, document = candidate("bronze")
    document["source"]["representation"] = "raw"
    with pytest.raises(ValueError, match="primary derived"):
        reconcile([obj], [document])
    document["source"]["representation"] = "projection"
    document["recovery"]["role"] = "compatibility_replica"
    with pytest.raises(ValueError, match="primary derived"):
        reconcile([obj], [document])


def test_output_order_and_duplicate_remote_location() -> None:
    first, doc1 = candidate()
    second, doc2 = candidate()
    second = replace(second, acquisition_id="other")
    doc2["source"]["acquisition_id"] = "other"
    with pytest.raises(ValueError, match="duplicate distribution"):
        reconcile([first, second], [doc1, doc2])
    second = replace(second, path="tables/other.parquet")
    for group in ("location", "verification", "rights"):
        doc2[group]["path"] = second.path
    bindings = reconcile([second, first], [doc1, doc2])
    assert [binding.object for binding in bindings] == [second, first]
