"""Complete metadata enumeration must not imply payload rights or acquisition."""

from __future__ import annotations

import copy
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from scripts import observe_hf_estate as cli

from global_medicines_atlas.hf_estate import (
    EnumerationReceipt,
    EstateEntry,
    EstateSnapshot,
    OwnerVisibilityEvidence,
    build_estate_snapshot,
)

NOW = datetime(2026, 8, 30, tzinfo=UTC)


def listings() -> dict[str, list[dict[str, Any]]]:
    return {
        "model": [],
        "dataset": [
            {
                "id": "owner/public-data",
                "private": False,
                "gated": False,
                "sha": "a" * 40,
            },
            {
                "id": "owner/private-data",
                "private": True,
                "gated": False,
                "sha": "b" * 40,
                "cardData": {"secret": "must-not-escape"},
            },
        ],
        "space": [{"id": "owner/app", "private": False, "sha": "c" * 40}],
        "collection": [
            {"slug": "owner/collection-123", "private": False, "items": []}
        ],
    }


def snapshot() -> EstateSnapshot:
    return build_estate_snapshot(
        "owner",
        listings(),
        listings(),
        observed_at=NOW,
        authenticated_owner="owner",
    )


def test_inventory_covers_empty_and_nonempty_kinds_without_leaks() -> None:
    result = snapshot()
    assert len(result.entries) == 4
    assert {receipt.kind for receipt in result.enumerations} == {
        "model",
        "dataset",
        "space",
        "collection",
    }
    output = result.model_dump_json()
    assert "must-not-escape" not in output
    assert "private-data" not in output
    assert "cardData" not in output
    assert all(
        entry.publication_state == "not_assessed" for entry in result.entries
    )
    assert result.enumeration_scope == "authenticated_visible_owner_metadata"


def test_missing_kind_duplicate_and_wrong_owner_fail() -> None:
    missing = listings()
    del missing["model"]
    with pytest.raises(ValueError, match="four kinds"):
        build_estate_snapshot(
            "owner",
            missing,
            missing,
            observed_at=NOW,
            authenticated_owner="owner",
        )
    for mutation in ("duplicate", "owner"):
        payload = listings()
        if mutation == "duplicate":
            payload["dataset"].append(payload["dataset"][0])
        else:
            payload["dataset"][0]["id"] = "other/public-data"
        with pytest.raises(ValueError, match=r"duplicate|another owner"):
            build_estate_snapshot(
                "owner",
                payload,
                payload,
                observed_at=NOW,
                authenticated_owner="owner",
            )


def test_drift_and_truncation_fail_closed() -> None:
    second = listings()
    second["dataset"][0]["sha"] = "d" * 40
    with pytest.raises(ValueError, match="changed"):
        build_estate_snapshot(
            "owner",
            listings(),
            second,
            observed_at=NOW,
            authenticated_owner="owner",
        )
    with pytest.raises(ValueError, match="limit"):
        build_estate_snapshot(
            "owner",
            listings(),
            listings(),
            observed_at=NOW,
            authenticated_owner="owner",
            limit=2,
        )


def test_observation_denominator_rejects_deleted_entry() -> None:
    document = snapshot().model_dump(mode="json")
    document["entries"].pop()
    with pytest.raises(ValidationError, match="denominator"):
        EstateSnapshot.model_validate(document)


def test_anonymous_or_different_account_cannot_claim_complete_owner_inventory() -> (
    None
):
    for owner in (None, "other"):
        with pytest.raises(ValueError, match="authenticated owner"):
            build_estate_snapshot(
                "owner",
                listings(),
                listings(),
                observed_at=NOW,
                authenticated_owner=owner,
            )


@pytest.mark.parametrize(
    ("field", "value"),
    [("private", None), ("private", "false"), ("sha", "main"), ("gated", None)],
)
def test_absent_or_malformed_required_metadata_is_not_public(
    field: str, value: Any
) -> None:
    payload = listings()
    payload["dataset"][0][field] = value
    with pytest.raises(
        (ValueError, TypeError), match=r"visibility|revision|gated"
    ):
        build_estate_snapshot(
            "owner",
            payload,
            payload,
            observed_at=NOW,
            authenticated_owner="owner",
        )


def test_order_changes_do_not_change_snapshot_identity() -> None:
    first = snapshot()
    second = copy.deepcopy(listings())
    second["dataset"].reverse()
    other = build_estate_snapshot(
        "owner",
        listings(),
        second,
        observed_at=NOW,
        authenticated_owner="owner",
    )
    assert other == first


@pytest.mark.parametrize("kind", ["dataset", "collection"])
def test_invalid_identity_and_missing_metadata(kind: str) -> None:
    payload = listings()
    key = "slug" if kind == "collection" else "id"
    payload[kind][0][key] = "owner/../bad"
    with pytest.raises(ValueError, match="identity"):
        build_estate_snapshot(
            "owner",
            payload,
            payload,
            observed_at=NOW,
            authenticated_owner="owner",
        )
    payload = listings()
    del payload[kind][0]["items" if kind == "collection" else "sha"]
    with pytest.raises(ValueError, match="missing"):
        build_estate_snapshot(
            "owner",
            payload,
            payload,
            observed_at=NOW,
            authenticated_owner="owner",
        )


def test_empty_repo_and_same_size_collection_drift() -> None:
    payload = listings()
    payload["dataset"][0]["sha"] = None
    result = build_estate_snapshot(
        "owner", payload, payload, observed_at=NOW, authenticated_owner="owner"
    )
    assert any(
        row.revision is None and row.kind == "dataset" for row in result.entries
    )
    first, second = listings(), listings()
    first["collection"][0]["items"] = [
        {"item_id": "owner/one", "item_type": "dataset"}
    ]
    second["collection"][0]["items"] = [
        {"item_id": "owner/two", "item_type": "dataset"}
    ]
    with pytest.raises(ValueError, match="changed"):
        build_estate_snapshot(
            "owner", first, second, observed_at=NOW, authenticated_owner="owner"
        )


def test_snapshot_rejects_receipt_and_identity_tampering() -> None:
    result = snapshot()
    document = result.model_dump(mode="json")
    document["enumerations"].pop()
    with pytest.raises(ValidationError, match="four kinds"):
        EstateSnapshot.model_validate(document)
    document = result.model_dump(mode="json")
    document["owner"] = "another"
    with pytest.raises(ValidationError, match="owner mismatch"):
        EstateSnapshot.model_validate(document)
    for row in result.entries:
        tampered = row.model_dump(mode="json")
        tampered["identity"] = "owner/changed"
        with pytest.raises(
            ValidationError, match=r"private metadata|digest mismatch"
        ):
            EstateEntry.model_validate(tampered)
    with pytest.raises(ValidationError, match="endpoint limit"):
        EnumerationReceipt(
            kind="collection", count=1, limit=101, entries_sha256="a" * 64
        )


@pytest.mark.parametrize(
    ("identity", "scope"),
    [
        (
            "edithatogo/australian-mbs-source-archive",
            "australian_source_archive",
        ),
        ("edithatogo/dataset-estate-registry", "gma_related"),
    ],
)
def test_scope_labels_do_not_authorize_publication(
    identity: str, scope: str
) -> None:
    payload: dict[str, list[dict[str, Any]]] = {kind: [] for kind in listings()}
    payload["dataset"] = [
        {"id": identity, "private": False, "gated": False, "sha": "a" * 40}
    ]
    result = build_estate_snapshot(
        "edithatogo",
        payload,
        payload,
        observed_at=NOW,
        authenticated_owner="edithatogo",
    )
    assert result.entries[0].scope == scope
    assert result.entries[0].publication_state == "not_assessed"


def test_metadata_command_bounds_and_redacts_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = cli.subprocess.Popen
    code = ["print('safe')"]

    def launch(_command: list[str], **kwargs: Any) -> Any:
        return original([sys.executable, "-c", code[0]], **kwargs)

    monkeypatch.setattr(cli.subprocess, "Popen", launch)
    command = ["hf", "auth", "whoami"]
    assert cli.metadata_command(command) == b"safe\n"
    code[0] = "import sys; sys.exit('sensitive-error')"
    with pytest.raises(ValueError, match="no raw diagnostic"):
        cli.metadata_command(command)
    code[0] = "print('x' * 1000)"
    monkeypatch.setattr(cli, "MAX_OUTPUT_BYTES", 10)
    with pytest.raises(ValueError, match="byte"):
        cli.metadata_command(command)
    code[0] = "import time; time.sleep(1)"
    monkeypatch.setattr(cli, "COMMAND_TIMEOUT_SECONDS", 0)
    with pytest.raises(ValueError, match="time bound"):
        cli.metadata_command(command)


@pytest.mark.parametrize(
    "command",
    [
        ["hf", "upload", "owner/data", "file"],
        [
            "hf",
            "datasets",
            "list",
            "--format",
            "json",
            "--author",
            "--token",
            "secret",
        ],
        ["hf", "auth", "list"],
    ],
)
def test_local_mutation_and_credential_commands_are_rejected(
    command: list[str],
) -> None:
    with pytest.raises(ValueError, match="read-only metadata"):
        cli.metadata_command(command)


def test_noncanonical_hub_endpoint_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_ENDPOINT", "https://mirror.invalid")
    with pytest.raises(ValueError, match="official Hub endpoint"):
        cli.metadata_command(["hf", "auth", "whoami"])


def test_cli_uses_explicit_caps_and_minimal_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def execute(command: list[str]) -> bytes:
        calls.append(command)
        return b"[]"

    monkeypatch.setattr(cli, "metadata_command", execute)
    assert set(cli.observe("owner")) == set(listings())
    assert all("--limit" in call and "--format" in call for call in calls)
    assert calls[-1][-1] == "100"
    assert all("--token" not in call for call in calls)

    def malformed(_command: list[str]) -> bytes:
        return b"{}"

    monkeypatch.setattr(cli, "metadata_command", malformed)
    with pytest.raises(ValueError, match="JSON object array"):
        cli.observe("owner")


def test_cli_writes_only_redacted_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    target = tmp_path / "estate.json"
    monkeypatch.setattr(
        sys, "argv", ["observe", "--owner", "owner", "--output", str(target)]
    )

    def identity(_command: list[str]) -> bytes:
        return b"user=owner orgs=\n"

    def scan(_owner: str) -> dict[str, list[dict[str, Any]]]:
        return listings()

    monkeypatch.setattr(cli, "metadata_command", identity)
    monkeypatch.setattr(cli, "observe", scan)
    assert cli.main() == 0
    assert "private-data" not in target.read_text()
    EstateSnapshot.model_validate(json.loads(target.read_text()))

    def unauthenticated(_command: list[str]) -> bytes:
        return b"Not logged in\n"

    monkeypatch.setattr(cli, "metadata_command", unauthenticated)
    with pytest.raises(ValueError, match="authenticated owner"):
        cli.main()


def test_malformed_membership_and_receipt_cap() -> None:
    payload = listings()
    payload["collection"][0]["items"] = ["not-an-object"]
    with pytest.raises(ValueError, match="membership malformed"):
        build_estate_snapshot(
            "owner",
            payload,
            payload,
            observed_at=NOW,
            authenticated_owner="owner",
        )
    with pytest.raises(ValidationError, match="reached limit"):
        EnumerationReceipt(
            kind="dataset", count=2, limit=2, entries_sha256="a" * 64
        )


def test_committed_snapshot_and_generated_schema_are_consistent() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas/hf-estate-v1.json").read_text())
    assert schema == EstateSnapshot.model_json_schema()
    document = json.loads(
        (root / "quality/qualifications/hf-estate-20260830.json").read_text()
    )
    # jsonschema's overload includes an untyped optional legacy schema argument.
    validator = cast("Any", Draft202012Validator(schema))
    assert not list(validator.iter_errors(document))
    result = EstateSnapshot.model_validate(document)
    assert all(
        row.identity.startswith("private:")
        for row in result.entries
        if row.private
    )


def test_owner_visibility_requires_complete_current_observation() -> None:
    evidence = OwnerVisibilityEvidence(
        owner="owner",
        scope_owner="owner",
        scope_kind="user",
        endpoint="https://huggingface.co/api/whoami-v2",
        observed_at=NOW,
        permissions=(
            "repo.content.read",
            "repo.access.read",
            "collection.read",
        ),
    )
    result = build_estate_snapshot(
        "owner",
        listings(),
        listings(),
        observed_at=NOW,
        authenticated_owner="owner",
        visibility_evidence=evidence,
    )
    assert result.credential_visibility_attested
    for updates in (
        {"permissions": ["repo.content.read"]},
        {"scope_owner": "another"},
    ):
        invalid = evidence.model_dump(mode="json") | updates
        with pytest.raises(ValidationError, match="owner-wide"):
            OwnerVisibilityEvidence.model_validate(invalid)
    for updates in (
        {"owner": "another", "scope_owner": "another"},
        {"observed_at": "2025-01-01T00:00:00Z"},
    ):
        invalid_evidence = OwnerVisibilityEvidence.model_validate(
            evidence.model_dump(mode="json") | updates
        )
        with pytest.raises(ValueError, match="observation window"):
            build_estate_snapshot(
                "owner",
                listings(),
                listings(),
                observed_at=NOW,
                authenticated_owner="owner",
                visibility_evidence=invalid_evidence,
            )
    document = snapshot().model_dump(mode="json")
    document["credential_visibility_attested"] = True
    with pytest.raises(ValidationError, match="visibility claim"):
        EstateSnapshot.model_validate(document)


def test_cli_binds_safe_visibility_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    evidence_file = tmp_path / "permission.json"
    evidence = OwnerVisibilityEvidence(
        owner="owner",
        scope_owner="owner",
        scope_kind="user",
        endpoint="https://huggingface.co/api/whoami-v2",
        observed_at=datetime.now(UTC),
        permissions=(
            "repo.content.read",
            "repo.access.read",
            "collection.read",
        ),
    )
    evidence_file.write_text(evidence.model_dump_json())
    target = tmp_path / "estate.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "observe",
            "--owner",
            "owner",
            "--output",
            str(target),
            "--visibility-evidence",
            str(evidence_file),
        ],
    )

    def identity(_command: list[str]) -> bytes:
        return b"user=owner\n"

    def scan(_owner: str) -> dict[str, list[dict[str, Any]]]:
        return listings()

    monkeypatch.setattr(cli, "metadata_command", identity)
    monkeypatch.setattr(cli, "observe", scan)
    assert cli.main() == 0
    assert EstateSnapshot.model_validate_json(
        target.read_bytes()
    ).credential_visibility_attested
    evidence_file.write_text('{"unexpected_secret": "must-not-escape"}')
    with pytest.raises(ValueError, match="no raw diagnostic") as error:
        cli.main()
    assert "must-not-escape" not in str(error.value)
    monkeypatch.setattr(cli, "MAX_OUTPUT_BYTES", 1)
    with pytest.raises(ValueError, match="byte bound"):
        cli.main()
