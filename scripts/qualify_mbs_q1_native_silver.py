"""Qualify candidate Q1 source-to-Parquet parity on exact protected main.

Only aggregate receipts leave the runner. Native source and derivative values
are never uploaded by this workflow. Rights, admission and publication remain
separate gates.
"""

from __future__ import annotations

import argparse
import json
import os
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import duckdb
import httpx
import pyarrow.parquet as pq

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.bronze_raw_evidence import RawEvidenceManifest
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_demographic_package import (
    build_demographic_package,
    verify_demographic_package,
)
from global_medicines_atlas.mbs_demographic_silver import DemographicSource
from global_medicines_atlas.receipts import AcquisitionEvent

if __package__:
    from scripts import (
        qualify_mbs_q1hr_benefit_scale_comparison as source_reader,
    )
else:
    import qualify_mbs_q1hr_benefit_scale_comparison as source_reader

ROOT = Path(__file__).resolve().parents[1]
ACQUISITIONS = (
    "4546f1d31d7e46f5b91df63eb71ccc1785f4d6d7905e654a7723f6c123ee57fc",
    "8b109720cd702440c4e14f35eb337ef8b8a466e11cae0556aa281567202d51e3",
)
COMMIT_LENGTH = 40


def source_context(index: int) -> DemographicSource:
    """Load existing exact B1/B2 records, without fabricating a SourceReceipt."""
    acquisition = ACQUISITIONS[index]
    family = "au-data-gov-mbs-demographics"
    event = AcquisitionEvent.model_validate_json(
        (
            ROOT
            / f"quality/bronze/imported-acquisitions/{family}/{acquisition}.json"
        ).read_bytes()
    )
    manifest = RawEvidenceManifest.model_validate_json(
        (
            ROOT
            / f"quality/bronze/raw-evidence/{family}/{acquisition}/manifest.json"
        ).read_bytes()
    )
    item = source_reader.OBJECTS[index]
    source = DemographicSource(
        acquisition=event,
        raw_manifest=manifest,
        dataset=source_reader.DATASET,
        source_revision=source_reader.REVISION,
        source_path=cast("str", item["path"]),
        source_format="workbook" if index == 0 else "csv",
    )
    if source.source_sha256 != item["sha256"]:
        raise ValueError("Q1 retained source context digest differs")
    return source


def qualify_object(
    payload: bytes,
    source: DemographicSource,
    directory: Path,
    *,
    expected_rows: int,
) -> dict[str, Any]:
    """Compare two exact builds and every primary field with an independent reader."""
    first = build_demographic_package(payload, source, directory / "first")
    second = build_demographic_package(payload, source, directory / "second")
    if first != second:
        raise ValueError("Q1 deterministic candidate rebuild differs")
    restored = verify_demographic_package(directory / "first")
    original = (
        source_reader.workbook_rows(payload)
        if source.source_format == "workbook"
        else source_reader.csv_rows(payload)
    )
    if len(original) != expected_rows:
        raise ValueError("Q1 independent source row denominator differs")
    ordinal = 0
    primary = directory / "first/primary.parquet"
    for batch in pq.ParquetFile(primary).iter_batches(batch_size=1024):  # pyright: ignore[reportUnknownMemberType] -- optional Arrow selectors unused
        for row in batch.to_pylist():
            if (
                ordinal >= len(original)
                or tuple(cell["value"] for cell in row["native_cells"])
                != original[ordinal]
            ):
                raise ValueError(
                    "Q1 source-to-output native field parity differs"
                )
            ordinal += 1
    if ordinal != expected_rows:
        raise ValueError("Q1 restored primary row denominator differs")
    with duckdb.connect() as consumer:
        observed = consumer.execute(
            "SELECT count(*), count(*) FILTER (WHERE age_native = 'Unknown'), count(*) FILTER (WHERE patient_rate_state <> 'unavailable' OR age_lower_bound IS NOT NULL OR age_upper_bound IS NOT NULL) FROM read_parquet(?)",
            [str(primary)],
        ).fetchone()
    coverage = restored["coverage"][source.object_id]
    if observed != (expected_rows, coverage["literal_unknown_age_rows"], 0):
        raise ValueError(
            "Q1 DuckDB consumer count or uncertainty guard differs"
        )
    try:
        source.benefit_semantics.require_interpreted()
    except ValueError:
        pooling_blocked = True
    else:
        raise ValueError("Q1 unresolved measure interpretation was accepted")
    return {
        "source_object_id": source.object_id,
        "source_sha256": source.source_sha256,
        "source_measure_id": source.source_measure_id,
        "acquisition_sha256": source.acquisition.digest(),
        "b2_manifest_sha256": source.raw_manifest.manifest_sha256,
        "package_files": restored["files"],
        "package_manifest_sha256": sha256(
            (directory / "first/qualification.json").read_bytes()
        ).hexdigest(),
        "coverage": {
            key: value
            for key, value in coverage.items()
            if key != "native_age_groups"
        },
        "ancillary_cells": restored["ancillary_cells"],
        "native_workbook_cells": restored["native_workbook_cells"],
        "rebuild_equal": True,
        "source_native_primary_fields_equal": ordinal * 8,
        "independent_parquet_restore": True,
        "duckdb_consumer_counts_equal": True,
        "unqualified_pooling_blocked": pooling_blocked,
        "patient_rate_state": "unavailable",
        "candidate_only": True,
    }


def qualify(exact_commit: str) -> dict[str, Any]:
    """Acquire only the two pinned existing objects on exact main Actions."""
    if not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY")
        == "edithatogo/global-medicines-atlas"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and len(exact_commit) == COMMIT_LENGTH
        and all(char in "0123456789abcdef" for char in exact_commit)
        and os.environ.get("GITHUB_SHA") == exact_commit
    ):
        raise ValueError("Qualification requires exact main Actions commit")
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=120,
        max_bytes=25_000_000,
        max_attempts=1,
        max_redirects=3,
    )
    results: list[dict[str, Any]] = []
    with httpx.Client(
        timeout=120,
        trust_env=False,
        follow_redirects=True,
        max_redirects=3,
        transport=BoundIPAddressTransport(policy=policy),
    ) as client:
        for index, item in enumerate(source_reader.OBJECTS):
            source = source_context(index)
            payload = source_reader.fetch_exact_source_bytes(client, item)
            expected = (
                source_reader.EXPECTED_WORKBOOK_ROWS
                if index == 0
                else source_reader.EXPECTED_CSV_ROWS
            )
            with TemporaryDirectory(prefix="q1-native-silver-") as temporary:
                result = qualify_object(
                    payload, source, Path(temporary), expected_rows=expected
                )
            results.append(result)
            del payload
    if results[0]["source_measure_id"] == results[1]["source_measure_id"]:
        raise ValueError("Q1 independent source measures collapsed")
    return {
        "schema_id": "global-medicines-atlas.q1-native-silver-candidate-qualification",
        "schema_version": 1,
        "workflow_commit": exact_commit,
        "dataset": source_reader.DATASET,
        "source_revision": source_reader.REVISION,
        "objects": results,
        "temporary_derivatives_removed": True,
        "boundaries": {
            "candidate_only": True,
            "new_sources": 0,
            "new_admissions": 0,
            "new_federated_canaries": 0,
            "publications": 0,
            "source_values_emitted": False,
            "benefit_equivalence_established": False,
            "rights_conclusion_changed": False,
        },
    }


def main() -> None:
    """Write only aggregate output fingerprints and verification outcomes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = qualify(args.exact_commit)
    except Exception:
        raise SystemExit(
            "Q1 candidate qualification failed; source details withheld"
        ) from None
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
