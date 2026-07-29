from __future__ import annotations

import hashlib
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tarfile
import zipfile
from pathlib import Path

import pytest
from scripts.qualify_release import (
    QualificationError,
    qualify_release_assets,
)

VERSION = "0.7.0"
TAG = f"v{VERSION}"


def _run(root: Path, *arguments: str) -> str:
    executable = shutil.which("git")
    assert executable is not None
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [executable, "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        shell=False,
        text=True,
    )
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        """
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"
[project]
name = "global-medicines-atlas"
dynamic = ["version"]
license = "Apache-2.0"
[tool.hatch.version]
source = "vcs"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{VERSION}] - 2026-07-29\n",
        encoding="utf-8",
    )
    (root / "CITATION.cff").write_text(
        "\n".join((
            "cff-version: 1.2.0",
            f'version: "{VERSION}"',
            'date-released: "2026-07-29"',
            'license: "Apache-2.0"',
        ))
        + "\n",
        encoding="utf-8",
    )
    (root / "NOTICE").write_text(
        "Test fixture with an explicit licence decision.\n",
        encoding="utf-8",
    )
    _run(root, "init")
    _run(root, "config", "user.email", "test@example.test")
    _run(root, "config", "user.name", "Test")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "fixture")
    _run(root, "tag", TAG)
    return root, _run(root, "rev-parse", "HEAD")


def _stage(root: Path) -> Path:
    stage = root / "build" / "release-stage"
    dataset = root / "build" / "dataset-input"
    data = dataset / "data"
    metadata = dataset / "metadata"
    data.mkdir(parents=True)
    metadata.mkdir()
    parquet = data / "medicines.parquet"
    parquet.write_bytes(b"PAR1fixture")
    card = metadata / "dataset-card.json"
    card.write_text('{"title":"fixture"}\n', encoding="utf-8")
    files = [
        {
            "path": "data/medicines.parquet",
            "sha256": _sha256(parquet),
            "size": parquet.stat().st_size,
        },
        {
            "path": "metadata/dataset-card.json",
            "sha256": _sha256(card),
            "size": card.stat().st_size,
        },
    ]
    (dataset / "package-manifest.json").write_text(
        json.dumps({"files": files}), encoding="utf-8"
    )
    (dataset / "SHA256SUMS").write_bytes(
        "".join(
            f"{item['sha256']}  {item['path']}\n" for item in files
        ).encode()
    )
    stage.mkdir(parents=True, exist_ok=True)
    dataset_archive = stage / (
        f"global-medicines-atlas-dataset-{VERSION}.tar.gz"
    )
    with tarfile.open(dataset_archive, "w:gz") as archive:
        for item in sorted(dataset.rglob("*")):
            if item.is_file():
                archive.add(item, arcname=item.relative_to(dataset).as_posix())
    wheel = stage / f"global_medicines_atlas-{VERSION}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"global_medicines_atlas-{VERSION}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: global-medicines-atlas\nVersion: {VERSION}\n",
        )
    (stage / "uv.lock").write_text(
        'version = 1\n\n[[package]]\nname = "dep"\nversion = "1.2.3"\n',
        encoding="utf-8",
    )
    (stage / "sbom.cdx.json").write_text(
        json.dumps({
            "bomFormat": "CycloneDX",
            "metadata": {
                "component": {
                    "name": "global-medicines-atlas",
                    "version": VERSION,
                }
            },
            "components": [{"name": "dep", "version": "1.2.3"}],
        }),
        encoding="utf-8",
    )
    return stage


def _qualify(root: Path, stage: Path, commit: str) -> dict[str, object]:
    return qualify_release_assets(
        root=root,
        stage=stage,
        release_tag=TAG,
        commit=commit,
        dynamic_version=VERSION,
    )


def test_qualifies_and_binds_every_exact_staged_byte(tmp_path: Path) -> None:
    root, commit = _repository(tmp_path)
    stage = _stage(root)

    receipt = _qualify(root, stage, commit)

    assert receipt["qualified"] is True
    checksums = (stage / "SHA256SUMS").read_text(encoding="utf-8")
    bound = {line.split("  ", maxsplit=1)[1] for line in checksums.splitlines()}
    assert bound == {
        item.relative_to(stage).as_posix()
        for item in stage.rglob("*")
        if item.is_file() and item != stage / "SHA256SUMS"
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("tag", "canonical vSemVer"),
        ("commit", "tag, checked-out HEAD and commit"),
        ("dynamic", "dynamic version"),
        ("citation", "tracked release inputs differ"),
        ("wheel", "wheel filename and METADATA"),
        ("sbom-project", "built project and version"),
        ("sbom-lock", "absent from uv.lock"),
        ("dataset", "dataset manifest mismatch"),
    ],
)
def test_semantic_failures_never_produce_qualification(
    tmp_path: Path, mutation: str, message: str
) -> None:
    root, commit = _repository(tmp_path)
    stage = _stage(root)
    tag = TAG
    dynamic = VERSION
    if mutation == "tag":
        tag = VERSION
    elif mutation == "commit":
        commit = "f" * 40
    elif mutation == "dynamic":
        dynamic = "0.7.1"
    elif mutation == "citation":
        citation = root / "CITATION.cff"
        citation.write_text(
            citation.read_text(encoding="utf-8").replace(VERSION, "0.7.1"),
            encoding="utf-8",
        )
    elif mutation == "wheel":
        wheel = next(stage.glob("*.whl"))
        replacement = stage / wheel.name.replace(VERSION, "0.7.1")
        wheel.rename(replacement)
    elif mutation == "sbom-project":
        sbom = json.loads((stage / "sbom.cdx.json").read_text())
        sbom["metadata"]["component"]["version"] = "0.7.1"
        (stage / "sbom.cdx.json").write_text(json.dumps(sbom))
    elif mutation == "sbom-lock":
        sbom = json.loads((stage / "sbom.cdx.json").read_text())
        sbom["components"].append({"name": "unlocked", "version": "9.9.9"})
        (stage / "sbom.cdx.json").write_text(json.dumps(sbom))
    else:
        dataset = root / "build" / "dataset-input"
        (dataset / "data/medicines.parquet").write_bytes(b"changed")
        dataset_archive = stage / (
            f"global-medicines-atlas-dataset-{VERSION}.tar.gz"
        )
        with tarfile.open(dataset_archive, "w:gz") as archive:
            for item in sorted(dataset.rglob("*")):
                if item.is_file():
                    archive.add(
                        item, arcname=item.relative_to(dataset).as_posix()
                    )

    with pytest.raises(QualificationError, match=message):
        qualify_release_assets(
            root=root,
            stage=stage,
            release_tag=tag,
            commit=commit,
            dynamic_version=dynamic,
        )
    assert not (stage / "qualification.json").exists()
    assert not (stage / "SHA256SUMS").exists()
