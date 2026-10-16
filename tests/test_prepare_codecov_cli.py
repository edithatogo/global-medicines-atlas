from __future__ import annotations

import hashlib
import io
import subprocess  # ruff: ignore[suspicious-subprocess-import] - mock only
import urllib.request
from collections.abc import Sequence
from pathlib import Path

import pytest
from scripts import prepare_codecov_cli


def test_prepare_verifies_pinned_wheel_before_installing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel = b"verified wheel fixture"
    digest = hashlib.sha256(wheel).hexdigest()
    calls: list[list[str]] = []

    monkeypatch.setattr(prepare_codecov_cli, "CODECOV_WHEEL_SIZE", len(wheel))
    monkeypatch.setattr(prepare_codecov_cli, "CODECOV_WHEEL_SHA256", digest)

    def open_wheel(
        _url: str | urllib.request.Request, *, timeout: float
    ) -> io.BytesIO:
        del timeout
        return io.BytesIO(wheel)

    monkeypatch.setattr(
        prepare_codecov_cli.urllib.request, "urlopen", open_wheel
    )

    def which(command: str, mode: int = 0) -> str:
        del mode
        return f"/tools/{command}"

    monkeypatch.setattr(prepare_codecov_cli.shutil, "which", which)

    def run(
        command: str | Sequence[str],
        *,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        del check, timeout
        calls.append([command] if isinstance(command, str) else list(command))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(prepare_codecov_cli.subprocess, "run", run)

    destination = prepare_codecov_cli.prepare(
        tmp_path,
        python_executable=Path("/isolated/bin/python"),
    )

    assert destination == Path("/isolated/bin/codecovcli")
    wheel_path = str(tmp_path / prepare_codecov_cli.CODECOV_WHEEL_NAME)
    assert calls == [
        [
            "/tools/pypi-attestations",
            "verify",
            "pypi",
            "--repository",
            prepare_codecov_cli.CODECOV_REPOSITORY,
            wheel_path,
        ],
        [
            "/tools/uv",
            "pip",
            "install",
            "--python",
            "/isolated/bin/python",
            "--no-deps",
            wheel_path,
        ],
    ]
    assert not destination.exists()


@pytest.mark.parametrize("failure", ["digest", "attestation"])
def test_prepare_never_installs_unverified_wheel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    wheel = b"verified wheel fixture"
    monkeypatch.setattr(prepare_codecov_cli, "CODECOV_WHEEL_SIZE", len(wheel))
    monkeypatch.setattr(
        prepare_codecov_cli,
        "CODECOV_WHEEL_SHA256",
        "0" * 64 if failure == "digest" else hashlib.sha256(wheel).hexdigest(),
    )

    def open_wheel(
        _url: str | urllib.request.Request, *, timeout: float
    ) -> io.BytesIO:
        del timeout
        return io.BytesIO(wheel)

    monkeypatch.setattr(
        prepare_codecov_cli.urllib.request, "urlopen", open_wheel
    )

    def which(command: str, mode: int = 0) -> str:
        del mode
        return f"/tools/{command}"

    monkeypatch.setattr(prepare_codecov_cli.shutil, "which", which)
    calls: list[list[str]] = []

    def run(
        command: str | Sequence[str],
        *,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        del check, timeout
        values = [command] if isinstance(command, str) else list(command)
        calls.append(values)
        if failure == "attestation":
            raise subprocess.CalledProcessError(1, values)
        return subprocess.CompletedProcess(values, 0)

    monkeypatch.setattr(prepare_codecov_cli.subprocess, "run", run)

    with pytest.raises(ValueError if failure == "digest" else RuntimeError):
        prepare_codecov_cli.prepare(
            tmp_path,
            python_executable=Path("/isolated/bin/python"),
        )

    if failure == "digest":
        assert calls == []
    else:
        assert len(calls) == 1
        assert calls[0][1:3] == ["verify", "pypi"]
    assert not list(tmp_path.iterdir())
