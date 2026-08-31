"""Offline synthetic receipt bytes never establish admission or authority."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

import global_medicines_atlas.federation_receipt_closure as closure
from global_medicines_atlas.federation_receipt_closure import (
    ReceiptPayload,
    verify_receipt_closure,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "contracts/medallion/v4/federation.schema.json").read_bytes()
PAYLOAD = b"synthetic opaque receipt; not a rights or publication decision"
URL = "https://example.org/receipts/synthetic.json"


def fixture():
    document = json.loads(
        (ROOT / "contracts/medallion/v4/fixtures/valid.json").read_bytes()
    )
    receipt = {"url": URL, "sha256": hashlib.sha256(PAYLOAD).hexdigest()}

    def replace(value):
        if isinstance(value, dict):
            if set(value) == {"url", "sha256"}:
                value.update(receipt)
            else:
                for child in value.values():
                    replace(child)
        elif isinstance(value, list):
            for child in value:
                replace(child)

    replace(document)
    document["lineage"]["inputs"] = [copy.deepcopy(receipt)]
    document["lineage"]["promotion_receipt"] = copy.deepcopy(receipt)
    document["recovery"]["restore_receipt"] = copy.deepcopy(receipt)
    document["recovery"]["authorization_receipt"] = copy.deepcopy(receipt)
    document["cache"].update(
        state="removed", cleanup_receipt=copy.deepcopy(receipt)
    )
    document["consumers"] = [
        {
            "repository": "example/consumer",
            "commit": "a" * 40,
            "canary": copy.deepcopy(receipt),
        }
    ]
    return document


def check(document=None, receipts=None):
    return verify_receipt_closure(
        json.dumps(fixture() if document is None else document).encode(),
        (ReceiptPayload(url=URL, payload=PAYLOAD),)
        if receipts is None
        else receipts,
        schema=SCHEMA,
    )


def test_all_nested_roles_retained_while_shared_bytes_counted_once():
    result = check()
    assert {item.role for item in result.roles} == {
        "/publication/receipt",
        "/verification/receipt",
        "/rights/authorization",
        "/discovery/estate_entry",
        "/lineage/inputs/0",
        "/lineage/v1_conformance",
        "/lineage/v2_field_lineage",
        "/lineage/v3_replay",
        "/lineage/promotion_receipt",
        "/recovery/checksum_inventory",
        "/recovery/restore_receipt",
        "/recovery/authorization_receipt",
        "/cache/cleanup_receipt",
        "/consumers/0/canary",
    }
    assert len(result.receipts) == 1
    assert result.receipts[0].byte_count == len(PAYLOAD)
    assert result.scope == "receipt_bytes_only"
    assert "opaque receipt" not in result.model_dump_json()
    assert "admitted_contracts" not in result.model_dump()


@pytest.mark.parametrize(
    "case", ["missing", "extra", "duplicate", "digest", "conflict"]
)
def test_missing_extra_duplicate_and_conflicting_bytes_reject(case):
    document = fixture()
    receipts = (ReceiptPayload(url=URL, payload=PAYLOAD),)
    if case == "missing":
        receipts = ()
    elif case == "extra":
        receipts += (
            ReceiptPayload(url="https://example.org/extra", payload=b"x"),
        )
    elif case == "duplicate":
        receipts *= 2
    elif case == "digest":
        receipts = (ReceiptPayload(url=URL, payload=PAYLOAD[:-1]),)
    else:
        document["rights"]["authorization"]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="receipt"):
        check(document, receipts)


def test_receipt_bodies_are_not_parsed_or_recursively_followed():
    body = json.dumps({
        "url": "http://localhost/never-fetch",
        "sha256": "f" * 64,
    }).encode()
    document = fixture()
    for role in check().roles:
        current = document
        parts = role.role.split("/")[1:]
        for part in parts:
            current = (
                current[int(part)]
                if isinstance(current, list)
                else current[part]
            )
        current["sha256"] = hashlib.sha256(body).hexdigest()
    result = check(document, (ReceiptPayload(url=URL, payload=body),))
    assert len(result.receipts) == 1
    assert "localhost" not in result.model_dump_json()


def test_copied_mutable_or_invalid_payload_is_revalidated():
    original = ReceiptPayload(url=URL, payload=PAYLOAD)
    bad = original.model_copy(update={"payload": bytearray(PAYLOAD)})
    with pytest.raises(ValueError, match="receipt"):
        check(receipts=(bad,))
    with pytest.raises(ValueError, match="receipt"):
        check(receipts=(original.model_copy(update={"url": 1}),))
    with pytest.raises(TypeError, match="count"):
        check(receipts=iter((original,)))
    with pytest.raises(ValueError, match="receipt"):
        check(receipts=(object(),))


def test_distinct_urls_sharing_digest_require_both_supplied_objects():
    document = fixture()
    other = "https://example.org/another-receipt"
    document["publication"]["receipt"]["url"] = other
    with pytest.raises(ValueError, match="missing"):
        check(document)
    supplied = (
        ReceiptPayload(url=URL, payload=PAYLOAD),
        ReceiptPayload(url=other, payload=PAYLOAD),
    )
    result = check(document, supplied)
    assert len(result.receipts) == 2
    assert result == check(document, supplied[::-1])


def test_limits_reject_before_hashing_receipt_payloads(monkeypatch):
    original = ReceiptPayload(url=URL, payload=PAYLOAD)
    monkeypatch.setattr(closure, "MAX_RECEIPT_BYTES", len(PAYLOAD) - 1)
    with pytest.raises(ValueError, match="byte"):
        check(receipts=(original,))
    monkeypatch.setattr(closure, "MAX_RECEIPT_BYTES", len(PAYLOAD))
    monkeypatch.setattr(closure, "MAX_TOTAL_BYTES", len(PAYLOAD))
    assert check().receipts[0].byte_count == len(PAYLOAD)
    monkeypatch.setattr(closure, "MAX_TOTAL_BYTES", len(PAYLOAD) - 1)
    with pytest.raises(ValueError, match="byte"):
        check()


def test_role_and_payload_count_limits_are_inclusive(monkeypatch):
    monkeypatch.setattr(closure, "MAX_REFERENCES", 14)
    assert len(check().roles) == 14
    monkeypatch.setattr(closure, "MAX_REFERENCES", 13)
    with pytest.raises(ValueError, match="reference"):
        check()
    monkeypatch.setattr(closure, "MAX_REFERENCES", 1)
    with pytest.raises(ValueError, match="count"):
        check(receipts=(ReceiptPayload(url=URL, payload=PAYLOAD),) * 2)


def test_schema_pin_contract_size_and_invalid_contract_are_rejected():
    raw = json.dumps(fixture()).encode()
    with pytest.raises(ValueError, match="schema"):
        verify_receipt_closure(raw, (), schema=b"{}")
    with pytest.raises(ValueError, match="contract"):
        verify_receipt_closure(
            b" " * (closure.METADATA_BYTES + 1), (), schema=SCHEMA
        )
    with pytest.raises(ValueError, match="contract"):
        verify_receipt_closure(b"{}", (), schema=SCHEMA)
    document = fixture()
    document["authority"]["schema_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="schema"):
        check(document)


def test_order_independence_and_output_immutability():
    first = check()
    document = fixture()
    second = check(dict(reversed(tuple(document.items()))))
    assert first.roles == second.roles
    assert first.receipts == second.receipts
    mutable = first.model_copy(update={"roles": list(first.roles)})
    checked = type(first).model_validate(mutable)
    mutable.roles.clear()
    assert len(checked.roles) == 14


def test_duplicate_json_keys_cannot_hide_receipt_roles():
    raw = json.dumps(fixture()).encode()
    raw = raw.replace(
        b'"publication": {', b'"publication": {}, "publication": {', 1
    )
    with pytest.raises(ValueError, match="contract"):
        verify_receipt_closure(
            raw, (ReceiptPayload(url=URL, payload=PAYLOAD),), schema=SCHEMA
        )


@pytest.mark.parametrize("case", ["duplicate", "digest", "extra", "budget"])
def test_copied_output_inventory_revalidates(case, monkeypatch):
    result = check()
    if case == "duplicate":
        unsafe = result.model_copy(update={"roles": result.roles * 2})
    elif case == "digest":
        unsafe = result.model_copy(
            update={
                "receipts": (
                    result.receipts[0].model_copy(update={"sha256": "f" * 64}),
                )
            }
        )
    elif case == "extra":
        unsafe = result.model_copy(
            update={
                "receipts": (
                    result.receipts[0].model_copy(
                        update={"url": "https://example.org/extra"}
                    ),
                )
            }
        )
    else:
        monkeypatch.setattr(closure, "MAX_TOTAL_BYTES", len(PAYLOAD) - 1)
        unsafe = result
    with pytest.raises(ValueError, match="receipt"):
        type(result).model_validate(unsafe)


def test_missing_format_plugins_fail_closed(monkeypatch):
    original = closure.FormatChecker
    monkeypatch.setattr(
        closure, "FormatChecker", lambda: original(formats=["date"])
    )
    with pytest.raises(ValueError, match="format"):
        check()


@pytest.mark.parametrize("case", ["count", "individual", "aggregate"])
def test_input_bounds_precede_contract_parse_and_payload_hash(
    case, monkeypatch
):
    raw = json.dumps(fixture()).encode()
    supplied = (ReceiptPayload(url=URL, payload=PAYLOAD),)
    if case == "count":
        monkeypatch.setattr(closure, "MAX_REFERENCES", 0)
    elif case == "individual":
        monkeypatch.setattr(closure, "MAX_RECEIPT_BYTES", len(PAYLOAD) - 1)
    else:
        monkeypatch.setattr(closure, "MAX_TOTAL_BYTES", len(PAYLOAD) - 1)

    def forbidden(*_args, **_kwargs):
        pytest.fail("expensive work before input bounds")

    monkeypatch.setattr(closure, "_document", forbidden)
    monkeypatch.setattr(closure.hashlib, "sha256", forbidden)
    with pytest.raises(ValueError, match=r"byte|count"):
        verify_receipt_closure(raw, supplied, schema=SCHEMA)


@pytest.mark.parametrize("shape", ["receipt", "malformed", "consumer", "split"])
def test_reference_preflight_precedes_schema_unique_items(shape, monkeypatch):
    document = fixture()
    count = 128 if shape == "split" else 257
    refs = [
        {"url": f"https://example.org/{index}", "sha256": "a" * 64}
        for index in range(count)
    ]
    if shape == "malformed":
        refs = [{**ref, "extra": "not-allowed"} for ref in refs]
    if shape in {"consumer", "split"}:
        document["consumers"] = [
            {
                "repository": f"example/consumer-{index}",
                "commit": "a" * 40,
                "canary": ref,
            }
            for index, ref in enumerate(refs)
        ]
    if shape != "consumer":
        document["lineage"]["inputs"] = refs

    class ForbiddenValidator:
        def __init__(self, *_args, **_kwargs):
            pass

        def validate(self, _document):
            pytest.fail("schema uniqueItems reached before reference preflight")

    monkeypatch.setattr(closure, "Draft202012Validator", ForbiddenValidator)
    with pytest.raises(ValueError, match=r"reference|container"):
        check(document)


def test_structural_preflight_has_exact_node_depth_and_container_bounds(
    monkeypatch,
):
    monkeypatch.setattr(closure, "MAX_STRUCTURE_NODES", 2)
    closure._preflight([0])
    with pytest.raises(ValueError, match="node/depth"):
        closure._preflight([0, 1])
    monkeypatch.setattr(closure, "MAX_STRUCTURE_NODES", 8192)
    monkeypatch.setattr(closure, "MAX_STRUCTURE_DEPTH", 2)
    closure._preflight([[0]])
    with pytest.raises(ValueError, match="node/depth"):
        closure._preflight([[["synthetic-private-marker"]]])
    monkeypatch.setattr(closure, "MAX_REFERENCES", 2)
    closure._preflight({"a": 0, "b": 0})
    with pytest.raises(ValueError, match="container"):
        closure._preflight({"a": 0, "b": 0, "c": 0})


def test_preflight_does_not_replace_schema_or_leak_invalid_values():
    document = fixture()
    document["lineage"]["inputs"] = [
        {
            "url": URL,
            "sha256": "a" * 64,
            "extra": "synthetic-private-marker",
        }
    ]
    with pytest.raises(
        ValueError, match="invalid federation contract"
    ) as error:
        check(document)
    assert "synthetic-private-marker" not in str(error.value)
