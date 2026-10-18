"""Freeze approved M-112 path membership and bind revision observations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / "quality/qualifications"
APPROVED_INVENTORY_PATH = (
    "quality/qualifications/australian-m112-object-inventory-20260930.json"
)
CURRENT_RECONCILIATION_PATH = "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261018.json"
APPROVAL_EVIDENCE_PATH = (
    "conductor/tracks/australian_benefits_silver_gold_20260829/evidence.jsonl"
)
OUTPUT = QUAL / "australian-m112-frozen-object-inventory-20261018.json"
EXPECTED_APPROVED_INVENTORY_SHA256 = (
    "ccc0667b1ce8ba19d4bed0a6590e2bc55ab954d7bd6cc51f56e51231cc780460"
)
EXPECTED_APPROVED_DENOMINATOR = 1759
EXPECTED_RAW_PATHS = 1736
EXPECTED_PROJECTION_PATHS = 23
EXPECTED_PRODUCERS = 5
EXPECTED_SCOPE_APPROVAL_SHA256 = (
    "883b9517d8e646b41885a74da924a3fcb796e1772e5dcdd9394d469b09bb7b71"
)
APPROVAL_KIND = "australian_m112_exact_denominator_maintainer_approval"


def _json(path: str) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def _sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _path_digest(keys: list[tuple[str, str]]) -> str:
    body = "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        for row in sorted(keys)
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_report() -> dict[str, Any]:  # ruff: ignore[too-many-locals,too-many-branches] -- keep the approved-snapshot comparison auditable as one deterministic freeze gate
    """Build a deterministic lock receipt without reading source payloads."""
    approved = _json(APPROVED_INVENTORY_PATH)
    current = _json(CURRENT_RECONCILIATION_PATH)
    evidence_bytes = (ROOT / APPROVAL_EVIDENCE_PATH).read_bytes()

    observed_inventory_sha256 = _sha256(APPROVED_INVENTORY_PATH)
    if observed_inventory_sha256 != EXPECTED_APPROVED_INVENTORY_SHA256:
        raise ValueError("the approved M-112 inventory artifact changed")

    approval_lines = [
        line
        for line in evidence_bytes.decode("utf-8").splitlines()
        if line.strip() and json.loads(line).get("kind") == APPROVAL_KIND
    ]
    if len(approval_lines) != 1:
        raise ValueError("expected one exact M-112 denominator approval record")
    approval = json.loads(approval_lines[0])
    if approval.get(
        "qualification_sha256"
    ) != EXPECTED_SCOPE_APPROVAL_SHA256 or approval.get("denominator") != {
        "candidate_producer_dataset_count": EXPECTED_PRODUCERS,
        "existing_projection_paths": EXPECTED_PROJECTION_PATHS,
        "raw_source_payload_paths": EXPECTED_RAW_PATHS,
        "total_candidate_paths": EXPECTED_APPROVED_DENOMINATOR,
    }:
        raise ValueError("maintainer approval does not match the frozen scope")

    approved_raw = cast(
        "list[dict[str, Any]]", approved["raw_source_payload_candidates"]
    )
    approved_projections = cast(
        "list[dict[str, Any]]", approved["existing_data_projection_candidates"]
    )
    current_objects = cast("list[dict[str, Any]]", current["objects"])
    approved_rows = [("raw_source_payload", row) for row in approved_raw] + [
        ("existing_data_projection", row) for row in approved_projections
    ]
    approved_by_path: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
    for object_class, row in approved_rows:
        key = (row["dataset"], row["path"])
        if key in approved_by_path:
            raise ValueError(f"duplicate approved path identity: {key}")
        approved_by_path[key] = (object_class, row)

    current_by_path: dict[tuple[str, str], dict[str, Any]] = {}
    for row in current_objects:
        key = (row["dataset"], row["path"])
        if key in current_by_path:
            raise ValueError(f"duplicate current path identity: {key}")
        current_by_path[key] = row

    if len(approved_by_path) != EXPECTED_APPROVED_DENOMINATOR:
        raise ValueError("approved M-112 path inventory count changed")
    if len(approved_raw) != EXPECTED_RAW_PATHS:
        raise ValueError("approved M-112 raw path count changed")
    if len(approved_projections) != EXPECTED_PROJECTION_PATHS:
        raise ValueError("approved M-112 projection path count changed")
    if set(approved_by_path) != set(current_by_path):
        raise ValueError(
            "current reconciliation path membership differs from approval"
        )

    dataset_revisions = {
        row["dataset"]: row["revision"]
        for row in cast("list[dict[str, Any]]", approved["datasets"])
    }
    if len(dataset_revisions) != EXPECTED_PRODUCERS:
        raise ValueError("approved M-112 producer count changed")

    members: list[dict[str, str]] = []
    revision_changes = 0
    for key in sorted(approved_by_path):
        object_class, approved_row = approved_by_path[key]
        current_row = current_by_path[key]
        approved_revision = approved_row["revision"]
        current_revision = current_row["revision"]
        revision_changes += approved_revision != current_revision
        members.append({
            "dataset": key[0],
            "path": key[1],
            "object_class": object_class,
            "approved_inventory_revision": approved_revision,
            "approved_dataset_revision": dataset_revisions[key[0]],
            "current_reconciliation_revision": current_revision,
        })

    path_id_sha256 = _path_digest(list(approved_by_path))
    return {
        "schema_id": "global-medicines-atlas.australian-m112-frozen-object-inventory",
        "schema_version": 1,
        "recorded_at": "2026-10-18",
        "purpose": (
            "Freeze the maintainer-approved M-112 dataset/path membership; "
            "retain approved and current producer revisions as separate "
            "observations, not denominator changes."
        ),
        "approval": {
            "evidence_path": APPROVAL_EVIDENCE_PATH,
            "kind": APPROVAL_KIND,
            "qualification_path": approval["qualification"],
            "qualification_sha256": approval["qualification_sha256"],
            "approval_record_sha256": hashlib.sha256(
                approval_lines[0].encode("utf-8")
            ).hexdigest(),
            "decision": approval["decision"],
            "approved_inventory_path": APPROVED_INVENTORY_PATH,
            "approved_inventory_sha256": observed_inventory_sha256,
        },
        "scope": {
            "membership_key": ["dataset", "path"],
            "approved_member_count": len(members),
            "raw_source_payload_paths": len(approved_raw),
            "existing_projection_paths": len(approved_projections),
            "producer_dataset_count": len(dataset_revisions),
            "path_membership_sha256": path_id_sha256,
            "same_membership_as_current_reconciliation": True,
            "members_with_revision_advanced_since_approval": revision_changes,
            "current_reconciliation_path": CURRENT_RECONCILIATION_PATH,
            "current_reconciliation_sha256": _sha256(
                CURRENT_RECONCILIATION_PATH
            ),
        },
        "members": members,
        "boundaries": {
            "new_sources_added": False,
            "source_payload_bytes_read": False,
            "rights_or_licensing_conclusion_added": False,
            "source_admission_or_v4_admission_performed": False,
            "consumer_canary_performed": False,
            "producer_revision_changes_redefine_membership": False,
        },
    }


def main() -> None:
    report = build_report()
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
