from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from global_medicines_atlas.clean_room_rehearsal import (
    CleanRoomReceipt,
    RehearsalError,
)
from global_medicines_atlas.clean_room_rehearsal import (
    rehearse_publication as _rehearse_publication,
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


def _wheel(
    *, project: str = "global-medicines-atlas", version: str = "0.7.0"
) -> bytes:
    stream = BytesIO()
    distribution = project.replace("-", "_")
    with zipfile.ZipFile(stream, mode="w") as archive:
        metadata = (
            "Metadata-Version: 2.4\n"
            f"Name: {project}\n"
            f"Version: {version}\n"
            "Requires-Dist: pydantic>=2\n\n"
        )
        info = zipfile.ZipInfo(f"{distribution}-{version}.dist-info/METADATA")
        info.date_time = (1980, 1, 1, 0, 0, 0)
        archive.writestr(info, metadata)
    return stream.getvalue()


def _fixture(root: Path) -> Path:
    root.mkdir()
    payloads = {
        "global_medicines_atlas-0.7.0-py3-none-any.whl": _wheel(),
        "uv.lock": (
            b'version = 1\n\n[[package]]\nname = "global-medicines-atlas"\n'
            b'version = "0.7.0"\ndependencies = [{ name = "pydantic" }]\n\n'
            b'[[package]]\nname = "pydantic"\nversion = "2.12.5"\n'
            b"dependencies = []\n"
        ),
        "sbom.cdx.json": _canonical({
            "bomFormat": "CycloneDX",
            "components": [{"name": "pydantic", "version": "2.12.5"}],
            "metadata": {
                "component": {
                    "name": "global-medicines-atlas",
                    "version": "0.7.0",
                }
            },
            "specVersion": "1.6",
        }),
    }
    payloads["provenance.bundle.json"] = _canonical({"mode": "valid"})
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
        "global_medicines_atlas-0.7.0-py3-none-any.whl": "package",
        "provenance.bundle.json": "provenance-bundle",
        "qualified-assets.json": "asset-manifest",
        "qualification.json": "qualification",
        "sbom.cdx.json": "sbom",
        "SHA256SUMS": "checksums",
        "uv.lock": "runtime-lock",
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
        "expected_project": "global-medicines-atlas",
        "expected_version": "0.7.0",
        "schema_version": "2",
    }
    declaration_path = root.parent / "declaration.json"
    declaration_path.write_bytes(_canonical(declaration))
    sigstore_fixture = b'{"mediaType":"application/vnd.dev.sigstore.trustedroot+json;version=0.1"}\n'
    (root.parent / "trusted-root.jsonl").write_bytes(sigstore_fixture)
    (root.parent / "trust-policy.json").write_bytes(
        _canonical({
            "certificate_identity": "https://github.com/edithatogo/gma/.github/workflows/release.yml@refs/heads/main",
            "oidc_issuer": "https://token.actions.githubusercontent.com",
            "predicate_type": "https://slsa.dev/provenance/v1",
            "repository": "edithatogo/global-medicines-atlas",
            "schema_version": "1",
            "signer_workflow": "github.com/edithatogo/gma/.github/workflows/release.yml",
            "trusted_root_path": "trusted-root.jsonl",
            "trusted_root_sha256": _sha(sigstore_fixture),
        })
    )
    fake = root.parent / "fake_gh.py"
    fake.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, pathlib, sys
args = sys.argv[1:]
with pathlib.Path(__file__).with_name("verifier-commands.jsonl").open("a") as log:
    log.write(json.dumps(args) + "\\n")
artifact = pathlib.Path(args[2])
bundle = pathlib.Path(args[args.index("--bundle") + 1])
mode = json.loads(bundle.read_text())["mode"]
if mode == "fail":
    raise SystemExit(1)
if mode == "invalid-json":
    print("not-json")
    raise SystemExit(0)
if mode == "not-list":
    print("{}")
    raise SystemExit(0)
if mode == "missing-result":
    print("[{}]")
    raise SystemExit(0)
digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
certificate = {
    "sourceRepository": "edithatogo/global-medicines-atlas",
    "subjectAlternativeName": "https://github.com/edithatogo/gma/.github/workflows/release.yml@refs/heads/main",
    "issuer": "https://token.actions.githubusercontent.com",
    "signerWorkflow": "github.com/edithatogo/gma/.github/workflows/release.yml",
}
if mode == "wrong-identity":
    certificate["sourceRepository"] = "attacker/repo"
if mode == "wrong-workflow":
    certificate["signerWorkflow"] = "github.com/attacker/repo/.github/workflows/a.yml"
if mode == "wrong-san":
    certificate["subjectAlternativeName"] = "https://attacker.invalid"
if mode == "wrong-issuer":
    certificate["issuer"] = "https://attacker.invalid"
subject_digest = "0" * 64 if mode == "wrong-subject" else digest
predicate_type = "https://attacker.invalid/predicate" if mode == "wrong-predicate" else "https://slsa.dev/provenance/v1"
result = [{
    "verificationResult": {
        "signature": {"certificate": certificate},
        "verifiedTimestamps": [] if mode == "no-timestamps" else [{"type": "tlog"}],
        "statement": {
            "predicateType": predicate_type,
            "subject": [{"name": artifact.name, "digest": {"sha256": subject_digest}}],
        },
    }
}]
print(json.dumps([] if mode == "unsigned" else result))
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    (root.parent / "fake-gh.cmd").write_text(
        f'@"{sys.executable}" "{fake}" %*\n', encoding="utf-8"
    )
    return declaration_path


def rehearse_publication(
    *,
    source_root: Path,
    declaration_path: Path,
    receipt_path: Path,
) -> CleanRoomReceipt:
    return _rehearse_publication(
        source_root=source_root,
        declaration_path=declaration_path,
        trust_policy_path=source_root.parent / "trust-policy.json",
        receipt_path=receipt_path,
        verifier_command=(
            sys.executable,
            str(source_root.parent / "fake_gh.py"),
        ),
    )


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


def _bind_raw_manifest(
    source: Path, declaration: Path, manifest: dict[str, object]
) -> None:
    manifest_payload = _canonical(manifest)
    (source / "qualified-assets.json").write_bytes(manifest_payload)
    qualification: dict[str, object] = json.loads(
        (source / "qualification.json").read_text(encoding="utf-8")
    )
    qualification["qualified_assets_sha256"] = _sha(manifest_payload)
    (source / "qualification.json").write_bytes(_canonical(qualification))
    _refresh_checksums_and_declaration(source, declaration)


def _rebind_attestation(source: Path) -> None:
    assert (source / "provenance.bundle.json").is_file()


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
    assert first.python_network_denied is False
    assert first.child_process_network_isolation == "unverified"
    assert (
        first.provenance_verification_mode
        == "local-bundle-and-digest-pinned-trusted-root"
    )
    assert first.published is False
    assert len(first.artifacts) == 7
    commands = [
        json.loads(line)
        for line in (tmp_path / "verifier-commands.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(commands) == 6
    for command in commands:
        assert command[:2] == ["attestation", "verify"]
        assert command[3] == "--bundle"
        assert Path(command[4]).name == "provenance.bundle.json"
        assert command[command.index("--repo") + 1] == (
            "edithatogo/global-medicines-atlas"
        )
        assert command[command.index("--signer-workflow") + 1] == (
            "github.com/edithatogo/gma/.github/workflows/release.yml"
        )
        trusted_root_arg = command[command.index("--custom-trusted-root") + 1]
        assert Path(trusted_root_arg) == tmp_path / "trusted-root.jsonl"
        assert command[-1] == "--format=json"


@pytest.mark.parametrize(
    ("target", "replacement", "message"),
    [
        (
            "global_medicines_atlas-0.7.0-py3-none-any.whl",
            b"tampered",
            "declared identity mismatch",
        ),
        ("provenance.bundle.json", b"{}", "declared identity mismatch"),
        ("uv.lock", b"", "declared identity mismatch"),
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
    cast(
        "list[tuple[dict[str, object], str]]",
        [
            (
                {"bomFormat": "SPDX", "components": [], "specVersion": "1.6"},
                "CycloneDX",
            ),
            (
                {
                    "bomFormat": "CycloneDX",
                    "components": [],
                    "metadata": {
                        "component": {
                            "name": "global-medicines-atlas",
                            "version": "0.7.0",
                        }
                    },
                    "specVersion": "1.6",
                },
                "components",
            ),
            (
                {
                    "bomFormat": "CycloneDX",
                    "components": ["invalid"],
                    "metadata": {
                        "component": {
                            "name": "global-medicines-atlas",
                            "version": "0.7.0",
                        }
                    },
                    "specVersion": "1.6",
                },
                "component must",
            ),
            (
                {
                    "bomFormat": "CycloneDX",
                    "components": [{"name": "package"}],
                    "metadata": {
                        "component": {
                            "name": "global-medicines-atlas",
                            "version": "0.7.0",
                        }
                    },
                    "specVersion": "1.6",
                },
                "name and version",
            ),
        ],
    ),
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
        (
            f"{'0' * 64}  global_medicines_atlas-0.7.0-py3-none-any.whl\n",
            "bind every",
        ),
        (
            (
                f"{'0' * 64}  global_medicines_atlas-0.7.0-py3-none-any.whl\n"
                f"{'0' * 64}  global_medicines_atlas-0.7.0-py3-none-any.whl\n"
            ),
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
    target = source / "package-real.whl"
    original = source / "global_medicines_atlas-0.7.0-py3-none-any.whl"
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


@pytest.mark.parametrize(
    ("files", "message"),
    [
        (["invalid"], "entry must be an object"),
        ([{"path": 1, "sha256": "0" * 64, "size": 0}], "invalid fields"),
        (
            [
                {"path": "uv.lock", "sha256": "0" * 64, "size": 0},
                {"path": "uv.lock", "sha256": "0" * 64, "size": 0},
            ],
            "duplicate asset manifest",
        ),
    ],
)
def test_rehearsal_rejects_malformed_asset_entries(
    tmp_path: Path, files: list[object], message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    _bind_raw_manifest(source, declaration, {"files": files})
    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_manifest_identity_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    manifest: dict[str, object] = json.loads(
        (source / "qualified-assets.json").read_text(encoding="utf-8")
    )
    entries = cast("list[dict[str, object]]", manifest["files"])
    entries[0]["sha256"] = "0" * 64
    _bind_raw_manifest(source, declaration, manifest)
    with pytest.raises(RehearsalError, match="identity mismatch"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_complete_but_wrong_checksum(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    lines: list[str] = []
    for path in sorted(source.iterdir()):
        if path.name == "SHA256SUMS":
            continue
        digest = "0" * 64 if path.name == "uv.lock" else _sha(path.read_bytes())
        lines.append(f"{digest}  {path.name}\n")
    (source / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")
    _refresh_declaration(source, declaration)
    with pytest.raises(RehearsalError, match="checksum mismatch"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_arbitrary_but_well_formed_sbom(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    sbom = {
        "bomFormat": "CycloneDX",
        "components": [{"name": "arbitrary", "version": "999"}],
        "metadata": {
            "component": {
                "name": "global-medicines-atlas",
                "version": "0.7.0",
            }
        },
        "specVersion": "1.6",
    }
    (source / "sbom.cdx.json").write_bytes(_canonical(sbom))
    _rebind_attestation(source)
    _rebind_governed_controls(source, declaration)
    with pytest.raises(RehearsalError, match="exact runtime lock closure"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_self_consistent_replacement_package(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    (source / "global_medicines_atlas-0.7.0-py3-none-any.whl").write_bytes(
        _wheel(project="replacement-project")
    )
    _rebind_attestation(source)
    _rebind_governed_controls(source, declaration)
    with pytest.raises(RehearsalError, match="disagrees with declaration"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_rejects_self_consistent_non_wheel_package(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    (source / "global_medicines_atlas-0.7.0-py3-none-any.whl").write_bytes(
        b"not-a-wheel"
    )
    _rebind_attestation(source)
    _rebind_governed_controls(source, declaration)
    with pytest.raises(RehearsalError, match="readable wheel"):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


@pytest.mark.parametrize(
    ("lock", "message"),
    [
        (b"[", "valid TOML"),
        (b"version = 1\n", "package records"),
        (
            b"".join((
                b'[[package]]\nname="global-medicines-atlas"\nversion="0.7.0"\n',
                b"dependencies=[]\n",
            )),
            "wheel requirements disagree",
        ),
        (
            b"".join((
                b'[[package]]\nname="global-medicines-atlas"\nversion="0.7.0"\n',
                b'dependencies=[{name="pydantic"}]\n',
            )),
            "not locked",
        ),
        (
            b"".join((
                b'[[package]]\nname="global-medicines-atlas"\nversion="0.7.0"\n',
                b'dependencies=[{name="pydantic"}]\n',
                b'[[package]]\nname="pydantic"\nversion="2"\ndependencies=[]\n',
                b'[[package]]\nname="pydantic"\nversion="3"\ndependencies=[]\n',
            )),
            "unique",
        ),
        (
            b'[[package]]\nname="other"\nversion="1"\ndependencies=[]\n',
            "lacks the expected project",
        ),
    ],
)
def test_rehearsal_rejects_invalid_runtime_lock(
    tmp_path: Path, lock: bytes, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    (source / "uv.lock").write_bytes(lock)
    _rebind_attestation(source)
    _rebind_governed_controls(source, declaration)
    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("fail", "verification failed"),
        ("unsigned", "no verified attestations"),
        ("wrong-identity", "violates trust policy"),
        ("wrong-workflow", "violates trust policy"),
        ("wrong-san", "violates trust policy"),
        ("wrong-issuer", "violates trust policy"),
        ("wrong-predicate", "predicate type"),
        ("no-timestamps", "transparency timestamps"),
        ("wrong-subject", "do not match exact governed bytes"),
        ("invalid-json", "not valid JSON"),
        ("not-list", "no verified attestations"),
        ("missing-result", "lacks verificationResult"),
    ],
)
def test_rehearsal_rejects_unverified_provenance_bundle(
    tmp_path: Path, mode: str, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    (source / "provenance.bundle.json").write_bytes(_canonical({"mode": mode}))
    _rebind_governed_controls(source, declaration)
    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


def test_rehearsal_fails_closed_when_gh_is_missing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    with pytest.raises(RehearsalError, match="verifier is unavailable"):
        _rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            trust_policy_path=tmp_path / "trust-policy.json",
            receipt_path=tmp_path / "receipt.json",
            verifier_command=("definitely-missing-gh-executable",),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "trusted root is missing"),
        ("tampered", "digest does not match"),
        ("escape", "unsafe relative path"),
    ],
)
def test_rehearsal_rejects_invalid_trusted_root(
    tmp_path: Path, mutation: str, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    trusted_root = tmp_path / "trusted-root.jsonl"
    if mutation == "missing":
        trusted_root.unlink()
    elif mutation == "tampered":
        trusted_root.write_bytes(b"tampered")
    else:
        policy: dict[str, object] = json.loads(
            (tmp_path / "trust-policy.json").read_text(encoding="utf-8")
        )
        policy["trusted_root_path"] = "../outside-trusted-root.jsonl"
        (tmp_path / "trust-policy.json").write_bytes(_canonical(policy))
    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


@pytest.mark.parametrize(
    ("sbom", "message"),
    cast(
        "list[tuple[dict[str, object], str]]",
        [
            ({"bomFormat": "CycloneDX", "components": [{}]}, "specVersion"),
            (
                {
                    "bomFormat": "CycloneDX",
                    "components": [{}],
                    "specVersion": "1.6",
                },
                "project metadata",
            ),
            (
                {
                    "bomFormat": "CycloneDX",
                    "components": [{}],
                    "metadata": {},
                    "specVersion": "1.6",
                },
                "project component",
            ),
            (
                {
                    "bomFormat": "CycloneDX",
                    "components": [{"name": "pydantic", "version": "2.12.5"}],
                    "metadata": {
                        "component": {"name": "other", "version": "0.7.0"}
                    },
                    "specVersion": "1.6",
                },
                "identity disagrees",
            ),
            (
                {
                    "bomFormat": "CycloneDX",
                    "components": [
                        {"name": "pydantic", "version": "2.12.5"},
                        {"name": "pydantic", "version": "2.12.5"},
                    ],
                    "metadata": {
                        "component": {
                            "name": "global-medicines-atlas",
                            "version": "0.7.0",
                        }
                    },
                    "specVersion": "1.6",
                },
                "unique",
            ),
        ],
    ),
)
def test_rehearsal_rejects_additional_sbom_failures(
    tmp_path: Path, sbom: dict[str, object], message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    (source / "sbom.cdx.json").write_bytes(_canonical(sbom))
    _rebind_attestation(source)
    _rebind_governed_controls(source, declaration)
    with pytest.raises(RehearsalError, match=message):
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
    verifier = (
        tmp_path / "fake-gh.cmd"
        if sys.platform == "win32"
        else tmp_path / "fake_gh.py"
    )

    result = __import__("subprocess").run(
        [
            sys.executable,
            str(ROOT / "scripts" / "rehearse_publication_package.py"),
            "--source-root",
            str(source),
            "--declaration",
            str(declaration),
            "--trust-policy",
            str(tmp_path / "trust-policy.json"),
            "--verifier",
            str(verifier),
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
    output = json.loads(result.stdout)
    assert output["python_network_denied"] is True
    assert output["child_process_network_isolation"] == "unverified"
    assert {path.name: path.read_bytes() for path in source.iterdir()} == before
    assert receipt.is_file()


@given(
    st.binary(min_size=0, max_size=64).filter(lambda value: value != _wheel())
)
@settings(deadline=None)
def test_any_package_byte_change_is_rejected(replacement: bytes) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        declaration = _fixture(source)
        (source / "global_medicines_atlas-0.7.0-py3-none-any.whl").write_bytes(
            replacement
        )
        with pytest.raises(RehearsalError, match="declared identity mismatch"):
            rehearse_publication(
                source_root=source,
                declaration_path=declaration,
                receipt_path=root / "receipt.json",
            )
