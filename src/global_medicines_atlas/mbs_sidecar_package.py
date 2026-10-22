"""Atomic deterministic sidecar candidates with complete source restore."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict
from hashlib import sha256
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
from .mbs_sidecar_inventory import BoundSidecar
from .mbs_sidecar_layout import profile_sidecar
from .mbs_sidecar_silver import (
    account_native_record,
    iter_sidecar_batches,
    sidecar_schema,
)

DATA_FILE = "records.parquet"
MANIFEST = "manifest.json"
BOUNDARIES = {
    "rights_qualified": False,
    "admitted": False,
    "published": False,
    "semantics_qualified": False,
}


def _rows(batches: Iterator[pa.RecordBatch]) -> Iterator[dict[str, Any]]:
    for batch in batches:
        yield from batch.to_pylist()


def _coverage() -> dict[str, Any]:
    return {
        "records": 0,
        "native_fields": 0,
        "empty_records": 0,
        "state_counts": Counter(),
    }


def _observe(row: dict[str, Any], coverage: dict[str, Any]) -> None:
    coverage["records"] += 1
    coverage["native_fields"] += len(row["native_fields"])
    coverage["empty_records"] += not row["native_fields"]
    coverage["state_counts"].update(
        field["state"] for field in row["native_fields"]
    )


def _finish(
    coverage: dict[str, Any], layout: dict[str, Any], digest: Any
) -> dict[str, Any]:
    records = layout.get(
        "records", layout.get("elements", layout.get("native_records"))
    )
    fields = layout.get(
        "native_fields",
        layout.get("delimiter_occurrences", {}).get("tab", 0)
        + layout.get("native_records", 0),
    )
    expected_digest = layout.get(
        "native_fields_sha256", layout.get("native_lines_sha256")
    )
    if (
        coverage["records"] != records
        or coverage["native_fields"] != fields
        or digest.hexdigest() != expected_digest
    ):
        raise ValueError(
            "MBS sidecar independent native coverage or parity differs"
        )
    return {**coverage, "native_digest_sha256": digest.hexdigest()}


def _manifest(
    output: Path,
    source: BoundSidecar,
    coverage: dict[str, Any],
    layout_sha256: str,
) -> dict[str, Any]:
    identity = {
        "schema_id": "global-medicines-atlas.mbs-sidecar-native-package",
        "schema_version": 1,
        "candidate_only": True,
        "source": json.loads(canonical_package_json(asdict(source))),
        "native_layout_sha256": layout_sha256,
        "coverage": {
            **coverage,
            "state_counts": dict(sorted(coverage["state_counts"].items())),
        },
        "files": {DATA_FILE: file_fingerprint(output / DATA_FILE)},
        "boundaries": dict(BOUNDARIES),
    }
    return {
        **identity,
        "output_id": sha256(canonical_package_json(identity)).hexdigest(),
    }


def verify_sidecar_package(
    output: Path, payload: bytes, source: BoundSidecar
) -> dict[str, Any]:
    """Compare every restored typed/native record against a fresh source parse.

    Exact schema metadata includes original B1/B2 pins. Internal checks do not
    substitute for an external digest binding, rights, admission or semantics.
    """
    layout = profile_sidecar(payload, source)["layout"]
    layout_sha = sha256(canonical_package_json(layout)).hexdigest()
    output = Path(output)
    if {path.name for path in output.iterdir()} != {DATA_FILE, MANIFEST}:
        raise ValueError("MBS sidecar package file inventory differs")
    report = json.loads((output / MANIFEST).read_bytes())
    if report.get("files") != {DATA_FILE: file_fingerprint(output / DATA_FILE)}:
        raise ValueError("MBS sidecar package file digest or size differs")
    parquet = pq.ParquetFile(output / DATA_FILE)
    if not parquet.schema_arrow.equals(
        sidecar_schema(source), check_metadata=True
    ):
        raise ValueError("MBS sidecar package Arrow schema differs")
    actual = iter(_rows(parquet.iter_batches(batch_size=1024)))  # pyright: ignore[reportUnknownMemberType] -- optional Arrow selectors unused
    coverage = _coverage()
    digest = sha256()
    for expected in _rows(iter_sidecar_batches(payload, source)):
        if next(actual, None) != expected:
            raise ValueError(
                "MBS sidecar restored native record or lineage differs"
            )
        _observe(expected, coverage)
        account_native_record(expected, source.format, digest)
    if next(actual, None) is not None:
        raise ValueError("MBS sidecar restored record denominator differs")
    coverage = _finish(coverage, layout, digest)
    if report != _manifest(output, source, coverage, layout_sha):
        raise ValueError(
            "MBS sidecar coverage, identity or qualification differs"
        )
    return report


def build_sidecar_package(
    payload: bytes, source: BoundSidecar, output: Path
) -> dict[str, Any]:
    """Rename atomically only after source exhaustion and complete restore."""
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("MBS sidecar candidate output already exists")
    layout = profile_sidecar(payload, source)["layout"]
    layout_sha = sha256(canonical_package_json(layout)).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".sidecar-package-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "package"
        staged.mkdir()
        coverage = _coverage()
        digest = sha256()
        with candidate_parquet_writer(
            staged / DATA_FILE, sidecar_schema(source)
        ) as writer:
            for batch in iter_sidecar_batches(payload, source):
                writer.write_batch(batch)
                for row in batch.to_pylist():
                    _observe(row, coverage)
                    account_native_record(row, source.format, digest)
        coverage = _finish(coverage, layout, digest)
        report = _manifest(staged, source, coverage, layout_sha)
        (staged / MANIFEST).write_bytes(canonical_package_json(report))
        verify_sidecar_package(staged, payload, source)
        staged.rename(output)
    return report
