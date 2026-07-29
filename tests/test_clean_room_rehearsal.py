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
    subject_names = (
        "global_medicines_atlas-0.7.0-py3-none-any.whl",
        "sbom.cdx.json",
        "uv.lock",
    )
    payloads["provenance.intoto.json"] = _canonical({
        "_type": "https://in-toto.io/Statement/v1",
        "predicate": {
            "builder": {"id": "https://github.com/edithatogo/gma/builder"}
        },
        "predicateType": "https://slsa.dev/provenance/v1",
        "subject": [
            {"digest": {"sha256": _sha(payloads[name])}, "name": name}
            for name in subject_names
        ],
    })
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
        "provenance.intoto.json": "provenance-attestation",
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
        "trusted_builder_id": "https://github.com/edithatogo/gma/builder",
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


def _rebind_attestation(source: Path) -> None:
    attestation: dict[str, object] = json.loads(
        (source / "provenance.intoto.json").read_text(encoding="utf-8")
    )
    attestation["subject"] = [
        {"digest": {"sha256": _sha((source / name).read_bytes())}, "name": name}
        for name in (
            "global_medicines_atlas-0.7.0-py3-none-any.whl",
            "sbom.cdx.json",
            "uv.lock",
        )
    ]
    (source / "provenance.intoto.json").write_bytes(_canonical(attestation))


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
    assert len(first.artifacts) == 7


@pytest.mark.parametrize(
    ("target", "replacement", "message"),
    [
        (
            "global_medicines_atlas-0.7.0-py3-none-any.whl",
            b"tampered",
            "declared identity mismatch",
        ),
        ("provenance.intoto.json", b"{}", "declared identity mismatch"),
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
    ("mutation", "message"),
    [
        ("type", "in-toto"),
        ("predicate-type", "SLSA"),
        ("predicate", "predicate must"),
        ("subjects", "subjects must"),
    ],
)
def test_rehearsal_rejects_malformed_attestation(
    tmp_path: Path, mutation: str, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    attestation: dict[str, object] = json.loads(
        (source / "provenance.intoto.json").read_text(encoding="utf-8")
    )
    if mutation == "type":
        attestation["_type"] = "arbitrary"
    elif mutation == "predicate-type":
        attestation["predicateType"] = "arbitrary"
    elif mutation == "predicate":
        attestation["predicate"] = "arbitrary"
    else:
        attestation["subject"] = "arbitrary"
    (source / "provenance.intoto.json").write_bytes(_canonical(attestation))
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


@pytest.mark.parametrize(
    ("subject", "message"),
    [
        ("invalid", "subject must"),
        ({"name": 1, "digest": {}}, "subject is malformed"),
        ({"name": "uv.lock", "digest": {}}, "subject digest"),
    ],
)
def test_rehearsal_rejects_malformed_attestation_subject(
    tmp_path: Path, subject: object, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    attestation: dict[str, object] = json.loads(
        (source / "provenance.intoto.json").read_text(encoding="utf-8")
    )
    attestation["subject"] = [subject]
    (source / "provenance.intoto.json").write_bytes(_canonical(attestation))
    _rebind_governed_controls(source, declaration)
    with pytest.raises(RehearsalError, match=message):
        rehearse_publication(
            source_root=source,
            declaration_path=declaration,
            receipt_path=tmp_path / "receipt.json",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("builder", "builder identity"),
        ("subject", "subjects do not match"),
    ],
)
def test_rehearsal_rejects_rebound_untrusted_attestation(
    tmp_path: Path, mutation: str, message: str
) -> None:
    source = tmp_path / "source"
    declaration = _fixture(source)
    attestation: dict[str, object] = json.loads(
        (source / "provenance.intoto.json").read_text(encoding="utf-8")
    )
    if mutation == "builder":
        predicate = cast("dict[str, object]", attestation["predicate"])
        predicate["builder"] = {"id": "https://attacker.invalid/builder"}
    else:
        subjects = cast("list[dict[str, object]]", attestation["subject"])
        subjects[0]["digest"] = {"sha256": "0" * 64}
    (source / "provenance.intoto.json").write_bytes(_canonical(attestation))
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
    st.binary(min_size=0, max_size=64).filter(lambda value: value != _wheel())
)
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
