"""File-backed historical MBS member inventory without native-name disclosure."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZipFile

from .archive_safety import (
    DEFAULT_ARCHIVE_POLICY,
    ArchivePolicy,
    verify_zip_file,
)
from .mbs_archive_inventory import DATASET, REVISION, BoundArchive

# Only these exact retained raw objects need a larger compressed-file bound.
# Member sizes, expansion, path, encryption and decompression limits stay fixed.
LARGE_IDENTITIES = {
    (
        "raw/mbs/utilisation/demographics/mbs-demographics-historical-2003-2007-.zip",
        "9f649eb3c7c3fdc0c3b362d34f00ffb2e9f3374ec4629e9dd15a8c8ddc1d7c00",
        284302149,
    ),
    (
        "raw/mbs/utilisation/demographics/mbs-demographics-historical-2008-2012.zip",
        "7f7eeb62fbc6191ab76e3dcf6cc602aa9438b1eec037d7e5c385fe131acd5355",
        358227575,
    ),
}
MAX_REPORT_BYTES = 8 * 1024 * 1024
PREFIX_BYTES = 8
SUFFIX_HINTS = {
    ".csv",
    ".xls",
    ".xlsx",
    ".xml",
    ".txt",
    ".zip",
    ".pdf",
    ".doc",
    ".docx",
}


def archive_policy(source: BoundArchive) -> ArchivePolicy:
    """Keep default bounds except exact compressed sizes of two frozen objects."""
    identity = (source.source_path, source.source_sha256, source.source_bytes)
    if (
        source.dataset == DATASET
        and source.revision == REVISION
        and identity in LARGE_IDENTITIES
    ):
        return replace(
            DEFAULT_ARCHIVE_POLICY, max_archive_bytes=source.source_bytes
        )
    return DEFAULT_ARCHIVE_POLICY


def _magic(prefix: bytes) -> str:
    signatures = (
        (bytes.fromhex("d0cf11e0a1b11ae1"), "compound-document-signature"),
        (b"PK\x03\x04", "zip-container-signature"),
        (b"PK\x05\x06", "zip-container-signature"),
        (b"%PDF-", "pdf-signature"),
        (b"\x1f\x8b", "gzip-signature"),
        (b"BZh", "bzip2-signature"),
    )
    return next(
        (
            kind
            for signature, kind in signatures
            if prefix.startswith(signature)
        ),
        "unknown",
    )


def profile_archive_members(path: Path, source: BoundArchive) -> dict[str, Any]:
    """Verify every member stream and then inspect only a bounded magic prefix.

    The caller must supply a private immutable staged file on protected Actions
    for real sources. No extraction occurs. Neither a suffix nor a magic hint
    qualifies an XLS/OOXML/CSV schema, date era or table interpretation.
    Native names contribute only to hashed identities and the prior manifest
    digest, so no source-native member names or content values leave the worker.
    """
    policy = archive_policy(source)
    receipt = verify_zip_file(
        path,
        expected_sha256=source.source_sha256,
        expected_size=source.source_bytes,
        policy=policy,
    )
    native = [
        (member.path, member.sha256, member.size_bytes)
        for member in receipt.members
    ]
    native_digest = hashlib.sha256(
        json.dumps(native, separators=(",", ":")).encode()
    ).hexdigest()
    if source.prior_member_count is not None and (
        source.prior_member_count != len(receipt.members)
        or source.prior_expanded_bytes != receipt.total_uncompressed_bytes
        or source.prior_inventory_sha256 != native_digest
    ):
        raise ValueError("MBS archive prior member inventory differs")
    reports: list[dict[str, Any]] = []
    kinds: Counter[str] = Counter()
    with ZipFile(path) as archive:
        lookup = {
            PurePosixPath(info.filename.replace("\\", "/")).as_posix(): info
            for info in archive.infolist()
            if not info.is_dir()
        }
        for ordinal, member in enumerate(receipt.members):
            with archive.open(lookup[member.path]) as stream:
                prefix = stream.read(PREFIX_BYTES)
            kind = _magic(prefix)
            suffix = PurePosixPath(member.path).suffix.lower()
            kinds[kind] += 1
            reports.append({
                "ordinal": ordinal,
                "verified_relative_path_sha256": hashlib.sha256(
                    member.path.encode()
                ).hexdigest(),
                "sha256": member.sha256,
                "bytes": member.size_bytes,
                "declared_suffix_hint": suffix
                if suffix in SUFFIX_HINTS
                else "unknown",
                "magic_kind": kind,
            })
    report = {
        "schema_id": "global-medicines-atlas.mbs-historical-member-inventory",
        "schema_version": 1,
        "source_path": source.source_path,
        "source_sha256": receipt.archive_sha256,
        "source_bytes": source.source_bytes,
        "acquisition_id": source.acquisition_id,
        "b1_sha256": source.b1_sha256,
        "b2_sha256": source.b2_sha256,
        "prior_status": source.prior_status,
        "container_integrity_verified": True,
        "member_count": len(receipt.members),
        "expanded_bytes": receipt.total_uncompressed_bytes,
        "native_member_inventory_sha256": native_digest,
        "compressed_byte_limit": policy.max_archive_bytes,
        "members": reports,
        "magic_kind_counts": dict(sorted(kinds.items())),
        "member_formats_qualified": False,
        "native_values_or_names_emitted": False,
        "new_admissions": 0,
        "publications": 0,
    }
    if (
        len(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
        > MAX_REPORT_BYTES
    ):
        raise ValueError("MBS archive complete report byte bound exceeded")
    return report
