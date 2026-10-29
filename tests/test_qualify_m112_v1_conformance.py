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


def test_durable_candidate_receipt_does_not_claim_v4_role_acceptance() -> None:
    report = qualification._read_json(  # pyright: ignore[reportPrivateUsage]
        qualification.ROOT, qualification.ROLE_REPORT
    )
    receipt = report["v1_conformance_candidate_receipt"]

    assert receipt["git_commit"] == "290cc219217821404cf25bcfc58761821389d614"
    assert receipt["url"].endswith(
        "/290cc219217821404cf25bcfc58761821389d614/"
        "quality/qualifications/australian-m112-v1-conformance-20261019.json"
    )
    assert (
        receipt["sha256"]
        == "826f7380ecb925d9c51dad826307f2d94348ed9ac44320ef70f8faff25709842"
    )
    assert receipt["anonymous_readback_verified"] is True
    assert (
        receipt["contract_role_state"] == "candidate_receipt_available_unbound"
    )
    assert report["cohort"]["v4_admissions"] == 0
    assert report["cohort"]["consumer_canaries"] == 0
    assert all(
        item["contract_role_states"]["lineage.v1_conformance"]
        == "candidate_receipt_available_unbound"
        for item in report["objects"]
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


def test_pbs_v1_conformance_is_exact_six_and_remains_candidate_only() -> None:
    document = qualification.qualify(cohort="pbs")
    assert document == qualification.qualify(cohort="pbs")
    assert len(document["artifacts"]) == 6
    assert len(document["promotion_decisions"]) == 6
    for artifact in document["artifacts"]:
        assert artifact["artifact_id"].startswith(
            "m112:edithatogo/australian-pbs-utilisation-archive@"
            "9f1d53cd50eea251b326da42a96f3ac72ebce97a:raw/pbs/"
        )
        assert artifact["promotion_status"] == "candidate"
        assert artifact["rights_decision"]["reason_codes"] == [
            "maintainer_attested_exact_scope_permission_not_independently_reviewed"
        ]
    assert all(
        decision["status"] == "blocked"
        for decision in document["promotion_decisions"]
    )


def test_pbs_rights_basis_does_not_become_a_general_mbs_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = qualification._read_json  # pyright: ignore[reportPrivateUsage]

    def read_json(root: Path, relative: str) -> dict[str, Any]:
        document = original(root, relative)
        if relative == qualification.ROLE_REPORT:
            document["objects"][0]["rights_state"] = (
                "maintainer_attested_exact_public_release_permission_for_pbs_"
                "utilisation_raw_object"
            )
        return document

    monkeypatch.setattr(qualification, "_read_json", read_json)
    with pytest.raises(ValueError, match="exact-scope rights"):
        qualification.qualify()


def test_pbs_conformance_rejects_an_unbound_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = qualification._read_json  # pyright: ignore[reportPrivateUsage]

    def read_json(root: Path, relative: str) -> dict[str, Any]:
        document = original(root, relative)
        if relative.endswith(
            "australian-m112-pbs-utilisation-rights-lineage-reconciliation-20261028.json"
        ):
            document["objects"][0]["path"] = "raw/pbs/unapproved.csv"
        return document

    monkeypatch.setattr(qualification, "_read_json", read_json)
    with pytest.raises(ValueError, match="exact PBS replay target"):
        qualification.qualify(cohort="pbs")


def test_v1_conformance_rejects_unknown_cohort() -> None:
    with pytest.raises(
        ValueError, match="unsupported M-112 conformance cohort"
    ):
        qualification.qualify(cohort="unknown")


def test_pbs_conformance_rejects_partial_cohort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = qualification._read_json  # pyright: ignore[reportPrivateUsage]

    def read_json(root: Path, relative: str) -> dict[str, Any]:
        document = original(root, relative)
        if relative.endswith(
            "australian-m112-pbs-utilisation-rights-lineage-reconciliation-20261028.json"
        ):
            document["objects"].pop()
        return document

    monkeypatch.setattr(qualification, "_read_json", read_json)
    with pytest.raises(ValueError, match="exact six-object cohort"):
        qualification.qualify(cohort="pbs")
