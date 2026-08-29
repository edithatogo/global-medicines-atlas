#!/usr/bin/env python3
"""Qualify one CMS Part D payload on an ephemeral hosted runner."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import AnyHttpUrl

from global_medicines_atlas.cms_partd_acquisition import (
    inspect_cms_partd_payload,
    recover_cms_partd_private_archive,
    write_cms_partd_private_archive,
)


def qualify_shard(
    payload: Path,
    *,
    url: AnyHttpUrl,
    family: Literal["formulary", "spending"],
    identity: str,
    hub_path: str,
    expected_sha256: str,
    output: Path,
    qualified_at: datetime,
) -> dict[str, object]:
    """Inspect, project, archive, and restore one exact public payload."""
    if identity != sha256(str(url).encode()).hexdigest():
        raise ValueError("CMS Part D shard identity diverged from source URL")
    evidence = inspect_cms_partd_payload(payload, url=url, family=family)
    if evidence.sha256 != expected_sha256:
        raise ValueError("CMS Part D shard digest diverged from public receipt")

    output.mkdir(parents=True, exist_ok=False)
    payload_row = {
        "identity": identity,
        "family": family,
        "url": str(url),
        "hub_path": hub_path,
        "sha256": evidence.sha256,
        "byte_count": evidence.byte_count,
        "archive_member_count": len(evidence.archive_members),
    }
    member_rows = [
        {
            "identity": identity,
            "payload_sha256": evidence.sha256,
            "source_url": str(url),
            **member.model_dump(mode="json"),
        }
        for member in evidence.archive_members
    ]
    payload_parquet = output / "payload-manifest.parquet"
    member_parquet = output / "archive-members.parquet"
    payload_schema = pa.schema([
        ("identity", pa.string()),
        ("family", pa.string()),
        ("url", pa.string()),
        ("hub_path", pa.string()),
        ("sha256", pa.string()),
        ("byte_count", pa.int64()),
        ("archive_member_count", pa.int64()),
    ])
    member_schema = pa.schema([
        ("identity", pa.string()),
        ("payload_sha256", pa.string()),
        ("source_url", pa.string()),
        ("path", pa.string()),
        ("byte_count", pa.int64()),
        ("compressed_byte_count", pa.int64()),
        ("crc32", pa.string()),
        ("sha256", pa.string()),
    ])
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        pa.Table.from_pylist([payload_row], schema=payload_schema),
        payload_parquet,
    )
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        pa.Table.from_pylist(member_rows, schema=member_schema), member_parquet
    )

    private_archive = output / "private-archive.tar"
    archive_member = f"payloads/{identity}"
    archive_sha256, archive_byte_count = write_cms_partd_private_archive(
        ((archive_member, payload),), private_archive
    )
    recovered = recover_cms_partd_private_archive(
        private_archive,
        output / "clean-room",
        {archive_member: evidence.sha256},
    )
    private_archive.unlink()
    shutil.rmtree(output / "clean-room")
    report: dict[str, object] = {
        "schema_id": "global-medicines-atlas.cms-partd-bronze-shard",
        "schema_version": 1,
        "qualified_at": qualified_at.astimezone(UTC).isoformat(),
        **payload_row,
        "payload_manifest_sha256": sha256(
            payload_parquet.read_bytes()
        ).hexdigest(),
        "archive_member_manifest_sha256": sha256(
            member_parquet.read_bytes()
        ).hexdigest(),
        "private_archive_sha256": archive_sha256,
        "private_archive_byte_count": archive_byte_count,
        "clean_room_recovered_payload_count": recovered,
        "source_bytes_committed": False,
        "source_bytes_retained_on_runner": False,
        "agreement_for_use_applies": True,
    }
    (output / "qualification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--url", type=AnyHttpUrl, required=True)
    parser.add_argument(
        "--family", choices=("formulary", "spending"), required=True
    )
    parser.add_argument("--identity", required=True)
    parser.add_argument("--hub-path", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--qualified-at", type=datetime.fromisoformat, required=True
    )
    args = parser.parse_args()
    report = qualify_shard(
        args.payload,
        url=args.url,
        family=args.family,
        identity=args.identity,
        hub_path=args.hub_path,
        expected_sha256=args.expected_sha256,
        output=args.output,
        qualified_at=args.qualified_at,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
