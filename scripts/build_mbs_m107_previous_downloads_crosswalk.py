"""Build a metadata-only crosswalk for the MBS Previous Downloads PDFs."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX = (
    ROOT
    / "quality/qualifications/australian-mbs-official-index-reconciliation-20261017.json"
)
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/australian-mbs-harvest-publication-authorization.json"
)
OUTPUT = (
    ROOT
    / "quality/qualifications/australian-mbs-m107-previous-downloads-crosswalk-20261018.json"
)
HTTP_OK_STATUS = 200
MONTHS = {
    name: f"{number:02d}"
    for number, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        1,
    )
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _period_comparison(label: str, filename: str) -> dict[str, Any]:
    label_match = re.search(
        r"\b((?:19|20)\d{2})\s*(January|February|March|April|May|June|July|August|September|October|November|December)",
        label,
        flags=re.IGNORECASE,
    )
    file_match = re.match(r"(\d{6})", filename)
    if label_match is None or file_match is None:
        return {"status": "not_comparable_from_label_and_filename"}

    label_token = (
        f"{label_match.group(1)}{MONTHS[label_match.group(2).title()]}"
    )
    filename_token = file_match.group(1)
    return {
        "status": "same_tokens"
        if label_token == filename_token
        else "different_tokens",
        "displayed_label_token": label_token,
        "filename_token": filename_token,
    }


def build_report() -> dict[str, Any]:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    previous = index["previous_downloads"]
    if previous["http_status"] != HTTP_OK_STATUS:
        raise ValueError(
            "Previous Downloads metadata observation is not successful"
        )
    files = previous["files"]
    url_occurrences: Counter[str] = Counter(item["url"] for item in files)
    rows = [
        {
            "page_id": "Previous Downloads",
            "displayed_label": item["label"],
            "filename": item["filename"],
            "source_url": item["url"],
            "same_url_link_occurrence_count": url_occurrences[item["url"]],
            "label_filename_period_comparison": _period_comparison(
                item["label"], item["filename"]
            ),
            "authorization": {
                "allowed_categories": authorization["categories"],
                "historical_pdf_word_scope": "not established by this authorization",
                "category_match": False,
                "source_rights_decision": "not established for this link",
            },
            "source_payload_requested": False,
            "source_payload_read": False,
        }
        for item in files
    ]
    comparison_counts = Counter(
        item["label_filename_period_comparison"]["status"] for item in rows
    )
    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.australian-mbs-m107-previous-downloads-crosswalk",
        "schema_version": 1,
        "recorded_at": "2026-10-18",
        "requirement": "M-107",
        "status": "official_page_metadata_crosswalk_rights_and_acceptance_open",
        "scope": {
            "official_page": "Previous Downloads",
            "listed_pdf_files": previous["listed_file_count"],
            "pdf_link_occurrences": len(rows),
            "distinct_pdf_source_urls": len(url_occurrences),
            "duplicate_url_identity_count": sum(
                count > 1 for count in url_occurrences.values()
            ),
            "duplicate_link_occurrence_excess": len(rows)
            - len(url_occurrences),
            "listed_period_years": previous["listed_period_years"],
            "label_filename_period_comparison_counts": dict(
                sorted(comparison_counts.items())
            ),
            "source_payloads_requested": False,
            "source_payloads_read": False,
            "m107_accepted": False,
        },
        "source_observation": {
            "path": INDEX.relative_to(ROOT).as_posix(),
            "recorded_at": index["recorded_at"],
            "sha256": _sha256(INDEX),
            "page_observation_window": index["downloads_index"][
                "observation_window_utc"
            ],
        },
        "authorization_input": {
            "path": AUTHORIZATION.relative_to(ROOT).as_posix(),
            "sha256": _sha256(AUTHORIZATION),
            "allowed_categories": authorization["categories"],
            "historical_pdf_word_scope": "not established by this authorization",
        },
        "interpretation": {
            "period_boundary": "The label and filename are compared only as metadata; neither is accepted as a verified effective date.",
            "rights_boundary": "The current MBS authorization covers listed source categories and does not establish historical PDF rights.",
            "completeness_boundary": "This is the Previous Downloads page inventory, not a complete historical MBS/PBS period denominator or M-107 acceptance.",
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
