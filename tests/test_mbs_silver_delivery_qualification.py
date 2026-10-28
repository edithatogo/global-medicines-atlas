"""Focused fail-closed controls for exact existing Silver delivery evidence."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from global_medicines_atlas import (
    mbs_silver_delivery_qualification as module,
)
from global_medicines_atlas.mbs_silver_delivery_qualification import (
    PINS,
    digest,
    qualify_delivery,
    verify_payload,
)
from global_medicines_atlas.receipts import SourceReceipt


def test_identity_binds_bytes_and_size() -> None:
    payload = b"synthetic"
    sha = hashlib.sha256(payload).hexdigest()
    verify_payload(payload, len(payload), sha)
    with pytest.raises(ValueError, match="digest"):
        verify_payload(payload, len(payload) + 1, sha)
    with pytest.raises(ValueError, match="digest"):
        verify_payload(payload, len(payload), "0" * 64)


def test_invalid_commit_prevents_fetch(tmp_path: Path) -> None:
    def forbidden(_url: str, _limit: int) -> bytes:
        pytest.fail("transport must remain unused")

    with pytest.raises(ValueError, match="Git identity"):
        qualify_delivery(tmp_path, forbidden, producer_commit="main")


def test_changed_input_prevents_fetch(tmp_path: Path) -> None:
    path = tmp_path / next(iter(PINS))
    path.parent.mkdir(parents=True)
    path.write_text("{}")

    def forbidden(_url: str, _limit: int) -> bytes:
        pytest.fail("transport must remain unused")

    with pytest.raises(ValueError, match="document digest"):
        qualify_delivery(tmp_path, forbidden, producer_commit="a" * 40)


def test_canonical_hash_is_key_order_independent() -> None:
    assert digest({"b": 2, "a": 1}) == digest({"a": 1, "b": 2})
    assert digest([1, 2]) != digest([2, 1])


def test_replay_checks_values_and_native_preservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch = pa.RecordBatch.from_pylist([
        {
            "ItemNum": {
                "native_state": "value",
                "native_value": "synthetic",
                "typed_value": "synthetic",
            }
        }
    ])
    sink = io.BytesIO()
    pq.write_table(pa.Table.from_batches([batch]), sink)  # pyright: ignore[reportUnknownMemberType]
    payload = sink.getvalue()
    monkeypatch.setattr(module, "EXPECTED_ROWS", 1)
    monkeypatch.setattr(
        module,
        "mbs_field_contracts",
        lambda: (
            SimpleNamespace(target_table="services", native_name="ItemNum"),
        ),
    )

    def replay(*_args: object, **_kwargs: object) -> Iterator[pa.RecordBatch]:
        return iter((batch,))

    monkeypatch.setattr(module, "iter_mbs_silver_batches", replay)
    monkeypatch.setattr(
        module,
        "MBS_SILVER_OBJECTS",
        {
            "services": SimpleNamespace(
                path="synthetic/services.parquet",
                byte_count=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
            )
        },
    )
    report = module.compare_table(
        b"synthetic",
        cast("SourceReceipt", cast("Any", object())),
        payload,
        "services",
    )
    assert report["passed"] is True
    assert report["native_values_preserved"] is True
    assert "synthetic" not in str(report["replay_sha256"])
    changed = pa.RecordBatch.from_pylist([
        {
            "ItemNum": {
                "native_state": "value",
                "native_value": "changed",
                "typed_value": "changed",
            }
        }
    ])

    def changed_replay(
        *_args: object, **_kwargs: object
    ) -> Iterator[pa.RecordBatch]:
        return iter((changed,))

    monkeypatch.setattr(module, "iter_mbs_silver_batches", changed_replay)
    report = module.compare_table(
        b"synthetic",
        cast("SourceReceipt", cast("Any", object())),
        payload,
        "services",
    )
    assert report["passed"] is False
    assert report["native_values_preserved"] is False


@pytest.mark.parametrize("scenario", ["pass", "mismatch"])
def test_full_six_object_qualification(  # ruff: ignore[too-many-locals, too-many-statements] -- one integrated success and fail-closed scenario exercises the whole bounded workflow.
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    """Exercise all role assembly and actual contract schemas with fake bytes."""
    mismatch = scenario == "mismatch"
    repo = Path(__file__).resolve().parents[1]
    shutil.copytree(
        repo / "contracts/medallion", tmp_path / "contracts/medallion"
    )
    source = b"<MBS_XML><Data><ItemNum>1</ItemNum></Data></MBS_XML>"
    source_sha = hashlib.sha256(source).hexdigest()
    original = SourceReceipt.model_validate_json(
        (repo / module.RECEIPT_PATH).read_bytes()
    )
    receipt = original.model_copy(
        update={
            "payload": original.payload.model_copy(
                update={"sha256": source_sha, "byte_count": len(source)}
            )
        }
    )
    receipt_path = tmp_path / module.RECEIPT_PATH
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(receipt.model_dump_json())
    payloads: dict[str, bytes] = {}
    objects: dict[str, Any] = {}
    for name, obj in module.MBS_SILVER_OBJECTS.items():
        batches = tuple(
            module.iter_mbs_silver_batches(
                source, receipt, table=cast("Any", name), date_format="mbs-dmy"
            )
        )
        table = pa.Table.from_batches(batches)
        if mismatch and name == "caps":
            table = table.set_column(
                0,
                table.schema.field(0),
                pa.array(["different"], type=table.schema.field(0).type),
            )
        sink = io.BytesIO()
        pq.write_table(table, sink)  # pyright: ignore[reportUnknownMemberType]
        payloads[name] = sink.getvalue()
        objects[name] = SimpleNamespace(
            path=obj.path,
            byte_count=len(payloads[name]),
            sha256=hashlib.sha256(payloads[name]).hexdigest(),
        )
    monkeypatch.setattr(module, "MBS_SILVER_OBJECTS", objects)
    monkeypatch.setattr(module, "EXPECTED_ROWS", 1)
    monkeypatch.setattr(module, "SOURCE_OBJECT_BYTES", len(source))
    monkeypatch.setattr(module, "SOURCE_OBJECT_SHA256", source_sha)
    monkeypatch.setattr(module, "SOURCE_RECEIPT_SHA256", receipt.digest())
    pins = {}
    for path in module.PINS:
        document = json.loads((repo / path).read_text())
        entries = [
            {
                "path": obj.path,
                "byte_count": obj.byte_count,
                "sha256": obj.sha256,
            }
            for obj in objects.values()
        ]
        if "manifest.json" in path:
            document["objects"] = entries
        elif "semantic-manifest" in path:
            document["source_identity"]["source_sha256"] = source_sha
        elif "lineage-reviewed" in path:
            document["outputs"] = entries
        else:
            document["authorized_objects"] = entries
        raw = json.dumps(document).encode()
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        pins[path] = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(module, "PINS", pins)
    calls: list[str] = []

    def fetch(url: str, limit: int) -> bytes:
        calls.append(url)
        data = (
            source
            if url == module.SOURCE_URI
            else payloads[url.rsplit("/", 1)[1].removesuffix(".parquet")]
        )
        assert len(data) == limit
        return data

    reports = module.qualify_delivery(tmp_path, fetch, producer_commit="b" * 40)
    assert len(reports) == 7
    assert len(calls) == 13
    assert len(reports["v2-field-lineage"]["records"]) == 40
    assert reports["qualification"]["status"] == (
        "blocked" if mismatch else "passed"
    )
    assert reports["silver-promotion"]["status"] == (
        "blocked" if mismatch else "approved_within_scope"
    )
    assert all(
        item["status"] == ("blocked" if mismatch else "approved")
        for item in reports["v1-conformance"]["promotion_decisions"]
    )
    assert reports["cache-cleanup"]["remaining_entries"] == 0
    assert reports["primary-restore"]["object_count"] == 6
    module.validate_role_semantics(
        reports["v1-conformance"],
        reports["v2-field-lineage"],
        reports["v3-backfill-replay"],
    )
