from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from global_medicines_atlas.clean_room_rehearsal import (
    RehearsalError,
    rehearse_publication,
)

ROOT = Path(__file__).resolve().parents[1]


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        + "\n"
    ).encode()


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _fixture(root: Path) -> Path:
    root.mkdir()
    payloads = {
        "dataset.tar.gz": b"governed-package",
        "sbom.cdx.json": _canonical({
            "bomFormat": "CycloneDX",
            "components": [
                {"name": "global-medicines-atlas", "version": "0.7.0"}
            ],
            "specVersion": "1.6",
        }),
    }
    manifest = _canonical({
        "files": [
            {"path": path, "sha256": _sha(payload), "size": len(payload)}
            for path, payload in sorted(payloads.items())
        ]
    })
    payloads["qualified-assets.json"] = manifest
    payloads["qualification.json"] = _canonical({
        "dry_run_validated": True,
        "published": False,
        "qualified_assets_sha256": _sha(manifest),
    })
    payloads["SHA256SUMS"] = "".join(
        f"{_sha(payload)}  {path}\n"
        for path, payload in sorted(payloads.items())
    ).encode()
    roles = {
        "dataset.tar.gz": "package",
        "qualified-assets.json": "asset-manifest",
        "qualification.json": "qualification",
        "sbom.cdx.json": "sbom",
        "SHA256SUMS": "checksums",
    }
    for path, payload in payloads.items():
        (root / path).write_bytes(payload)
    declaration = {
        "artifacts": [
            {
                "path": path,
                "role": roles[path],
                "sha256": _sha(payload),
                "size": len(payload),
            }
            for path, payload in sorted(payloads.items())
        ],
        "schema_version": "1",
    }
    declaration_path = root.parent / "declaration.json"
    declaration_path.write_bytes(_canonical(declaration))
    return declaration_path


def _refresh_checksums_and_declaration(source: Path, declaration: Path) -> None:
    checksums = "".join(
        f"{_sha(path.read_bytes())}  {path.name}\n"
        for path in sorted(source.iterdir())
        if path.name != "SHA256SUMS"
    ).encode()
    (source / "SHA256SUMS").write_bytes(checksums)
    _refresh_declaration(source, declaration)


def _refresh_declaration(source: Path, declaration: Path) -> None:
    data = json.loads(declaration.read_text(encoding="utf-8"))
    for entry in data["artifacts"]:
        payload = (source / entry["path"]).read_bytes()
        entry["sha256"], entry["size"] = _sha(payload), len(payload)
    declaration.write_bytes(_canonical(data))


def _rebind_governed_controls(source: Path, declaration: Path) -> None:
    manifest: dict[str, object] = json.loads(
        (source / "qualified-assets.json").read_text(encoding="utf-8")
    )
    entries = manifest["files"]
    assert isinstance(entries, list)
    for item in cast("list[object]", entries):
        raw = cast("dict[str, object]", item)
        assert isinstance(raw, dict)
        path = raw.get("path")
        assert isinstance(path, str)
        payload = (source / path).read_bytes()
        raw["sha256"], raw["size"] = _sha(payload), len(payload)
    manifest_payload = _canonical(manifest)
    (source / "qualified-assets.json").write_bytes(manifest_payload)
    qualification: dict[str, object] = json.loads(
        (source / "qualification.json").read_text(encoding="utf-8")
    )
    qualification["qualified_assets_sha256"] = _sha(manifest_payload)
    (source / "qualification.json").write_bytes(_canonical(qualification))
    _refresh_checksums_and_declaration(source, declaration)


def test_rehearsal_emits_deterministic_durable_receipt(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    first_path = tmp_path / "receipts" / "first.json"
    second_path = tmp_path / "receipts" / "second.json"

    first = rehearse_publication(
        source_root=source,
        declaration_path=declaration,
        receipt_path=first_path,
    )
    second = rehearse_publication(
        source_root=source,
        declaration_path=declaration,
        receipt_path=second_path,
    )

    assert first == second
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first.verified is True
    assert first.network_accessed is False
    assert first.published is False
    assert len(first.artifacts) == 5


@pytest.mark.parametrize(
    ("target", "replacement", "message"),
    [
        ("dataset.tar.gz", b"tampered", "declared identity mismatch"),
        ("sbom.cdx.json", b"{}", "declared identity mismatch"),
        ("qualification.json", b"{}", "declared identity mismatch"),
        ("SHA256SUMS", b"", "declared identity mismatch"),
    ],
)
def test_rehearsal_rejects_tampering(
    tmp_path: Path, target: str, replacement: bytes, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    (source / target).write_bytes(replacement)

    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_hidden_manifest_dependency(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    manifest_path = source / "qualified-assets.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"].append({
        "path": "../hidden.bin",
        "sha256": "0" * 64,
        "size": 1,
    })
    changed = _canonical(manifest)
    manifest_path.write_bytes(changed)
    declaration_data = json.loads(declaration.read_text())
    entry = next(
        item
        for item in declaration_data["artifacts"]
        if item["path"] == "qualified-assets.json"
    )
    entry["sha256"], entry["size"] = _sha(changed), len(changed)
    declaration.write_bytes(_canonical(declaration_data))
    _refresh_checksums_and_declaration(source, declaration)

    with pytest.raises(RehearsalError, match="unsafe relative path"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_stale_qualification_binding(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    qualification = _canonical({
        "dry_run_validated": True,
        "qualified_assets_sha256": "0" * 64,
    })
    (source / "qualification.json").write_bytes(qualification)
    data = json.loads(declaration.read_text())
    entry = next(
        item
        for item in data["artifacts"]
        if item["path"] == "qualification.json"
    )
    entry["sha256"], entry["size"] = _sha(qualification), len(qualification)
    declaration.write_bytes(_canonical(data))
    _refresh_checksums_and_declaration(source, declaration)

    with pytest.raises(RehearsalError, match="not bound"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_receipt_inside_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    with pytest.raises(RehearsalError, match="outside"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=source / "receipt.json",
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"{", "not readable canonical JSON"),
        (_canonical([]), "must be a JSON object"),
    ],
)
def test_rehearsal_rejects_invalid_sbom_json(
    tmp_path: Path, payload: bytes, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    (source / "sbom.cdx.json").write_bytes(payload)
    _rebind_governed_controls(source, declaration)
    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


@pytest.mark.parametrize(
    ("sbom", "message"),
    [
        (
            {"bomFormat": "SPDX", "components": [], "specVersion": "1.6"},
            "CycloneDX",
        ),
        (
            {"bomFormat": "CycloneDX", "components": [], "specVersion": "1.6"},
            "components",
        ),
        (
            {
                "bomFormat": "CycloneDX",
                "components": ["invalid"],
                "specVersion": "1.6",
            },
            "component must",
        ),
        (
            {
                "bomFormat": "CycloneDX",
                "components": [{"name": "package"}],
                "specVersion": "1.6",
            },
            "name and version",
        ),
    ],
)
def test_rehearsal_rejects_semantically_invalid_sbom(
    tmp_path: Path, sbom: object, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    (source / "sbom.cdx.json").write_bytes(_canonical(sbom))
    _rebind_governed_controls(source, declaration)
    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


@pytest.mark.parametrize(
    ("receipt", "message"),
    [
        ({"qualified_assets_sha256": "0" * 64}, "not successful"),
        (
            {
                "published": True,
                "qualified": True,
                "qualified_assets_sha256": "placeholder",
            },
            "not bound",
        ),
    ],
)
def test_rehearsal_rejects_invalid_qualification_state(
    tmp_path: Path, receipt: dict[str, object], message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    if receipt.get("qualified") is True:
        receipt["qualified_assets_sha256"] = _sha(
            (source / "qualified-assets.json").read_bytes()
        )
        message = "rejects publication"
    (source / "qualification.json").write_bytes(_canonical(receipt))
    _refresh_checksums_and_declaration(source, declaration)
    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("not-a-checksum\n", "invalid entry"),
        (f"{'0' * 64}  dataset.tar.gz\n", "bind every"),
        (
            f"{'0' * 64}  dataset.tar.gz\n{'0' * 64}  dataset.tar.gz\n",
            "duplicate checksum",
        ),
    ],
)
def test_rehearsal_rejects_invalid_checksum_control(
    tmp_path: Path, content: str, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    (source / "SHA256SUMS").write_text(content, encoding="utf-8")
    _refresh_declaration(source, declaration)
    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_missing_and_duplicate_declarations(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    data = json.loads(declaration.read_text(encoding="utf-8"))
    data["artifacts"][0]["role"] = data["artifacts"][1]["role"]
    declaration.write_bytes(_canonical(data))
    with pytest.raises(RehearsalError, match="duplicate artifact role"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate-path", "duplicate declared path"),
        ("absolute-path", "unsafe relative path"),
        ("missing-file", "declared artifact is missing"),
    ],
)
def test_rehearsal_rejects_invalid_declared_boundaries(
    tmp_path: Path, mutation: str, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    data: dict[str, object] = json.loads(
        declaration.read_text(encoding="utf-8")
    )
    artifacts = cast("list[dict[str, object]]", data["artifacts"])
    if mutation == "duplicate-path":
        artifacts[1]["path"] = artifacts[0]["path"]
    elif mutation == "absolute-path":
        artifacts[0]["path"] = "C:/outside.bin"
    else:
        artifacts[0]["path"] = "missing.bin"
    declaration.write_bytes(_canonical(data))
    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_symlink_input(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    target = source / "dataset-real.tar.gz"
    original = source / "dataset.tar.gz"
    original.replace(target)
    try:
        original.symlink_to(target)
    except OSError:
        pytest.skip(
            "symlinks are unavailable without Windows developer privileges"
        )
    with pytest.raises(RehearsalError, match="symbolic links"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_undeclared_manifest_payload(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    manifest: dict[str, object] = {"files": []}
    (source / "qualified-assets.json").write_bytes(_canonical(manifest))
    _refresh_checksums_and_declaration(source, declaration)
    with pytest.raises(RehearsalError, match="exact governed payloads"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_malformed_asset_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    manifest_payload = _canonical({"files": "not-a-list"})
    (source / "qualified-assets.json").write_bytes(manifest_payload)
    qualification: dict[str, object] = {
        "dry_run_validated": True,
        "qualified_assets_sha256": _sha(manifest_payload),
    }
    (source / "qualification.json").write_bytes(_canonical(qualification))
    _refresh_checksums_and_declaration(source, declaration)
    with pytest.raises(RehearsalError, match="files must be a list"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_cli_runs_offline_and_does_not_mutate_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    receipt = tmp_path / "receipt.json"

    result = __import__("subprocess").run(
        [
            sys.executable,
            str(ROOT / "scripts" / "rehearse_publication_package.py"),
            "--source-root",
            str(source),
            "--declaration",
            str(declaration),
            "--receipt",
            str(receipt),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["network_accessed"] is False
    assert {path.name: path.read_bytes() for path in source.iterdir()} == before
    assert receipt.is_file()


@given(
    st.binary(min_size=0, max_size=64).filter(
        lambda value: value != b"governed-package"
    )
)
def test_any_package_byte_change_is_rejected(replacement: bytes) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        declaration = _fixture(source)
        (source / "dataset.tar.gz").write_bytes(replacement)
        with pytest.raises(RehearsalError, match="declared identity mismatch"):
            rehearse_publication(
                source_root=source,
                declaration_path=declaration,
                receipt_path=root / "receipt.json",
            )
