"""Focused tests for NZ migration consolidation verification."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/verify_nz_consolidation.py"


def _load_script() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "verify_nz_consolidation",
        SCRIPT,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


VERIFY = _load_script()


def _copy_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    inventory = tmp_path / "inventory.json"
    preservation = tmp_path / "preservation.json"
    vendor = tmp_path / "vendor/nzmedicines"
    shutil.copy(VERIFY.INVENTORY_PATH, inventory)
    shutil.copy(VERIFY.PRESERVATION_PATH, preservation)
    shutil.copytree(VERIFY.VENDOR_ROOT, vendor)
    return inventory, preservation, vendor


def _verify(paths: tuple[Path, Path, Path]) -> dict[str, object]:
    inventory, preservation, vendor = paths
    return cast(
        "dict[str, object]",
        VERIFY.verify_consolidation(
            inventory_path=inventory,
            preservation_path=preservation,
            vendor_root=vendor,
        ),
    )


def _read(path: Path) -> dict[str, object]:
    return cast(
        "dict[str, object]",
        json.loads(path.read_text(encoding="utf-8")),
    )


def _write(path: Path, value: dict[str, object]) -> None:
    path.write_text(
        json.dumps(value, indent=2) + "\n",
        encoding="utf-8",
    )


def test_repository_consolidation_passes() -> None:
    receipt = VERIFY.verify_consolidation()
    assert receipt["status"] == "passed"
    assert receipt["upstream_asset_count"] == 25
    assert receipt["adapted_output_count"] > 0
    assert receipt["local_inventory_metadata_count"] == 137
    assert receipt["resident_byte_verified_count"] == 4
    assert receipt["placeholder_metadata_only_count"] == 132


def test_receipt_uses_bounded_preservation_claims() -> None:
    receipt = VERIFY.verify_consolidation()
    checks = cast("dict[str, object]", receipt["checks"])

    assert checks["isolated_import_boundary"] is True
    assert checks["retained_local_inventory_metadata"] is True
    assert "no_local_work_overwritten" not in checks
    assert receipt["historical_payload_preservation"] == (
        "not_independently_verified"
    )


def test_placeholder_count_comes_from_inventory_metadata(
    tmp_path: Path,
) -> None:
    paths = _copy_inputs(tmp_path)
    inventory = _read(paths[0])
    assets = cast("list[dict[str, object]]", inventory["assets"])
    placeholder = next(
        row
        for row in assets
        if row["scope"] == "local" and row["resident"] is False
    )
    placeholder["resident"] = None
    _write(paths[0], inventory)

    receipt = _verify(paths)

    assert receipt["local_inventory_metadata_count"] == 137
    assert receipt["placeholder_metadata_only_count"] == 131
    assert receipt["resident_byte_verified_count"] == 4


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("disposition", "", "Invalid disposition"),
        ("sha256", "0" * 63, "Invalid source digest"),
        ("upstream_commit", "0" * 40, "Source commit differs"),
    ],
)
def test_rejects_incomplete_source_identity(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    paths = _copy_inputs(tmp_path)
    inventory = _read(paths[0])
    assets = cast("list[dict[str, object]]", inventory["assets"])
    upstream = next(row for row in assets if row["scope"] == "upstream")
    upstream[field] = value
    _write(paths[0], inventory)
    with pytest.raises(ValueError, match=message):
        _verify(paths)


def test_rejects_duplicate_artifact_disposition(tmp_path: Path) -> None:
    paths = _copy_inputs(tmp_path)
    inventory = _read(paths[0])
    assets = cast("list[dict[str, object]]", inventory["assets"])
    assets.append(dict(assets[0]))
    _write(paths[0], inventory)
    with pytest.raises(ValueError, match="Duplicate inventory path"):
        _verify(paths)


def test_rejects_coordinated_inventory_and_vendor_tamper(
    tmp_path: Path,
) -> None:
    paths = _copy_inputs(tmp_path)
    inventory = _read(paths[0])
    assets = cast("list[dict[str, object]]", inventory["assets"])
    upstream = next(row for row in assets if row["scope"] == "upstream")
    relative = Path(cast("str", upstream["path"])).relative_to(
        "vendor/nzmedicines"
    )
    target = paths[2] / relative
    target.write_bytes(target.read_bytes() + b"tamper")
    upstream["size_bytes"] = target.stat().st_size
    upstream["sha256"] = VERIFY._sha256(target)
    _write(paths[0], inventory)
    with pytest.raises(ValueError, match="Preservation aggregate differs"):
        _verify(paths)


def test_rejects_vendor_membership_drift(tmp_path: Path) -> None:
    paths = _copy_inputs(tmp_path)
    (paths[2] / "unexpected.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError, match="tree membership differs"):
        _verify(paths)


def test_rejects_local_work_inside_vendor(tmp_path: Path) -> None:
    paths = _copy_inputs(tmp_path)
    inventory = _read(paths[0])
    assets = cast("list[dict[str, object]]", inventory["assets"])
    local = next(row for row in assets if row["scope"] == "local")
    local["path"] = "vendor/local-work.py"
    _write(paths[0], inventory)
    with pytest.raises(ValueError, match="Local work is recorded inside"):
        _verify(paths)


def test_receipt_is_deterministic_and_build_only(tmp_path: Path) -> None:
    receipt = VERIFY.verify_consolidation()
    first = PROJECT_ROOT / "build/test-receipts/nz-first.json"
    second = PROJECT_ROOT / "build/test-receipts/nz-second.json"
    VERIFY.write_receipt(receipt, first)
    VERIFY.write_receipt(receipt, second)
    try:
        assert first.read_bytes() == second.read_bytes()
    finally:
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)
    with pytest.raises(ValueError, match="beneath build"):
        VERIFY.write_receipt(receipt, tmp_path / "receipt.json")


def test_cli_emits_build_receipt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = PROJECT_ROOT / "build/test-receipts/nz-cli.json"
    output.unlink(missing_ok=True)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT), "--output", str(output)],
    )
    try:
        assert VERIFY.main() == 0
        assert json.loads(capsys.readouterr().out)["status"] == "passed"
        assert json.loads(output.read_text(encoding="utf-8"))["status"] == (
            "passed"
        )
    finally:
        output.unlink(missing_ok=True)
