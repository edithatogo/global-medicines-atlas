"""Reconcile pinned B1/B2 projections and retained receipts to frozen M-112 paths."""

from __future__ import annotations

import hashlib
import json
import operator
import re
import urllib.request
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / "quality/qualifications"
OVERLAY = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261018-retained-joins.json"
)
UTILISATION = (
    QUAL / "australian-m112-utilisation-digest-reconciliation-20261004.json"
)
SOURCE_ARCHIVE = (
    QUAL / "australian-m112-source-archive-digest-reconciliation-20261004.json"
)
PROJECTION_RECEIPT = (
    QUAL / "australian-m112-projection-identity-readback-20261018.json"
)
P7_AUDIT = (
    QUAL / "australian-m112-source-archive-receipt-join-audit-20260930.json"
)
P7_STORAGE = QUAL / "mbs-p7-storage-receipt-reconciliation-20261003.json"
RAW_IDENTITY_READBACK = (
    QUAL / "australian-m112-raw-identity-readback-20261018.json"
)
JULY_RECEIPT = (
    ROOT
    / "quality/bronze/receipts/au-mbs/bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d.json"
)
OUTPUT = QUAL / "australian-m112-projected-b1-b2-path-joins-20261019.json"
DATASET = "edithatogo/reimbursement-atlas"
REVISION = "8e062578f14e12cf3238700a93946339da9c5d88"
SOURCE_REPO = "edithatogo/reimbursement-atlas"
SOURCE_REPO_REVISION = "a93516ed416118bc51c1db2b71ab540fa4d0fe52"
SOURCE_RECEIPT_FILES = {
    "data/derived/historical_sources/historical_source_downloads.jsonl": {
        "byte_count": 313081,
        "sha256": "8ae141cf09f298669a8421583063a0b0d3ea1bcafb245d1d03288cc7a107df8f",
    },
    "data/derived/historical_sources/pbs_archive_v1/historical_source_downloads.jsonl": {
        "byte_count": 969952,
        "sha256": "aff99a68d7f7af7e7d2766b80599f75365c06f8c7620f317cf4b15104473772e",
    },
    "data/derived/historical_sources/pbs_structured_archive_v1/historical_source_downloads.jsonl": {
        "byte_count": 634150,
        "sha256": "597831281f9f3dea5b83c9af2fe02ca6d6165626b139899244789a4053917ee8",
    },
}
MBS_SOURCE_DATASET = "edithatogo/australian-mbs-source-archive"
MBS_SOURCE_REVISION = "40891976f77ee5e7688edceed25c9ac98a77547e"
MBS_SOURCE_RECEIPT_PATH = (
    "bronze/mbs/releases/Downloads-20260701/MBS-XML-20260701.XML.receipt.json"
)
MBS_SOURCE_RECEIPT_SHA256 = (
    "01f052db621eb1a03ec08198cdcafbc04b8a98238fc06c391e788b7ec73112eb"
)
TABLES = (
    "data/medallion/acquisition_b1/data.jsonl",
    "data/medallion/evidence_b2/data.jsonl",
    "data/medallion/promotion_decisions/data.jsonl",
    "data/medallion/pbs_pdf_provenance/data.jsonl",
    "data/medallion/pbs_structured_provenance/data.jsonl",
    "data/medallion/pbs_archive_variants/data.jsonl",
)
EXPECTED_RAW = 1736
EXPECTED_B1_MATCHES = 1706
EXPECTED_EXISTING_JOINS = 26
EXPECTED_COMPLETE = 6
EXPECTED_UNBOUND_PATHS_BEFORE_VARIANTS = 5
EXPECTED_PINNED_TREE_FILES = 1733
EXPECTED_ANONYMOUS_RAW_READBACKS = 92
MAX_TREE_PAGES = 100


def read_json(path: Path) -> dict[str, Any]:
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stream_table(path: str, identity: dict[str, Any]) -> list[dict[str, Any]]:
    url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{quote(path, safe='/')}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "global-medicines-atlas-m112-lineage-audit/1.0"},
    )
    with urllib.request.urlopen(  # ruff: ignore[suspicious-url-open-usage] -- fixed HTTPS host and immutable revision above
        request, timeout=60
    ) as response:
        body = response.read()
    if (
        len(body) != identity["byte_count"]
        or hashlib.sha256(body).hexdigest() != identity["sha256"]
    ):
        raise ValueError(
            f"anonymous pinned projection identity mismatch: {path}"
        )
    rows = [json.loads(line) for line in body.splitlines()]
    if any(not isinstance(row, dict) for row in rows):
        raise TypeError(f"expected JSON objects in {path}")
    return rows


def read_source_receipt_file(path: str) -> tuple[bytes, list[dict[str, Any]]]:
    url = (
        f"https://raw.githubusercontent.com/{SOURCE_REPO}/"
        f"{SOURCE_REPO_REVISION}/{quote(path, safe='/')}"
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "global-medicines-atlas-m112-lineage-audit/1.0"},
    )
    with urllib.request.urlopen(  # ruff: ignore[suspicious-url-open-usage] -- fixed HTTPS host and immutable repository revision above
        request, timeout=60
    ) as response:
        body = response.read()
    identity = SOURCE_RECEIPT_FILES[path]
    if (
        len(body) != identity["byte_count"]
        or hashlib.sha256(body).hexdigest() != identity["sha256"]
    ):
        raise ValueError(f"source receipt projection identity mismatch: {path}")
    rows = [json.loads(line) for line in body.splitlines()]
    if any(not isinstance(row, dict) for row in rows):
        raise TypeError(f"expected JSON objects in {path}")
    return body, cast("list[dict[str, Any]]", rows)


def read_pinned_mbs_receipt() -> tuple[bytes, dict[str, Any]]:
    url = (
        f"https://huggingface.co/datasets/{MBS_SOURCE_DATASET}/resolve/"
        f"{MBS_SOURCE_REVISION}/{quote(MBS_SOURCE_RECEIPT_PATH, safe='/')}"
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "global-medicines-atlas-m112-lineage-audit/1.0"},
    )
    with urllib.request.urlopen(  # ruff: ignore[suspicious-url-open-usage] -- fixed HTTPS host and immutable dataset revision above
        request, timeout=60
    ) as response:
        body = response.read()
    if hashlib.sha256(body).hexdigest() != MBS_SOURCE_RECEIPT_SHA256:
        raise ValueError("pinned MBS receipt identity mismatch")
    value: Any = json.loads(body)
    if not isinstance(value, dict):
        raise TypeError("expected a JSON object in the pinned MBS receipt")
    return body, cast("dict[str, Any]", value)


def read_pinned_tree_paths() -> list[str]:
    """Read only the public file-name inventory for the immutable dataset revision."""
    url = (
        f"https://huggingface.co/api/datasets/{DATASET}/tree/{REVISION}"
        "?recursive=true&expand=false&limit=1000"
    )
    paths: list[str] = []
    pages = 0
    while url:
        if not url.startswith("https://huggingface.co/api/datasets/"):
            raise ValueError(
                "dataset tree pagination left the approved HTTPS host"
            )
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "global-medicines-atlas-m112-lineage-audit/1.0"
            },
        )
        with urllib.request.urlopen(  # ruff: ignore[suspicious-url-open-usage] -- fixed HTTPS host and immutable revision above
            request, timeout=60
        ) as response:
            rows_value: Any = json.load(response)
            link = response.headers.get("Link", "")
        if not isinstance(rows_value, list):
            raise TypeError("expected dataset tree inventory rows")
        rows = cast("list[dict[str, Any]]", rows_value)
        paths.extend(
            row["path"]
            for row in rows
            if row.get("type") == "file" and isinstance(row.get("path"), str)
        )
        match = re.search(r'<([^>]+)>; rel="next"', link)
        url = match.group(1) if match else ""
        pages += 1
        if pages > MAX_TREE_PAGES:
            raise ValueError("dataset tree pagination exceeded 100 pages")
    return sorted(paths)


def main() -> None:  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- keep path-identity evidence reconciliation in one auditable flow
    overlay = read_json(OVERLAY)
    utilisation = read_json(UTILISATION)
    source_archive = read_json(SOURCE_ARCHIVE)
    readback = read_json(PROJECTION_RECEIPT)
    p7_audit = read_json(P7_AUDIT)
    p7_storage = read_json(P7_STORAGE)
    raw_readback = read_json(RAW_IDENTITY_READBACK)
    july_receipt = read_json(JULY_RECEIPT)
    if readback["scope"]["revision"] != REVISION:
        raise ValueError("pinned projection revision changed")
    receipt_by_path = {item["path"]: item for item in readback["objects"]}
    tables = {
        path: stream_table(path, receipt_by_path[path]) for path in TABLES
    }
    pinned_tree_paths = read_pinned_tree_paths()
    if len(pinned_tree_paths) != EXPECTED_PINNED_TREE_FILES:
        raise ValueError("pinned dataset file inventory count changed")
    receipt_artifact_paths = [
        path
        for path in pinned_tree_paths
        if "/receipts/" in f"/{path}/"
        or "/admissions/" in f"/{path}/"
        or "/references/" in f"/{path}/"
        or path.endswith("receipt.json")
    ]
    objects = overlay["objects"]
    raw = [
        row for row in objects if row["candidate_class"] == "raw_source_payload"
    ]
    if len(raw) != EXPECTED_RAW:
        raise ValueError("frozen M-112 raw denominator changed")
    existing_rows = [
        *utilisation["verified_objects"],
        *source_archive["verified_objects"],
        *overlay["retained_evidence_join_increment"]["new_joins"],
    ]
    existing_keys = {
        (
            row["dataset"],
            row.get("revision", row.get("dataset_revision")),
            row["path"],
        )
        for row in existing_rows
    }
    if len(existing_keys) != EXPECTED_EXISTING_JOINS:
        raise ValueError("existing exact raw digest/path joins changed")
    raw_readback_rows = raw_readback["objects"]
    if len(raw_readback_rows) != EXPECTED_ANONYMOUS_RAW_READBACKS or any(
        row.get("anonymous_readback") is not True
        or row.get("path_basename_sha256_matches") is not True
        or row.get("byte_count_match") is not True
        for row in raw_readback_rows
    ):
        raise ValueError("anonymous raw path readback set changed")

    acquisitions: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in tables[TABLES[0]]:
        sha, size = row.get("payload_sha256"), row.get("byte_size")
        if isinstance(sha, str) and isinstance(size, int):
            acquisitions.setdefault((sha, size), []).append(row)
    evidence_by_acquisition: dict[str, list[dict[str, Any]]] = {}
    for row in tables[TABLES[1]]:
        evidence_by_acquisition.setdefault(row["acquisition_id"], []).append(
            row
        )
    promotions_by_subject: dict[str, list[dict[str, Any]]] = {}
    for row in tables[TABLES[2]]:
        if (
            row.get("from_layer") == "bronze_b1"
            and row.get("to_layer") == "bronze_b2"
        ):
            promotions_by_subject.setdefault(row["subject_id"], []).append(row)
    provenance = [*tables[TABLES[3]], *tables[TABLES[4]]]

    source_receipt_files: dict[str, dict[str, Any]] = {}
    source_receipts_by_identity: dict[
        tuple[str, int, str, str, str], list[tuple[str, dict[str, Any]]]
    ] = {}
    for path, expected_identity in SOURCE_RECEIPT_FILES.items():
        _, receipt_rows = read_source_receipt_file(path)
        source_receipt_files[path] = {
            **expected_identity,
            "git_repository": SOURCE_REPO,
            "git_revision": SOURCE_REPO_REVISION,
            "record_count": len(receipt_rows),
        }
        for receipt_row in receipt_rows:
            sha = receipt_row.get("checksum_sha256")
            size = receipt_row.get("byte_size")
            source_version = receipt_row.get("source_version_id")
            source_locator = receipt_row.get("source_url")
            source_id = receipt_row.get("source_id")
            if (
                isinstance(sha, str)
                and isinstance(size, int)
                and isinstance(source_version, str)
                and isinstance(source_locator, str)
                and isinstance(source_id, str)
            ):
                key = (sha, size, source_version, source_locator, source_id)
                source_receipts_by_identity.setdefault(key, []).append((
                    path,
                    receipt_row,
                ))

    mbs_receipt_bytes, mbs_receipt = read_pinned_mbs_receipt()
    mbs_receipt_sha256 = hashlib.sha256(mbs_receipt_bytes).hexdigest()

    matches: list[dict[str, Any]] = []
    for item in raw:
        identity = item["identity"]
        key = (item["dataset"], item["revision"], item["path"])
        candidates = acquisitions.get(
            (identity.get("sha256"), identity.get("byte_count")), []
        )
        if not candidates:
            continue
        if len(candidates) != 1:
            raise ValueError(f"non-unique B1 projection match: {item['path']}")
        acquisition = candidates[0]
        acquisition_id = acquisition["acquisition_id"]
        b2 = [
            row
            for row in evidence_by_acquisition.get(acquisition_id, [])
            if row.get("payload_sha256") == identity.get("sha256")
            and row.get("byte_size") == identity.get("byte_count")
            and row.get("source_id") == acquisition.get("source_id")
        ]
        promotion = [
            row
            for row in promotions_by_subject.get(acquisition_id, [])
            if identity.get("sha256") in row.get("input_sha256", [])
        ]
        if len(b2) > 1 or len(promotion) > 1:
            raise ValueError(
                f"non-unique B2/promotion projection match: {item['path']}"
            )
        source_receipt_candidates = source_receipts_by_identity.get(
            (
                identity["sha256"],
                identity["byte_count"],
                acquisition.get("source_version_id"),
                acquisition.get("source_locator"),
                acquisition.get("source_id"),
            ),
            [],
        )
        if len(source_receipt_candidates) > 1:
            raise ValueError(
                f"non-unique source receipt projection match: {item['path']}"
            )
        source_receipt_binding: dict[str, Any] | None = None
        if source_receipt_candidates:
            receipt_path, receipt_row = source_receipt_candidates[0]
            receipt_row_bytes = json.dumps(
                receipt_row,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            source_receipt_binding = {
                "evidence_kind": "producer_historical_source_download_receipt_projection",
                "receipt_projection_path": receipt_path,
                "receipt_record_sha256": hashlib.sha256(
                    receipt_row_bytes
                ).hexdigest(),
            }
        provenance_matches = [
            row
            for row in provenance
            if row.get("checksum_sha256") == identity.get("sha256")
            and row.get("byte_size") == identity.get("byte_count")
        ]
        matches.append({
            "dataset": item["dataset"],
            "revision": item["revision"],
            "path": item["path"],
            "sha256": identity.get("sha256"),
            "byte_count": identity.get("byte_count"),
            "existing_exact_path_join": key in existing_keys,
            "b1_acquisition_id": acquisition_id,
            "b1_source_id": acquisition.get("source_id"),
            "b1_event_id": acquisition.get("event_id"),
            "b1_source_version_id": acquisition.get("source_version_id"),
            "b1_source_locator": acquisition.get("source_locator"),
            "b1_retrieved_at": acquisition.get("retrieved_at"),
            "b2_projection_linked": bool(b2),
            "b2_evidence_id": b2[0].get("evidence_id") if b2 else None,
            "b2_immutable_locator": b2[0].get("immutable_locator")
            if b2
            else None,
            "b2_fixity_verified_at": b2[0].get("fixity_verified_at")
            if b2
            else None,
            "promotion_projection": None
            if not promotion
            else {
                "status": promotion[0].get("status"),
                "decided_at": promotion[0].get("decided_at"),
                "required_gate_ids": promotion[0].get("required_gate_ids"),
                "passed_gate_ids": promotion[0].get("passed_gate_ids"),
                "required_gates_passed": set(
                    promotion[0].get("required_gate_ids", [])
                )
                <= set(promotion[0].get("passed_gate_ids", [])),
                "epoch_timestamp_placeholder": promotion[0].get("decided_at")
                == "1970-01-01T00:00:00Z",
            },
            "source_provenance_projection_count": len(provenance_matches),
            "b1_b2_lineage_complete_before_receipt_audit": item[
                "b1_b2_lineage"
            ]["complete"],
            "source_receipt_binding": source_receipt_binding,
            "parallel_b1_projection_locator_discrepancy": bool(
                source_receipt_binding
                and source_receipt_binding.get(
                    "b1_source_locator_matches_receipt"
                )
                is False
            ),
            "disposition": "projection_join_candidate_only",
            "unresolved_roles": [
                *(
                    []
                    if source_receipt_binding
                    else ["source receipt identity"]
                ),
                *(
                    []
                    if item["b1_b2_lineage"]["complete"]
                    else ["persisted landed-admission history"]
                ),
                *(
                    [
                        "B1 source locator does not match path-specific source receipt"
                    ]
                    if (
                        source_receipt_binding
                        and source_receipt_binding.get(
                            "b1_source_locator_matches_receipt"
                        )
                        is False
                        and not item["b1_b2_lineage"]["complete"]
                    )
                    else []
                ),
            ],
        })
    if len(matches) != EXPECTED_B1_MATCHES:
        raise ValueError("exact B1 projection match count changed")

    mbs_raw_path = "raw/mbs/releases/Downloads-20260701/MBS-XML-20260701.XML"
    mbs_match = next(
        row
        for row in matches
        if row["dataset"] == MBS_SOURCE_DATASET and row["path"] == mbs_raw_path
    )
    if not (
        mbs_receipt.get("archive_path") == mbs_raw_path
        and mbs_receipt.get("sha256") == mbs_match["sha256"]
        and mbs_receipt.get("byte_count") == mbs_match["byte_count"]
    ):
        raise ValueError("pinned MBS source receipt does not bind the raw path")
    if mbs_match["source_receipt_binding"] is not None:
        raise ValueError(
            "MBS raw path unexpectedly matched two receipt records"
        )
    mbs_match["source_receipt_binding"] = {
        "evidence_kind": "pinned_path_specific_australian_harvest_receipt",
        "source_dataset": MBS_SOURCE_DATASET,
        "source_dataset_revision": MBS_SOURCE_REVISION,
        "receipt_path": MBS_SOURCE_RECEIPT_PATH,
        "receipt_sha256": mbs_receipt_sha256,
        "receipt_byte_count": len(mbs_receipt_bytes),
        "source_id": mbs_receipt["source_id"],
        "source_url": mbs_receipt["source_url"],
        "identity_join": ["archive_path", "sha256", "byte_count"],
        "is_native_b1_source_receipt_artifact": False,
        "b1_source_locator": mbs_match["b1_source_locator"],
        "b1_source_locator_matches_receipt": (
            mbs_match["b1_source_locator"] == mbs_receipt["source_url"]
        ),
    }
    mbs_match["parallel_b1_projection_locator_discrepancy"] = not mbs_match[
        "source_receipt_binding"
    ]["b1_source_locator_matches_receipt"]
    mbs_match["unresolved_roles"] = [
        role
        for role in mbs_match["unresolved_roles"]
        if role != "source receipt identity"
    ]
    if (
        not mbs_match["source_receipt_binding"][
            "b1_source_locator_matches_receipt"
        ]
        and not mbs_match["b1_b2_lineage_complete_before_receipt_audit"]
    ):
        mbs_match["unresolved_roles"].append(
            "B1 source locator does not match path-specific source receipt"
        )
    receipt_matched = sum(
        row["source_receipt_binding"] is not None for row in matches
    )
    receipt_projection_matched = sum(
        row["source_receipt_binding"]["evidence_kind"]
        == "producer_historical_source_download_receipt_projection"
        for row in matches
        if row["source_receipt_binding"] is not None
    )
    exact_b1_receipt_matches = sum(
        row["source_receipt_binding"] is not None
        and row["source_receipt_binding"].get(
            "b1_source_locator_matches_receipt", True
        )
        for row in matches
    )
    if (
        receipt_matched,
        receipt_projection_matched,
        exact_b1_receipt_matches,
    ) != (1706, 1705, 1705):
        raise ValueError("source receipt/path join totals changed")

    joined = existing_keys | {
        (row["dataset"], row["revision"], row["path"]) for row in matches
    }
    projection_keys = {
        (row["dataset"], row["revision"], row["path"]) for row in matches
    }
    readback_keys = {
        (row["dataset"], row["revision"], row["path"])
        for row in raw_readback_rows
    }
    if len(readback_keys & projection_keys) != EXPECTED_ANONYMOUS_RAW_READBACKS:
        raise ValueError(
            "anonymous raw readback to projection path overlap changed"
        )
    alias = overlay["retained_evidence_join_increment"][
        "existing_alias_binding"
    ]
    alias_object = next(row for row in raw if row["path"] == alias["path"])
    alias_key = (
        alias_object["dataset"],
        alias_object["revision"],
        alias["path"],
    )
    p7_path = "raw/mbs/legacy/2024-07/MBS-2024.07-Group-P7-Genetics.xlsx"
    p7 = next(row for row in raw if row["path"] == p7_path)
    p7_audit_object = next(
        row for row in p7_audit["mbs"]["objects"] if row["path"] == p7_path
    )
    p7_receipt = next(
        row
        for row in p7_audit_object["receipt_or_authorization_matches"]
        if row["kind"] == "historic_hosted_publication_receipt"
    )
    if not (
        p7_audit_object["path_digest_size_joined"]
        and p7_receipt["sha256"] == p7["identity"]["sha256"]
        and p7_receipt["bytes"] == p7["identity"]["byte_count"]
        and p7_storage["source_origin_acquisition_evidenced"] is False
        and p7_storage["admission_lifecycle_evidenced"] is False
    ):
        raise ValueError("P7 historic receipt/path evidence changed")
    july_path = "raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML"
    july = next(row for row in raw if row["path"] == july_path)
    july_identity = july["identity"]
    if not (
        july_receipt["payload"]["sha256"] == july_identity["sha256"]
        and july_receipt["payload"]["byte_count"] == july_identity["byte_count"]
    ):
        raise ValueError("July source receipt/path identity changed")
    p7_key = (p7["dataset"], p7["revision"], p7["path"])
    july_key = (july["dataset"], july["revision"], july["path"])
    path_bindings = joined | {alias_key, p7_key, july_key}
    unbound_before_variants = [
        {
            "dataset": row["dataset"],
            "revision": row["revision"],
            "path": row["path"],
            "sha256": row["identity"].get("sha256"),
            "byte_count": row["identity"].get("byte_count"),
        }
        for row in raw
        if (row["dataset"], row["revision"], row["path"]) not in path_bindings
    ]
    if len(unbound_before_variants) != EXPECTED_UNBOUND_PATHS_BEFORE_VARIANTS:
        raise ValueError("the PBS variant identity residual changed")
    variants_by_identity: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in tables[TABLES[5]]:
        sha, size = row.get("checksum_sha256"), row.get("byte_size")
        if not isinstance(sha, str) or not isinstance(size, int):
            continue
        variants_by_identity.setdefault((sha, size), []).append(row)
    variant_identity_matches: list[dict[str, Any]] = []
    for item in unbound_before_variants:
        archive_id = Path(item["path"]).parent.name
        candidates = variants_by_identity.get(
            (item["sha256"], item["byte_count"]), []
        )
        if len(candidates) != 1 or candidates[0].get("id") != archive_id:
            raise ValueError(
                f"PBS archive-variant identity mismatch: {item['path']}"
            )
        variant = candidates[0]
        if not Path(item["path"]).name.startswith(f"{item['sha256']}.pdf"):
            raise ValueError(
                f"PBS payload filename digest mismatch: {item['path']}"
            )
        variant_identity_matches.append({
            **item,
            "variant_id": variant["id"],
            "source_id": variant["source_id"],
            "archive_timestamp": variant["archive_timestamp"],
            "official_source_url": variant["official_source_url"],
            "archive_replay_url": variant["archive_replay_url"],
            "archive_digest_verified": variant["archive_digest_verified"],
            "raw_redistribution_status": variant["raw_redistribution_status"],
            "identity_role": "source-variant metadata identity only",
            "b1_acquisition_receipt_present": False,
            "b2_reference_present": False,
            "admission_history_present": False,
        })
        path_bindings.add((item["dataset"], item["revision"], item["path"]))
    unbound: list[dict[str, Any]] = [
        {
            "dataset": row["dataset"],
            "revision": row["revision"],
            "path": row["path"],
        }
        for row in raw
        if (row["dataset"], row["revision"], row["path"]) not in path_bindings
    ]
    complete = sum(
        row["b1_b2_lineage"].get("complete") is True for row in objects
    )
    if complete != EXPECTED_COMPLETE or unbound:
        raise ValueError("lineage totals or unresolved path set changed")

    inputs = [
        OVERLAY,
        UTILISATION,
        SOURCE_ARCHIVE,
        PROJECTION_RECEIPT,
        P7_AUDIT,
        P7_STORAGE,
        JULY_RECEIPT,
        RAW_IDENTITY_READBACK,
    ]
    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.m112-projected-b1-b2-path-joins",
        "schema_version": 1,
        "recorded_at": "2026-10-19",
        "scope": {
            "approved_objects": 1759,
            "raw_paths": EXPECTED_RAW,
            "denominator_changed": False,
        },
        "method": {
            "metadata_readback": "anonymous pinned-revision HTTPS; SHA-256 and byte count verified",
            "producer_receipt_projection_readback": "pinned GitHub source-repository commit; file SHA-256 verified",
            "raw_payloads_requested": False,
            "raw_payload_values_inspected": False,
        },
        "inputs": [
            {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}
            for path in inputs
        ],
        "projection_revision": REVISION,
        "source_receipt_readback": {
            "producer_repository": SOURCE_REPO,
            "producer_repository_revision": SOURCE_REPO_REVISION,
            "historical_download_receipt_projection_identity_join": [
                "payload_sha256",
                "byte_count",
                "source_version_id",
                "source_locator",
                "source_id",
            ],
            "historical_download_receipt_projections": source_receipt_files,
            "historical_download_receipt_projection_matches": receipt_projection_matched,
            "exact_b1_source_download_receipt_projection_joins": exact_b1_receipt_matches,
            "path_specific_receipts_with_b1_locator_discrepancies": receipt_matched
            - exact_b1_receipt_matches,
            "path_specific_mbs_receipt": {
                "dataset": MBS_SOURCE_DATASET,
                "revision": MBS_SOURCE_REVISION,
                "path": MBS_SOURCE_RECEIPT_PATH,
                "sha256": mbs_receipt_sha256,
                "byte_count": len(mbs_receipt_bytes),
                "matched_object_path": mbs_raw_path,
            },
            "unique_b1_b2_projection_matches_with_path_receipt_identity_evidence": receipt_matched,
            "b1_b2_projection_matches_without_source_receipt_evidence": len(
                matches
            )
            - receipt_matched,
            "projection_matches_still_missing_persisted_landed_admission_history": sum(
                "persisted landed-admission history" in row["unresolved_roles"]
                for row in matches
            ),
            "complete_b1_b2_lineages_added": 0,
            "interpretation": "Historical download rows bind content identity and source version/locator but remain producer projections, not native per-object receipt artifacts or admission history. The MBS sidecar binds its exact path, digest, and byte count, but its source URL differs from the parallel reimbursement-atlas B1 projection locator. Existing MBS path-specific B1/B2 lineage evidence remains authoritative for that already-complete object. Receipt matches do not create a landed admission event.",
        },
        "pinned_dataset_tree_inventory": {
            "path_count": len(pinned_tree_paths),
            "sorted_path_list_sha256": hashlib.sha256(
                "\n".join(pinned_tree_paths).encode("utf-8")
            ).hexdigest(),
            "standalone_receipt_admission_or_reference_artifact_paths": receipt_artifact_paths,
            "interpretation": "The immutable reimbursement-atlas repository contains B1/B2 and other metadata projections but no separate per-object receipt, admission, or reference sidecar files.",
        },
        "summary": {
            "existing_b1_b2_receipt_path_joins": len(existing_keys),
            "cumulative_exact_raw_digest_path_joins": overlay[
                "retained_evidence_join_increment"
            ]["cumulative_exact_raw_digest_path_joins"],
            "raw_paths_outside_cumulative_exact_digest_join_subset": overlay[
                "retained_evidence_join_increment"
            ]["raw_paths_outside_digest_join_subset"],
            "anonymous_raw_digest_readbacks": len(raw_readback_rows),
            "anonymous_raw_readbacks_also_b1_b2_projection_matched": len(
                readback_keys & projection_keys
            ),
            "metadata_projection_raw_path_matches": len(matches),
            "new_distinct_projection_path_matches": len(
                {(r["dataset"], r["revision"], r["path"]) for r in matches}
                - existing_keys
            ),
            "raw_paths_bound_by_existing_join_or_projection": len(joined),
            "prior_m112_source_receipt_path_bindings": 1,
            "historic_publication_receipt_path_bindings": 1,
            "separate_same_content_alias_path_bindings": 1,
            "raw_paths_with_any_path_identity_binding": len(path_bindings),
            "raw_paths_without_any_path_identity_binding": len(unbound),
            "pbs_archive_variant_metadata_identity_matches": len(
                variant_identity_matches
            ),
            "complete_b1_b2_lineages_before_audit": complete,
            "complete_b1_b2_lineages_added": 0,
            "complete_b1_b2_lineages_after_audit": complete,
            "b1_b2_projection_matches_with_path_receipt_identity_evidence": receipt_matched,
            "exact_b1_source_download_receipt_projection_joins": exact_b1_receipt_matches,
            "path_specific_receipts_with_b1_locator_discrepancies": receipt_matched
            - exact_b1_receipt_matches,
            "b1_b2_projection_matches_missing_landed_admission_history": sum(
                "persisted landed-admission history" in row["unresolved_roles"]
                for row in matches
            ),
            "b2_projection_links": sum(
                row["b2_projection_linked"] for row in matches
            ),
            "approved_promotion_rows_with_required_gates_passed": sum(
                row["promotion_projection"] is not None
                and row["promotion_projection"]["status"] == "approved"
                and row["promotion_projection"]["required_gates_passed"]
                for row in matches
            ),
            "promotion_rows_with_epoch_placeholder": sum(
                row["promotion_projection"] is not None
                and row["promotion_projection"]["epoch_timestamp_placeholder"]
                for row in matches
            ),
        },
        "july_2025_source_receipt": {
            "path": july_path,
            "sha256": july_identity["sha256"],
            "lifecycle_roles_present": {
                "separate_acquisition": False,
                "b2_reference": False,
                "admission_history": False,
            },
        },
        "p7_historic_publication_receipt": {
            "path": p7_path,
            "sha256": p7["identity"]["sha256"],
            "receipt_revision": p7_receipt["dataset_revision"],
            "source_origin_acquisition_evidenced": False,
            "b2_reference_evidenced": False,
            "admission_lifecycle_evidenced": False,
        },
        "raw_paths_without_any_path_identity_binding": sorted(
            unbound,
            key=operator.itemgetter("dataset", "revision", "path"),
        ),
        "pbs_archive_variant_identity_matches": sorted(
            variant_identity_matches,
            key=operator.itemgetter("dataset", "revision", "path"),
        ),
        "projection_matches": sorted(
            matches,
            key=operator.itemgetter("dataset", "revision", "path"),
        ),
        "boundaries": {
            "all_1759_deferrals_preserved": True,
            "rights_or_release_conclusion_added": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
            "source_owner_work_modified": False,
            "reserved_july_derivative_modified": False,
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"report": str(OUTPUT), "summary": report["summary"]},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
