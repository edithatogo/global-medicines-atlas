"""Build a value-free PBS schedule-link crosswalk for M-107."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

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
    / "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261005.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def build_report() -> dict[str, Any]:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))
    rights_doc = json.loads(RIGHTS.read_text(encoding="utf-8"))
    m112 = json.loads(M112.read_text(encoding="utf-8"))

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
            for path in (INDEX, IDENTITIES, RIGHTS, M112)
        ],
        "interpretation": {
            "known_object_match_boundary": (
                "A date, XML V3 label, and source-native archive filename match identifies a known public object; "
                "it does not establish URL-to-receipt lineage, rights, period completeness, or admission."
            ),
            "unresolved_boundary": (
                "An unresolved link-to-object mapping is not evidence that a source period or object is absent."
            ),
        },
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
