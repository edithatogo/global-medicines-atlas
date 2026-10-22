"""Deterministic historical PBS candidate package with exhaustive native restore.

This module performs no acquisition or publication. Callers must respect source
rights and use protected hosted execution for real retained source payloads.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from hashlib import sha256
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .mbs_demographic_package import (
    candidate_parquet_writer,
    canonical_package_json,
    file_fingerprint,
)
from .pbs_direct_values import iter_direct_historical_value_batches
from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
)
from .pbs_native_values import iter_pbs_historical_value_batches
from .pbs_xml_slots import iter_pbs_xml_slots
from .receipts import SourceReceipt

PARQUET = "values.parquet"
MANIFEST = "manifest.json"
BATCH_ROWS = 1024
BOUNDARIES = {
    "rights_qualified": False,
    "admitted": False,
    "published": False,
    "domain_semantics_qualified": False,
}
_DOMAIN_FIELDS = {"mapping_target", "mapping_status", "item_occurrence_id"}


def _rows(batches: Iterator[pa.RecordBatch]) -> Iterator[dict[str, Any]]:
    for batch in batches:
        yield from batch.to_pylist()


def _source_native_digest(
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
) -> tuple[int, str]:
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    bound = {
        "source_id": binding.source.source_id,
        "source_sha256": binding.member_payload.sha256,
        "schema_era": binding.source.catalog_version,
        "receipt_sha256": binding.parent_receipt_sha256,
        "member_binding_sha256": binding.digest(),
        "archive_sha256": binding.archive_payload.sha256,
        "member_path": binding.member_path,
    }
    digest = sha256()
    count = 0
    for ordinal, slot in enumerate(iter_pbs_xml_slots(member)):
        row = {
            **bound,
            "source_field_id": f"{binding.member_payload.sha256}:{slot.path}",
            "source_ordinal": ordinal,
            "record_id": slot.record_id,
            "path": slot.path,
            "schema_path": slot.schema_path,
            "value": slot.value,
            "state": "null" if slot.value is None else "value",
        }
        digest.update(canonical_package_json(row))
        count += 1
    return count, digest.hexdigest()


def _coverage_rows(rows: Iterator[dict[str, Any]]) -> dict[str, Any]:
    """Read every restored row, preserving nulls and all native field states."""
    entities = fields = 0
    conversions: Counter[str] = Counter()
    targets: Counter[str] = Counter()
    digest = sha256()
    for row in rows:
        entities += 1
        conversions[row["candidate_conversion_status"]] += 1
        targets[row["mapping_target"]] += 1
        for field in row["native_fields"]:
            fields += 1
            digest.update(
                canonical_package_json({
                    key: value
                    for key, value in field.items()
                    if key not in _DOMAIN_FIELDS
                })
            )
    return {
        "entities": entities,
        "native_fields": fields,
        "native_fields_sha256": digest.hexdigest(),
        "conversion_statuses": dict(sorted(conversions.items())),
        "mapping_targets": dict(sorted(targets.items())),
    }


def _coverage(parquet: pq.ParquetFile) -> dict[str, Any]:
    return _coverage_rows(
        _rows(parquet.iter_batches(batch_size=BATCH_ROWS))  # pyright: ignore[reportUnknownMemberType] -- optional Arrow selectors unused
    )


def _manifest(
    path: Path,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    identity = {
        "schema_id": "global-medicines-atlas.pbs-native-value-package",
        "schema_version": 1,
        "candidate_only": True,
        "parent_receipt_sha256": parent.digest(),
        "member_binding_sha256": binding.digest(),
        "member_binding": binding.model_dump(mode="json"),
        "parquet": file_fingerprint(path / PARQUET),
        "coverage": coverage,
        "boundaries": dict(BOUNDARIES),
    }
    return {
        **identity,
        "output_id": sha256(canonical_package_json(identity)).hexdigest(),
    }


def verify_value_package(
    output: Path,
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
) -> dict[str, Any]:
    """Restore all fields against native source and all values against producer.

    The manifest must be externally digest-bound before admission. Internal
    integrity does not qualify rights, source-domain semantics or release.
    Native field comparison uses the separate unharmonised Silver stream;
    typed values and complete Arrow metadata are checked in a second pass.
    """
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    output = Path(output)
    if {path.name for path in output.iterdir()} != {MANIFEST, PARQUET}:
        raise ValueError("PBS package file inventory differs")
    report: dict[str, Any] = json.loads((output / MANIFEST).read_bytes())
    if report.get("parquet") != file_fingerprint(output / PARQUET):
        raise ValueError("PBS package digest or size differs")
    parquet = pq.ParquetFile(output / PARQUET)
    native_count, native_digest = _source_native_digest(
        archive, member, parent, binding
    )
    # Fixed producer and reader row counts need not share physical row groups.
    expected_batches = iter(
        iter_pbs_historical_value_batches(archive, member, parent, binding)
    )
    first = next(expected_batches, None)
    if first is None or not parquet.schema_arrow.equals(
        first.schema, check_metadata=True
    ):
        raise ValueError("PBS restored Arrow schema differs")
    expected = iter(_rows(chain((first,), expected_batches)))

    def checked_rows() -> Iterator[dict[str, Any]]:
        for row in _rows(parquet.iter_batches(batch_size=BATCH_ROWS)):  # pyright: ignore[reportUnknownMemberType] -- optional Arrow selectors unused
            if row != next(expected, None):
                raise ValueError("PBS restored value or lineage differs")
            yield row

    coverage = _coverage_rows(checked_rows())
    if (
        coverage["native_fields"] != native_count
        or coverage["native_fields_sha256"] != native_digest
    ):
        raise ValueError("PBS restored native field coverage or parity differs")
    if next(expected, None) is not None or report != _manifest(
        output, parent, binding, coverage
    ):
        raise ValueError(
            "PBS package coverage, identity or qualification differs"
        )
    return report


def build_value_package(
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    output: Path,
) -> dict[str, Any]:
    """Finalize atomically after complete source exhaustion and restore checks."""
    output = Path(output)
    if output.exists():
        raise FileExistsError("PBS candidate output already exists")
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".pbs-values-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "package"
        staged.mkdir()
        batches = iter(
            iter_pbs_historical_value_batches(archive, member, parent, binding)
        )
        first = next(batches, None)
        if first is None:
            raise ValueError("PBS value package has no source entities")
        with candidate_parquet_writer(staged / PARQUET, first.schema) as writer:
            writer.write_batch(first)
            for batch in batches:
                writer.write_batch(batch)
        coverage = _coverage(pq.ParquetFile(staged / PARQUET))
        report = _manifest(staged, parent, binding, coverage)
        (staged / MANIFEST).write_bytes(canonical_package_json(report))
        verify_value_package(staged, archive, member, parent, binding)
        staged.rename(output)
    return report


def _validate_file_limit(max_file_bytes: int) -> None:
    if type(max_file_bytes) is not int or not 0 < max_file_bytes <= 4 * 1024**3:
        raise ValueError("PBS package byte limit is invalid")


def qualify_value_package_pair(
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    output: Path,
    *,
    max_file_bytes: int = 4 * 1024**3,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Check two serialization builds plus one complete source reparse/restore.

    Both writers consume the same bounded first-pass batches. A fresh producer
    subsequently checks every restored row, and the separate native stream
    checks every original field. Identical file digests bind that restore to
    both outputs. This is not two independent end-to-end pipeline builds.
    Callers remove these temporary derivatives after retaining the aggregate.
    """
    output = Path(output)
    if output.exists():
        raise FileExistsError("PBS candidate pair already exists")
    _validate_file_limit(max_file_bytes)
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".pbs-value-pair-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "pair"
        directories = [staged / name for name in ("first", "second")]
        for directory in directories:
            directory.mkdir(parents=True)
        batches = iter(
            iter_direct_historical_value_batches(
                archive, member, parent, binding
            )
        )
        first = next(batches, None)
        if first is None:
            raise ValueError("PBS value package has no source entities")
        count = rows = 0
        with ExitStack() as stack:
            writers = [
                stack.enter_context(
                    candidate_parquet_writer(directory / PARQUET, first.schema)
                )
                for directory in directories
            ]

            def written_rows() -> Iterator[dict[str, Any]]:
                nonlocal count, rows
                for batch in chain((first,), batches):
                    for writer in writers:
                        writer.write_batch(batch)
                    count += 1
                    rows += batch.num_rows
                    if any(
                        (directory / PARQUET).stat().st_size > max_file_bytes
                        for directory in directories
                    ):
                        raise ValueError("PBS package byte limit exceeded")
                    if progress is not None:
                        progress("package-write", count, rows)
                    yield from batch.to_pylist()

            coverage = _coverage_rows(written_rows())
        fingerprints = [
            file_fingerprint(directory / PARQUET) for directory in directories
        ]
        if any(item["bytes"] > max_file_bytes for item in fingerprints):
            raise ValueError("PBS package byte limit exceeded")
        if fingerprints[0] != fingerprints[1]:
            raise ValueError("PBS independent serialization builds differ")
        for directory in directories:
            (directory / MANIFEST).write_bytes(
                canonical_package_json(
                    _manifest(directory, parent, binding, coverage)
                )
            )
        if progress is not None:
            progress("package-restore", count, rows)
        report = verify_value_package(
            directories[0], archive, member, parent, binding
        )
        if (directories[0] / MANIFEST).read_bytes() != (
            directories[1] / MANIFEST
        ).read_bytes():
            raise ValueError("PBS serialization manifests differ")
        staged.rename(output)
    return {
        "schema_version": 1,
        "serialization_builds": 2,
        "independent_pipeline_builds": False,
        "parquet_bytes_identical": True,
        "complete_source_reparse_and_restore": True,
        "restored_file_digest": fingerprints[0],
        "package": report,
        "new_admissions": 0,
        "publications": 0,
    }
