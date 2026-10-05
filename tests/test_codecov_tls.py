from __future__ import annotations

import ssl
from typing import Any

import pytest
from scripts import check_codecov_tls


class _FakeSocket:
    def __enter__(self) -> _FakeSocket:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None


class _FakeTLS:
    def __enter__(self) -> _FakeTLS:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None

    def getpeercert(self, *, binary_form: bool = False) -> Any:
        if binary_form:
            return b"verified-certificate"
        return {
            "notAfter": "Dec  3 01:33:03 2026 GMT",
            "serialNumber": "A1B2",
        }


class _FakeContext:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.server_name: str | None = None

    def wrap_socket(
        self, _raw_socket: _FakeSocket, *, server_hostname: str
    ) -> _FakeTLS:
        self.server_name = server_hostname
        if self.error is not None:
            raise self.error
        return _FakeTLS()


def _install_tls_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    error: Exception | None = None,
) -> tuple[_FakeContext, list[tuple[tuple[str, int], int]]]:
    context = _FakeContext(error)
    connections: list[tuple[tuple[str, int], int]] = []

    monkeypatch.setattr(
        check_codecov_tls.ssl, "create_default_context", lambda: context
    )

    def connect(address: tuple[str, int], *, timeout: int) -> _FakeSocket:
        connections.append((address, timeout))
        return _FakeSocket()

    monkeypatch.setattr(check_codecov_tls.socket, "create_connection", connect)
    return context, connections


def test_verified_endpoint_returns_identity_and_checks_expected_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, connections = _install_tls_fakes(monkeypatch)

    expiry, serial, fingerprint = check_codecov_tls.verify_upload_endpoint()

    assert expiry == "2026-12-03T01:33:03+00:00"
    assert serial == "A1B2"
    assert fingerprint == (
        "ddbcd4ffb4d2d04ca4d47bd0459a8bc95176e49f54639c3dae682d98f49e6669"
    )
    assert context.server_name == "ingest.codecov.io"
    assert connections == [(("ingest.codecov.io", 443), 10)]


def test_expired_certificate_fails_closed_with_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ssl.SSLCertVerificationError(10, "certificate has expired")
    _install_tls_fakes(monkeypatch, error=error)

    with pytest.raises(RuntimeError, match="certificate has expired"):
        check_codecov_tls.verify_upload_endpoint()


@pytest.mark.parametrize(
    "error",
    [
        ssl.SSLCertVerificationError(62, "hostname mismatch"),
        ssl.SSLError("unexpected EOF"),
        OSError("connection timed out"),
    ],
)
def test_tls_and_transport_errors_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    _install_tls_fakes(monkeypatch, error=error)

    with pytest.raises(RuntimeError):
        check_codecov_tls.verify_upload_endpoint()
