"""Exact PBS admission policy is independent from candidate contract claims."""

from __future__ import annotations

import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed local CLI, no shell
import sys
from pathlib import Path

import pytest
import scripts.qualify_m112_pbs_v4_admission as qualification

from global_medicines_atlas.federation_receipt_closure import ReceiptClosure


def _objects() -> list[dict[str, object]]:
    return json.loads(
        (qualification.ROOT / qualification.MANIFEST).read_bytes()
    )["objects"]


@pytest.mark.parametrize("target_path", [row["path"] for row in _objects()])
def test_each_exact_pbs_contract_has_independent_source_trust(
    target_path: str,
) -> None:
    raw, trusted = qualification.load_candidate(target_path=target_path)
    document = json.loads(raw)
    assert trusted.path == target_path
    assert trusted.dataset == "edithatogo/australian-pbs-utilisation-archive"
    assert trusted.representation == "raw"
    assert trusted.effective_date is None
    assert trusted.schema_era == "unqualified-native-schema"
    assert document["source"]["acquisition_id"] == trusted.acquisition_id
    assert len(trusted.lineage) == 6
    assert document["consumers"] == []


@pytest.mark.parametrize("target_path", ["raw/pbs/unknown.csv", "../secret"])
def test_unbound_pbs_target_is_rejected(target_path: str) -> None:
    with pytest.raises(ValueError, match="exact PBS"):
        qualification.load_candidate(target_path=target_path)


def test_changed_contract_is_rejected_before_network(
    tmp_path: Path,
) -> None:
    manifest = qualification.ROOT / qualification.MANIFEST
    destination = tmp_path / qualification.MANIFEST
    destination.parent.mkdir(parents=True)
    destination.write_bytes(manifest.read_bytes())
    row = _objects()[0]
    path = Path(str(row["contract_path"]))
    local = tmp_path / path
    local.write_bytes((qualification.ROOT / path).read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest"):
        qualification.load_candidate(tmp_path, target_path=str(row["path"]))


def test_changed_manifest_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / qualification.MANIFEST
    path.parent.mkdir(parents=True)
    path.write_bytes(
        (qualification.ROOT / qualification.MANIFEST).read_bytes() + b"\n"
    )
    with pytest.raises(ValueError, match="digest"):
        qualification.load_candidate(
            tmp_path, target_path=str(_objects()[0]["path"])
        )


def test_local_verification_refuses_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="Actions dispatch"):
        qualification.qualify(
            target_path=str(_objects()[0]["path"]), workflow_commit="a" * 40
        )


@pytest.mark.parametrize("target_path", [row["path"] for row in _objects()])
def test_independent_profile_admits_only_the_verified_exact_contract(
    monkeypatch: pytest.MonkeyPatch,
    target_path: str,
) -> None:
    report = json.loads(
        (
            qualification.ROOT
            / qualification.DIRECTORY
            / "receipt-closure.json"
        ).read_bytes()
    )
    row = next(x for x in report["objects"] if x["path"] == target_path)
    closure = ReceiptClosure.model_validate(row["closure"])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", qualification.REPOSITORY)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")

    def closed(*_args: object, **_kwargs: object) -> ReceiptClosure:
        return closure

    monkeypatch.setattr(qualification, "receipt_closure", closed)

    def canary(
        raw: bytes, admission: dict[str, object], **_kwargs: object
    ) -> dict[str, object]:
        assert admission["path"] == target_path
        assert json.loads(raw)["location"]["path"] == target_path
        return {"status": "synthetic_test_reader_passed"}

    monkeypatch.setattr(qualification, "run_reader_canary", canary)
    result = qualification.qualify(
        target_path=target_path, workflow_commit="a" * 40
    )
    assert result["admission"]["path"] == target_path
    assert result["boundaries"]["public_dataset_mutated"] is False
    assert result["boundaries"]["federation_gate_closed"] is False


def test_wrong_independent_profile_rejects_closed_contract() -> None:
    path = str(_objects()[0]["path"])
    raw, trusted = qualification.load_candidate(target_path=path)
    report = json.loads(
        (
            qualification.ROOT
            / qualification.DIRECTORY
            / "receipt-closure.json"
        ).read_bytes()
    )
    closure = ReceiptClosure.model_validate(report["objects"][0]["closure"])
    wrong = trusted.model_copy(update={"source_id": "untrusted-source"})
    with pytest.raises(ValueError, match="independently trusted"):
        qualification.admit_closed_contract(
            raw,
            closure,
            schema=(qualification.ROOT / qualification.SCHEMA).read_bytes(),
            trusted=wrong,
        )


def test_changed_remote_receipt_bytes_fail_closure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, _ = qualification.load_candidate(
        target_path=str(_objects()[0]["path"])
    )

    def incorrect(_url: str, _client: object) -> bytes:
        return b"synthetic incorrect receipt bytes"

    monkeypatch.setattr(qualification, "_download_receipt", incorrect)
    with pytest.raises(ValueError, match="receipt"):
        qualification.receipt_closure(raw)


def test_remote_receipt_byte_budget_is_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, _ = qualification.load_candidate(
        target_path=str(_objects()[0]["path"])
    )

    def oversized(_url: str, _client: object) -> bytes:
        return b"xx"

    monkeypatch.setattr(qualification, "_download_receipt", oversized)
    monkeypatch.setattr(qualification, "MAX_RECEIPT_BYTES", 1)
    with pytest.raises(ValueError, match="byte budget"):
        qualification.receipt_closure(raw)


def test_cli_check_records_no_admission(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "qualification",
            "--target-path",
            str(_objects()[0]["path"]),
            "--check",
        ],
    )
    qualification.main()
    assert (
        json.loads(capsys.readouterr().out)["status"]
        == "candidate_policy_checked_not_admitted"
    )


def test_cli_verify_requires_report_and_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "qualification",
            "--target-path",
            str(_objects()[0]["path"]),
            "--verify",
        ],
    )
    with pytest.raises(SystemExit, match="2"):
        qualification.main()


def test_missing_attempt_refuses_before_receipt_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": qualification.REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "123",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
    with pytest.raises(ValueError, match="workflow attempt"):
        qualification.qualify(
            target_path=str(_objects()[0]["path"]), workflow_commit="a" * 40
        )


def test_hosted_workflow_has_only_six_explicit_read_only_targets() -> None:
    path = (
        qualification.ROOT
        / ".github/workflows/australian-m112-pbs-v4-admission-qualification.yml"
    )
    text = path.read_text()
    targets = {
        line.strip().removeprefix("- ")
        for line in text.splitlines()
        if line.strip().startswith("- raw/")
    }
    assert targets == {str(row["path"]) for row in _objects()}
    assert "test \"$GITHUB_REF\" = 'refs/heads/main'" in text
    assert 'test "$GITHUB_SHA" = "$REQUESTED_COMMIT"' in text
    assert "contents: read" in text
    assert "persist-credentials: false" in text
    assert "cancel-in-progress: false" in text
    assert "HF_HUB_DISABLE_IMPLICIT_TOKEN: '1'" in text
    assert "upload-artifact@" in text
    assert "secrets." not in text


def test_cli_verify_writes_only_the_returned_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "metadata" / "receipt.json"

    def verified(
        *, target_path: str, workflow_commit: str
    ) -> dict[str, object]:
        assert target_path == str(_objects()[0]["path"])
        assert workflow_commit == "a" * 40
        return {"status": "synthetic_test_result"}

    monkeypatch.setattr(qualification, "qualify", verified)
    monkeypatch.setattr(
        "sys.argv",
        [
            "qualification",
            "--target-path",
            str(_objects()[0]["path"]),
            "--verify",
            "--workflow-commit",
            "a" * 40,
            "--report",
            str(output),
        ],
    )
    qualification.main()
    assert json.loads(output.read_bytes()) == {
        "status": "synthetic_test_result"
    }


def test_script_entrypoint_checks_policy_without_source_reads() -> None:
    completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed argument array, shell=False
        [
            sys.executable,
            str(
                qualification.ROOT / "scripts/qualify_m112_pbs_v4_admission.py"
            ),
            "--target-path",
            str(_objects()[0]["path"]),
            "--check",
        ],
        cwd=qualification.ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
        shell=False,
    )
    assert (
        json.loads(completed.stdout)["status"]
        == "candidate_policy_checked_not_admitted"
    )


def test_changed_independent_schema_pin_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = tmp_path / "untrusted-schema.json"
    schema.write_bytes(
        (qualification.ROOT / qualification.SCHEMA).read_bytes() + b"\n"
    )
    monkeypatch.setattr(qualification, "SCHEMA", schema)
    with pytest.raises(ValueError, match="schema digest"):
        qualification.load_candidate(target_path=str(_objects()[0]["path"]))
