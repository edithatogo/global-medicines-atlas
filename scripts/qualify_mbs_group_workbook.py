"""Qualify complete frozen MBS group workbook outputs only on exact main Actions."""

from __future__ import annotations

import argparse
import json
import os
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import duckdb
import httpx
import pyarrow.parquet as pq

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_group_workbook_layout import load_reference
from global_medicines_atlas.mbs_group_workbook_package import (
    build_group_workbook_package,
    verify_group_workbook_package,
)
from global_medicines_atlas.mbs_group_workbook_silver import (
    GroupWorkbookSource,
    load_group_workbook_source,
)

if __package__:
    from scripts import (
        qualify_mbs_q1hr_benefit_scale_comparison as source_reader,
    )
else:
    import qualify_mbs_q1hr_benefit_scale_comparison as source_reader

ROOT = Path(__file__).resolve().parents[1]
COMMIT_LENGTH = 40


def qualify_object(
    payload: bytes, source: GroupWorkbookSource, directory: Path
) -> dict[str, Any]:
    """Build twice, restore every cell, independently compare primary slots."""
    first = build_group_workbook_package(payload, source, directory / "first")
    second = build_group_workbook_package(payload, source, directory / "second")
    if first != second:
        raise ValueError("group workbook deterministic rebuild differs")
    restored = verify_group_workbook_package(
        directory / "first", payload, source
    )
    original = source_reader.workbook_rows(payload)
    if (
        not original
        or len(original) != restored["coverage"]["native_primary_rows"]
    ):
        raise ValueError(
            "group workbook independent native row denominator differs"
        )
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
                    "group workbook independent native primary parity differs"
                )
            ordinal += 1
    if ordinal != len(original):
        raise ValueError("group workbook restored primary denominator differs")
    with duckdb.connect() as consumer:
        counts = consumer.execute(
            "SELECT count(*), count(*) FILTER (WHERE patient_rate_state <> 'unavailable' OR benefit_interpretation_state <> 'native_unresolved' OR record_kind <> 'native_primary_row') FROM read_parquet(?)",
            [str(primary)],
        ).fetchone()
    if counts != (len(original), 0):
        raise ValueError(
            "group workbook consumer count or uncertainty guard differs"
        )
    try:
        source.benefit_semantics.require_interpreted()
    except ValueError:
        pooling_blocked = True
    else:
        raise ValueError(
            "group workbook unresolved benefit meaning was accepted"
        )
    return {
        "source_object_id": source.object_id,
        "source_sha256": source.source_sha256,
        "source_measure_id": source.source_measure_id,
        "acquisition_sha256": source.acquisition.digest(),
        "b2_manifest_sha256": source.raw_manifest.manifest_sha256,
        "coverage": restored["coverage"],
        "package_files": restored["files"],
        "manifest_sha256": sha256(
            (directory / "first/manifest.json").read_bytes()
        ).hexdigest(),
        "output_id": restored["output_id"],
        "rebuild_equal": True,
        "complete_source_restore": True,
        "independent_primary_native_fields_equal": ordinal * 8,
        "duckdb_consumer_counts_equal": True,
        "unqualified_pooling_blocked": pooling_blocked,
        "source_date_alignment": "unqualified",
        "candidate_only": True,
    }


def qualify(exact_commit: str) -> dict[str, Any]:
    """Read exactly the retained frozen source after protected runner checks."""
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
    source = load_group_workbook_source(ROOT)
    reference = load_reference(ROOT)
    if (
        source.dataset != source_reader.DATASET
        or source.source_revision != source_reader.REVISION
    ):
        raise ValueError("group workbook transport identity differs")
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=120,
        max_bytes=25_000_000,
        max_attempts=1,
        max_redirects=3,
    )
    with httpx.Client(
        timeout=120,
        trust_env=False,
        follow_redirects=True,
        max_redirects=3,
        transport=BoundIPAddressTransport(policy=policy),
    ) as client:
        payload = source_reader.fetch_exact_source_bytes(client, reference)
    with TemporaryDirectory(prefix="mbs-group-workbook-") as temporary:
        result = qualify_object(payload, source, Path(temporary))
    del payload
    return {
        "schema_id": "global-medicines-atlas.mbs-group-workbook-candidate-qualification",
        "schema_version": 1,
        "workflow_commit": exact_commit,
        "source_path": source.source_path,
        "source_revision": source.source_revision,
        "result": result,
        "temporary_derivatives_removed": True,
        "boundaries": {
            "candidate_only": True,
            "new_sources": 0,
            "new_admissions": 0,
            "new_federated_canaries": 0,
            "publications": 0,
            "rights_conclusion_changed": False,
            "benefit_equivalence_established": False,
        },
    }


def main() -> None:
    """Emit only aggregate metadata; withhold source-bearing exception text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = qualify(args.exact_commit)
    except Exception:
        raise SystemExit(
            "Group workbook qualification failed; source details withheld"
        ) from None
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
