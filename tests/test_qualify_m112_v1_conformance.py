"""M-112 v1 conformance remains candidate-only and evidence-bound."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_m112_v1_conformance as qualification
from jsonschema import Draft202012Validator


def test_v1_conformance_binds_all_exact_eligible_raw_b2_objects() -> None:
    document = qualification.qualify()
    schema = qualification._read_json(  # pyright: ignore[reportPrivateUsage]
        qualification.ROOT, qualification.V1_SCHEMA
    )

    Draft202012Validator(schema).validate(document)  # pyright: ignore[reportUnknownMemberType]
    assert len(document["artifacts"]) == 16
    assert len(document["promotion_decisions"]) == 16
    assert {item["layer"] for item in document["artifacts"]} == {"bronze_b2"}
    assert {item["promotion_status"] for item in document["artifacts"]} == {
        "candidate"
    }
    assert {item["status"] for item in document["promotion_decisions"]} == {
        "blocked"
    }
    assert all(
        item["reason_codes"] == ["v4_contract_roles_incomplete"]
        for item in document["promotion_decisions"]
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("rights_state", "unknown", "exact-scope rights"),
        ("anonymous_digest_readback", False, "anonymous digest"),
        ("lineage_role", "missing", "complete B1/B2 lineage"),
    ],
)
def test_ineligible_m112_object_fails_closed(
    monkeypatch: pytest.MonkeyPatch, field: str, value: Any, message: str
) -> None:
    original = qualification._read_json  # pyright: ignore[reportPrivateUsage]

    def read_json(root: Path, relative: str) -> dict[str, Any]:
        result = original(root, relative)
        if relative == qualification.ROLE_REPORT:
            if field == "lineage_role":
                result["objects"][0]["contract_role_states"][
                    "lineage.inputs"
                ] = value
            else:
                result["objects"][0][field] = value
        return result

    monkeypatch.setattr(qualification, "_read_json", read_json)
    with pytest.raises(ValueError, match=message):
        qualification.qualify()


def test_stale_bound_evidence_digest_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = qualification._read_json  # pyright: ignore[reportPrivateUsage]

    def read_json(root: Path, relative: str) -> dict[str, Any]:
        result = original(root, relative)
        if relative == qualification.ROLE_REPORT:
            result["objects"][0]["rights_decision"]["sha256"] = "0" * 64
        return result

    monkeypatch.setattr(qualification, "_read_json", read_json)
    with pytest.raises(ValueError, match="evidence reference digest mismatch"):
        qualification.qualify()
