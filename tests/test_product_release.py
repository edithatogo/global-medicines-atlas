import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError
from scripts import run_product_qualification
from scripts.qualify_product_release import build_evidence
from scripts.run_product_qualification import implementation_digest, run

from global_medicines_atlas.product_release import (
    ProductReleaseEvidence,
    ProductReleaseState,
    QualificationReceipt,
    validate_receipt,
)

FIXTURE = Path(
    "tests/fixtures/release-evidence/product/fixture-qualified-v0.6.json"
)
NOW = datetime(2026, 7, 29, 0, 0, tzinfo=UTC)
IMPLEMENTATION = "1" * 64


def receipt_payload(
    *,
    kind: str = "performance",
    subject_id: str = "PERF-QUERY",
    executed_at: datetime = NOW,
    implementation_digest: str = IMPLEMENTATION,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1",
        "receipt_id": "receipt-1",
        "kind": kind,
        "subject_id": subject_id,
        "executed_at": executed_at.isoformat().replace("+00:00", "Z"),
        "product_version": "0.6",
        "api_version": "v1",
        "implementation_digest": implementation_digest,
        "result": {
            "passed": True,
            "observed_ms": 42.0 if kind == "performance" else None,
            "sample_size": 20 if kind == "performance" else None,
            "detail": "executed check passed",
        },
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    payload["payload_digest"] = sha256(encoded).hexdigest()
    return payload


def test_default_fixture_is_fail_closed():
    value = build_evidence(now=NOW)
    assert value.state is ProductReleaseState.BLOCKED
    assert not value.gates["performance_budgets_verified"]
    assert not value.gates["abuse_cases_verified"]
    assert all(item.observed_ms is None for item in value.performance)
    assert all(item.receipt_id is None for item in value.threats)


def test_valid_receipt_is_bound_to_expected_check():
    receipt = QualificationReceipt.model_validate(receipt_payload())
    assert (
        validate_receipt(
            receipt,
            kind="performance",
            subject_id="PERF-QUERY",
            implementation_digest=IMPLEMENTATION,
            now=NOW,
        )
        is None
    )
    assert "subject" in (
        validate_receipt(
            receipt,
            kind="performance",
            subject_id="PERF-CONTRACT",
            implementation_digest=IMPLEMENTATION,
            now=NOW,
        )
        or ""
    )


def test_stale_and_mismatched_receipts_are_rejected():
    stale = QualificationReceipt.model_validate(
        receipt_payload(executed_at=NOW - timedelta(days=8))
    )
    assert "stale" in (
        validate_receipt(
            stale,
            kind="performance",
            subject_id="PERF-QUERY",
            implementation_digest=IMPLEMENTATION,
            now=NOW,
        )
        or ""
    )
    current = QualificationReceipt.model_validate(receipt_payload())
    assert "implementation" in (
        validate_receipt(
            current,
            kind="performance",
            subject_id="PERF-QUERY",
            implementation_digest="2" * 64,
            now=NOW,
        )
        or ""
    )


def test_tampered_receipt_is_rejected():
    payload = receipt_payload()
    result = payload["result"]
    assert isinstance(result, dict)
    result["observed_ms"] = 0.1
    with pytest.raises(ValidationError, match="payload digest"):
        QualificationReceipt.model_validate(payload)


def test_generator_fails_closed_for_stale_and_tampered_receipts(
    tmp_path: Path,
):
    stale = receipt_payload(executed_at=NOW - timedelta(days=8))
    (tmp_path / "stale.json").write_text(json.dumps(stale), encoding="utf-8")
    tampered = receipt_payload(subject_id="PERF-CONTRACT")
    result = tampered["result"]
    assert isinstance(result, dict)
    result["passed"] = False
    (tmp_path / "tampered.json").write_text(
        json.dumps(tampered), encoding="utf-8"
    )

    value = build_evidence(
        receipts_dir=tmp_path,
        implementation_digest=IMPLEMENTATION,
        now=NOW,
    )

    assert not value.gates["performance_budgets_verified"]
    assert all(item.receipt_id is None for item in value.performance)


def test_direct_construction_rejects_forged_release_state():
    payload = build_evidence(now=NOW).model_dump(mode="json")
    payload["state"] = "release_qualified"
    with pytest.raises(ValidationError, match="state must be"):
        ProductReleaseEvidence.model_validate(payload)


def test_canonical_evidence_matches_committed_fixture():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    value = ProductReleaseEvidence.model_validate(payload)
    assert value.state is ProductReleaseState.BLOCKED
    assert json.loads(value.canonical_json()) == payload


def test_default_regeneration_is_deterministic():
    first = build_evidence(now=NOW).canonical_json()
    second = build_evidence(now=NOW + timedelta(days=1)).canonical_json()
    assert first == second
    assert b"1000-row" not in first


def test_runner_qualifies_fixture_gates_and_binds_receipts(tmp_path: Path):
    output = tmp_path / "evidence.json"
    receipts = tmp_path / "receipts"
    run(output, receipts)
    evidence = ProductReleaseEvidence.model_validate_json(output.read_text())
    assert evidence.state is ProductReleaseState.FIXTURE_QUALIFIED
    assert evidence.gates["performance_budgets_verified"]
    assert evidence.gates["abuse_cases_verified"]
    assert all(item.receipt_id for item in evidence.performance)
    assert all(item.receipt_id for item in evidence.threats)


def test_runner_publishes_nothing_when_a_check_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    output = tmp_path / "evidence.json"
    receipts = tmp_path / "receipts"

    def over_budget(_workload: object) -> float:
        return 9_999

    monkeypatch.setattr(run_product_qualification, "_p95", over_budget)

    with pytest.raises(RuntimeError, match="exceeded"):
        run(output, receipts)

    assert not output.exists()
    assert not receipts.exists()


def test_direct_runner_cli_from_repository_root(tmp_path: Path):
    destination = tmp_path / "product-qualification"
    uv_executable = shutil.which("uv")
    assert uv_executable is not None
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [
            str(Path(uv_executable).resolve()),
            "run",
            "--group",
            "dev",
            "python",
            "scripts/run_product_qualification.py",
            "--output",
            str(destination),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    evidence = destination / "evidence.json"
    receipts = destination / "receipts"
    assert evidence.is_file()
    assert len(tuple(receipts.glob("*.json"))) == 8
    assert '"state":"fixture_qualified"' in evidence.read_text()


@pytest.mark.parametrize(
    "changed",
    [
        "src/global_medicines_atlas/templates/atlas.html",
        "src/global_medicines_atlas/static/atlas.css",
        "pyproject.toml",
        "uv.lock",
    ],
)
def test_runtime_manifest_change_invalidates_receipt(
    tmp_path: Path,
    changed: str,
):
    manifest = (
        "src/global_medicines_atlas/templates/atlas.html",
        "src/global_medicines_atlas/static/atlas.css",
        "pyproject.toml",
        "uv.lock",
    )
    for relative in manifest:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture:{relative}\n", encoding="utf-8")
    original_digest = implementation_digest(tmp_path, manifest=manifest)
    receipt = QualificationReceipt.model_validate(
        receipt_payload(implementation_digest=original_digest)
    )

    changed_path = tmp_path / changed
    changed_path.write_text(
        changed_path.read_text(encoding="utf-8") + "runtime-change\n",
        encoding="utf-8",
    )
    changed_digest = implementation_digest(tmp_path, manifest=manifest)

    assert changed_digest != original_digest
    assert "implementation" in (
        validate_receipt(
            receipt,
            kind="performance",
            subject_id="PERF-QUERY",
            implementation_digest=changed_digest,
            now=NOW,
        )
        or ""
    )
