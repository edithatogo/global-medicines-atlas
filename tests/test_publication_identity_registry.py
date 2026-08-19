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
    PublicationObjectRole,
    PublicationSystem,
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
    assert {item.system for item in registry.identities} == {
        PublicationSystem.GITHUB,
        PublicationSystem.HUGGING_FACE,
        PublicationSystem.ZENODO,
    }
    assert PublicationSystem.OSF not in {
        item.system for item in registry.identities
    }
    assert len({item.object_id for item in registry.identities}) == 3
    assert len({item.object_role for item in registry.identities}) == 3


def test_current_registry_is_publishable_without_deprecated_osf() -> None:
    registry = PublicationIdentityRegistry.model_validate(_payload())
    assert registry.blocking_reasons() == ()
    registry.assert_publishable()
    registry.assert_object_publishable("software-source-release")
    registry.assert_object_publishable("derived-dataset")
    registry.assert_object_publishable("archival-record")
    with pytest.raises(ValueError, match="unknown publication object"):
        registry.assert_object_publishable("protocol-preregistration")
    with pytest.raises(ValueError, match="unknown publication object"):
        registry.assert_object_publishable("missing")


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


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {"related_object_ids": ["derived-dataset", "derived-dataset"]},
            "must be unique",
        ),
        (
            {
                "identifier_state": "unresolved",
                "identifier": "https://example.invalid/unresolved",
            },
            "cannot claim",
        ),
        (
            {"identifier_state": "configured", "identifier": None},
            "requires an identifier",
        ),
        (
            {
                "licence_state": "unresolved",
                "licence_expression": "TEST-ONLY",
            },
            "cannot claim",
        ),
    ],
)
def test_identity_state_contradictions_fail_closed(
    updates: dict[str, object],
    message: str,
) -> None:
    payload = copy.deepcopy(_payload())
    payload["identities"][0].update(updates)
    with pytest.raises(ValidationError, match=message):
        PublicationIdentityRegistry.model_validate(payload)


def test_live_registry_rejects_deprecated_osf_identity() -> None:
    payload = copy.deepcopy(_payload())
    payload["identities"][2].update({
        "object_id": "protocol-preregistration",
        "system": "osf",
        "object_role": "protocol_preregistration",
        "identifier": None,
        "identifier_state": "unresolved",
        "identifier_evidence": None,
        "licence_state": "unresolved",
        "licence_expression": None,
        "licence_decision_evidence": None,
        "related_object_ids": ["software-source-release"],
    })
    payload["identities"][0]["related_object_ids"] = ["derived-dataset"]
    payload["identities"][1]["related_object_ids"] = ["software-source-release"]
    with pytest.raises(ValidationError, match="deprecated"):
        PublicationIdentityRegistry.model_validate(payload)


def test_registry_runtime_rejects_duplicate_systems_and_roles() -> None:
    registry = PublicationIdentityRegistry.model_validate(_payload())
    duplicate_system = registry.identities[1].model_copy(
        update={"system": PublicationSystem.GITHUB}
    )
    with pytest.raises(ValueError, match="system exactly once"):
        registry.model_copy(
            update={
                "identities": (
                    registry.identities[0],
                    duplicate_system,
                    *registry.identities[2:],
                )
            }
        ).identities_are_complete_non_overlapping_and_closed()

    duplicate_role = registry.identities[1].model_copy(
        update={"object_role": PublicationObjectRole.SOFTWARE_SOURCE_RELEASE}
    )
    with pytest.raises(ValueError, match="must not overlap"):
        registry.model_copy(
            update={
                "identities": (
                    registry.identities[0],
                    duplicate_role,
                    *registry.identities[2:],
                )
            }
        ).identities_are_complete_non_overlapping_and_closed()


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
