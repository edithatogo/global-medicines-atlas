"""Exact July raw v4 qualification remains bounded and fail closed."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_mbs_july_frozen_v4 as qualification


def _hosted(monkeypatch: pytest.MonkeyPatch, commit: str) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", qualification.REPO)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_SHA", commit)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")


def test_candidate_uses_existing_exact_source_and_preserves_recovery_limits() -> (
    None
):
    raw, trusted = qualification.candidate()
    document = json.loads(raw)
    assert raw == (qualification.ROOT / qualification.OUTPUT).read_bytes()
    assert trusted.path == qualification.lineage.JULY
    assert trusted.sha256 == document["location"]["sha256"]
    assert trusted.schema_era == "2025-07-version-3"
    assert trusted.comparison_cohort == "legacy"
    assert (
        document["rights"]["basis"]
        == "maintainer_attested_exact_scope_permission_not_independently_reviewed"
    )
    assert document["recovery"]["role"] == "primary"
    assert document["recovery"]["independent"] is False
    assert document["recovery"]["rpo_seconds"] is None
    assert document["consumers"] == []


@pytest.mark.parametrize(
    ("field", "value"),
    [("comparison_cohort", "current"), ("acquisition_id", "wrong")],
)
def test_candidate_rejects_changed_source_profile(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    original = qualification.bounded.read_bound_metadata

    def read(root: Path, path: str, digest: str) -> dict[str, Any]:
        result = original(root, path, digest)
        if path == qualification.SILVER_PROFILE:
            result = copy.deepcopy(result)
            result["source"][field] = value
        return result

    monkeypatch.setattr(qualification.bounded, "read_bound_metadata", read)
    with pytest.raises(ValueError, match="source profile differs"):
        qualification.candidate()


def test_candidate_rejects_changed_privacy_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = qualification.bounded.read_bound_metadata
    path_to_change = qualification.lineage.INPUTS["july_receipt"][0]

    def read(root: Path, path: str, digest: str) -> dict[str, Any]:
        result = original(root, path, digest)
        if path == path_to_change:
            result = copy.deepcopy(result)
            result["sensitivity"]["data_sensitivity"] = "restricted"
        return result

    monkeypatch.setattr(qualification.bounded, "read_bound_metadata", read)
    with pytest.raises(
        ValueError, match="historical MBS B1/B2 lifecycle differs"
    ):
        qualification.candidate()


def test_local_verify_fails_before_loading_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(
        qualification,
        "candidate",
        lambda *_args: pytest.fail("unexpected candidate read"),
    )
    with pytest.raises(ValueError, match="Actions dispatch on main"):
        qualification.qualify(workflow_commit="a" * 40)


def test_invalid_hosted_run_fails_before_loading_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    _hosted(monkeypatch, commit)
    monkeypatch.setenv("GITHUB_RUN_ID", "0")
    monkeypatch.setattr(
        qualification,
        "candidate",
        lambda *_args: pytest.fail("unexpected candidate read"),
    )
    with pytest.raises(ValueError, match="run identity missing"):
        qualification.qualify(workflow_commit=commit)


def test_stale_contract_fails_before_receipt_or_source_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commit = "a" * 40
    _hosted(monkeypatch, commit)
    raw, trust = qualification.candidate()
    monkeypatch.setattr(qualification, "candidate", lambda _root: (raw, trust))
    monkeypatch.setattr(
        qualification.shared,
        "receipt_closure",
        lambda *_args, **_kwargs: pytest.fail("unexpected receipt fetch"),
    )
    path = tmp_path / qualification.OUTPUT
    path.parent.mkdir(parents=True)
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="contract is stale"):
        qualification.qualify(workflow_commit=commit, root=tmp_path)


def test_hosted_orchestration_uses_admission_for_bounded_canary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    _hosted(monkeypatch, commit)
    raw, trust = qualification.candidate()
    monkeypatch.setattr(qualification, "candidate", lambda _root: (raw, trust))

    class Result:
        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"status": "synthetic"}

    closure = Result()
    monkeypatch.setattr(
        qualification.shared, "receipt_closure", lambda _raw, **_kwargs: closure
    )
    monkeypatch.setattr(
        qualification,
        "admit_closed_contract",
        lambda _raw, _closure, **_kwargs: Result(),
    )
    seen: list[dict[str, str]] = []

    def canary(
        _raw: bytes, admission: dict[str, str], **_kwargs: Any
    ) -> dict[str, str]:
        seen.append(admission)
        return {"status": "synthetic"}

    monkeypatch.setattr(qualification, "run_reader_canary", canary)
    result = qualification.qualify(workflow_commit=commit)
    assert seen == [{"status": "synthetic"}]
    assert result["status"] == "passed"
    assert result["boundaries"]["dataset_added_or_published"] is False
    assert result["boundaries"]["independent_recovery_established"] is False


def test_cli_writes_and_checks_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw, trust = qualification.candidate()
    monkeypatch.setattr(qualification, "candidate", lambda: (raw, trust))
    monkeypatch.setattr(qualification, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["qualification", "--write"])
    assert qualification.main() == 0
    monkeypatch.setattr(sys, "argv", ["qualification", "--check"])
    assert qualification.main() == 0
    (tmp_path / qualification.OUTPUT).write_text("{}")
    with pytest.raises(ValueError, match="contract is stale"):
        qualification.main()
