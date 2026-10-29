"""Qualify one exact existing MBS group CSV on protected main, without release."""

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

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.bronze_raw_evidence import RawEvidenceManifest
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_demographic_csv_cohort import (
    FROZEN,
    FROZEN_SHA256,
)
from global_medicines_atlas.mbs_group_package import (
    build_group_package,
    verify_group_package,
)
from global_medicines_atlas.mbs_group_silver import (
    GROUP_HEADERS,
    MbsGroupSource,
)
from global_medicines_atlas.mbs_utilisation_header_inventory import (
    load_header_inventory_contract,
)
from global_medicines_atlas.receipts import AcquisitionEvent

if __package__:
    from scripts import qualify_mbs_q1hr_benefit_scale_comparison as transport
else:
    import qualify_mbs_q1hr_benefit_scale_comparison as transport

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = "raw/mbs/utilisation/group/mbs-group-2016-july.csv"
SOURCE_SHA256 = (
    "62ad118d94cd565a051164aa645eff1fef84a5beb74d501e3dc64344fcf16d3b"
)
EXPECTED_ROWS = 164_543
COMMIT_LENGTH = 40


def load_group_source(root: Path) -> tuple[MbsGroupSource, dict[str, Any]]:
    """Join retained structural/catalogue evidence and B1/B2 to frozen membership."""
    candidates, schemas = load_header_inventory_contract(root)
    selected = [
        row for row in candidates if row["raw_reference"]["path"] == SOURCE_PATH
    ]
    if len(selected) != 1:
        raise ValueError("exactly one retained group CSV candidate is required")
    candidate = selected[0]
    reference = candidate["raw_reference"]
    payload = (root / FROZEN).read_bytes()
    if sha256(payload).hexdigest() != FROZEN_SHA256:
        raise ValueError("frozen group metadata digest differs")
    members = {
        (row["dataset"], row["path"]) for row in json.loads(payload)["members"]
    }
    if (
        (reference["dataset"], SOURCE_PATH) not in members
        or schemas[candidate["resource_id"]] != GROUP_HEADERS
        or reference["dataset"] != transport.DATASET
        or reference["revision"] != transport.REVISION
        or reference["sha256"] != SOURCE_SHA256
    ):
        raise ValueError(
            "group source identity, schema or frozen membership differs"
        )
    family, acquisition = candidate["source_id"], candidate["acquisition_id"]
    source = MbsGroupSource(
        acquisition=AcquisitionEvent.model_validate_json(
            (
                root
                / f"quality/bronze/imported-acquisitions/{family}/{acquisition}.json"
            ).read_bytes()
        ),
        raw_manifest=RawEvidenceManifest.model_validate_json(
            (
                root
                / f"quality/bronze/raw-evidence/{family}/{acquisition}/manifest.json"
            ).read_bytes()
        ),
        dataset=reference["dataset"],
        source_revision=reference["revision"],
        source_path=SOURCE_PATH,
        source_format="csv",
    )
    if source.source_sha256 != SOURCE_SHA256:
        raise ValueError("group retained B1/B2 digest differs")
    return source, reference


def qualify_object(
    payload: bytes,
    source: MbsGroupSource,
    directory: Path,
    *,
    expected_rows: int,
) -> dict[str, Any]:
    """Repeat deterministic builds and restore before bounded consumer checks."""
    first = build_group_package(payload, source, directory / "first")
    second = build_group_package(payload, source, directory / "second")
    if first != second:
        raise ValueError("group candidate deterministic rebuild differs")
    restored = verify_group_package(directory / "first", payload)
    if restored["coverage"]["data_records"] != expected_rows:
        raise ValueError("group candidate row denominator differs")
    with duckdb.connect() as consumer:
        counts = consumer.execute(
            "SELECT count(*) FILTER (WHERE record_kind='data'), count(*) FILTER (WHERE record_kind='header'), count(*) FILTER (WHERE patient_rate_state <> 'unavailable' OR benefit_interpretation_state <> 'native_unresolved') FROM read_parquet(?)",
            [str(directory / "first/group.parquet")],
        ).fetchone()
    if counts != (expected_rows, 1, 0):
        raise ValueError(
            "group consumer counts or interpretation guard differs"
        )
    try:
        source.benefit_semantics.require_interpreted()
    except ValueError:
        pooling_blocked = True
    else:
        raise ValueError("group unresolved benefit meaning was accepted")
    return {
        "source_object_id": source.object_id,
        "source_sha256": source.source_sha256,
        "source_measure_id": source.source_measure_id,
        "acquisition_sha256": source.acquisition.digest(),
        "b2_manifest_sha256": source.raw_manifest.manifest_sha256,
        "coverage": restored["coverage"],
        "parquet": restored["parquet"],
        "manifest_sha256": sha256(
            (directory / "first/qualification.json").read_bytes()
        ).hexdigest(),
        "rebuild_equal": True,
        "independent_native_parity_verified": True,
        "duckdb_counts_verified": True,
        "unqualified_pooling_blocked": pooling_blocked,
        "candidate_only": True,
    }


def qualify(exact_commit: str) -> dict[str, Any]:
    """Verify exact main identity before acquiring the existing pinned CSV."""
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
    source, reference = load_group_source(ROOT)
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
        payload = transport.fetch_exact_source_bytes(
            client,
            {
                "path": SOURCE_PATH,
                "sha256": SOURCE_SHA256,
                "bytes": reference["byte_count"],
            },
        )
    with TemporaryDirectory(prefix="mbs-group-native-") as temporary:
        result = qualify_object(
            payload, source, Path(temporary), expected_rows=EXPECTED_ROWS
        )
    del payload
    return {
        "schema_id": "global-medicines-atlas.mbs-group-native-candidate-qualification",
        "schema_version": 1,
        "workflow_commit": exact_commit,
        "dataset": source.dataset,
        "source_revision": source.source_revision,
        "source_path": SOURCE_PATH,
        "result": result,
        "temporary_derivatives_removed": True,
        "boundaries": {
            "candidate_only": True,
            "new_sources": 0,
            "new_admissions": 0,
            "new_federated_canaries": 0,
            "publications": 0,
            "rights_conclusion_changed": False,
            "age_dimension_inferred": False,
            "hierarchy_equivalence_established": False,
        },
    }


def main() -> None:
    """Write aggregate evidence only, withholding source-bearing exception text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = qualify(args.exact_commit)
    except Exception:
        raise SystemExit(
            "Group candidate qualification failed; source details withheld"
        ) from None
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
