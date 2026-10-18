"""Content screening rejects synthetic risk canaries before export."""

import hashlib
import json

import pytest

from global_medicines_atlas.frontier_content_screening import (
    ScreenedPayload,
    screen_graph_payloads,
)


def test_screening_finds_sensitive_field_names_without_echoing_values() -> None:
    payload = json.dumps({
        "fields": [{"name": "patient_name", "value": "Ada Example"}]
    })

    receipt = screen_graph_payloads((
        ScreenedPayload(path="node:1", payload=payload),
    ))

    assert receipt.state == "review_required"
    assert [item.category for item in receipt.findings] == [
        "sensitive_field_name"
    ]
    assert "Ada Example" not in receipt.model_dump_json()


@pytest.mark.parametrize(
    ("carrier", "field_name"),
    [
        ("native_name", "patient_name"),
        ("source_field_id", "member_id"),
        ("path", "$.person.email"),
        ("schema_path", "schema/subscriber/address"),
    ],
)
def test_screening_recognizes_native_graph_field_name_carriers(
    carrier: str, field_name: str
) -> None:
    payload = json.dumps({carrier: field_name, "native_value": "synthetic"})

    receipt = screen_graph_payloads((
        ScreenedPayload(path="node:native-field", payload=payload),
    ))

    assert receipt.state == "review_required"
    assert [item.category for item in receipt.findings] == [
        "sensitive_field_name"
    ]
    assert field_name not in receipt.model_dump_json()


def test_screening_finds_direct_identifier_patterns() -> None:
    payload = json.dumps({
        "field": "contact",
        "value": "synthetic@example.invalid",
    })

    receipt = screen_graph_payloads((
        ScreenedPayload(path="edge:1", payload=payload),
    ))

    assert receipt.state == "review_required"
    assert {item.category for item in receipt.findings} == {"email_like_value"}


def test_screening_uses_exact_digest_canaries_without_storing_values() -> None:
    canary = "SYNTHETIC-RESTRICTED-CONTENT-CANARY"
    payload = json.dumps({"value": canary})
    digest = hashlib.sha256(canary.encode()).hexdigest()

    receipt = screen_graph_payloads(
        (ScreenedPayload(path="edge:2", payload=payload),),
        blocked_value_sha256=frozenset({digest}),
    )

    assert {item.category for item in receipt.findings} == {
        "known_value_digest"
    }
    assert canary not in receipt.model_dump_json()


@pytest.mark.parametrize(
    "payload",
    [
        '{"value":"safe","value":"ambiguous"}',
        "not-json",
        '"scalar"',
    ],
)
def test_screening_fails_closed_on_invalid_or_ambiguous_payload(
    payload: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match="screening payload"):
        screen_graph_payloads((
            ScreenedPayload(path="node:bad", payload=payload),
        ))


def test_clean_synthetic_payload_is_screened_but_not_cleared() -> None:
    receipt = screen_graph_payloads((
        ScreenedPayload(path="node:clean", payload='{"name":"Medicine X"}'),
    ))

    assert receipt.state == "no_pattern_detected"
    assert receipt.rights_cleared is False
    assert receipt.payload_count == 1


def test_screening_rejects_empty_payload_set() -> None:
    with pytest.raises(ValueError, match="at least one payload"):
        screen_graph_payloads(())
