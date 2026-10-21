"""Inventory only the three exact frozen BSD/RVG objects on main Actions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_sidecar_inventory import (
    DATASET,
    REVISION,
    BoundSidecar,
    load_sidecars,
)
from global_medicines_atlas.mbs_sidecar_layout import MAX_BYTES, profile_sidecar
from global_medicines_atlas.parser_safety import ParserSafetyError

ROOT = Path(__file__).resolve().parents[1]
COMMIT_LENGTH = 40
MAX_RESULT_BYTES = 1024 * 1024
INFO_URL = f"https://huggingface.co/api/datasets/{DATASET}/revision/{REVISION}"


def _context(exact_commit: str) -> None:
    if not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY")
        == "edithatogo/global-medicines-atlas"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and len(exact_commit) == COMMIT_LENGTH
        and all(char in "0123456789abcdef" for char in exact_commit)
        and os.environ.get("GITHUB_SHA") == exact_commit
    ):
        raise ValueError("Sidecar inventory requires exact main Actions commit")


def _url(path: str) -> str:
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{quote(path, safe='/')}?download=true"


def _read(client: httpx.Client, url: str, limit: int) -> bytes:
    client.cookies.clear()
    chunks: list[bytes] = []
    count = 0
    with client.stream("GET", url) as response:
        response.raise_for_status()
        if response.headers.get("content-encoding", "identity") != "identity":
            raise ValueError("MBS sidecar response encoding differs")
        for chunk in response.iter_bytes():
            count += len(chunk)
            if count > limit:
                raise ValueError("MBS sidecar response byte bound exceeded")
            chunks.append(chunk)
    return b"".join(chunks)


def _pinned(client: httpx.Client, path: str, digest: str, size: int) -> bytes:
    if not 0 < size <= MAX_BYTES:
        raise ValueError("MBS sidecar pinned byte bound differs")
    data = _read(client, _url(path), size)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("MBS sidecar exact digest or size differs")
    return data


def _public(client: httpx.Client) -> None:
    info = json.loads(_read(client, INFO_URL, MAX_BYTES))
    if (
        info.get("id") != DATASET
        or info.get("sha") != REVISION
        or info.get("private") is not False
        or info.get("gated") is not False
    ):
        raise ValueError("MBS sidecar exact public revision differs")


def _object(client: httpx.Client, source: BoundSidecar) -> dict[str, Any]:
    if source.dataset != DATASET or source.revision != REVISION:
        raise ValueError("MBS sidecar source transport binding differs")
    for pin in source.metadata:
        data = _pinned(client, pin.path, pin.sha256, pin.byte_count)
        if not isinstance(json.loads(data), dict):
            raise TypeError("MBS sidecar original metadata shape differs")
    payload = _pinned(
        client, source.source_path, source.sha256, source.byte_count
    )
    report = profile_sidecar(payload, source)
    del payload
    return report


def qualify(
    exact_commit: str, *, transport: httpx.BaseTransport | None = None
) -> dict[str, Any]:
    """Stop before transport unless exact main; verify metadata before payloads."""
    _context(exact_commit)
    sources = load_sidecars(ROOT)
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=120,
        max_bytes=MAX_BYTES,
        max_attempts=1,
        max_redirects=3,
    )
    with httpx.Client(
        transport=transport or BoundIPAddressTransport(policy=policy),
        trust_env=False,
        follow_redirects=True,
        max_redirects=3,
        timeout=120,
        headers={"Accept-Encoding": "identity"},
    ) as client:
        _public(client)
        reports = [_object(client, source) for source in sources]
        _public(client)
    return {
        "schema_id": "global-medicines-atlas.frozen-mbs-sidecar-native-inventory",
        "schema_version": 1,
        "status": "passed",
        "workflow_commit": exact_commit,
        "dataset": DATASET,
        "revision": REVISION,
        "objects": reports,
        "native_values_emitted": False,
        "typed_output_qualified": False,
        "new_sources": 0,
        "new_admissions": 0,
        "new_federated_canaries": 0,
        "publications": 0,
        "rights_conclusion_changed": False,
    }


def _receipt_payload(report: dict[str, Any]) -> bytes:
    payload = (
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if len(payload) > MAX_RESULT_BYTES:
        raise ValueError("sidecar aggregate result bound exceeded")
    return payload


def _failure_category(error: Exception) -> str:
    categories: tuple[tuple[type[Exception], str], ...] = (
        (UnicodeDecodeError, "source-encoding"),
        (ParserSafetyError, "parser-safety"),
        (csv.Error, "csv-grammar"),
        (httpx.HTTPStatusError, "transport-http"),
        (httpx.TransportError, "transport"),
        (ValueError, "validation"),
        (TypeError, "validation"),
    )
    return next(
        (code for kind, code in categories if isinstance(error, kind)),
        "unavailable",
    )


def main(argv: list[str] | None = None) -> int:
    """Write aggregate-only results; never expose source-bearing exceptions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("existing sidecar receipt must be preserved")
    try:
        report = qualify(args.exact_commit)
        payload = _receipt_payload(report)
    except Exception as error:
        report = {
            "schema_version": 1,
            "status": "failed",
            "reason": "sidecar-inventory-did-not-complete",
            "failure_category": _failure_category(error),
            "native_values_emitted": False,
            "publications": 0,
        }
        payload = (json.dumps(report, sort_keys=True) + "\n").encode()
    args.output.write_bytes(payload)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
