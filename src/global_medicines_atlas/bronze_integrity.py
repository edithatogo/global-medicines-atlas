# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false

"""Inspect untrusted bronze bytes without mutating them.

Landing preserves forensic payloads and receipts. This module classifies
truncation, corruption, archive hostility, media mismatch, schema poisoning,
replays, and checksum failures so admission can quarantine processing.
"""

from __future__ import annotations

import csv
import json
from hashlib import sha256
from io import StringIO

from pydantic import Field

from .archive_safety import (
    WINDOWS_RESERVED_NAMES,
    ArchiveSafetyError,
    inspect_gzip,
    inspect_tar,
    inspect_zip,
)
from .models import FrozenModel
from .parser_safety import ParserSafetyError, parse_xml
from .receipts import SHA256_PATTERN

POISON_FIELD_NAMES = frozenset({
    "acquisition_id",
    "content_id",
    "payload_sha256",
    "receipt_digest",
    "__proto__",
    "constructor",
    "prototype",
})
HOSTILE_FILENAME_CHARS = frozenset({"\x00", "/", "\\", ":"})


class IntegrityFinding(FrozenModel):
    """One integrity check against preserved bytes."""

    check_id: str = Field(min_length=1)
    passed: bool
    message: str = Field(min_length=1)


class IntegrityInspection(FrozenModel):
    """Forensic inspection bound to a content digest, never to Iceberg."""

    content_id: str = Field(pattern=SHA256_PATTERN)
    sniffed_kind: str
    findings: tuple[IntegrityFinding, ...]
    reason_codes: tuple[str, ...] = ()

    @property
    def blocking(self) -> bool:
        """True when processing must fail closed."""

        return bool(self.reason_codes)


TAR_MAGIC = b"ustar"
TAR_MAGIC_END = 262
CSV_SNIFF_BYTES = 1024
MAX_POISON_DEPTH = 8


class _Collector:
    """Accumulates forensic findings without mutating payload bytes."""

    def __init__(self) -> None:
        self.findings: list[IntegrityFinding] = []
        self.reasons: list[str] = []

    def fail(self, check_id: str, code: str, message: str) -> None:
        self.findings.append(
            IntegrityFinding(
                check_id=check_id,
                passed=False,
                message=message,
            )
        )
        self.reasons.append(code)

    def ok(self, check_id: str, message: str) -> None:
        self.findings.append(
            IntegrityFinding(
                check_id=check_id,
                passed=True,
                message=message,
            )
        )


def sniff_payload_kind(payload: bytes) -> str:
    """Classify payload kind from magic bytes; unknown stays bytes."""

    kind = "bytes"
    if payload.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        kind = "zip"
    elif len(payload) > TAR_MAGIC_END and payload[257:TAR_MAGIC_END] == TAR_MAGIC:
        kind = "tar"
    elif payload.startswith(b"\x1f\x8b"):
        kind = "gzip"
    else:
        stripped = payload.lstrip()
        if stripped.startswith((b"{", b"[")):
            kind = "json"
        elif stripped.startswith((b"<", b"<?xml")):
            kind = "xml"
        elif (
            b"," in payload[:CSV_SNIFF_BYTES]
        ):
            kind = "csv"
    return kind


def _normalize_media(declared_media: str | None) -> str | None:
    if declared_media is None:
        return None
    lowered = declared_media.lower().rsplit(".", 1)[-1].lstrip(".")
    aliases = {
        "json": "json",
        "xml": "xml",
        "csv": "csv",
        "zip": "zip",
        "gz": "gzip",
        "gzip": "gzip",
        "tgz": "tar",
        "tar": "tar",
        "bin": None,
    }
    return aliases.get(lowered, lowered or None)


def _hostile_filename(name: str) -> str | None:
    if not name or name in {".", ".."}:
        return "empty or relative filename"
    if any(char in name for char in HOSTILE_FILENAME_CHARS):
        return "path separator or NUL in filename"
    stem = name.rstrip(" .").split(".", maxsplit=1)[0].upper()
    if stem in WINDOWS_RESERVED_NAMES:
        return "Windows reserved device name"
    if ".." in name.replace("\\", "/").split("/"):
        return "path traversal in filename"
    return None


def _walk_poison_keys(value: object, *, depth: int = 0) -> str | None:
    if depth > MAX_POISON_DEPTH:
        return "json nesting exceeded integrity walk"
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            if key in POISON_FIELD_NAMES:
                return f"poison field {key}"
            nested = _walk_poison_keys(item, depth=depth + 1)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for item in value[:64]:
            nested = _walk_poison_keys(item, depth=depth + 1)
            if nested is not None:
                return nested
    return None


def _check_checksum(
    collector: _Collector,
    *,
    content_id: str,
    expected_sha256: str | None,
) -> None:
    if expected_sha256 is not None and expected_sha256 != content_id:
        collector.fail(
            "checksum",
            "checksum_mismatch",
            "payload digest does not match expected checksum",
        )
        return
    collector.ok(
        "checksum",
        "payload digest matches declared checksum or is unbound",
    )


def _check_length(
    collector: _Collector,
    payload: bytes,
    declared_length: int | None,
) -> None:
    if declared_length is None:
        collector.ok("length", "no declared length to compare")
        return
    if len(payload) < declared_length:
        collector.fail(
            "length",
            "truncated_download",
            "payload shorter than declared Content-Length",
        )
        return
    if len(payload) > declared_length:
        collector.fail(
            "length",
            "content_length_mismatch",
            "payload longer than declared Content-Length",
        )
        return
    collector.ok("length", "payload length matches declared length")


def _check_filename(
    collector: _Collector,
    declared_filename: str | None,
) -> None:
    if declared_filename is None:
        collector.ok("filename", "no declared filename")
        return
    hostile = _hostile_filename(declared_filename)
    if hostile is None:
        collector.ok("filename", "declared filename is portable")
        return
    collector.fail("filename", "hostile_filename", hostile)


def _check_media(
    collector: _Collector,
    declared_media: str | None,
    sniffed: str,
) -> None:
    declared = _normalize_media(declared_media)
    if (
        declared is not None
        and sniffed not in {declared, "bytes"}
        and not (declared == "tar" and sniffed == "gzip")
    ):
        collector.fail(
            "media",
            "mime_extension_mismatch",
            f"declared {declared} but sniffed {sniffed}",
        )
        return
    collector.ok("media", "declared media is compatible with sniffed kind")


def _check_history(
    collector: _Collector,
    *,
    content_id: str,
    previous_content_id: str | None,
    previous_acquisition_id: str | None,
    acquisition_id: str | None,
) -> None:
    if previous_content_id is not None and previous_content_id != content_id:
        collector.fail(
            "mutation",
            "unexpected_source_mutation",
            "payload digest changed against a prior content_id",
        )
    else:
        collector.ok("mutation", "no unexpected content mutation")
    replayed = (
        previous_acquisition_id is not None
        and acquisition_id is not None
        and previous_acquisition_id == acquisition_id
    )
    if not replayed:
        collector.ok("replay", "acquisition identity is not a colliding replay")
        return
    if previous_content_id != content_id:
        collector.fail(
            "replay",
            "replayed_acquisition",
            "same acquisition_id presented with different bytes",
        )
        return
    collector.fail(
        "replay",
        "replayed_acquisition",
        "identical acquisition event was replayed",
    )


def _check_identity(
    collector: _Collector,
    *,
    payload: bytes,
    content_id: str,
    expected_sha256: str | None,
    declared_length: int | None,
    declared_filename: str | None,
    declared_media: str | None,
    sniffed: str,
    previous_content_id: str | None,
    previous_acquisition_id: str | None,
    acquisition_id: str | None,
) -> None:
    _check_checksum(
        collector,
        content_id=content_id,
        expected_sha256=expected_sha256,
    )
    _check_length(collector, payload, declared_length)
    _check_filename(collector, declared_filename)
    _check_media(collector, declared_media, sniffed)
    _check_history(
        collector,
        content_id=content_id,
        previous_content_id=previous_content_id,
        previous_acquisition_id=previous_acquisition_id,
        acquisition_id=acquisition_id,
    )


def _check_archive(collector: _Collector, payload: bytes, sniffed: str) -> None:
    if sniffed == "zip":
        try:
            inspect_zip(payload)
        except ArchiveSafetyError as error:
            collector.fail(
                "archive",
                "malicious_or_corrupt_archive",
                str(error),
            )
            return
        collector.ok("archive", "zip members are within safety policy")
        return
    if sniffed not in {"tar", "gzip"}:
        return
    try:
        inspect_tar(payload)
    except ArchiveSafetyError:
        if sniffed != "gzip":
            collector.fail(
                "archive",
                "malicious_or_corrupt_archive",
                "tar archive failed safety policy",
            )
            return
        try:
            inspect_gzip(payload)
        except ArchiveSafetyError as error:
            collector.fail(
                "archive",
                "malicious_or_corrupt_archive",
                str(error),
            )
            return
        collector.ok("archive", "gzip stream is within safety policy")
        return
    collector.ok("archive", "tar members are within safety policy")


def _check_json(collector: _Collector, payload: bytes) -> None:
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        collector.fail(
            "parse",
            "malformed_payload",
            str(error) or "invalid JSON",
        )
        return
    poison = _walk_poison_keys(parsed)
    if poison is None:
        collector.ok("parse", "JSON parsed without poison identity fields")
        return
    collector.fail("schema", "schema_poisoning", poison)


def _check_xml(collector: _Collector, payload: bytes) -> None:
    try:
        parse_xml(payload)
    except ParserSafetyError as error:
        collector.fail("parse", "malformed_payload", str(error))
        return
    collector.ok("parse", "XML parsed under fail-closed policy")


def _check_csv(collector: _Collector, payload: bytes) -> None:
    if b"\x00" in payload:
        collector.fail("parse", "malformed_payload", "CSV contains NUL bytes")
        return
    try:
        rows = list(csv.reader(StringIO(payload.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as error:
        collector.fail(
            "parse",
            "malformed_payload",
            str(error) or "invalid CSV",
        )
        return
    if not rows:
        collector.fail("parse", "malformed_payload", "CSV has no rows")
        return
    collector.ok("parse", "CSV parsed without NUL bytes")


def _check_document(
    collector: _Collector,
    payload: bytes,
    sniffed: str,
) -> None:
    if sniffed == "json":
        _check_json(collector, payload)
        return
    if sniffed == "xml":
        _check_xml(collector, payload)
        return
    if sniffed == "csv":
        _check_csv(collector, payload)
        return
    collector.ok("parse", "opaque bytes preserved without parser claim")


def inspect_untrusted_payload(
    payload: bytes,
    *,
    declared_media: str | None = None,
    declared_filename: str | None = None,
    expected_sha256: str | None = None,
    declared_length: int | None = None,
    previous_content_id: str | None = None,
    previous_acquisition_id: str | None = None,
    acquisition_id: str | None = None,
) -> IntegrityInspection:
    """Inspect bytes in place; never rewrite or delete the payload."""

    content_id = sha256(payload).hexdigest()
    sniffed = sniff_payload_kind(payload)
    collector = _Collector()
    _check_identity(
        collector,
        payload=payload,
        content_id=content_id,
        expected_sha256=expected_sha256,
        declared_length=declared_length,
        declared_filename=declared_filename,
        declared_media=declared_media,
        sniffed=sniffed,
        previous_content_id=previous_content_id,
        previous_acquisition_id=previous_acquisition_id,
        acquisition_id=acquisition_id,
    )
    _check_archive(collector, payload, sniffed)
    _check_document(collector, payload, sniffed)
    return IntegrityInspection(
        content_id=content_id,
        sniffed_kind=sniffed,
        findings=tuple(collector.findings),
        reason_codes=tuple(dict.fromkeys(collector.reasons)),
    )
