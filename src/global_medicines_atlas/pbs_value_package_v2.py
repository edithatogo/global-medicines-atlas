"""Versioned PBS packages with exhaustive native-core and annotation verification.

Every original value, position, provenance constant and annotation is checked.
The independent XML oracle omits repeated constant metadata from its digest;
those constants and derived IDs are verified separately on every restored field.
This is candidate qualification, not source interpretation, rights or admission.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from . import pbs_entities as entities
from .mbs_demographic_package import canonical_package_json, file_fingerprint
from .pbs_direct_values import iter_direct_historical_value_batches
from .pbs_domain import (  # pyright: ignore[reportPrivateUsage] -- shared internal structural rule
    _mapping,  # pyright: ignore[reportPrivateUsage] -- shared internal rule
    pbs_domain_schema,
)
from .pbs_historical_silver import (
    _schema as historical_schema,  # pyright: ignore[reportPrivateUsage] -- exact existing logical schema
)
from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
)
from .pbs_native_values import (  # pyright: ignore[reportPrivateUsage] -- shared existing conversion rule
    _values,  # pyright: ignore[reportPrivateUsage] -- shared conversion rule
    pbs_value_schema,
)
from .pbs_xml_slots import iter_pbs_xml_slots
from .receipts import SourceReceipt

PACKAGE_SCHEMA_VERSION = 2
PARQUET = "values.parquet"
MANIFEST = "manifest.json"
BATCH_ROWS = 1024
PROGRESS_BATCHES = 32
MAX_FILE_BYTES = 4 * 1024**3
MAX_MANIFEST_BYTES = 1024 * 1024
CORE_KEYS = (
    "source_ordinal",
    "record_id",
    "path",
    "schema_path",
    "value",
    "state",
)
SERIALIZATION = {
    "parquet_version": "2.6",
    "compression": "zstd",
    "compression_level": 3,
    "use_dictionary": True,
    "data_page_version": "2.0",
    "rows_per_batch": BATCH_ROWS,
}
BOUNDARIES = {
    "rights_qualified": False,
    "admitted": False,
    "published": False,
    "domain_semantics_qualified": False,
}
Progress = Callable[[str, int, int], None]


def _progress(
    callback: Progress | None, phase: str, batches: int, rows: int
) -> None:
    if callback is not None:
        callback(phase, batches, rows)


def _schema(parent: SourceReceipt, binding: PbsXmlMemberBinding) -> pa.Schema:
    return pbs_value_schema(
        entities._schema(pbs_domain_schema(historical_schema(parent, binding)))  # pyright: ignore[reportPrivateUsage] -- exact existing schema
    )  # pyright: ignore[reportPrivateUsage] -- exact existing entity schema


def _bound(binding: PbsXmlMemberBinding) -> dict[str, Any]:
    return {
        "source_id": binding.source.source_id,
        "source_sha256": binding.member_payload.sha256,
        "schema_era": binding.source.catalog_version,
        "receipt_sha256": binding.parent_receipt_sha256,
        "member_binding_sha256": binding.digest(),
        "archive_sha256": binding.archive_payload.sha256,
        "member_path": binding.member_path,
    }


def _core(values: list[Any]) -> bytes:
    return (
        json.dumps(
            values, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode()


def _oracle(member: bytes, progress: Progress | None = None) -> dict[str, Any]:
    digest = sha256()
    fields = records = 0
    previous = None
    _progress(progress, "package-native-oracle", 0, 0)
    for ordinal, slot in enumerate(iter_pbs_xml_slots(member)):
        digest.update(
            _core([
                ordinal,
                slot.record_id,
                slot.path,
                slot.schema_path,
                slot.value,
                "null" if slot.value is None else "value",
            ])
        )
        fields += 1
        records += slot.record_id != previous
        previous = slot.record_id
        if fields % (BATCH_ROWS * PROGRESS_BATCHES) == 0:
            _progress(
                progress, "package-native-oracle", fields // BATCH_ROWS, fields
            )
    _progress(progress, "package-native-oracle", fields // BATCH_ROWS, fields)
    return {
        "entities": records,
        "native_fields": fields,
        "native_core_sha256": digest.hexdigest(),
    }


def _checked_row(
    row: dict[str, Any],
    bound: dict[str, Any],
    ordinal: int,
    previous: str | None,
) -> None:
    fields = row["native_fields"]
    if not fields or any(field is None for field in fields):
        raise ValueError("PBS v2 native element has missing fields")
    first = fields[0]
    record = first["record_id"]
    if record == previous:
        raise ValueError("PBS v2 native element is split across rows")
    mapping = _mapping(first)
    for offset, field in enumerate(fields):
        if (
            field["record_id"] != record
            or field["source_ordinal"] != ordinal + offset
        ):
            raise ValueError("PBS v2 native order or grouping differs")
        if any(field[key] != value for key, value in bound.items()):
            raise ValueError("PBS v2 original field lineage differs")
        if (
            field["source_field_id"]
            != f"{bound['source_sha256']}:{field['path']}"
        ):
            raise ValueError("PBS v2 source field identity differs")
        if any(field[key] != value for key, value in mapping.items()):
            raise ValueError("PBS v2 structural field annotation differs")
    expected = entities._row(fields)  # pyright: ignore[reportPrivateUsage] -- recompute all top-level source properties
    expected.update(_values(expected))
    if row != expected:
        raise ValueError("PBS v2 entity or value annotation differs")


def _scan(
    batches: Iterator[pa.RecordBatch],
    binding: PbsXmlMemberBinding,
    *,
    checked: bool,
    progress: Progress | None = None,
    phase: str = "package-restore",
) -> dict[str, Any]:
    bound = _bound(binding)
    fields = records = 0
    previous = None
    conversions: Counter[str] = Counter()
    targets: Counter[str] = Counter()
    digest = sha256()
    for batch_count, batch in enumerate(batches, start=1):
        for row in batch.to_pylist():
            if checked:
                _checked_row(row, bound, fields, previous)
            for field in row["native_fields"]:
                digest.update(_core([field[key] for key in CORE_KEYS]))
                fields += 1
            records += 1
            previous = row["native_fields"][0]["record_id"]
            conversions[row["candidate_conversion_status"]] += 1
            targets[row["mapping_target"]] += 1
        if batch_count % PROGRESS_BATCHES == 0:
            _progress(progress, phase, batch_count, records)
    _progress(
        progress, phase, (records + BATCH_ROWS - 1) // BATCH_ROWS, records
    )
    return {
        "entities": records,
        "native_fields": fields,
        "native_core_sha256": digest.hexdigest(),
        "conversion_statuses": dict(sorted(conversions.items())),
        "mapping_targets": dict(sorted(targets.items())),
    }


def _fingerprint(path: Path) -> dict[str, Any]:
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_FILE_BYTES
    ):
        raise ValueError("PBS v2 package file type or byte limit differs")
    return file_fingerprint(path)


def _manifest(
    output: Path,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    identity = {
        "schema_id": "global-medicines-atlas.pbs-native-value-package",
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "candidate_only": True,
        "native_core_keys": list(CORE_KEYS),
        "serialization": dict(SERIALIZATION),
        "parent_receipt_sha256": parent.digest(),
        "member_binding_sha256": binding.digest(),
        "member_binding": binding.model_dump(mode="json"),
        "parquet": _fingerprint(output / PARQUET),
        "coverage": coverage,
        "boundaries": dict(BOUNDARIES),
    }
    return {
        **identity,
        "output_id": sha256(canonical_package_json(identity)).hexdigest(),
    }


def _verify(
    output: Path,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    oracle: dict[str, Any],
    progress: Progress | None = None,
) -> dict[str, Any]:
    if (
        output.is_symlink()
        or {p.name for p in output.iterdir()} != {PARQUET, MANIFEST}
        or (output / MANIFEST).is_symlink()
        or (output / MANIFEST).stat().st_size > MAX_MANIFEST_BYTES
    ):
        raise ValueError("PBS v2 package inventory or manifest bound differs")
    report = json.loads((output / MANIFEST).read_bytes())
    if report.get("parquet") != _fingerprint(output / PARQUET):
        raise ValueError("PBS v2 package digest or size differs")
    parquet = pq.ParquetFile(output / PARQUET)
    if not parquet.schema_arrow.equals(
        _schema(parent, binding), check_metadata=True
    ):
        raise ValueError("PBS v2 restored Arrow schema differs")
    _progress(progress, "package-restore", 0, 0)
    actual = _scan(
        parquet.iter_batches(batch_size=BATCH_ROWS),  # pyright: ignore[reportUnknownMemberType] -- unused Arrow selectors
        binding,
        checked=True,
        progress=progress,
    )  # pyright: ignore[reportUnknownMemberType] -- unused Arrow selectors
    if any(actual[key] != value for key, value in oracle.items()):
        raise ValueError(
            "PBS v2 independent native core coverage or parity differs"
        )
    if report != _manifest(output, parent, binding, actual):
        raise ValueError(
            "PBS v2 package coverage, identity or qualification differs"
        )
    return report


def verify_value_package_v2(
    output: Path,
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
) -> dict[str, Any]:
    """Check every source slot, provenance constant, identity and annotation.

    Source bytes are immutable inputs. Schema metadata and every native row
    retain the original parent/archive/member evidence. No Arrow producer replay
    is needed: source slots bind data, while pure rules validate all annotations.
    """
    parent = SourceReceipt.model_validate(parent.model_dump())
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    return _verify(Path(output), parent, binding, _oracle(member))


def qualify_value_package_pair_v2(
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    output: Path,
    *,
    max_file_bytes: int = MAX_FILE_BYTES,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Write two fixed-profile files and exhaustively verify an independent oracle.

    Both serialization builds consume the same bounded producer batches. The
    separate XML oracle and restored annotation checks verify the complete input;
    this is not two independent whole-pipeline builds. All prior gates remain.
    """
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("PBS v2 candidate pair already exists")
    if (
        type(max_file_bytes) is not int
        or not 0 < max_file_bytes <= MAX_FILE_BYTES
    ):
        raise ValueError("PBS v2 package byte limit is invalid")
    parent = SourceReceipt.model_validate(parent.model_dump())
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    oracle = _oracle(member, progress)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".pbs-v2-pair-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "pair"
        directories = [staged / name for name in ("first", "second")]
        for directory in directories:
            directory.mkdir(parents=True)
        schema = _schema(parent, binding)
        with ExitStack() as stack:
            writers = [
                stack.enter_context(
                    pq.ParquetWriter(
                        directory / PARQUET,
                        schema,
                        version="2.6",
                        compression="zstd",
                        compression_level=3,
                        use_dictionary=True,
                        write_statistics=True,
                        data_page_version="2.0",
                    )
                )
                for directory in directories
            ]

            def written() -> Iterator[pa.RecordBatch]:
                for batch in iter_direct_historical_value_batches(
                    archive, member, parent, binding
                ):
                    for writer in writers:
                        writer.write_batch(batch)
                    if any(
                        (directory / PARQUET).stat().st_size > max_file_bytes
                        for directory in directories
                    ):
                        raise ValueError("PBS v2 package byte limit exceeded")
                    yield batch

            _progress(progress, "package-write", 0, 0)
            coverage = _scan(
                written(),
                binding,
                checked=False,
                progress=progress,
                phase="package-write",
            )
        if any(coverage[key] != value for key, value in oracle.items()):
            raise ValueError(
                "PBS v2 written native core coverage or parity differs"
            )
        fingerprints = [
            _fingerprint(directory / PARQUET) for directory in directories
        ]
        if any(item["bytes"] > max_file_bytes for item in fingerprints):
            raise ValueError("PBS v2 package byte limit exceeded")
        if fingerprints[0] != fingerprints[1]:
            raise ValueError("PBS v2 serialization builds differ")
        for directory in directories:
            (directory / MANIFEST).write_bytes(
                canonical_package_json(
                    _manifest(directory, parent, binding, coverage)
                )
            )
        report = _verify(directories[0], parent, binding, oracle, progress)
        if (directories[0] / MANIFEST).read_bytes() != (
            directories[1] / MANIFEST
        ).read_bytes():
            raise ValueError("PBS v2 serialization manifests differ")
        staged.rename(output)
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "serialization_builds": 2,
        "independent_pipeline_builds": False,
        "parquet_bytes_identical": True,
        "complete_source_reparse_and_restore": True,
        "restored_file_digest": fingerprints[0],
        "package": report,
        "new_admissions": 0,
        "publications": 0,
    }
