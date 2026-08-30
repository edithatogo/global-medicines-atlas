"""Portable v4 contract canaries; every fixture is synthetic, not publication."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from global_medicines_atlas.federation import validate_federation_semantics

CONTRACT = Path(__file__).resolve().parents[1] / "contracts/medallion/v4"


def load(name: str) -> dict[str, Any]:
    return json.loads((CONTRACT / name).read_text())


def test_valid_contract() -> None:
    schema = load("federation.schema.json")
    Draft202012Validator.check_schema(schema)
    document = load("fixtures/valid.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        document
    )
    validate_federation_semantics(document)


def test_schema_digest_is_pinned() -> None:
    assert hashlib.sha256(
        (CONTRACT / "federation.schema.json").read_bytes()
    ).hexdigest() == (
        "ac28485a70e0853266e4c140f9a07cd557eb27816b0b408b9bf2927a4cffacec"
    )


def test_every_field_is_required() -> None:
    """An omitted nested field must not quietly become an unverified default."""
    document = load("fixtures/valid.json")
    validator = Draft202012Validator(load("federation.schema.json"))
    for group, value in document.items():
        candidate = copy.deepcopy(document)
        del candidate[group]
        assert not validator.is_valid(candidate), group
        if isinstance(value, dict):
            for field in value:
                candidate = copy.deepcopy(document)
                del candidate[group][field]
                assert not validator.is_valid(candidate), (group, field)


@pytest.mark.parametrize(
    ("group", "field", "value"),
    [
        ("location", "revision", "main"),
        ("location", "revision", "a" * 40 + "\n"),
        ("location", "path", "raw/file.xml\n"),
        ("location", "sha256", "d" * 64 + "\n"),
        ("location", "path", "../secret"),
        ("location", "path", "/absolute"),
        ("location", "path", "raw/%2e%2e/secret"),
        ("location", "path", "raw//file"),
        ("location", "private", True),
        ("location", "gated", "auto"),
        ("location", "bytes", -1),
        ("location", "sha256", "bad"),
        ("publication", "origin", "workstation"),
        ("verification", "anonymous", False),
        ("verification", "status", "pending"),
        ("rights", "publication", "pending"),
        ("rights", "sensitivity", "unresolved"),
        ("cache", "offline_behavior", "use_any_cached_bytes"),
        ("source", "retrieved_at", "not-a-date"),
        ("source", "bronze_stratum", "B4"),
    ],
)
def test_schema_rejects_unsafe_fields(
    group: str, field: str, value: Any
) -> None:
    document = load("fixtures/valid.json")
    document[group][field] = value
    validator = Draft202012Validator(
        load("federation.schema.json"), format_checker=FormatChecker()
    )
    assert not validator.is_valid(document)


@pytest.mark.parametrize(
    ("group", "field", "value", "reason"),
    [
        ("verification", "revision", "b" * 40, "verification identity"),
        ("verification", "sha256", "b" * 64, "verification identity"),
        ("verification", "bytes", 12, "verification identity"),
        ("verification", "path", "raw/other.xml", "verification identity"),
        ("rights", "subject_sha256", "b" * 64, "authorization identity"),
        ("rights", "dataset", "example/other", "authorization identity"),
        ("source", "layer", "silver", "Bronze stratum"),
        ("source", "representation", "projection", "projection lineage"),
        ("verification", "verified_at", "2025-01-01T00:00:00Z", "time order"),
        ("cache", "expires_at", "2025-01-01T00:00:00Z", "cache expiry"),
        ("cache", "cleanup_receipt", None, "cleanup receipt"),
        (
            "publication",
            "run",
            "https://github.com/other/repo/actions/runs/1",
            "producer",
        ),
    ],
)
def test_semantics_rejects_misbound_evidence(
    group: str, field: str, value: Any, reason: str
) -> None:
    document = load("fixtures/valid.json")
    document[group][field] = value
    with pytest.raises(ValueError, match=reason):
        validate_federation_semantics(document)


def test_committed_negative_fixture() -> None:
    with pytest.raises(ValueError, match="verification identity"):
        validate_federation_semantics(
            load("fixtures/invalid-mismatched-digest.json")
        )


@pytest.mark.parametrize("layer", ["silver", "gold", "platinum"])
def test_derived_layers_require_lineage_and_promotion(layer: str) -> None:
    document = load("fixtures/valid.json")
    document["source"].update(
        layer=layer, bronze_stratum=None, representation="projection"
    )
    document["lineage"]["inputs"] = [document["verification"]["receipt"]]
    with pytest.raises(ValueError, match="promotion receipt"):
        validate_federation_semantics(document)
    document["lineage"]["promotion_receipt"] = document["verification"][
        "receipt"
    ]
    validate_federation_semantics(document)


@pytest.mark.parametrize(
    ("representation", "stratum"), [("index", "B0"), ("metadata", "B1")]
)
def test_bronze_representation_mapping(
    representation: str, stratum: str
) -> None:
    document = load("fixtures/valid.json")
    document["source"]["representation"] = representation
    with pytest.raises(ValueError, match="stratum mismatch"):
        validate_federation_semantics(document)
    document["source"]["bronze_stratum"] = stratum
    validate_federation_semantics(document)


def test_raw_cannot_be_an_index_or_later_layer() -> None:
    document = load("fixtures/valid.json")
    document["source"]["bronze_stratum"] = "B1"
    with pytest.raises(ValueError, match="raw evidence"):
        validate_federation_semantics(document)


def test_synthetic_and_cleanup_claims_are_truthful() -> None:
    document = load("fixtures/valid.json")
    document["evidence_kind"] = "live"
    with pytest.raises(ValueError, match="synthetic evidence"):
        validate_federation_semantics(document)
    document["evidence_kind"] = "synthetic"
    document["cache"]["state"] = "transient"
    with pytest.raises(ValueError, match="unremoved cache"):
        validate_federation_semantics(document)
    document["cache"]["cleanup_receipt"] = None
    validate_federation_semantics(document)


def test_same_account_replica_is_not_independent() -> None:
    document = load("fixtures/valid.json")
    recovery = document["recovery"]
    recovery.update(role="independent_replica", independent=True)
    with pytest.raises(ValueError, match="independent replica"):
        validate_federation_semantics(document)
    recovery.update(role="compatibility_replica")
    with pytest.raises(ValueError, match="compatibility replica"):
        validate_federation_semantics(document)
    recovery.update(role="primary")
    with pytest.raises(ValueError, match="independent role"):
        validate_federation_semantics(document)
    recovery.update(role="compatibility_replica", independent=False)
    validate_federation_semantics(document)


def test_independent_recovery_requires_all_evidence() -> None:
    document = load("fixtures/valid.json")
    recovery = document["recovery"]
    recovery.update(
        role="independent_replica",
        independent=True,
        administrative_domain="independent-operator",
        region="replica-region",
        primary_region="primary-region",
        rpo_seconds=0,
        rto_seconds=60,
        restore_receipt=document["verification"]["receipt"],
        authorization_receipt=document["rights"]["authorization"],
    )
    validate_federation_semantics(document)
    for field in (
        "restore_receipt",
        "authorization_receipt",
        "rpo_seconds",
        "rto_seconds",
    ):
        candidate = copy.deepcopy(document)
        candidate["recovery"][field] = None
        with pytest.raises(ValueError, match="independent replica"):
            validate_federation_semantics(candidate)


def test_b0_cannot_claim_projection() -> None:
    document = load("fixtures/valid.json")
    document["source"].update(bronze_stratum="B0", representation="projection")
    document["lineage"]["inputs"] = [document["verification"]["receipt"]]
    with pytest.raises(ValueError, match="B0"):
        validate_federation_semantics(document)


@pytest.mark.parametrize("value", [" ", "\t\n", " trailing", "trailing "])
def test_required_text_cannot_be_blank_or_padded(value: str) -> None:
    document = load("fixtures/valid.json")
    document["rights"]["basis"] = value
    assert not Draft202012Validator(load("federation.schema.json")).is_valid(
        document
    )


@pytest.mark.parametrize("padding", [" ", "", "\t"])
def test_replica_identity_comparison_is_canonical(padding: str) -> None:
    document = load("fixtures/valid.json")
    recovery = document["recovery"]
    recovery.update(
        role="independent_replica",
        independent=True,
        administrative_domain="HUGGINGFACE:EXAMPLE" + padding,
        region="US-EAST-1" + padding,
        primary_region="us-east-1",
        rpo_seconds=0,
        rto_seconds=60,
        restore_receipt=document["verification"]["receipt"],
        authorization_receipt=document["rights"]["authorization"],
    )
    with pytest.raises(ValueError, match="independent replica"):
        validate_federation_semantics(document)
