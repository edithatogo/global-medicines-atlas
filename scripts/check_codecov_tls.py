"""Fail closed when Codecov's OIDC upload endpoint cannot verify TLS."""

from __future__ import annotations

import hashlib
import socket
import ssl
import sys
from datetime import UTC, datetime

CODECOV_UPLOAD_HOST = "ingest.codecov.io"
CONNECT_TIMEOUT_SECONDS = 10


def verify_upload_endpoint(
    *,
    host: str = CODECOV_UPLOAD_HOST,
    port: int = 443,
    timeout: int = CONNECT_TIMEOUT_SECONDS,
) -> tuple[str, str, str]:
    """Return expiry, serial, and fingerprint only for a verified TLS peer."""
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        with (
            socket.create_connection(
                (host, port), timeout=timeout
            ) as raw_socket,
            context.wrap_socket(raw_socket, server_hostname=host) as tls_socket,
        ):
            certificate = tls_socket.getpeercert()
            certificate_der = tls_socket.getpeercert(binary_form=True)
    except ssl.SSLCertVerificationError as exc:
        raise RuntimeError(
            f"Codecov upload TLS certificate verification failed for {host}: "
            f"{exc}"
        ) from exc
    except (OSError, ssl.SSLError) as exc:
        raise RuntimeError(
            f"Could not establish verified TLS to Codecov upload host {host}: "
            f"{type(exc).__name__}"
        ) from exc

    if certificate is None:
        raise RuntimeError(
            f"Codecov upload host {host} returned incomplete certificate metadata"
        )
    not_after = certificate.get("notAfter")
    if not isinstance(not_after, str) or not not_after or not certificate_der:
        raise RuntimeError(
            f"Codecov upload host {host} returned incomplete certificate metadata"
        )
    expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
        tzinfo=UTC
    )
    if expiry <= datetime.now(UTC):
        raise RuntimeError(
            f"Codecov upload TLS certificate for {host} expired at "
            f"{expiry.isoformat()}"
        )

    fingerprint = hashlib.sha256(certificate_der).hexdigest()
    serial_number = certificate.get("serialNumber")
    serial = serial_number if isinstance(serial_number, str) else "unknown"
    return expiry.isoformat(), serial, fingerprint


def main() -> int:
    try:
        expiry, serial, fingerprint = verify_upload_endpoint()
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        f"Verified Codecov upload TLS for {CODECOV_UPLOAD_HOST}; "
        f"expires={expiry}; serial={serial}; sha256={fingerprint}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
