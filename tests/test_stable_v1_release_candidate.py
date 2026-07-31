"""Fail-closed contracts for the unsigned stable-v1 release candidate."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tarfile
import zipfile
from pathlib import Path

import pytest
import scripts.build_stable_v1_release_candidate as candidate_script
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from scripts.build_stable_v1_release_candidate import (
    assert_reproducible_builds,
    build_provenance_references,
    built_wheel_version,
    canonicalize_sbom,
    canonicalize_sdist,
    canonicalize_wheel,
    consume_candidate,
    portable_venv_python,
    verification_commands,
)

import global_medicines_atlas.stable_v1_release_candidate as candidate_module
from global_medicines_atlas.stable_v1_release_candidate import (
    CHECKSUMS_PATH,
    GUIDE_PATH,
    LOCK_PATH,
    MANIFEST_PATH,
    PROVENANCE_PATH,
    RELEASE_CANDIDATE_SCHEMA_ID,
    SBOM_PATH,
    ArtifactRole,
    CandidateArtifact,
    CandidateManifest,
    CandidateState,
    ProvenanceReference,
    ReferenceKind,
    ReleaseCandidateError,
    StableV1ReleaseCandidateReceipt,
    VerificationCommand,
    build_receipt,
    candidate_artifact,
    canonical_json_bytes,
    immutable_artifact,
    receipt_from_json,
    reference_payload,
    sha256_file,
    verify_candidate_package,
    write_manifest_and_checksums,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/stable-v1-release-candidate-v1.json"
VERSION = "1.0.0rc1"
REFERENCE_FILES = (
    ".github/workflows/release-provenance.yml",
    "pylock.toml",
    "quality/release-build-constraints.txt",
    "quality/release-build-toolchain.json",
    "quality/qualifications/stable-v1-consumer-compatibility.json",
    "schemas/release-evidence-v1.json",
    "schemas/stable-v1-consumer-compatibility-v1.json",
    "schemas/stable-v1-release-candidate-v1.json",
    "scripts/build_stable_v1_release_candidate.py",
    "src/global_medicines_atlas/stable_v1_release_candidate.py",
    "uv.lock",
)


def _run(root: Path, *arguments: str) -> str:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        list(arguments),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_wheel_canonicalization_normalizes_generated_version_and_record(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "candidate.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("package/_version.py", b"a = 1\r\nb = 2\r\n")
        archive.writestr("package/data.bin", b"\x00\x01")
        archive.writestr(
            "package-1.0.dist-info/RECORD",
            b"stale,sha256=stale,1\r\n",
        )

    canonicalize_wheel(wheel)

    with zipfile.ZipFile(wheel) as archive:
        assert archive.read("package/_version.py") == b"a = 1\nb = 2\n"
        record = archive.read("package-1.0.dist-info/RECORD").decode()
    assert "\r" not in record
    assert "stale" not in record
    assert "package/_version.py,sha256=" in record
    assert "package-1.0.dist-info/RECORD,,\n" in record


def test_sdist_canonicalization_uses_stored_gzip_blocks(
    tmp_path: Path,
) -> None:
    source = tmp_path / "candidate.tar.gz"
    payload = b"platform-independent payload\n" * 20
    with tarfile.open(source, "w:gz") as archive:
        info = tarfile.TarInfo("candidate/payload.txt")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    canonicalize_sdist(source, source_date_epoch="1700000000")
    first = source.read_bytes()
    canonicalize_sdist(source, source_date_epoch="1700000000")

    assert source.read_bytes() == first
    assert first[:10] == b"\x1f\x8b\x08\x00\x00\xf1Se\x00\xff"
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(first))) as archive:
        extracted = archive.extractfile("candidate/payload.txt")
        assert extracted is not None
        assert extracted.read() == payload


def _repository(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "repository"
    root.mkdir()
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.email", "candidate@example.invalid")
    _run(root, "git", "config", "user.name", "Candidate Test")
    for relative in REFERENCE_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {relative}\n", encoding="utf-8")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "-q", "-m", "fixture")
    commit = _run(root, "git", "rev-parse", "HEAD")
    tree = _run(root, "git", "rev-parse", "HEAD^{tree}")
    return root, commit, tree


def _wheel(
    path: Path,
    version: str = VERSION,
    name: str = "global-medicines-atlas",
) -> None:
    metadata = f"Name: {name}\nVersion: {version}\n"
    with zipfile.ZipFile(path, mode="w") as archive:
        archive.writestr(
            f"global_medicines_atlas-{version}.dist-info/METADATA", metadata
        )


def _sdist(
    path: Path,
    version: str = VERSION,
    name: str = "global-medicines-atlas",
) -> None:
    metadata = f"Name: {name}\nVersion: {version}\n".encode()
    with tarfile.open(path, mode="w:gz") as archive:
        info = tarfile.TarInfo(f"global_medicines_atlas-{version}/PKG-INFO")
        info.size = len(metadata)
        archive.addfile(info, io.BytesIO(metadata))


def _sbom(path: Path, version: str = VERSION) -> None:
    path.write_bytes(
        canonical_json_bytes({
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "metadata": {
                "component": {
                    "name": "global-medicines-atlas",
                    "type": "application",
                    "version": version,
                }
            },
            "components": [],
        })
    )


def _package(
    tmp_path: Path,
) -> tuple[Path, Path, StableV1ReleaseCandidateReceipt]:
    root, commit, tree = _repository(tmp_path)
    stage = tmp_path / "stage"
    dist = stage / "dist"
    dist.mkdir(parents=True)
    wheel = dist / f"global_medicines_atlas-{VERSION}-py3-none-any.whl"
    sdist = dist / f"global_medicines_atlas-{VERSION}.tar.gz"
    _wheel(wheel)
    _sdist(sdist)
    _sbom(stage / SBOM_PATH)
    (stage / LOCK_PATH).write_text("version = 1\n", encoding="utf-8")
    (stage / GUIDE_PATH).write_text("# Verify\n", encoding="utf-8")
    references = build_provenance_references(root, commit)
    (stage / PROVENANCE_PATH).write_bytes(reference_payload(references))
    artifacts = tuple(
        sorted(
            (
                candidate_artifact(
                    stage,
                    wheel,
                    role=ArtifactRole.WHEEL,
                    media_type="application/vnd.pypa.wheel+zip",
                ),
                candidate_artifact(
                    stage,
                    sdist,
                    role=ArtifactRole.SDIST,
                    media_type="application/gzip",
                ),
                candidate_artifact(
                    stage,
                    stage / SBOM_PATH,
                    role=ArtifactRole.SBOM,
                    media_type="application/vnd.cyclonedx+json",
                ),
                candidate_artifact(
                    stage,
                    stage / LOCK_PATH,
                    role=ArtifactRole.DEPENDENCY_LOCK,
                    media_type="application/toml",
                ),
                candidate_artifact(
                    stage,
                    stage / PROVENANCE_PATH,
                    role=ArtifactRole.PROVENANCE_REFERENCES,
                    media_type="application/json",
                ),
                candidate_artifact(
                    stage,
                    stage / GUIDE_PATH,
                    role=ArtifactRole.VERIFICATION_GUIDE,
                    media_type="text/markdown",
                ),
            ),
            key=lambda item: item.path,
        )
    )
    candidate_id = f"stable-v1-rc-{commit[:12]}"
    manifest, checksums = write_manifest_and_checksums(
        stage=stage,
        candidate_id=candidate_id,
        source_commit=commit,
        source_tree=tree,
        package_version=VERSION,
        artifacts=artifacts,
    )
    receipt = build_receipt(
        candidate_id=candidate_id,
        source_commit=commit,
        source_tree=tree,
        package_version=VERSION,
        artifacts=artifacts,
        manifest=manifest,
        checksums=checksums,
        provenance_references=references,
        verification_commands=verification_commands(wheel.name, sdist.name),
        limitations=("one", "two", "three", "four"),
    )
    return root, stage, receipt


def _rewrite_controls(
    stage: Path, receipt: StableV1ReleaseCandidateReceipt
) -> StableV1ReleaseCandidateReceipt:
    for name in (MANIFEST_PATH, CHECKSUMS_PATH):
        (stage / name).unlink(missing_ok=True)
    artifacts = tuple(
        candidate_artifact(
            stage,
            stage / item.path,
            role=item.role,
            media_type=item.media_type,
        )
        for item in receipt.artifacts
    )
    manifest, checksums = write_manifest_and_checksums(
        stage=stage,
        candidate_id=receipt.candidate_id,
        source_commit=receipt.source_commit,
        source_tree=receipt.source_tree,
        package_version=receipt.package_version,
        artifacts=artifacts,
    )
    return build_receipt(
        candidate_id=receipt.candidate_id,
        source_commit=receipt.source_commit,
        source_tree=receipt.source_tree,
        package_version=receipt.package_version,
        artifacts=artifacts,
        manifest=manifest,
        checksums=checksums,
        provenance_references=receipt.provenance_references,
        verification_commands=receipt.verification_commands,
        limitations=receipt.limitations,
    )


def _rebind_existing_controls(
    stage: Path,
    receipt: StableV1ReleaseCandidateReceipt,
    *,
    references: tuple[ProvenanceReference, ...] | None = None,
) -> StableV1ReleaseCandidateReceipt:
    checksum_targets = sorted(
        path
        for path in stage.rglob("*")
        if path.is_file() and path.name != CHECKSUMS_PATH
    )
    (stage / CHECKSUMS_PATH).write_text(
        "".join(
            f"{sha256_file(path)}  {path.relative_to(stage).as_posix()}\n"
            for path in checksum_targets
        ),
        encoding="utf-8",
        newline="\n",
    )
    return build_receipt(
        candidate_id=receipt.candidate_id,
        source_commit=receipt.source_commit,
        source_tree=receipt.source_tree,
        package_version=receipt.package_version,
        artifacts=receipt.artifacts,
        manifest=immutable_artifact(stage, stage / MANIFEST_PATH),
        checksums=immutable_artifact(stage, stage / CHECKSUMS_PATH),
        provenance_references=references or receipt.provenance_references,
        verification_commands=receipt.verification_commands,
        limitations=receipt.limitations,
    )


def test_candidate_package_verifies_and_is_deterministic(
    tmp_path: Path,
) -> None:
    root, stage, receipt = _package(tmp_path)

    verify_candidate_package(root=root, stage=stage, receipt=receipt)
    assert receipt.content_sha256 == receipt.expected_content_sha256()
    assert receipt.canonical_bytes() == receipt.canonical_bytes()
    assert receipt.state == CandidateState()
    assert RELEASE_CANDIDATE_SCHEMA_ID in receipt.canonical_bytes().decode()


def test_receipt_matches_checked_in_json_schema(tmp_path: Path) -> None:
    _, _, receipt = _package(tmp_path)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    validator.validate(receipt.model_dump(mode="json"))
    invalid = receipt.model_dump(mode="json")
    invalid["state"]["approved"] = True
    assert list(validator.iter_errors(invalid))


@pytest.mark.parametrize(
    "field",
    [
        "signed",
        "approved",
        "published",
        "provenance_attested",
        "git_tag_created",
        "github_release_created",
    ],
)
def test_authority_or_external_action_cannot_be_inferred(field: str) -> None:
    with pytest.raises(ValidationError):
        CandidateState.model_validate({field: True})


@pytest.mark.parametrize(
    "command",
    [
        ("git", "tag", "v1.0.0"),
        ("gh", "release", "create", "v1.0.0"),
        ("uv", "publish"),
        ("cosign", "sign", "artifact"),
    ],
)
def test_verification_commands_cannot_publish_tag_or_sign(
    command: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError, match="may not publish"):
        VerificationCommand(
            command_id="forbidden",
            argv=command,
            expected_result="never",
        )


def test_verification_commands_create_independent_portable_consumers() -> None:
    commands = verification_commands("candidate.whl", "candidate.tar.gz")
    by_id = {command.command_id: command for command in commands}

    assert set(by_id) == {
        "verify-candidate",
        "verify-sdist-consumer",
        "verify-wheel-consumer",
    }
    for role in ("wheel", "sdist"):
        command = by_id[f"verify-{role}-consumer"]
        assert "consume" in command.argv
        assert command.argv[command.argv.index("--artifact") + 1] == role
        environment = command.argv[command.argv.index("--environment") + 1]
        assert environment == f"build/stable-v1/consumer-{role}"
        assert not any(
            ".candidate-venv/python" in part for part in command.argv
        )


def test_portable_venv_python_supports_posix_and_windows_layouts(
    tmp_path: Path,
) -> None:
    posix = tmp_path / "posix"
    posix_python = posix / "bin/python"
    posix_python.parent.mkdir(parents=True)
    posix_python.write_bytes(b"")
    assert portable_venv_python(posix) == posix_python

    windows = tmp_path / "windows"
    windows_python = windows / "Scripts/python.exe"
    windows_python.parent.mkdir(parents=True)
    windows_python.write_bytes(b"")
    assert portable_venv_python(windows) == windows_python

    with pytest.raises(ReleaseCandidateError, match="interpreter layout"):
        portable_venv_python(tmp_path / "missing")


def test_consumer_probe_creates_and_reinstalls_exact_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, stage, receipt = _package(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_bytes(receipt.canonical_bytes())
    environment = tmp_path / "consumer"
    calls: list[tuple[str, ...]] = []

    def fake_run(
        cwd: Path,
        *arguments: str,
        environment: dict[str, str] | None = None,
    ) -> bytes:
        del cwd, environment
        calls.append(arguments)
        if arguments[:2] == ("uv", "venv"):
            python = Path(arguments[-1]) / "bin/python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"")
        if arguments and arguments[0].endswith("python") and "-c" in arguments:
            return json.dumps({
                "api": "passed",
                "metadata_version": VERSION,
                "openapi_paths": 1,
                "package_version": VERSION,
            }).encode()
        return b""

    monkeypatch.setattr(
        "scripts.build_stable_v1_release_candidate._run", fake_run
    )
    monkeypatch.setattr(
        "scripts.build_stable_v1_release_candidate._verify_build_toolchain",
        lambda root: (root / "constraints.txt", "uv"),
    )

    evidence = consume_candidate(
        root=root,
        stage=stage,
        receipt_path=receipt_path,
        artifact_role=ArtifactRole.WHEEL,
        environment=environment,
    )

    assert evidence["state"] == "passed"
    assert evidence["artifact_role"] == "wheel"
    assert sum(call[:3] == ("uv", "pip", "install") for call in calls) == 2
    assert any("--reinstall" in call for call in calls)
    assert any(
        call[-2:] == ("global_medicines_atlas.cli", "--help") for call in calls
    )


def test_consumer_probe_rejects_existing_environment(tmp_path: Path) -> None:
    root, stage, receipt = _package(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_bytes(receipt.canonical_bytes())
    environment = tmp_path / "consumer"
    environment.mkdir()

    with pytest.raises(ReleaseCandidateError, match="must not already exist"):
        consume_candidate(
            root=root,
            stage=stage,
            receipt_path=receipt_path,
            artifact_role=ArtifactRole.SDIST,
            environment=environment,
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"{", "valid JSON"),
        (b"[]", "one JSON object"),
        (
            json.dumps({
                "api": "failed",
                "metadata_version": VERSION,
                "openapi_paths": 1,
                "package_version": VERSION,
            }).encode(),
            "did not match",
        ),
    ],
)
def test_consumer_probe_payload_fails_closed(
    payload: bytes, message: str
) -> None:
    with pytest.raises(ReleaseCandidateError, match=message):
        candidate_script._parse_consumer_probe(payload, VERSION)


def test_consumer_probe_rejects_changed_reinstall_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, stage, receipt = _package(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_bytes(receipt.canonical_bytes())
    probe_count = 0

    def fake_run(
        cwd: Path,
        *arguments: str,
        environment: dict[str, str] | None = None,
    ) -> bytes:
        nonlocal probe_count
        del cwd, environment
        if arguments[:2] == ("uv", "venv"):
            python = Path(arguments[-1]) / "bin/python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"")
        if arguments and arguments[0].endswith("python") and "-c" in arguments:
            probe_count += 1
            return json.dumps({
                "api": "passed",
                "metadata_version": VERSION,
                "openapi_paths": probe_count,
                "package_version": VERSION,
            }).encode()
        return b""

    monkeypatch.setattr(candidate_script, "_run", fake_run)
    monkeypatch.setattr(
        candidate_script,
        "_verify_build_toolchain",
        lambda root: (root / "constraints.txt", "uv"),
    )

    with pytest.raises(ReleaseCandidateError, match="changed after reinstall"):
        consume_candidate(
            root=root,
            stage=stage,
            receipt_path=receipt_path,
            artifact_role=ArtifactRole.WHEEL,
            environment=Path("build/consumer"),
        )


def test_packaged_text_evidence_rejects_crlf(tmp_path: Path) -> None:
    for relative in candidate_script._PACKAGED_TEXT_SAMPLES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"canonical\n")
    first = tmp_path / candidate_script._PACKAGED_TEXT_SAMPLES[0]
    first.write_bytes(b"not\r\ncanonical\r\n")

    with pytest.raises(ReleaseCandidateError, match="not canonical LF"):
        candidate_script._packaged_text_evidence(tmp_path)


def test_dirty_source_and_failed_subprocess_are_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(candidate_script, "_git", lambda *_args: "dirty")
    with pytest.raises(ReleaseCandidateError, match="clean Git worktree"):
        candidate_script._assert_clean_source(tmp_path)

    error = subprocess.CalledProcessError(
        1, ["candidate-command"], stderr=b"expected failure"
    )
    monkeypatch.setattr(
        candidate_script.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    with pytest.raises(ReleaseCandidateError, match="expected failure"):
        candidate_script._run(tmp_path, "candidate-command")


def test_main_routes_reproduce_consume_build_and_verify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    evidence = {"content_sha256": "a" * 64, "state": "passed"}
    monkeypatch.setattr(
        candidate_script,
        "clean_detached_reproducibility",
        lambda _root: evidence,
    )
    assert (
        candidate_script.main([
            "reproduce",
            "--root",
            str(tmp_path),
            "--output",
            "evidence.json",
        ])
        == 0
    )
    assert json.loads((tmp_path / "evidence.json").read_text()) == evidence

    monkeypatch.setattr(
        candidate_script,
        "consume_candidate",
        lambda **_kwargs: {"artifact_role": "wheel", "state": "passed"},
    )
    assert (
        candidate_script.main([
            "consume",
            "--root",
            str(tmp_path),
            "--stage",
            "stage",
            "--receipt",
            "receipt.json",
            "--artifact",
            "wheel",
            "--environment",
            "consumer",
        ])
        == 0
    )

    monkeypatch.setattr(
        candidate_script, "build_candidate", lambda *_args: "b" * 64
    )
    monkeypatch.setattr(
        candidate_script, "verify_candidate", lambda *_args: "c" * 64
    )
    for command, digest in (("build", "b" * 64), ("verify", "c" * 64)):
        assert (
            candidate_script.main([
                command,
                "--root",
                str(tmp_path),
                "--stage",
                "stage",
                "--receipt",
                "receipt.json",
            ])
            == 0
        )
        assert digest in capsys.readouterr().out


def test_tampered_payload_fails_even_if_receipt_is_unchanged(
    tmp_path: Path,
) -> None:
    root, stage, receipt = _package(tmp_path)
    (stage / GUIDE_PATH).write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ReleaseCandidateError, match="identity mismatch"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


def test_extra_file_fails_closed(tmp_path: Path) -> None:
    root, stage, receipt = _package(tmp_path)
    (stage / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(ReleaseCandidateError, match="unexpected file set"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


def test_missing_checksum_entry_fails_closed(tmp_path: Path) -> None:
    root, stage, receipt = _package(tmp_path)
    lines = (stage / CHECKSUMS_PATH).read_text(encoding="utf-8").splitlines()
    (stage / CHECKSUMS_PATH).write_text("\n".join(lines[:-1]) + "\n")
    receipt = receipt.model_copy(
        update={"checksums": immutable_artifact(stage, stage / CHECKSUMS_PATH)}
    )
    payload = receipt.model_dump(mode="json", exclude={"content_sha256"})
    receipt = StableV1ReleaseCandidateReceipt.model_validate({
        **payload,
        "content_sha256": hashlib.sha256(
            canonical_json_bytes(payload)
        ).hexdigest(),
    })

    with pytest.raises(ReleaseCandidateError, match="does not bind"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_distribution_version_mismatch_fails_closed(
    tmp_path: Path, kind: str
) -> None:
    root, stage, receipt = _package(tmp_path)
    target = next(
        stage / item.path
        for item in receipt.artifacts
        if item.role.value == kind
    )
    if kind == "wheel":
        _wheel(target, "9.9.9")
    else:
        _sdist(target, "9.9.9")
    receipt = _rewrite_controls(stage, receipt)

    with pytest.raises(ReleaseCandidateError, match="versions disagree"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


@pytest.mark.parametrize(
    "mutation", ["format", "version", "serial", "timestamp"]
)
def test_sbom_identity_and_determinism_fail_closed(
    tmp_path: Path, mutation: str
) -> None:
    root, stage, receipt = _package(tmp_path)
    path = stage / SBOM_PATH
    sbom = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "format":
        sbom["bomFormat"] = "SPDX"
    elif mutation == "version":
        sbom["metadata"]["component"]["version"] = "9.9.9"
    elif mutation == "serial":
        sbom["serialNumber"] = "urn:uuid:random"
    else:
        sbom["metadata"]["timestamp"] = "2026-01-01T00:00:00Z"
    path.write_bytes(canonical_json_bytes(sbom))
    receipt = _rewrite_controls(stage, receipt)

    with pytest.raises(ReleaseCandidateError, match="SBOM"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


def test_changed_provenance_digest_fails_closed(tmp_path: Path) -> None:
    root, stage, receipt = _package(tmp_path)
    references = list(receipt.provenance_references)
    references[0] = references[0].model_copy(update={"sha256": "f" * 64})
    changed = tuple(references)
    (stage / PROVENANCE_PATH).write_bytes(reference_payload(changed))
    receipt = _rewrite_controls(stage, receipt)
    receipt = build_receipt(
        candidate_id=receipt.candidate_id,
        source_commit=receipt.source_commit,
        source_tree=receipt.source_tree,
        package_version=receipt.package_version,
        artifacts=receipt.artifacts,
        manifest=receipt.manifest,
        checksums=receipt.checksums,
        provenance_references=changed,
        verification_commands=receipt.verification_commands,
        limitations=receipt.limitations,
    )

    with pytest.raises(ReleaseCandidateError, match="reference changed"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


def test_receipt_loader_rejects_tampered_digest(tmp_path: Path) -> None:
    _, _, receipt = _package(tmp_path)
    path = tmp_path / "receipt.json"
    payload = receipt.model_dump(mode="json")
    payload["package_version"] = "changed"
    path.write_bytes(canonical_json_bytes(payload))

    with pytest.raises(ReleaseCandidateError, match="receipt is invalid"):
        receipt_from_json(path)


@pytest.mark.parametrize("path", ["../escape", "/absolute", "bad\\path"])
def test_candidate_artifact_paths_are_safe(path: str) -> None:
    with pytest.raises(ValidationError, match="safe repository-relative"):
        CandidateArtifact(
            path=path,
            sha256="a" * 64,
            size=1,
            role=ArtifactRole.WHEEL,
            media_type="application/zip",
        )


def test_incomplete_provenance_set_is_rejected(tmp_path: Path) -> None:
    root, commit, _ = _repository(tmp_path)
    references = build_provenance_references(root, commit)

    with pytest.raises(ReleaseCandidateError, match="incomplete"):
        reference_payload(references[:-1])


def test_controls_cannot_overwrite_existing_files(tmp_path: Path) -> None:
    _, stage, receipt = _package(tmp_path)

    with pytest.raises(ReleaseCandidateError, match="already exist"):
        write_manifest_and_checksums(
            stage=stage,
            candidate_id=receipt.candidate_id,
            source_commit=receipt.source_commit,
            source_tree=receipt.source_tree,
            package_version=receipt.package_version,
            artifacts=receipt.artifacts,
        )


@pytest.mark.parametrize(
    ("kind", "locator"),
    [
        (ReferenceKind.REPOSITORY_FILE, "file:wrong"),
        (ReferenceKind.GIT_COMMIT_OBJECT, "git:tree:wrong"),
        (ReferenceKind.GIT_COMMIT_OBJECT, "git:commit:short"),
        (ReferenceKind.GIT_TREE_LISTING, "git:commit:" + "a" * 40),
    ],
)
def test_provenance_locator_kind_is_fail_closed(
    kind: ReferenceKind, locator: str
) -> None:
    with pytest.raises(ValidationError):
        ProvenanceReference(
            role="invalid-reference",
            kind=kind,
            locator=locator,
            sha256="a" * 64,
        )


@pytest.mark.parametrize("mutation", ["unsorted", "duplicate-role"])
def test_manifest_requires_exact_sorted_artifacts(
    tmp_path: Path, mutation: str
) -> None:
    _, _, receipt = _package(tmp_path)
    files = [item.model_dump(mode="json") for item in receipt.artifacts]
    if mutation == "unsorted":
        files.reverse()
    else:
        files[0]["role"] = files[1]["role"]
    with pytest.raises(ValidationError):
        CandidateManifest(
            candidate_id=receipt.candidate_id,
            source_commit=receipt.source_commit,
            source_tree=receipt.source_tree,
            package_version=receipt.package_version,
            files=files,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("artifact-order", "artifacts must be sorted"),
        ("artifact-role", "artifact roles are incomplete"),
        ("reference-order", "references must be sorted"),
        ("reference-role", "references are incomplete"),
        ("command-order", "commands must be sorted"),
        ("command-id", "commands are incomplete"),
        ("manifest-path", "manifest path is not canonical"),
        ("checksum-path", "checksums path is not canonical"),
    ],
)
def test_receipt_requires_exact_sorted_contract_sets(
    tmp_path: Path, mutation: str, message: str
) -> None:
    _, _, receipt = _package(tmp_path)
    payload = receipt.model_dump(mode="json")
    if mutation == "artifact-order":
        payload["artifacts"].reverse()
    elif mutation == "artifact-role":
        payload["artifacts"][0]["role"] = payload["artifacts"][1]["role"]
    elif mutation == "reference-order":
        payload["provenance_references"].reverse()
    elif mutation == "reference-role":
        payload["provenance_references"][0]["role"] = payload[
            "provenance_references"
        ][1]["role"]
    elif mutation == "command-order":
        payload["verification_commands"].reverse()
    elif mutation == "command-id":
        payload["verification_commands"][0]["command_id"] = payload[
            "verification_commands"
        ][1]["command_id"]
    elif mutation == "manifest-path":
        payload["manifest"]["path"] = "other.json"
    else:
        payload["checksums"]["path"] = "other.sums"
    with pytest.raises(ValidationError, match=message):
        StableV1ReleaseCandidateReceipt.model_validate(payload)


def test_artifact_outside_stage_and_directory_fail_closed(
    tmp_path: Path,
) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("outside", encoding="utf-8")

    with pytest.raises(ReleaseCandidateError, match="escapes"):
        immutable_artifact(stage, outside)
    with pytest.raises(ReleaseCandidateError, match="regular files"):
        immutable_artifact(stage, stage)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_unreadable_distribution_metadata_fails_closed(
    tmp_path: Path, kind: str
) -> None:
    root, stage, receipt = _package(tmp_path)
    target = next(
        stage / item.path
        for item in receipt.artifacts
        if item.role.value == kind
    )
    target.write_bytes(b"not an archive")
    receipt = _rewrite_controls(stage, receipt)

    with pytest.raises(ReleaseCandidateError, match="metadata is unreadable"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_distribution_project_name_mismatch_fails_closed(
    tmp_path: Path, kind: str
) -> None:
    root, stage, receipt = _package(tmp_path)
    target = next(
        stage / item.path
        for item in receipt.artifacts
        if item.role.value == kind
    )
    if kind == "wheel":
        _wheel(target, name="another-project")
    else:
        _sdist(target, name="another-project")
    receipt = _rewrite_controls(stage, receipt)

    with pytest.raises(ReleaseCandidateError, match="project identity"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


@pytest.mark.parametrize("mutation", ["json", "array", "metadata", "component"])
def test_malformed_sbom_shapes_fail_closed(
    tmp_path: Path, mutation: str
) -> None:
    root, stage, receipt = _package(tmp_path)
    path = stage / SBOM_PATH
    if mutation == "json":
        path.write_text("{", encoding="utf-8")
    elif mutation == "array":
        path.write_text("[]", encoding="utf-8")
    elif mutation == "metadata":
        path.write_bytes(canonical_json_bytes({"bomFormat": "CycloneDX"}))
    else:
        path.write_bytes(
            canonical_json_bytes({
                "bomFormat": "CycloneDX",
                "metadata": {},
            })
        )
    receipt = _rewrite_controls(stage, receipt)

    with pytest.raises(ReleaseCandidateError, match="SBOM"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


@pytest.mark.parametrize(
    "line",
    [
        "invalid",
        "g" * 64 + "  VERIFY.md",
        "a" * 64 + "  ../escape",
        "a" * 64 + "  VERIFY.md\n" + "b" * 64 + "  VERIFY.md",
    ],
)
def test_noncanonical_checksum_syntax_fails_closed(
    tmp_path: Path, line: str
) -> None:
    root, stage, receipt = _package(tmp_path)
    (stage / CHECKSUMS_PATH).write_text(line + "\n", encoding="utf-8")
    receipt = build_receipt(
        candidate_id=receipt.candidate_id,
        source_commit=receipt.source_commit,
        source_tree=receipt.source_tree,
        package_version=receipt.package_version,
        artifacts=receipt.artifacts,
        manifest=receipt.manifest,
        checksums=immutable_artifact(stage, stage / CHECKSUMS_PATH),
        provenance_references=receipt.provenance_references,
        verification_commands=receipt.verification_commands,
        limitations=receipt.limitations,
    )

    with pytest.raises(ReleaseCandidateError, match="SHA256SUMS"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


def test_git_provenance_requires_git_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, stage, receipt = _package(tmp_path)
    monkeypatch.setattr(candidate_module.shutil, "which", lambda _: None)

    with pytest.raises(ReleaseCandidateError, match="Git provenance"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


@pytest.mark.parametrize("kind", ["commit", "tree"])
def test_provenance_git_reference_cannot_target_another_commit(
    tmp_path: Path, kind: str
) -> None:
    root, stage, receipt = _package(tmp_path)
    references = list(receipt.provenance_references)
    role = f"source-{kind}-{'object' if kind == 'commit' else 'listing'}"
    index = next(i for i, item in enumerate(references) if item.role == role)
    prefix = "git:commit:" if kind == "commit" else "git:tree-listing:"
    references[index] = references[index].model_copy(
        update={"locator": prefix + "f" * 40}
    )
    changed = tuple(references)
    (stage / PROVENANCE_PATH).write_bytes(reference_payload(changed))
    receipt = _rewrite_controls(stage, receipt)
    receipt = build_receipt(
        candidate_id=receipt.candidate_id,
        source_commit=receipt.source_commit,
        source_tree=receipt.source_tree,
        package_version=receipt.package_version,
        artifacts=receipt.artifacts,
        manifest=receipt.manifest,
        checksums=receipt.checksums,
        provenance_references=changed,
        verification_commands=receipt.verification_commands,
        limitations=receipt.limitations,
    )

    with pytest.raises(ReleaseCandidateError, match="targets another commit"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("candidate_id", "stable-v1-rc-ffffffffffff", "candidate identity"),
        ("source_commit", "f" * 40, "source commit"),
        ("source_tree", "f" * 40, "source tree"),
        ("package_version", "9.9.9", "package version"),
    ],
)
def test_manifest_semantic_identity_must_match_receipt(
    tmp_path: Path, field: str, replacement: str, message: str
) -> None:
    root, stage, receipt = _package(tmp_path)
    manifest_path = stage / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = replacement
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    receipt = _rebind_existing_controls(stage, receipt)

    with pytest.raises(ReleaseCandidateError, match=message):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


def test_manifest_artifact_set_must_match_receipt(tmp_path: Path) -> None:
    root, stage, receipt = _package(tmp_path)
    manifest_path = stage / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["media_type"] = "application/changed"
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    receipt = _rebind_existing_controls(stage, receipt)

    with pytest.raises(ReleaseCandidateError, match="artifacts disagree"):
        verify_candidate_package(root=root, stage=stage, receipt=receipt)


def test_receipt_digest_and_stage_shape_fail_closed(tmp_path: Path) -> None:
    root, stage, receipt = _package(tmp_path)
    invalid = receipt.model_copy(update={"content_sha256": "0" * 64})
    with pytest.raises(ReleaseCandidateError, match="receipt digest"):
        verify_candidate_package(root=root, stage=stage, receipt=invalid)
    with pytest.raises(ReleaseCandidateError, match="stage is unavailable"):
        verify_candidate_package(
            root=root, stage=tmp_path / "absent", receipt=receipt
        )
    file_stage = tmp_path / "file-stage"
    file_stage.write_text("not a directory", encoding="utf-8")
    with pytest.raises(ReleaseCandidateError, match="must be a directory"):
        verify_candidate_package(root=root, stage=file_stage, receipt=receipt)


def test_sbom_normalization_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "sbom.json"
    path.write_text(
        json.dumps({
            "bomFormat": "CycloneDX",
            "serialNumber": "random",
            "metadata": {
                "timestamp": "now",
                "component": {"name": "global-medicines-atlas"},
            },
        })
    )

    canonicalize_sbom(path, VERSION)
    first = path.read_bytes()
    canonicalize_sbom(path, VERSION)
    assert path.read_bytes() == first
    assert b"serialNumber" not in first
    assert b"timestamp" not in first


def test_repeated_build_comparison_rejects_different_bytes(
    tmp_path: Path,
) -> None:
    def build(name: str, payload: bytes) -> tuple[str, tuple[Path, Path], Path]:
        directory = tmp_path / name
        directory.mkdir()
        wheel = directory / "package.whl"
        sdist = directory / "package.tar.gz"
        sbom = directory / "sbom.json"
        wheel.write_bytes(payload)
        sdist.write_bytes(b"sdist")
        sbom.write_bytes(b"sbom")
        return VERSION, (wheel, sdist), sbom

    with pytest.raises(ReleaseCandidateError, match="different distribution"):
        assert_reproducible_builds(build("one", b"one"), build("two", b"two"))


def test_hash_helpers_report_exact_content(tmp_path: Path) -> None:
    path = tmp_path / "payload"
    path.write_bytes(b"candidate")

    assert sha256_file(path) == hashlib.sha256(b"candidate").hexdigest()
    assert immutable_artifact(tmp_path, path).size == len(b"candidate")


def test_built_version_comes_from_wheel_metadata(tmp_path: Path) -> None:
    wheel = tmp_path / "candidate.whl"
    _wheel(wheel)

    assert built_wheel_version(wheel) == VERSION


def test_documentation_and_script_preserve_external_gates() -> None:
    guide = (
        (ROOT / "docs/qualification/stable-v1-release-candidate.md")
        .read_text(encoding="utf-8")
        .casefold()
    )
    script = (
        (ROOT / "scripts/build_stable_v1_release_candidate.py")
        .read_text(encoding="utf-8")
        .casefold()
    )

    assert "unsigned, unapproved, and not published" in guide
    assert "explicit licence and release approval" in guide
    assert "subprocess.run" in script
    assert "gh release create" not in script
    assert "git tag" not in script
    assert "cosign sign" not in script
