"""Fail-closed tests for the approved metadata-only Hub transaction."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest
from scripts import publish_hf_public_metadata as publisher
from scripts import qualify_hf_public_registry_gap as audit


def _entry(repo_id: str, access: str) -> dict[str, Any]:
    return {
        "repo_id": repo_id,
        "family": "fixture",
        "role": "fixture",
        "canonical_repo_id": repo_id,
        "origin_repository": None,
        "upstream_source": "Fixture only.",
        "status": "fixture",
        "access": access,
        "rights_status": "source_specific_review_required",
        "viewer_status": "not_verified",
    }


def _schema() -> dict[str, Any]:
    item = {
        "type": "object",
        "required": [
            "repo_id",
            "family",
            "role",
            "canonical_repo_id",
            "status",
            "access",
            "rights_status",
            "viewer_status",
        ],
        "properties": {
            "repo_id": {"type": "string"},
            "family": {"type": "string"},
            "role": {"type": "string"},
            "canonical_repo_id": {"type": "string"},
            "origin_repository": {"type": ["string", "null"]},
            "upstream_source": {"type": "string"},
            "status": {"type": "string"},
            "access": {"enum": ["public", "private", "gated"]},
            "rights_status": {"type": "string"},
            "viewer_status": {"type": "string"},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["datasets"],
        "properties": {"datasets": {"type": "array", "items": item}},
    }


def _case() -> tuple[bytes, bytes, dict[str, Any], dict[str, Any]]:
    gated_id = "owner/public-but-catalog-gated"
    private_id = "owner/public-but-catalog-private"
    unmatched_id = "edithatogo/gfjd-source-archive"
    private_existing_id = "owner/preexisting-private-row"
    baseline = {
        "datasets": [
            _entry(gated_id, "gated"),
            _entry(private_id, "private"),
            _entry(unmatched_id, "public"),
            _entry(private_existing_id, "private"),
        ]
    }
    baseline_bytes = (json.dumps(baseline, indent=2) + "\n").encode()
    schema_bytes = json.dumps(_schema()).encode()
    datasets = [
        {"repo_id": gated_id, "revision": "a" * 40, "gated": False},
        {"repo_id": private_id, "revision": "b" * 40, "gated": False},
        *[
            {
                "repo_id": f"owner/missing-{index:02d}",
                "revision": f"{index:040x}",
                "gated": False,
            }
            for index in range(26)
        ],
    ]
    collections: list[dict[str, Any]] = [
        {
            "slug": "owner/existing-public",
            "title": "Existing",
            "description": "Preserve.",
            "gated": False,
            "members": [],
        }
    ]
    record = audit.build_gap_record(
        datasets,
        collections,
        baseline_bytes,
        schema_bytes,
        observed_at=datetime(2026, 10, 1, tzinfo=UTC),
        registry_revision="c" * 40,
    )
    record["registry"]["revision"] = "c" * 40
    record["observation"]["public_dataset_metadata_sha256"] = "d" * 64
    record["observation"]["public_collection_metadata_sha256"] = "e" * 64
    approval = {
        "registry": {
            "baseline_revision": "c" * 40,
            "baseline_catalog_sha256": hashlib.sha256(
                baseline_bytes
            ).hexdigest(),
            "expected_public_dataset_metadata_sha256": "d" * 64,
            "expected_public_collection_metadata_sha256": "e" * 64,
            "access_mismatch_reconciliation": [
                {"repo_id": gated_id, "from": "gated", "to": "public"},
                {"repo_id": private_id, "from": "private", "to": "public"},
            ],
            "unmatched_existing_entries_to_preserve": [unmatched_id],
        }
    }
    return baseline_bytes, schema_bytes, record, approval


def test_target_catalog_adds_only_unknown_public_placeholders_and_access_fixes() -> (
    None
):
    baseline, schema, gap, approval = _case()
    target = json.loads(
        publisher.prepare_target_catalog(baseline, schema, gap, approval)
    )
    rows = {row["repo_id"]: row for row in target["datasets"]}

    assert len(rows) == 30
    assert rows["owner/public-but-catalog-gated"]["access"] == "public"
    assert rows["owner/public-but-catalog-private"]["access"] == "public"
    assert rows["edithatogo/gfjd-source-archive"] == _entry(
        "edithatogo/gfjd-source-archive", "public"
    )
    assert rows["owner/preexisting-private-row"]["access"] == "private"
    for index in range(26):
        entry = rows[f"owner/missing-{index:02d}"]
        assert entry["family"] == "unclassified"
        assert entry["origin_repository"] is None
        assert entry["rights_status"] == "source_specific_review_required"
        assert entry["viewer_status"] == "not_verified"
        assert entry["status"] == "not_assessed"


def test_target_catalog_rejects_stale_public_observation() -> None:
    baseline, schema, gap, approval = _case()
    gap["observation"]["public_dataset_metadata_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="public estate"):
        publisher.prepare_target_catalog(baseline, schema, gap, approval)


def test_target_catalog_rejects_access_change_outside_pinned_scope() -> None:
    baseline, schema, gap, approval = _case()
    gap["registry"]["public_access_mismatches"][0]["registry_access"] = "public"
    with pytest.raises(ValueError, match="access mismatches"):
        publisher.prepare_target_catalog(baseline, schema, gap, approval)


def test_target_catalog_rejects_rights_or_role_claims_in_placeholders() -> None:
    baseline, schema, gap, approval = _case()
    gap["registry"]["conservative_public_registry_draft_entries"][0][
        "catalog_entry"
    ]["rights_status"] = "open"
    with pytest.raises(ValueError, match="unsupported source"):
        publisher.prepare_target_catalog(baseline, schema, gap, approval)


def test_local_publication_fails_closed_before_accessing_hub() -> None:
    with pytest.raises(ValueError, match="only from GitHub Actions"):
        publisher.validate_actions_context({
            "GITHUB_ACTIONS": "false",
            "GITHUB_REF": "refs/heads/main",
            "GMA_MAINTAINER_PUBLICATION_APPROVED": "yes-i-approve-publication",
            "HF_TOKEN": "test-only-placeholder",
        })


def test_actions_environment_flags_without_oidc_proof_fail_closed() -> None:
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REF": "refs/heads/main",
        "GMA_MAINTAINER_PUBLICATION_APPROVED": "yes-i-approve-publication",
        "GITHUB_RUN_ID": "12345",
        "GITHUB_RUN_ATTEMPT": "1",
        "HF_TOKEN": "test-only-placeholder",
    }
    with pytest.raises(ValueError, match="OIDC identity token"):
        publisher.validate_actions_context(env)


def _actions_claims(
    env: dict[str, str],
    **claim_overrides: object,
) -> dict[str, object]:
    now = int(datetime.now(UTC).timestamp())
    claims: dict[str, object] = {
        "iss": "https://token.actions.githubusercontent.com",
        "aud": publisher.OIDC_AUDIENCE,
        "sub": "repo:edithatogo/global-medicines-atlas:environment:production",
        "repository": "edithatogo/global-medicines-atlas",
        "repository_owner": "edithatogo",
        "ref": "refs/heads/main",
        "workflow_ref": publisher.EXPECTED_WORKFLOW_REF,
        "environment": "production",
        "event_name": "workflow_dispatch",
        "runner_environment": "github-hosted",
        "run_id": int(env["GITHUB_RUN_ID"]),
        "run_attempt": int(env["GITHUB_RUN_ATTEMPT"]),
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        **claim_overrides,
    }
    return claims


def _oidc_test_environment() -> dict[str, str]:
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ID": "12345",
        "GITHUB_RUN_ATTEMPT": "1",
        "GMA_MAINTAINER_PUBLICATION_APPROVED": "yes-i-approve-publication",
        "HF_TOKEN": "test-only-placeholder",
    }


def test_oidc_identity_requires_github_signature_and_exact_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _oidc_test_environment()
    claims_by_token = {
        "valid": _actions_claims(env),
        "wrong-workflow": _actions_claims(
            env, workflow_ref="attacker.yml@refs/heads/main"
        ),
    }

    class FakePyJWTError(Exception):
        pass

    class FakeJwkClient:
        def __init__(self, uri: str, *, timeout: int) -> None:
            assert uri == publisher.OIDC_JWKS_URL
            assert timeout == 15

        def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
            assert token
            return SimpleNamespace(key="trusted-github-key")

    def fake_decode(
        token: str,
        key: str,
        *,
        algorithms: list[str],
        audience: str,
        issuer: str,
        options: dict[str, object],
        leeway: int,
    ) -> dict[str, object]:
        assert key == "trusted-github-key"
        assert algorithms == ["RS256"]
        assert audience == publisher.OIDC_AUDIENCE
        assert issuer == "https://token.actions.githubusercontent.com"
        assert options == {"require": ["iat", "exp", "nbf", "iss", "aud"]}
        assert leeway == 60
        if token not in claims_by_token:
            raise FakePyJWTError
        return claims_by_token[token]

    jwt_stub = cast("Any", ModuleType("jwt"))
    jwt_stub.PyJWKClient = FakeJwkClient
    jwt_stub.decode = fake_decode
    jwt_stub.PyJWTError = FakePyJWTError
    monkeypatch.setitem(sys.modules, "jwt", jwt_stub)

    env["GMA_ACTIONS_OIDC_TOKEN"] = "valid"  # ruff: ignore[hardcoded-password-string] -- mocked JWT fixture, not a credential.
    publisher._verify_actions_oidc(env)

    env["GMA_ACTIONS_OIDC_TOKEN"] = "invalid"  # ruff: ignore[hardcoded-password-string] -- mocked JWT fixture, not a credential.
    with pytest.raises(ValueError, match="signature or claims"):
        publisher._verify_actions_oidc(env)

    env["GMA_ACTIONS_OIDC_TOKEN"] = "wrong-workflow"  # ruff: ignore[hardcoded-password-string] -- mocked JWT fixture, not a credential.
    with pytest.raises(ValueError, match="claims do not match"):
        publisher._verify_actions_oidc(env)


def test_approval_members_reconcile_scope_assessment_field_names() -> None:
    approval = json.loads(
        (publisher.ROOT / publisher.APPROVAL_PATH).read_text()
    )
    scope = approval["candidate_scope"]
    assessment = json.loads(
        (publisher.ROOT / scope["scope_assessment_path"]).read_text()
    )

    publisher.validate_scope_assessment(assessment, scope)

    assessment["policy_aus_change_proposal"]["proposed_dataset_members"][0][
        "collection_note"
    ] = "unexpected note"
    with pytest.raises(ValueError, match="scope assessment"):
        publisher.validate_scope_assessment(assessment, scope)


def test_non_main_or_unapproved_actions_run_fails_closed() -> None:
    base = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REF": "refs/heads/feature",
        "GMA_MAINTAINER_PUBLICATION_APPROVED": "yes-i-approve-publication",
        "HF_TOKEN": "test-only-placeholder",
    }
    with pytest.raises(ValueError, match="protected main"):
        publisher.validate_actions_context(base)
    base["GITHUB_REF"] = "refs/heads/main"
    base["GMA_MAINTAINER_PUBLICATION_APPROVED"] = "no"
    with pytest.raises(ValueError, match="approval"):
        publisher.validate_actions_context(base)
