"""Append-only evidence for one completed Bronze transformation run."""

from __future__ import annotations

import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal, Self

import orjson
import pyarrow as pa
from pydantic import AwareDatetime, Field, model_validator

from .models import FrozenModel
from .receipts import SHA256_PATTERN

ROOT = Path(__file__).resolve().parents[2]
TRANSFORMATION_DIR = "transformations"
PARSER_IDENTITY = "utf-8-replace"
TRANSFORMATION_IDENTITY = "gma.bronze.source-faithful-parquet.v1"
PARQUET_SCHEMA_VERSION = "bronze-parquet-v1"
MANIFEST_PARSER_IDENTITY = "gma.acquisition-receipt.v2"
MANIFEST_TRANSFORMATION_IDENTITY = "gma.bronze.acquisition-manifest.v1"
MANIFEST_SCHEMA_VERSION = "bronze-acquisition-manifest-v1"
SOURCE_RECORDS_TRANSFORMATION_IDENTITY = "gma.bronze.source-records.v1"
SOURCE_RECORDS_SCHEMA_VERSION = "bronze-source-records-v1"


class TransformationOutput(FrozenModel):
    """Identity of the actual completed output file."""

    uri: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA256_PATTERN)
    byte_count: int = Field(ge=0)


class TransformationRunReceipt(FrozenModel):
    """Content-bound record of a parser/transformation execution."""

    schema_id: Literal["global-medicines-atlas.transformation-run"] = (
        "global-medicines-atlas.transformation-run"
    )
    schema_version: Literal[1] = 1
    run_id: str = Field(pattern=SHA256_PATTERN)
    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    input_content_id: str = Field(pattern=SHA256_PATTERN)
    parser_identity: str = Field(min_length=1)
    transformation_identity: str = Field(min_length=1)
    code_commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    output_schema_version: str = Field(min_length=1)
    environment_identity: str = Field(min_length=1)
    environment_sha256: str = Field(pattern=SHA256_PATTERN)
    output: TransformationOutput
    completed_at: AwareDatetime
    path: Path | None = Field(default=None, exclude=True)

    def canonical_json(self) -> bytes:
        payload = self.model_dump(mode="json", exclude_none=False)
        return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)

    @model_validator(mode="after")
    def validate_run_identity(self) -> Self:
        expected = transformation_run_id_for(
            acquisition_id=self.acquisition_id,
            input_content_id=self.input_content_id,
            parser_identity=self.parser_identity,
            transformation_identity=self.transformation_identity,
            code_commit=self.code_commit,
            output_schema_version=self.output_schema_version,
            environment_sha256=self.environment_sha256,
            output_sha256=self.output.sha256,
            output_byte_count=self.output.byte_count,
            completed_at=self.completed_at,
        )
        if self.run_id != expected:
            raise ValueError("run_id does not bind the transformation receipt")
        return self


def transformation_run_id_for(
    *,
    acquisition_id: str,
    input_content_id: str,
    parser_identity: str,
    transformation_identity: str,
    code_commit: str,
    output_schema_version: str,
    environment_sha256: str,
    output_sha256: str,
    output_byte_count: int,
    completed_at: datetime,
) -> str:
    """Bind one run to its input, implementation, environment, and output."""

    material = "\n".join((
        acquisition_id,
        input_content_id,
        parser_identity,
        transformation_identity,
        code_commit,
        output_schema_version,
        environment_sha256,
        output_sha256,
        str(output_byte_count),
        completed_at.isoformat(),
        "transformation-run-v1",
    ))
    return sha256(material.encode()).hexdigest()


def _code_commit() -> str:
    configured = os.environ.get("GITHUB_SHA")
    if configured and len(configured) in {40, 64}:
        return configured.lower()
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to identify transformation code")
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed command
        [git, "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        shell=False,
        text=True,
    )
    return result.stdout.strip().lower()


def _environment_identity() -> tuple[str, str]:
    lockfile = ROOT / "uv.lock"
    if lockfile.is_file():
        return "uv.lock", sha256(lockfile.read_bytes()).hexdigest()
    material = f"python-runtime\npyarrow={pa.__version__}".encode()
    return "python-runtime", sha256(material).hexdigest()


def receipt_for_parquet(
    parquet_path: Path,
    *,
    acquisition_id: str,
    input_content_id: str,
    completed_at: datetime | None = None,
    parser_identity: str = PARSER_IDENTITY,
    transformation_identity: str = TRANSFORMATION_IDENTITY,
    output_schema_version: str = PARQUET_SCHEMA_VERSION,
) -> TransformationRunReceipt:
    """Hash a completed Parquet file and create its run receipt."""

    output_bytes = parquet_path.read_bytes()
    finished = completed_at or datetime.now(UTC)
    commit = _code_commit()
    environment_identity, environment_sha256 = _environment_identity()
    output_sha256 = sha256(output_bytes).hexdigest()
    run_id = transformation_run_id_for(
        acquisition_id=acquisition_id,
        input_content_id=input_content_id,
        parser_identity=parser_identity,
        transformation_identity=transformation_identity,
        code_commit=commit,
        output_schema_version=output_schema_version,
        environment_sha256=environment_sha256,
        output_sha256=output_sha256,
        output_byte_count=len(output_bytes),
        completed_at=finished,
    )
    return TransformationRunReceipt(
        run_id=run_id,
        acquisition_id=acquisition_id,
        input_content_id=input_content_id,
        parser_identity=parser_identity,
        transformation_identity=transformation_identity,
        code_commit=commit,
        output_schema_version=output_schema_version,
        environment_identity=environment_identity,
        environment_sha256=environment_sha256,
        output=TransformationOutput(
            uri=parquet_path.as_uri(),
            sha256=output_sha256,
            byte_count=len(output_bytes),
        ),
        completed_at=finished,
    )


def write_transformation_run_receipt(
    receipt: TransformationRunReceipt,
    *,
    bronze_root: Path,
    source_id: str,
) -> TransformationRunReceipt:
    """Persist one immutable run event; identical retries are idempotent."""

    path = (
        bronze_root / TRANSFORMATION_DIR / source_id / f"{receipt.run_id}.json"
    )
    payload = receipt.canonical_json() + b"\n"
    if path.exists() and path.read_bytes() != payload:
        raise ValueError(
            "append-only transformation history cannot be rewritten"
        )
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return receipt.model_copy(update={"path": path})
