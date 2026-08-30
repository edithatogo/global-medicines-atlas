#!/usr/bin/env python3
"""Observe owner-visible Hub metadata twice; never acquire or publish payloads."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed read-only CLI argv, no shell
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.hf_estate import (
    COLLECTION_LIMIT,
    KINDS,
    REPOSITORY_LIMIT,
    OwnerVisibilityEvidence,
    build_estate_snapshot,
)

MAX_OUTPUT_BYTES = 8 * 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 120
OWNER_ARGUMENT_INDEX = 6


def metadata_command(command: list[str]) -> bytes:
    """Bound metadata capture without echoing CLI errors or sensitive fields."""
    if (
        os.environ.get("HF_ENDPOINT", "https://huggingface.co")
        != "https://huggingface.co"
    ):
        raise ValueError(
            "estate observation requires the official Hub endpoint"
        )
    allowed = command == ["hf", "auth", "whoami"]
    if len(command) > OWNER_ARGUMENT_INDEX and re.fullmatch(
        r"[A-Za-z0-9_-]+", command[OWNER_ARGUMENT_INDEX]
    ):
        allowed = allowed or any(
            command == listing_command(kind, command[OWNER_ARGUMENT_INDEX])
            for kind in KINDS
        )
    if not allowed:
        raise ValueError("only exact read-only metadata commands are permitted")
    with tempfile.TemporaryFile() as output:
        with subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed read-only CLI argv, no shell
            command,
            stdout=output,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        ) as process:
            deadline = time.monotonic() + COMMAND_TIMEOUT_SECONDS
            while process.poll() is None:
                if (
                    output.tell() > MAX_OUTPUT_BYTES
                    or time.monotonic() > deadline
                ):
                    process.kill()
                    process.wait()
                    raise ValueError(
                        "metadata command exceeded byte or time bound"
                    )
                time.sleep(0.05)
            if process.returncode != 0:
                raise ValueError(
                    "metadata command failed; no raw diagnostic retained"
                )
        if output.tell() > MAX_OUTPUT_BYTES:
            raise ValueError("metadata command exceeded byte bound")
        output.seek(0)
        return output.read(MAX_OUTPUT_BYTES + 1)


def listing_command(kind: str, owner: str) -> list[str]:
    """Build a fixed read-only CLI request with no arbitrary flags."""
    plural = {
        "collection": "collections",
        "dataset": "datasets",
        "model": "models",
        "space": "spaces",
    }[kind]
    command = ["hf", plural, "list", "--format", "json"]
    if kind == "collection":
        command.extend(["--owner", owner, "--limit", str(COLLECTION_LIMIT)])
    else:
        fields = "sha,private" if kind == "space" else "sha,private,gated"
        command.extend([
            "--author",
            owner,
            "--limit",
            str(REPOSITORY_LIMIT),
            "--expand",
            fields,
        ])
    return command


def observe(owner: str) -> dict[str, list[dict[str, Any]]]:
    """Request bounded listings, including explicit visibility and Git heads."""
    result: dict[str, list[dict[str, Any]]] = {}
    for kind in KINDS:
        command = listing_command(kind, owner)
        rows = json.loads(metadata_command(command))
        if not isinstance(rows, list) or not all(
            isinstance(row, dict) for row in cast("list[object]", rows)
        ):
            raise ValueError("metadata listing must be a JSON object array")
        result[kind] = cast("list[dict[str, Any]]", rows)
    return result


def main() -> int:
    """Generate a public-safe metadata snapshot only after a stable double scan."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--visibility-evidence", type=Path)
    args = parser.parse_args()
    identity = metadata_command(["hf", "auth", "whoami"]).decode().split()
    account = next(
        (
            word.removeprefix("user=")
            for word in identity
            if word.startswith("user=")
        ),
        None,
    )
    if account != args.owner:
        raise ValueError("matching authenticated owner required")
    visibility = None
    if args.visibility_evidence is not None:
        with args.visibility_evidence.open("rb") as evidence_file:
            content = evidence_file.read(MAX_OUTPUT_BYTES + 1)
        if len(content) > MAX_OUTPUT_BYTES:
            raise ValueError("visibility evidence exceeded byte bound")
        try:
            visibility = OwnerVisibilityEvidence.model_validate_json(content)
        except ValueError:
            raise ValueError(
                "invalid visibility evidence; no raw diagnostic retained"
            ) from None
    first = observe(args.owner)
    second = observe(args.owner)
    snapshot = build_estate_snapshot(
        args.owner,
        first,
        second,
        observed_at=datetime.now(UTC),
        authenticated_owner=account,
        visibility_evidence=visibility,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({
            "entries": len(snapshot.entries),
            "counts": {row.kind: row.count for row in snapshot.enumerations},
            "scope": snapshot.enumeration_scope,
        })
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
