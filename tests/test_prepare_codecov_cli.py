from __future__ import annotations

import hashlib
import io
import subprocess  # ruff: ignore[suspicious-subprocess-import] - mock only
from collections.abc import Sequence
from pathlib import Path

import pytest
from scripts import prepare_codecov_cli


def test_prepare_verifies_pinned_release_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary = b"verified codecov binary fixture"
    monkeypatch.setattr(prepare_codecov_cli, "CODECOV_ASSET_SIZE", len(binary))
    monkeypatch.setattr(
        prepare_codecov_cli,
        "CODECOV_ASSET_SHA256",
        hashlib.sha256(binary).hexdigest(),
    )
    monkeypatch.setattr(prepare_codecov_cli.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        prepare_codecov_cli.platform, "machine", lambda: "x86_64"
    )

    def open_asset(_url: str, *, timeout: float) -> io.BytesIO:
        assert timeout == 60
        return io.BytesIO(binary)

    monkeypatch.setattr(
        prepare_codecov_cli.urllib.request, "urlopen", open_asset
    )
    calls: list[list[str]] = []

    def run(
        command: str | Sequence[str],
        *,
        check: bool = False,
        capture_output: bool = False,
        shell: bool = True,
        text: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        values = [command] if isinstance(command, str) else list(command)
        calls.append(values)
        assert check
        assert capture_output
        assert not shell
        assert text
        assert timeout == 30
        return subprocess.CompletedProcess(
            values, 0, stdout="codecovcli version 11.3.1", stderr=""
        )

    monkeypatch.setattr(prepare_codecov_cli.subprocess, "run", run)

    destination = prepare_codecov_cli.prepare(tmp_path)

    assert destination == tmp_path / "codecovcli"
    assert destination.read_bytes() == binary
    assert destination.stat().st_mode & 0o111
    assert calls == [[str(destination), "--version"]]


@pytest.mark.parametrize("failure", ["digest", "version", "platform"])
def test_prepare_never_keeps_an_unverified_or_unsupported_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    binary = b"release asset fixture"
    monkeypatch.setattr(prepare_codecov_cli, "CODECOV_ASSET_SIZE", len(binary))
    monkeypatch.setattr(
        prepare_codecov_cli,
        "CODECOV_ASSET_SHA256",
        "0" * 64 if failure == "digest" else hashlib.sha256(binary).hexdigest(),
    )
    monkeypatch.setattr(
        prepare_codecov_cli.platform,
        "system",
        lambda: "Darwin" if failure == "platform" else "Linux",
    )
    monkeypatch.setattr(
        prepare_codecov_cli.platform, "machine", lambda: "x86_64"
    )

    def open_asset(_url: str, *, timeout: float) -> io.BytesIO:
        del timeout
        return io.BytesIO(binary)

    monkeypatch.setattr(
        prepare_codecov_cli.urllib.request, "urlopen", open_asset
    )

    def run(
        command: str | Sequence[str],
        *,
        check: bool = False,
        capture_output: bool = False,
        shell: bool = True,
        text: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del check, capture_output, shell, text, timeout
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "wrong version"
                if failure == "version"
                else "codecovcli version 11.3.1"
            ),
            stderr="",
        )

    monkeypatch.setattr(prepare_codecov_cli.subprocess, "run", run)

    with pytest.raises(
        RuntimeError if failure in {"version", "platform"} else ValueError
    ):
        prepare_codecov_cli.prepare(tmp_path)

    assert list(tmp_path.iterdir()) == []
