"""Deterministic generation of reviewed, publication-ready dataset packages."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, cast

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from .publication_contracts import (
    PublicationPackage,
    PublicationState,
    PublicationVerificationReceipt,
    RightsDisposition,
)

_PARQUET_NAME = "data/medicines.parquet"
_SOURCE_FIELD = "source_id"


class PackageGenerationError(ValueError):
    """Raised when reviewed input cannot safely become a release package."""


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    """One immutable package member."""

    path: str
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def size(self) -> int:
        return len(self.content)


@dataclass(frozen=True, slots=True)
class GeneratedPublicationPackage:
    """A deterministic set of files with a content-addressed identity."""

    files: tuple[GeneratedFile, ...]

    def __post_init__(self) -> None:
        paths = tuple(item.path for item in self.files)
        if paths != tuple(sorted(paths)):
            raise PackageGenerationError("generated files must be path-sorted")
        if len(paths) != len(set(paths)):
            raise PackageGenerationError("generated file paths must be unique")

    def file(self, path: str) -> GeneratedFile:
        for item in self.files:
            if item.path == path:
                return item
        raise KeyError(path)

    @property
    def sha256(self) -> str:
        digest = hashlib.sha256()
        for item in self.files:
            digest.update(item.path.encode())
            digest.update(b"\0")
            digest.update(item.sha256.encode())
            digest.update(b"\n")
        return digest.hexdigest()


def generate_publication_package(
    contract: PublicationPackage,
    qualification: PublicationVerificationReceipt,
    rows: Iterable[Mapping[str, Any]],
) -> GeneratedPublicationPackage:
    """Seal staged bytes only when qualification binds to their exact identity."""

    staged = stage_publication_package(contract, rows)
    _require_qualified(staged, qualification)
    preliminary = {item.path: item.content for item in staged.files}
    preliminary["metadata/qualification.json"] = _canonical_json(
        qualification.model_dump(mode="json")
    )
    checksums = _checksum_lines(preliminary)
    preliminary["SHA256SUMS"] = checksums
    preliminary["package-manifest.json"] = _manifest_bytes(
        contract,
        preliminary,
        staged_sha256=staged.sha256,
    )
    files = tuple(
        GeneratedFile(path=path, content=content)
        for path, content in sorted(preliminary.items())
    )
    return GeneratedPublicationPackage(files=files)


def stage_publication_package(
    contract: PublicationPackage,
    rows: Iterable[Mapping[str, Any]],
) -> GeneratedPublicationPackage:
    """Create deterministic bytes that privacy and content checks must review."""

    materialized = tuple(dict(row) for row in rows)
    _validate_rows(contract, materialized)
    parquet = _canonical_parquet(contract, materialized)
    staged: dict[str, bytes] = {
        _PARQUET_NAME: parquet,
        "metadata/citations.json": _canonical_json({
            "sources": [
                {
                    "retrieved_at": item.retrieved_at.isoformat(),
                    "source_id": item.source_id,
                    "source_sha256": item.source_sha256,
                    "source_uri": item.source_uri,
                }
                for item in sorted(
                    contract.dataset_card.provenance,
                    key=lambda value: value.source_id,
                )
            ]
        }),
        "metadata/coverage.json": _canonical_json({
            "coverage": [
                item.model_dump(mode="json")
                for item in sorted(
                    contract.dataset_card.coverage,
                    key=lambda value: (value.scope, value.jurisdictions),
                )
            ]
        }),
        "metadata/croissant.json": _croissant_bytes(contract, parquet),
        "metadata/data-dictionary.json": _canonical_json(
            contract.data_dictionary.model_dump(mode="json")
        ),
        "metadata/dataset-card.json": _canonical_json(
            contract.dataset_card.model_dump(mode="json")
        ),
    }
    files = tuple(
        GeneratedFile(path=path, content=content)
        for path, content in sorted(staged.items())
    )
    return GeneratedPublicationPackage(files=files)


def _require_qualified(
    staged: GeneratedPublicationPackage,
    receipt: PublicationVerificationReceipt,
) -> None:
    if receipt.state is not PublicationState.QUALIFIED:
        raise PackageGenerationError(
            "package generation requires a qualified receipt"
        )
    if receipt.package_sha256 != staged.sha256:
        raise PackageGenerationError(
            "qualification receipt is not bound to the exact staged bytes"
        )


def _validate_rows(
    contract: PublicationPackage,
    rows: tuple[dict[str, Any], ...],
) -> None:
    fields = tuple(item.name for item in contract.data_dictionary.fields)
    if _SOURCE_FIELD not in fields:
        raise PackageGenerationError("data dictionary must declare source_id")
    expected = set(fields)
    permitted = {
        item.source_id
        for item in contract.dataset_card.rights
        if item.disposition is RightsDisposition.PERMITTED
    }
    for index, row in enumerate(rows):
        if set(row) != expected:
            raise PackageGenerationError(
                f"row {index} does not exactly match the data dictionary"
            )
        source_id = row.get(_SOURCE_FIELD)
        if not isinstance(source_id, str) or source_id not in permitted:
            raise PackageGenerationError(
                f"row {index} has no explicitly permitted source"
            )


def _canonical_parquet(
    contract: PublicationPackage,
    rows: tuple[dict[str, Any], ...],
) -> bytes:
    columns = [item.name for item in contract.data_dictionary.fields]
    schema = {
        item.name: _polars_type(item.data_type)
        for item in contract.data_dictionary.fields
    }
    frame = pl.DataFrame(rows, schema=schema, orient="row", strict=True)
    for field in contract.data_dictionary.fields:
        if not field.nullable and frame[field.name].null_count():
            raise PackageGenerationError(
                f"non-nullable field contains nulls: {field.name}"
            )
    if frame.height:
        frame = frame.sort(
            columns,
            nulls_last=True,
            maintain_order=True,
        )
    table = frame.to_arrow().select(columns)
    table = table.replace_schema_metadata(None)
    sink = pa.BufferOutputStream()
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        table,
        sink,
        compression="zstd",
        compression_level=9,
        data_page_version="2.0",
        use_dictionary=False,
        write_page_index=False,
        write_statistics=True,
        version="2.6",
    )
    return sink.getvalue().to_pybytes()


def _polars_type(data_type: str) -> pl.DataType:
    normalized = data_type.casefold().replace("-", "").replace("_", "")
    supported: dict[str, pl.DataType] = {
        "bool": pl.Boolean(),
        "boolean": pl.Boolean(),
        "date": pl.Date(),
        "datetime": pl.Datetime("us", "UTC"),
        "float": pl.Float64(),
        "float64": pl.Float64(),
        "int": pl.Int64(),
        "int64": pl.Int64(),
        "integer": pl.Int64(),
        "str": pl.String(),
        "string": pl.String(),
    }
    try:
        return supported[normalized]
    except KeyError as error:
        raise PackageGenerationError(
            f"unsupported reviewed data type: {data_type}"
        ) from error


def _croissant_bytes(
    contract: PublicationPackage,
    parquet: bytes,
) -> bytes:
    payload = cast(
        "dict[str, object]",
        json.loads(contract.croissant.model_dump_json(by_alias=True)),
    )
    distributions = cast("list[dict[str, object]]", payload["distributions"])
    matches = [
        item for item in distributions if item.get("name") == _PARQUET_NAME
    ]
    if len(matches) != 1:
        raise PackageGenerationError(
            "Croissant must declare the canonical Parquet distribution"
        )
    matches[0]["content_url"] = _PARQUET_NAME
    matches[0]["encoding_format"] = "application/vnd.apache.parquet"
    matches[0]["sha256"] = hashlib.sha256(parquet).hexdigest()
    return _canonical_json(payload)


def _checksum_lines(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{hashlib.sha256(content).hexdigest()}  {path}\n"
        for path, content in sorted(files.items())
    ).encode()


def _manifest_bytes(
    contract: PublicationPackage,
    files: Mapping[str, bytes],
    *,
    staged_sha256: str,
) -> bytes:
    return _canonical_json({
        "contract_sha256": contract.sha256(),
        "files": [
            {
                "path": path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
            for path, content in sorted(files.items())
        ],
        "format_version": "1",
        "staged_sha256": staged_sha256,
    })


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
