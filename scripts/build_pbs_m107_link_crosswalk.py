"""Build a value-free PBS schedule-link crosswalk for M-107."""

from __future__ import annotations

import hashlib
import json
from operator import itemgetter
from pathlib import Path
from typing import Any

from scripts.pbs_m107_receipt_binding import validate_pbs_receipt_binding

ROOT = Path(__file__).resolve().parents[1]
INDEX = (
    ROOT
    / "quality/qualifications/australian-pbs-schedule-index-metadata-20261018.json"
)
IDENTITIES = (
    ROOT
    / "quality/qualifications/australian-m109-source-era-identities-20261017.json"
)
RIGHTS = ROOT / "quality/qualifications/source-rights-review-ledger.json"
OUTPUT = (
    ROOT
    / "quality/qualifications/australian-pbs-m107-link-crosswalk-20261018.json"
)
M112 = (
    ROOT
    / "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261018-pbs-receipt-binding.json"
)
READBACK = (
    ROOT / "quality/qualifications/"
    "australian-pbs-m107-known-object-manifest-readback-20261018.json"
)
PUBLIC_TREE = (
    ROOT
    / "quality/qualifications/australian-pbs-m107-public-tree-readback-20261018.json"
)
PUBLIC_DATASET = "edithatogo/australian-pbs-source-archive"
HTTP_OK = 200
SHA256_HEX_LENGTH = 64
HEX_DIGITS = frozenset("0123456789abcdef")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_HEX_LENGTH
        and set(value) <= HEX_DIGITS
    )


def _validate_metadata_response(
    response: dict[str, Any], expected_url: str
) -> int:
    if response.get("url") != expected_url:
        raise ValueError("PBS public tree response URL is not revision-pinned")
    if response.get("http_status") != HTTP_OK:
        raise ValueError("PBS public tree metadata response was not successful")
    byte_count = response.get("response_bytes")
    if not isinstance(byte_count, int) or isinstance(byte_count, bool):
        raise TypeError("PBS public tree response byte count is not an integer")
    if byte_count < 0 or not _is_sha256(response.get("response_sha256")):
        raise ValueError("PBS public tree response identity is malformed")
    return byte_count


def _is_public_tree_file(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    path, size = item.get("path"), item.get("bytes")
    if not isinstance(path, str) or not path or path.startswith("/"):
        return False
    if "\\" in path or ".." in Path(path).parts:
        return False
    return isinstance(size, int) and not isinstance(size, bool) and size >= 0


def _validate_readback_boundaries(
    boundaries: object, expected_metadata_bytes: int
) -> None:
    if not isinstance(boundaries, dict):
        raise TypeError("PBS public tree metadata boundaries are malformed")
    if (
        boundaries.get("source_payload_bytes_read") != 0
        or boundaries.get("metadata_response_bodies_retained") is not False
        or boundaries.get("rights_concluded") is not False
        or boundaries.get("missing_official_links_declared_absent") is not False
        or boundaries.get("m107_accepted") is not False
    ):
        raise ValueError("PBS public tree metadata boundary is invalid")
    if (
        boundaries.get("metadata_response_bytes_read")
        != expected_metadata_bytes
    ):
        raise ValueError("PBS public tree metadata byte total is inconsistent")


def validate_public_tree_readback(
    readback: dict[str, Any],
    *,
    expected_revision: str,
    expected_source_path: str,
    expected_source_bytes: int,
    expected_source_sha256: str,
) -> dict[str, Any]:
    """Validate a bounded public metadata inventory against known B1/B2 identity."""
    expected_schema = (
        "global-medicines-atlas.australian-pbs-m107-public-tree-readback"
    )
    if readback.get("schema_id") != expected_schema:
        raise ValueError("PBS public tree readback schema is invalid")
    if readback.get("schema_version") != 1:
        raise ValueError("PBS public tree readback version is invalid")
    if readback.get("dataset") != PUBLIC_DATASET:
        raise ValueError("PBS public tree dataset is not the expected archive")
    if readback.get("revision") != expected_revision:
        raise ValueError(
            "PBS public tree revision differs from source identity"
        )

    dataset_info, tree = readback.get("dataset_info"), readback.get("tree")
    if not isinstance(dataset_info, dict) or not isinstance(tree, dict):
        raise TypeError("PBS public tree response metadata is malformed")
    tree_url = (
        "https://huggingface.co/api/datasets/"
        f"{PUBLIC_DATASET}/tree/{expected_revision}?recursive=true&expand=false"
    )
    metadata_bytes = sum((
        _validate_metadata_response(
            dataset_info,
            f"https://huggingface.co/api/datasets/{PUBLIC_DATASET}",
        ),
        _validate_metadata_response(tree, tree_url),
    ))

    files = readback.get("files")
    if not isinstance(files, list):
        raise TypeError("PBS public tree file inventory is not a list")
    if readback.get("file_count") != len(files):
        raise ValueError("PBS public tree file count does not match inventory")
    if not all(_is_public_tree_file(item) for item in files):
        raise ValueError("PBS public tree file path or size is invalid")
    paths = [item["path"] for item in files]
    if len(set(paths)) != len(paths):
        raise ValueError("PBS public tree contains duplicate paths")

    raw_files = [item for item in files if item["path"].startswith("raw/")]
    if len(raw_files) != 1:
        raise ValueError("PBS public tree raw-path inventory changed")
    raw_file = raw_files[0]
    if (
        raw_file["path"] != expected_source_path
        or raw_file["bytes"] != expected_source_bytes
    ):
        raise ValueError(
            "PBS public raw path differs from known B1/B2 identity"
        )
    if not _is_sha256(expected_source_sha256):
        raise ValueError("PBS known source digest is malformed")
    _validate_readback_boundaries(readback.get("boundaries"), metadata_bytes)

    return {
        "dataset": PUBLIC_DATASET,
        "revision": expected_revision,
        "tree_http_status": tree["http_status"],
        "tree_response_bytes": tree["response_bytes"],
        "tree_response_sha256": tree["response_sha256"],
        "file_count": len(files),
        "files": sorted(
            ({"path": item["path"], "bytes": item["bytes"]} for item in files),
            key=itemgetter("path"),
        ),
        "raw_files": [
            {
                "path": raw_file["path"],
                "bytes": raw_file["bytes"],
                "sha256": expected_source_sha256,
                "sha256_evidence": "independent_manifest_and_receipt_readback",
            }
        ],
        "source_payload_bytes_read": 0,
        "response_body_retained": False,
        "interpretation": (
            "The pinned public tree contains one raw schedule path; other official "
            "links remain unresolved, not absent."
        ),
    }


def build_report() -> dict[str, Any]:  # ruff: ignore[too-many-locals] -- bounded readback joins remain explicit
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))
    rights_doc = json.loads(RIGHTS.read_text(encoding="utf-8"))
    m112 = json.loads(M112.read_text(encoding="utf-8"))
    readback = json.loads(READBACK.read_text(encoding="utf-8"))
    public_tree = json.loads(PUBLIC_TREE.read_text(encoding="utf-8"))

    source_identity = next(
        item
        for item in identities["pbs"]["sources"]
        if item["source_era"] == "2026-04-01-xml-v3"
    )
    m112_object = next(
        item
        for item in m112["objects"]
        if item.get("path") == source_identity["archive"]["path"]
    )
    rights = {item["source_id"]: item for item in rights_doc["entries"]}
    receipt_binding = validate_pbs_receipt_binding(
        index,
        identities,
        m112,
        readback,
        rights["au-pbs-historical-xml"],
    )
    public_archive_inventory = validate_public_tree_readback(
        public_tree,
        expected_revision=identities["readback"]["pbs"]["current_revision"],
        expected_source_path=source_identity["archive"]["path"],
        expected_source_bytes=source_identity["archive"]["bytes"],
        expected_source_sha256=source_identity["archive"]["sha256"],
    )
    public_archive_inventory["raw_files"][0]["official_url"] = receipt_binding[
        "official_url"
    ]
    public_archive_inventory["raw_files"][0]["url_binding_status"] = (
        receipt_binding["status"]
    )
    rows: list[dict[str, Any]] = []

    for page in index["year_pages"]:
        for link in page["schedule_data_links"]:
            format_label = link["format_label_classification"]
            source_id = (
                "au-pbs-api"
                if format_label == "pbs_api_csv"
                else "au-pbs-historical-xml"
            )
            exact_identity = (
                link["effective_date_from_page_heading"]
                == source_identity["effective_at"]
                and format_label == "xml_v3"
                and link["label"] == "PBS XML V3 file (ZIP 8MB)"
            )
            rights_entry = rights[source_id]
            row: dict[str, Any] = {
                "year_page": page["year"],
                "period_heading": link["period_heading"],
                "effective_date": link["effective_date_from_page_heading"],
                "label": link["label"],
                "url": link["url"],
                "format": format_label,
                "source_id": source_id,
                "source_payload_requested": link["source_file_requested"],
                "rights": {
                    "redistribute": rights_entry["redistribute"],
                    "transform": rights_entry["transform"],
                    "publish_source_bytes": rights_entry[
                        "publish_source_bytes"
                    ],
                    "disposition": rights_entry["disposition"],
                    "ledger_ref": f"quality/qualifications/source-rights-review-ledger.json#{source_id}",
                },
                "archive_identity_status": (
                    "date_format_label_match_to_known_public_object"
                    if exact_identity
                    else "unresolved_link_to_archive_identity"
                ),
                "acceptance_evidence_needed": [
                    "source-specific rights decision",
                    "exact source identity and acquisition receipt",
                    "B1/B2 lineage and anonymous digest readback",
                    "source-era schema and semantic qualification",
                    "approved historical period/source denominator",
                ],
            }
            if exact_identity:
                row["known_object"] = {
                    "path": source_identity["archive"]["path"],
                    "sha256": source_identity["archive"]["sha256"],
                    "bytes": source_identity["archive"]["bytes"],
                    "public_revision": identities["readback"]["pbs"][
                        "current_revision"
                    ],
                    "m112_disposition": m112_object["disposition"],
                    "m112_rights_state": m112_object["rights"]["state"],
                }
                if link["url"] == receipt_binding["official_url"]:
                    row["source_receipt_binding"] = receipt_binding
            rows.append(row)

    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.australian-pbs-m107-link-crosswalk",
        "schema_version": 1,
        "recorded_at": "2026-10-18",
        "requirement": "M-107",
        "status": "metadata_only_link_crosswalk_incomplete",
        "scope": {
            "official_schedule_link_count": len(rows),
            "distinct_schedule_periods": index["release_link_summary"][
                "distinct_schedule_periods_with_data_links"
            ],
            "known_public_object_link_count": sum(
                row["archive_identity_status"]
                == "date_format_label_match_to_known_public_object"
                for row in rows
            ),
            "public_archive_raw_file_count": len(
                public_archive_inventory["raw_files"]
            ),
            "exact_official_url_to_b1_receipt_metadata_count": sum(
                row.get("source_receipt_binding", {}).get("status")
                == "exact_official_url_to_b1_receipt_metadata"
                for row in rows
            ),
            "unresolved_archive_identity_link_count": sum(
                row["archive_identity_status"]
                == "unresolved_link_to_archive_identity"
                for row in rows
            ),
            "source_payloads_requested": False,
            "source_payloads_read": False,
            "rights_concluded": False,
            "m107_accepted": False,
        },
        "inputs": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha256(path)}
            for path in (INDEX, IDENTITIES, RIGHTS, M112, READBACK, PUBLIC_TREE)
        ],
        "interpretation": {
            "known_object_match_boundary": (
                "For the one exact official URL-to-B1-receipt join, the manifest, receipt, and current public object identities agree. "
                "A date, XML V3 label, or archive filename match alone does not establish lineage; this join does not establish rights, period completeness, or admission."
            ),
            "unresolved_boundary": (
                "An unresolved link-to-object mapping is not evidence that a source period or object is absent."
            ),
        },
        "public_archive_inventory": public_archive_inventory,
        "links": rows,
    }
    report["digest"] = {"algorithm": "sha256-canonical-json"}
    report["digest"]["value"] = _canonical_digest(report)
    return report


if __name__ == "__main__":
    OUTPUT.write_text(
        json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
