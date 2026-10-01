"""Fail-closed tests for the approved metadata-only Hub transaction."""

# pyright: reportPrivateUsage=false

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
    ] = f"unexpected note {publisher.POLICY_MEMBER_CAVEAT}"
    with pytest.raises(ValueError, match="scope assessment"):
        publisher.validate_scope_assessment(assessment, scope)


def test_policy_aus_approved_description_and_member_caveats_fit_hub_limits() -> (
    None
):
    approval = json.loads(
        (publisher.ROOT / publisher.APPROVAL_PATH).read_text()
    )
    scope = approval["candidate_scope"]
    caveat = publisher.POLICY_MEMBER_CAVEAT
    approval_bytes = (publisher.ROOT / publisher.APPROVAL_PATH).read_bytes()
    approval_digest = hashlib.sha256(approval_bytes).hexdigest()
    workflow = (
        publisher.ROOT / ".github/workflows/hf-public-metadata-publication.yml"
    ).read_text()

    assert scope["policy_aus_collection_note"] == publisher.POLICY_DESCRIPTION
    assert (
        len(scope["policy_aus_collection_note"])
        <= publisher.HUB_COLLECTION_DESCRIPTION_LIMIT
    )
    assert len(scope["members"]) == publisher.EXPECTED_AUSTRALIAN_MEMBER_COUNT
    assert all(
        caveat in member["note"]
        and len(member["note"]) <= publisher.HUB_COLLECTION_MEMBER_NOTE_LIMIT
        for member in scope["members"]
    )
    assert (
        f"--expected-approval-sha256\n          {approval_digest}" in workflow
    )


def test_scope_assessment_requires_explicit_maintainer_approval_record() -> (
    None
):
    approval = json.loads(
        (publisher.ROOT / publisher.APPROVAL_PATH).read_text()
    )
    scope = approval["candidate_scope"]
    assessment = json.loads(
        (publisher.ROOT / scope["scope_assessment_path"]).read_text()
    )
    assessment["policy_aus_change_proposal"]["approval_state"] = (
        "not_requested_or_granted"
    )

    with pytest.raises(ValueError, match="maintainer approval record"):
        publisher.validate_scope_assessment(assessment, scope)


def _collection_item(repo_id: str, note: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        item_id=repo_id,
        item_object_id=f"object-{repo_id}",
        item_type="dataset",
        note=note,
    )


def _transition_collections(
    approval: dict[str, Any], policy_note: str | None
) -> tuple[SimpleNamespace, SimpleNamespace]:
    scope = approval["candidate_scope"]
    first = scope["members"][0]["dataset"]
    policy = SimpleNamespace(
        slug=scope["policy_aus_slug"],
        title="Policy AUS",
        private=True,
        description=publisher.POLICY_OLD_DESCRIPTION,
        items=[_collection_item(first, policy_note)],
    )
    heor_slug = scope["heor_slug"]
    heor = SimpleNamespace(
        slug=heor_slug,
        private=False,
        description=(
            "Registry-driven view of health-economics, reimbursement, "
            "outcomes-research, and related evidence datasets."
        ),
        items=[
            _collection_item("edithatogo/australian-mbs-source-archive", None),
            _collection_item("edithatogo/australian-pbs-source-archive", None),
            _collection_item(
                "edithatogo/nz-health-appropriations", publisher.HEOR_NZ_NOTE
            ),
            _collection_item(
                "edithatogo/reimbursement-atlas",
                publisher.HEOR_EXISTING_NOTES["edithatogo/reimbursement-atlas"],
            ),
        ],
    )
    return policy, heor


def test_collection_transition_accepts_only_approved_prior_policy_note() -> (
    None
):
    approval = json.loads(
        (publisher.ROOT / publisher.APPROVAL_PATH).read_text()
    )
    previous_note = approval["candidate_scope"]["members"][0]["previous_note"]
    policy, heor = _transition_collections(approval, previous_note)

    publisher.validate_collection_transitions(policy, heor, approval)


def test_collection_transition_rejects_unrecognized_policy_note() -> None:
    approval = json.loads(
        (publisher.ROOT / publisher.APPROVAL_PATH).read_text()
    )
    policy, heor = _transition_collections(
        approval, "unrecognized note from an outside change"
    )

    with pytest.raises(ValueError, match="approved transition"):
        publisher.validate_collection_transitions(policy, heor, approval)


def test_collection_transition_accepts_prior_approved_heor_notes() -> None:
    approval = json.loads(
        (publisher.ROOT / publisher.APPROVAL_PATH).read_text()
    )
    scope = approval["candidate_scope"]
    prior_notes = {
        row["dataset"]: row["previous_note"] for row in scope["members"]
    }
    policy, heor = _transition_collections(
        approval, prior_notes[scope["members"][0]["dataset"]]
    )
    for item in heor.items:
        if item.item_id in prior_notes:
            item.note = prior_notes[item.item_id]
    heor.items.extend(
        _collection_item(dataset, prior_notes[dataset])
        for dataset in (
            "edithatogo/australian-mbs-utilisation-archive",
            "edithatogo/australian-pbs-utilisation-archive",
        )
    )

    publisher.validate_collection_transitions(policy, heor, approval)


def test_collection_transition_rejects_unrecognized_heor_note() -> None:
    approval = json.loads(
        (publisher.ROOT / publisher.APPROVAL_PATH).read_text()
    )
    policy, heor = _transition_collections(
        approval, approval["candidate_scope"]["members"][0]["previous_note"]
    )
    heor.items[0].note = "unrecognized HEOR note"

    with pytest.raises(ValueError, match="HEOR item note"):
        publisher.validate_collection_transitions(policy, heor, approval)


def test_collection_reconciler_updates_exact_approved_prior_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_id = "edithatogo/australian-mbs-source-archive"
    prior_note = "exact previously approved note"
    collection = SimpleNamespace(
        items=[_collection_item(repo_id, prior_note)],
        description="existing description",
        private=True,
    )
    test_token = "t" * 24
    hub = cast("Any", ModuleType("huggingface_hub"))

    def add_collection_item(**_kwargs: Any) -> None:
        return None

    def update_collection_metadata(**_kwargs: Any) -> None:
        return None

    def get_collection(_slug: str, *, token: str) -> SimpleNamespace:
        assert token == test_token
        return collection

    def update_collection_item(
        *, collection_slug: str, item_object_id: str, note: str, token: str
    ) -> None:
        assert collection_slug == "owner/collection"
        assert item_object_id == f"object-{repo_id}"
        assert token == test_token
        collection.items[0].note = note

    hub.add_collection_item = add_collection_item
    hub.get_collection = get_collection
    hub.update_collection_item = update_collection_item
    hub.update_collection_metadata = update_collection_metadata
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)

    result = publisher._reconcile_collection(
        test_token,
        slug="owner/collection",
        desired_notes={repo_id: "new approved note"},
        expected_members=set(),
        baseline_notes={repo_id: {None, prior_note}},
    )

    assert result.items[0].note == "new approved note"


def test_scope_assessment_binds_each_prior_policy_note() -> None:
    approval = json.loads(
        (publisher.ROOT / publisher.APPROVAL_PATH).read_text()
    )
    scope = approval["candidate_scope"]
    assessment = json.loads(
        (publisher.ROOT / scope["scope_assessment_path"]).read_text()
    )
    assessment["policy_aus_change_proposal"]["proposed_dataset_members"][0][
        "previous_collection_note"
    ] = "unrecognized prior note"

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
