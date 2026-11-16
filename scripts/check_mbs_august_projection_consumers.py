"""Check unadmitted August projection consumer identities without data reads.

The in-memory v4 probes are synthetic and are not production contracts,
admissions or proof that remote source bytes can be read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, BinaryIO

import scripts.qualify_mbs_august_projection_field_lineage as lineage
import scripts.qualify_mbs_august_projection_replay as replay
import scripts.qualify_mbs_july_frozen_v4 as existing
from scripts.qualify_m112_v4_july2016_admission import validate_contract

from global_medicines_atlas.federation_consumer import bind_consumer_contract
from global_medicines_atlas.federation_reader import FederatedReader

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = "quality/qualifications/australian-mbs-august-projection-consumer-preflight-20261115.json"
CONSUMER_COMMIT = "64820e666ca32957c0bbcfa3b3c5df75c619e2a8"


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


class _NoNetworkReader(FederatedReader):
    """Turn any unexpected remote call into a failure before I/O."""

    def _remote(self, document: dict[str, Any], output: BinaryIO) -> None:
        del document, output
        raise AssertionError("offline consumer probe attempted network access")


def _probe(
    root: Path,
    row: dict[str, Any],
    plan: dict[str, Any],
    v2_sha: str,
    replay_sha: str,
) -> bytes:
    raw, _ = existing.candidate(root, path=existing.lineage.AUGUST)
    probe: dict[str, Any] = json.loads(raw)
    probe["evidence_kind"] = "synthetic"
    probe["source"].update({
        "acquisition_id": plan["source"]["acquisition_id"],
        "representation": "projection",
        "comparison_cohort": "synthetic",
        "retrieved_at": plan["source"]["retrieved_at"],
    })
    identity = {
        "dataset": row["dataset"],
        "revision": row["revision"],
        "path": row["path"],
        "bytes": row["byte_count"],
        "sha256": row["sha256"],
    }
    probe["location"].update(identity)
    probe["verification"].update(identity)
    probe["rights"].update({
        "dataset": row["dataset"],
        "path": row["path"],
        "subject_sha256": row["sha256"],
    })
    # These in-memory references exercise v4 shape only. No receipt closure is
    # asserted and the placeholder URLs are never requested or retained.
    probe["lineage"]["v2_field_lineage"] = {
        "url": "https://example.invalid/synthetic-field-lineage",
        "sha256": v2_sha,
    }
    probe["lineage"]["v2_field_lineage_applicability"] = "provided"
    probe["lineage"]["v3_replay"] = {
        "url": "https://example.invalid/synthetic-metadata-replay",
        "sha256": replay_sha,
    }
    return validate_contract(probe, root=root)


def build(root: Path = ROOT) -> dict[str, Any]:
    """Validate eight synthetic identity probes and fail closed without admission."""
    vocabulary, crosswalk = lineage.build(root)
    expected = replay.build(root)
    for path, raw in expected.items():
        _require((root / path).read_bytes() == raw, "metadata replay is stale")
    report = json.loads(expected[replay.REPORT])
    plans = {row["path"]: row for row in report["objects"]}
    _require(len(plans) == lineage.OBJECT_COUNT, "replay path set differs")
    v2_sha = hashlib.sha256(
        (json.dumps(vocabulary, sort_keys=True, indent=2) + "\n").encode()
    ).hexdigest()
    replay_sha = hashlib.sha256(expected[replay.REPORT]).hexdigest()
    schema = (root / existing.SCHEMA).read_bytes()
    results: list[dict[str, Any]] = []
    with _NoNetworkReader(schema=schema, admission_records=()) as reader:
        for row in crosswalk["objects"]:
            plan = plans[row["path"]]
            _require(
                all(
                    row[k] == plan[k]
                    for k in (
                        "dataset",
                        "revision",
                        "path",
                        "sha256",
                        "byte_count",
                    )
                ),
                "projection identity differs from replay",
            )
            raw = _probe(root, row, plan, v2_sha, replay_sha)
            binding = bind_consumer_contract(
                raw,
                consumer_repository=existing.REPO,
                consumer_commit=CONSUMER_COMMIT,
            )
            _require(
                binding.evidence_kind == "synthetic"
                and binding.representation == "projection"
                and binding.dataset == row["dataset"]
                and binding.revision == row["revision"]
                and binding.path == row["path"]
                and binding.object_sha256 == row["sha256"]
                and binding.byte_count == row["byte_count"]
                and binding.acquisition_id == plan["source"]["acquisition_id"],
                "synthetic consumer identity binding differs",
            )
            try:
                with reader.open(raw):
                    raise AssertionError("unadmitted projection opened")
            except ValueError as exc:
                _require(
                    str(exc) == "contract is not independently admitted",
                    "unexpected consumer refusal",
                )
            results.append({
                "dataset": row["dataset"],
                "revision": row["revision"],
                "path": row["path"],
                "sha256": row["sha256"],
                "byte_count": row["byte_count"],
                "synthetic_v4_shape_and_consumer_identity": "passed",
                "reader_refuses_without_admission": "passed",
                "production_contract": "not_created",
                "actual_v4_admission": "not_performed",
                "actual_payload_consumer_canary": "not_performed",
                "independent_replica_required_before_admission": plan[
                    "independent_replica_required_before_admission"
                ],
            })
    return {
        "schema_id": "global-medicines-atlas.mbs-august-projection-consumer-preflight",
        "schema_version": 1,
        "recorded_on": "2026-11-16",
        "field_lineage_sha256": v2_sha,
        "metadata_replay_sha256": replay_sha,
        "objects": results,
        "boundaries": {
            "synthetic_probe_is_actual_contract_or_admission": False,
            "receipt_closure_proved": False,
            "actual_source_or_projection_bytes_read": False,
            "participant_or_cohort_data_accessed": False,
            "independent_recovery_established": False,
            "dataset_acquired_or_published": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), sort_keys=True, indent=2) + "\n").encode()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == raw,
            "consumer preflight is stale",
        )
    else:
        path.write_bytes(raw)
    print(
        "Eight synthetic consumer probes passed; no admissions or payload reads"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
