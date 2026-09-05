"""Synthetic fail-closed tests for frontier schema/REST contracts."""

import copy
import hashlib
import json

import pytest
from pydantic import ValidationError

from global_medicines_atlas.frontier_schema_evolution import (
    RestSchemaQualification,
    SchemaEvolutionDecision,
)


def descriptor(
    major: int, minor: int, fields: list[dict[str, object]]
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_id": "pbs.gold",
        "major": major,
        "minor": minor,
        "fields": fields,
    }
    value["canonical_sha256"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return value


def envelope() -> dict[str, object]:
    before = descriptor(
        1, 0, [{"name": "item_code", "field_type": "string", "nullable": False}]
    )
    after = descriptor(
        1,
        1,
        [
            {"name": "item_code", "field_type": "string", "nullable": False},
            {
                "name": "benefit_amount",
                "field_type": "number",
                "nullable": True,
            },
        ],
    )
    transition = {
        "schema_id": "pbs.gold",
        "before": before,
        "after": after,
        "compatibility": "compatible",
        "authority_promoted": False,
    }
    return {
        "schema_id": "global-medicines-atlas.frontier-schema-rest",
        "schema_version": 1,
        "transition": transition,
        "observations": [
            {
                "method": "GET",
                "path": "/v1/pbs.gold/items",
                "schema_sha256": after["canonical_sha256"],
                "status_code": 200,
                "outcome": "passed",
                "response_sha256": "a" * 64,
                "payload_retained": False,
                "request_count": 1,
            },
            {
                "method": "HEAD",
                "path": "/v1/pbs.gold/schema",
                "schema_sha256": after["canonical_sha256"],
                "status_code": 204,
                "outcome": "passed",
                "payload_retained": False,
                "request_count": 1,
            },
        ],
        "production_dependency_adopted": False,
        "technology_promotion_claimed": False,
    }


def test_additive_nullable_transition_and_pinned_rest_lifecycle_pass() -> None:
    report = RestSchemaQualification.model_validate(envelope())
    assert report.transition.compatibility == "compatible"
    assert all(item.payload_retained is False for item in report.observations)


@pytest.mark.parametrize(
    "mutation",
    [
        {
            "after_field": {
                "name": "benefit_amount",
                "field_type": "number",
                "nullable": False,
            }
        },
        {"path": "/v2/pbs.gold/items"},
        {"payload_retained": True},
    ],
)
def test_schema_rest_contract_rejects_unsafe_or_drifting_mutations(
    mutation: dict[str, object],
) -> None:
    raw = envelope()
    if "after_field" in mutation:
        raw["transition"] = copy.deepcopy(raw["transition"])
        after = raw["transition"]["after"]
        after["fields"].append(mutation["after_field"])
        after["canonical_sha256"] = hashlib.sha256(
            json.dumps(
                {k: v for k, v in after.items() if k != "canonical_sha256"},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        for item in raw["observations"]:
            item["schema_sha256"] = after["canonical_sha256"]
    elif "path" in mutation:
        raw["observations"][0]["path"] = mutation["path"]
    else:
        raw["observations"][0]["payload_retained"] = mutation[
            "payload_retained"
        ]
    with pytest.raises(ValidationError):
        RestSchemaQualification.model_validate(raw)


def test_breaking_transition_requires_reviewed_major_migration() -> None:
    before = descriptor(
        1, 0, [{"name": "item_code", "field_type": "string", "nullable": False}]
    )
    after = descriptor(
        2,
        0,
        [{"name": "item_code", "field_type": "integer", "nullable": False}],
    )
    decision = SchemaEvolutionDecision.model_validate({
        "schema_id": "pbs.gold",
        "before": before,
        "after": after,
        "compatibility": "breaking",
        "migration_id": "pbs-gold-v2-migration",
        "migration_reviewed": True,
        "authority_promoted": False,
    })
    assert decision.compatibility == "breaking"
