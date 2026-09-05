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
    assert result.successor == link()


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
