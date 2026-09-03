"""Independent trust, not self-consistency, controls v4 admission."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from global_medicines_atlas.federation_admission import (
    TrustedAdmissionProfile,
    admit_closed_contract,
)
from global_medicines_atlas.federation_receipt_closure import (
    ReceiptPayload,
    ReceiptRole,
    verify_receipt_closure,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "contracts/medallion/v4/federation.schema.json").read_bytes()
BODY = b"independently supplied synthetic receipt"
URL = "https://example.org/receipts/trusted.json"


def evidence():
    document: dict[str, Any] = json.loads(
        (ROOT / "contracts/medallion/v4/fixtures/valid.json").read_bytes()
    )
    ref = {"url": URL, "sha256": hashlib.sha256(BODY).hexdigest()}

    def replace(value: Any) -> None:
        if isinstance(value, dict):
            node = cast("dict[str, object]", value)
            if set(node) == {"url", "sha256"}:
                node.update(ref)
            else:
                for child in node.values():
                    replace(child)
        elif isinstance(value, list):
            for child in cast("list[object]", value):
                replace(child)

    replace(document)
    raw = json.dumps(document).encode()
    closed = verify_receipt_closure(
        raw, (ReceiptPayload(url=URL, payload=BODY),), schema=SCHEMA
    )
    roles = {role.role: role for role in closed.roles}
    trusted = TrustedAdmissionProfile(
        producer_repository="example/producer",
        dataset="example/synthetic-mbs",
        revision="a" * 40,
        path="raw/synthetic.xml",
        sha256="d" * 64,
        source_id="synthetic-mbs",
        acquisition_id="synthetic-acquisition",
        layer="bronze",
        bronze_stratum="B2",
        evidence_kind="synthetic",
        authorization=roles["/rights/authorization"],
        lineage=tuple(
            role for role in closed.roles if role.role.startswith("/lineage/")
        ),
    )
    return raw, closed, trusted


def test_exact_independent_profile_admits_without_io():
    raw, closed, trusted = evidence()
    result = admit_closed_contract(raw, closed, trusted=trusted)
    assert result.scope == "offline_trusted_profile"
    assert result.contract_sha256 == hashlib.sha256(raw).hexdigest()
    assert "authorization" not in result.model_dump()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("producer_repository", "attacker/repo"),
        ("dataset", "other/data"),
        ("revision", "b" * 40),
        ("path", "raw/other.xml"),
        ("sha256", "e" * 64),
        ("source_id", "other"),
        ("acquisition_id", "other"),
        ("layer", "silver"),
        ("bronze_stratum", "B1"),
        ("evidence_kind", "live"),
    ],
)
def test_subject_layer_and_authority_must_match_independent_profile(
    field: str, value: object
):
    raw, closed, trusted = evidence()
    with pytest.raises(ValueError, match="independently trusted"):
        admit_closed_contract(
            raw, closed, trusted=trusted.model_copy(update={field: value})
        )


def test_authorization_lineage_and_closure_cannot_be_substituted():
    raw, closed, trusted = evidence()
    other = ReceiptRole(
        role="/rights/authorization",
        url="https://example.org/other",
        sha256="f" * 64,
    )
    with pytest.raises(ValueError, match="authorization"):
        admit_closed_contract(
            raw,
            closed,
            trusted=trusted.model_copy(update={"authorization": other}),
        )
    with pytest.raises(ValueError, match="lineage"):
        admit_closed_contract(
            raw,
            closed,
            trusted=trusted.model_copy(
                update={"lineage": trusted.lineage[:-1]}
            ),
        )
    with pytest.raises(ValueError, match="different contract"):
        admit_closed_contract(raw + b" ", closed, trusted=trusted)


def test_existing_archive_or_malformed_bytes_are_not_retroactively_admitted():
    _, closed, trusted = evidence()
    with pytest.raises(ValueError, match="different contract"):
        admit_closed_contract(b"{}", closed, trusted=trusted)
    malformed = b"[]"
    matching = closed.model_copy(
        update={"contract_sha256": hashlib.sha256(malformed).hexdigest()}
    )
    with pytest.raises(ValueError, match="invalid closed"):
        admit_closed_contract(malformed, matching, trusted=trusted)
