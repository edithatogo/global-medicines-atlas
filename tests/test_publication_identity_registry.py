from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from global_medicines_atlas.publication_contracts import (
    PublicationIdentityRegistry,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "quality/qualifications/publication-identities.json"
SCHEMA = ROOT / "schemas/publication-identity-registry-v1.json"


def _payload() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_registry_schema_and_runtime_contract_validate() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_payload())
    registry = PublicationIdentityRegistry.model_validate(_payload())
    assert len({item.object_id for item in registry.identities}) == 4
    assert len({item.object_role for item in registry.identities}) == 4


def test_current_registry_is_explicitly_blocked_not_publishable() -> None:
    registry = PublicationIdentityRegistry.model_validate(_payload())
    assert registry.blocking_reasons()
    with pytest.raises(ValueError, match="registry is blocked"):
        registry.assert_publishable()


@pytest.mark.parametrize("field", ["object_id", "object_role", "identifier"])
def test_overlapping_identity_fields_fail_closed(field: str) -> None:
    payload = copy.deepcopy(_payload())
    payload["identities"][1][field] = payload["identities"][0][field]
    if field == "identifier":
        payload["identities"][1]["identifier_state"] = "configured"
    with pytest.raises(ValidationError):
        PublicationIdentityRegistry.model_validate(payload)


def test_wrong_system_role_and_dangling_relationship_fail_closed() -> None:
    wrong_role = copy.deepcopy(_payload())
    wrong_role["identities"][0]["object_role"] = "archival_doi_record"
    with pytest.raises(ValidationError):
        PublicationIdentityRegistry.model_validate(wrong_role)
    dangling = copy.deepcopy(_payload())
    dangling["identities"][0]["related_object_ids"] = ["missing-object"]
    with pytest.raises(ValidationError):
        PublicationIdentityRegistry.model_validate(dangling)


@given(st.sampled_from(["identifier", "licence"]))
def test_approval_words_without_evidence_never_open_gate(kind: str) -> None:
    payload = copy.deepcopy(_payload())
    row = payload["identities"][0]
    if kind == "identifier":
        row["identifier_state"] = "verified"
        row["identifier_evidence"] = None
    else:
        row["licence_state"] = "approved"
        row["licence_expression"] = "TEST-ONLY"
        row["licence_decision_evidence"] = None
    with pytest.raises(ValidationError):
        PublicationIdentityRegistry.model_validate(payload)
