"""Synthetic downstream compatibility bindings; no network or admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from global_medicines_atlas.federation_consumer import (
    SuccessorLink,
    bind_consumer_contract,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts/medallion/v4/fixtures/valid.json"


def contract() -> bytes:
    value = json.loads(FIXTURE.read_bytes())
    digest = "e" * 64
    value["location"].update(sha256=digest)
    value["verification"].update(sha256=digest)
    value["rights"]["subject_sha256"] = digest
    return json.dumps(value, sort_keys=True).encode()


def link() -> SuccessorLink:
    return SuccessorLink(
        legacy_repository="edithatogo/aus-health-data-scraper",
        successor_repository="edithatogo/global-medicines-atlas",
        successor_commit="b" * 40,
        notice_digest="f" * 64,
    )


def test_binding_preserves_producer_and_exact_contract_identity() -> None:
    raw = contract()
    result = bind_consumer_contract(
        raw,
        consumer_repository="edithatogo/reimbursement-atlas",
        consumer_commit="a" * 40,
        successor=link(),
    )
    assert result.contract_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.producer_repository == "example/producer"
    assert result.contract_repository == "edithatogo/global-medicines-atlas"
    assert result.contract_commit == "a" * 40
    assert (
        result.schema_sha256
        == "ac28485a70e0853266e4c140f9a07cd557eb27816b0b408b9bf2927a4cffacec"
    )
    assert result.successor == link()


def test_binding_preserves_source_era_and_temporal_identity() -> None:
    result = bind_consumer_contract(
        contract(),
        consumer_repository="edithatogo/reimbursement-atlas",
        consumer_commit="a" * 40,
    )

    assert result.layer == "bronze"
    assert result.bronze_stratum == "B2"
    assert result.representation == "raw"
    assert result.schema_era == "synthetic-v1"
    assert result.comparison_cohort == "synthetic"
    assert result.effective_date == "2026-08-01"
    assert result.retrieved_at == "2026-08-30T00:00:00Z"


@pytest.mark.parametrize(
    "section", ["authority", "source", "location", "verification"]
)
def test_malformed_contract_sections_fail_closed(section: str) -> None:
    value = json.loads(FIXTURE.read_bytes())
    value[section] = []

    with pytest.raises(ValueError, match="section must be an object"):
        bind_consumer_contract(
            json.dumps(value).encode(),
            consumer_repository="edithatogo/reimbursement-atlas",
            consumer_commit="a" * 40,
        )


def test_contract_authority_must_match_pinned_schema_and_commit() -> None:
    value = json.loads(FIXTURE.read_bytes())
    value["authority"]["schema_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="schema pin"):
        bind_consumer_contract(
            json.dumps(value).encode(),
            consumer_repository="edithatogo/reimbursement-atlas",
            consumer_commit="a" * 40,
        )

    value = json.loads(FIXTURE.read_bytes())
    value["authority"]["contract_commit"] = "main"
    with pytest.raises(ValueError, match="contract commit"):
        bind_consumer_contract(
            json.dumps(value).encode(),
            consumer_repository="edithatogo/reimbursement-atlas",
            consumer_commit="a" * 40,
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("producer", "producer repository"),
        ("revision", "identity mismatch"),
        ("digest", "identity mismatch"),
    ],
)
def test_malformed_or_drifting_identity_fails_closed(
    change: str, message: str
) -> None:
    value = json.loads(FIXTURE.read_bytes())
    if change == "producer":
        value["authority"]["producer_repository"] = "not-a-repository"
    elif change == "revision":
        value["location"]["revision"] = "main"
    else:
        value["location"]["sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match=message):
        bind_consumer_contract(
            json.dumps(value).encode(),
            consumer_repository="edithatogo/reimbursement-atlas",
            consumer_commit="a" * 40,
        )


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("document", "", [], "JSON object"),
        ("document", "evidence_kind", "unknown", "evidence kind"),
        ("location", "private", True, "public and non-gated"),
        ("location", "gated", True, "public and non-gated"),
        ("location", "path", "", "object path"),
        ("location", "bytes", -1, "byte count"),
        ("source", "source_id", "", "source identity"),
        ("source", "acquisition_id", None, "source identity"),
        ("source", "schema_era", " ", "source identity"),
        ("source", "layer", [], "source layer"),
        ("source", "bronze_stratum", [], "Bronze stratum"),
        ("source", "representation", {}, "representation"),
        ("source", "comparison_cohort", "other", "comparison cohort"),
        ("source", "effective_date", 42, "effective date"),
        ("source", "retrieved_at", "", "retrieval time"),
    ],
)
def test_invalid_identity_fields_fail_closed(
    section: str, field: str, value: object, message: str
) -> None:
    if section == "document":
        if not field:
            raw = json.dumps(value).encode()
        else:
            changed = json.loads(contract())
            changed[field] = value
            raw = json.dumps(changed).encode()
    else:
        changed = json.loads(contract())
        changed[section][field] = value
        if section == "location" and field in {"private", "gated"}:
            changed["location"][field] = value
        if section == "location" and field == "bytes":
            changed["verification"][field] = value
        if section == "location" and field == "path":
            changed["verification"][field] = value
        raw = json.dumps(changed).encode()

    with pytest.raises(ValueError, match=message):
        bind_consumer_contract(
            raw,
            consumer_repository="edithatogo/reimbursement-atlas",
            consumer_commit="a" * 40,
        )


def test_duplicate_json_members_are_rejected() -> None:
    raw = contract()
    marker = b'"source":'
    start = raw.index(marker)
    opening = raw.index(b"{", start) + 1
    raw = raw[:opening] + b'"source_id":"attacker",' + raw[opening:]
    with pytest.raises(ValueError, match="invalid consumer contract"):
        bind_consumer_contract(
            raw,
            consumer_repository="edithatogo/reimbursement-atlas",
            consumer_commit="a" * 40,
        )


def test_successor_cannot_be_authority_or_self_link() -> None:
    bad_authority = SuccessorLink(
        legacy_repository=link().legacy_repository,
        successor_repository="example/producer",
        successor_commit="b" * 40,
        notice_digest="f" * 64,
    )
    with pytest.raises(ValueError, match="replace producer"):
        bind_consumer_contract(
            contract(),
            consumer_repository="edithatogo/reimbursement-atlas",
            consumer_commit="a" * 40,
            successor=bad_authority,
        )

    bad_self_link = SuccessorLink(
        legacy_repository="edithatogo/reimbursement-atlas",
        successor_repository="edithatogo/reimbursement-atlas",
        successor_commit="b" * 40,
        notice_digest="f" * 64,
    )
    with pytest.raises(ValueError, match="must change repository"):
        bind_consumer_contract(
            contract(),
            consumer_repository="edithatogo/reimbursement-atlas",
            consumer_commit="a" * 40,
            successor=bad_self_link,
        )

    bad_digest = SuccessorLink(
        legacy_repository=link().legacy_repository,
        successor_repository=link().successor_repository,
        successor_commit="b" * 40,
        notice_digest="invalid",
    )
    with pytest.raises(ValueError, match="successor notice digest"):
        bind_consumer_contract(
            contract(),
            consumer_repository="edithatogo/reimbursement-atlas",
            consumer_commit="a" * 40,
            successor=bad_digest,
        )
