"""Exact-source and exclusion boundaries for the recovered NZULM archive."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import IO, Literal
from zipfile import ZipFile, ZipInfo

import pytest
from scripts import publish_nzulm_2023 as publisher


def source_contract(
    tmp_path: Path, *, member: str = "core.csv"
) -> tuple[Path, Path, dict[str, object]]:
    """Make a small synthetic archive with an explicitly excluded member."""
    source = tmp_path / "source.zip"
    payload = b"id,label\n1,synthetic\n"
    with ZipFile(source, "w") as bundle:
        bundle.writestr(member, payload)
        bundle.writestr("excluded.csv", b"synthetic excluded material")
    contract = tmp_path / "contract"
    contract.mkdir()
    manifest: dict[str, object] = {
        "publication_approved": True,
        "repository": "owner/synthetic",
        "source_archive": {
            "size_bytes": source.stat().st_size,
            "sha256": publisher.digest(source),
            "member_count": 2,
        },
        "files": [
            {
                "member": member,
                "path": f"data/{member}",
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ],
        "excluded_members": [{"member": "excluded.csv"}],
    }
    (contract / "manifest.json").write_text(json.dumps(manifest))
    (contract / "README.md").write_text("Synthetic terms.\n")
    (contract / "rights.json").write_text('{"synthetic": true}\n')
    return source, contract, manifest


def test_only_approved_member_is_opened_and_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, contract, _ = source_contract(tmp_path)
    opened: list[str] = []
    original = ZipFile.open

    def tracked_open(
        self: ZipFile,
        name: str | ZipInfo,
        mode: Literal["r", "w"] = "r",
        pwd: bytes | None = None,
        *,
        force_zip64: bool = False,
    ) -> IO[bytes]:
        opened.append(name if isinstance(name, str) else name.filename)
        return original(self, name, mode, pwd, force_zip64=force_zip64)

    monkeypatch.setattr(ZipFile, "open", tracked_open)
    output = tmp_path / "package"
    plan = publisher.prepare_snapshot(source, output, contract=contract)
    assert opened == ["core.csv"]
    assert not (output / "data/excluded.csv").exists()
    assert {a.relative_path for a in plan.artifacts} == {
        "data/core.csv",
        "README.md",
        "rights.json",
        "manifest.json",
    }
    assert (output / "data/core.csv").read_bytes() == (
        b"id,label\n1,synthetic\n"
    )


def test_zero_filled_placeholder_is_rejected_before_output(
    tmp_path: Path,
) -> None:
    source, contract, _ = source_contract(tmp_path)
    source.write_bytes(b"\0" * source.stat().st_size)
    output = tmp_path / "package"
    with pytest.raises(ValueError, match="approved archive"):
        publisher.prepare_snapshot(source, output, contract=contract)
    assert not output.exists()


def test_path_traversal_cannot_escape_package(tmp_path: Path) -> None:
    source, contract, _ = source_contract(tmp_path, member="../escape.csv")
    with pytest.raises(ValueError, match="relative POSIX"):
        publisher.prepare_snapshot(
            source, tmp_path / "package", contract=contract
        )
    assert not (tmp_path / "escape.csv").exists()


def test_changed_member_binding_is_rejected(tmp_path: Path) -> None:
    source, contract, manifest = source_contract(tmp_path)
    manifest["files"] = [
        {
            "member": "core.csv",
            "path": "data/core.csv",
            "size_bytes": 21,
            "sha256": "0" * 64,
        }
    ]
    (contract / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(
        ValueError, match=r"changed approved member|digest differs"
    ):
        publisher.prepare_snapshot(
            source, tmp_path / "package", contract=contract
        )


def test_missing_exclusion_does_not_admit_unknown_member(
    tmp_path: Path,
) -> None:
    source, contract, manifest = source_contract(tmp_path)
    manifest["excluded_members"] = []
    (contract / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="inventory differs"):
        publisher.prepare_snapshot(
            source, tmp_path / "package", contract=contract
        )


def test_approval_is_not_inferred_from_source_possession(
    tmp_path: Path,
) -> None:
    source, contract, manifest = source_contract(tmp_path)
    manifest["publication_approved"] = False
    (contract / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved archive"):
        publisher.prepare_snapshot(
            source, tmp_path / "package", contract=contract
        )


def test_local_publication_stops_before_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="Actions dispatch on main"):
        publisher.publish_snapshot(
            tmp_path / "missing", tmp_path / "out", "a" * 40
        )
    assert not (tmp_path / "out").exists()
