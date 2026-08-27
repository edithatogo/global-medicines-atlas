"""Versioned source-shape contracts used after generic Bronze inspection."""

from __future__ import annotations

import codecs
import csv
import json
import tarfile
import zipfile
from enum import StrEnum
from fnmatch import fnmatch
from io import BytesIO, StringIO

from pydantic import Field, model_validator

from .archive_safety import (
    ArchivePolicy,
    ArchiveSafetyError,
    inspect_gzip,
    inspect_tar,
    inspect_zip,
)
from .models import FrozenModel
from .parser_safety import parse_xml


class JsonContainer(StrEnum):
    OBJECT = "object"
    ARRAY = "array"
    JSON_LINES = "json_lines"


class ProfileMismatchAction(StrEnum):
    QUARANTINE = "quarantine"
    WARN = "warn"


class BronzeAdmissionProfile(FrozenModel):
    """Optional source-native shape contract; absent means generic policy."""

    schema_version: int = Field(default=1, ge=1, le=1)
    profile_id: str = Field(min_length=1)
    expected_media: tuple[str, ...] = ()
    json_containers: tuple[JsonContainer, ...] = (
        JsonContainer.OBJECT,
        JsonContainer.ARRAY,
        JsonContainer.JSON_LINES,
    )
    csv_delimiter: str | None = None
    csv_encoding: str = "utf-8"
    csv_required_headers: tuple[str, ...] = ()
    xml_root: str | None = None
    xml_namespace: str | None = None
    archive_type: str | None = None
    archive_member_patterns: tuple[str, ...] = ()
    document_or_opaque: bool = False
    max_size_bytes: int | None = Field(default=None, ge=1)
    max_member_count: int | None = Field(default=None, ge=1)
    max_expansion_ratio: float | None = Field(default=None, gt=0)
    max_nesting: int | None = Field(default=None, ge=1)
    mismatch_action: ProfileMismatchAction = ProfileMismatchAction.QUARANTINE

    @model_validator(mode="after")
    def validate_shape_contract(self) -> BronzeAdmissionProfile:
        if self.csv_delimiter is not None and len(self.csv_delimiter) != 1:
            raise ValueError("CSV delimiter must be one character")
        if self.archive_type is not None and self.archive_type not in {
            "zip",
            "tar",
            "gzip",
        }:
            raise ValueError("archive_type must be zip, tar, or gzip")
        try:
            codecs.lookup(self.csv_encoding)
        except LookupError as error:
            raise ValueError(
                "csv_encoding must name a registered codec"
            ) from error
        return self


def _inspect_profile_archive(
    payload: bytes,
    sniffed_kind: str,
    profile: BronzeAdmissionProfile,
) -> int:
    default_policy = ArchivePolicy()
    policy = ArchivePolicy(
        max_archive_bytes=profile.max_size_bytes
        or default_policy.max_archive_bytes,
        max_entries=profile.max_member_count or default_policy.max_entries,
        max_decompression_ratio=profile.max_expansion_ratio
        or default_policy.max_decompression_ratio,
        max_path_depth=profile.max_nesting or default_policy.max_path_depth,
    )
    if sniffed_kind == "zip":
        return inspect_zip(payload, policy)
    if sniffed_kind == "tar":
        return inspect_tar(payload, policy)
    inspect_gzip(payload, policy)
    return 1


def validate_source_profile(  # ruff: ignore[too-many-return-statements, too-many-branches]
    payload: bytes,
    *,
    sniffed_kind: str,
    profile: BronzeAdmissionProfile,
) -> tuple[bool, str]:
    """Return structural compatibility without changing source bytes."""

    if (
        profile.max_size_bytes is not None
        and len(payload) > profile.max_size_bytes
    ):
        return False, "payload exceeds profile size limit"
    if profile.expected_media and sniffed_kind not in profile.expected_media:
        return (
            False,
            f"profile expects media {profile.expected_media}, got {sniffed_kind}",
        )
    if profile.document_or_opaque:
        return True, "profile marks payload as document or opaque bytes"
    if sniffed_kind == "json":
        try:
            value = json.loads(payload)
            shape = (
                JsonContainer.OBJECT
                if isinstance(value, dict)
                else JsonContainer.ARRAY
                if isinstance(value, list)
                else None
            )
        except UnicodeDecodeError, ValueError:
            lines = [line for line in payload.splitlines() if line.strip()]
            try:
                if not lines or any(
                    not isinstance(json.loads(line), (dict, list))
                    for line in lines
                ):
                    return False, "payload is not valid JSON or JSON Lines"
            except UnicodeDecodeError, ValueError:
                return False, "payload is not valid JSON or JSON Lines"
            shape = JsonContainer.JSON_LINES
        if shape not in profile.json_containers:
            return False, f"JSON container {shape} is not permitted"
    elif sniffed_kind == "csv":
        try:
            text = payload.decode(profile.csv_encoding)
            rows = list(
                csv.reader(
                    StringIO(text), delimiter=profile.csv_delimiter or ","
                )
            )
        except (UnicodeDecodeError, csv.Error, ValueError) as error:
            return False, f"CSV profile validation failed: {error}"
        if profile.csv_required_headers and (
            not rows or not set(profile.csv_required_headers).issubset(rows[0])
        ):
            return False, "CSV required headers are missing"
    elif sniffed_kind == "xml":
        try:
            root = parse_xml(payload)
        except ValueError as error:
            return False, str(error)
        if (
            profile.xml_root is not None
            and root.tag.split("}")[-1] != profile.xml_root
        ):
            return False, f"XML root {root.tag!r} is not {profile.xml_root!r}"
        if profile.xml_namespace is not None and not root.tag.startswith(
            "{" + profile.xml_namespace + "}"
        ):
            return False, "XML namespace does not match profile"
    elif sniffed_kind in {"zip", "tar", "gzip"}:
        if (
            profile.archive_type is not None
            and sniffed_kind != profile.archive_type
        ):
            return False, f"archive type {sniffed_kind} does not match profile"
        try:
            _inspect_profile_archive(payload, sniffed_kind, profile)
        except ArchiveSafetyError as error:
            return False, str(error)
        if profile.archive_member_patterns:
            if sniffed_kind == "zip":
                with zipfile.ZipFile(BytesIO(payload)) as archive:
                    names = archive.namelist()
            elif sniffed_kind == "tar":
                with tarfile.open(
                    fileobj=BytesIO(payload), mode="r:*"
                ) as archive:
                    names = archive.getnames()
            else:
                names = ()
            if names and any(
                not any(
                    fnmatch(name, pattern)
                    for pattern in profile.archive_member_patterns
                )
                for name in names
            ):
                return False, "archive member is outside profile patterns"
    return True, "payload matches source profile"
