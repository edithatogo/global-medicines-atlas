"""Capture bounded rights-discovery receipts for all catalogue sources."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from global_medicines_atlas.rights_discovery import discover_rights_evidence

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"
DEFAULT_OUTPUT = (
    ROOT / "quality/qualifications/source-rights-discovery-20260821.json"
)


def _discover(url: str, observed_at: datetime) -> dict[str, Any]:
    with httpx.Client(
        follow_redirects=True,
        timeout=20,
        headers={"User-Agent": "global-medicines-atlas-rights-review/1"},
    ) as client:
        return discover_rights_evidence(
            url,
            client=client,
            observed_at=observed_at,
        ).model_dump(mode="json")


def build_live(*, workers: int = 8) -> dict[str, Any]:
    """Observe every distinct source landing page with bounded concurrency."""

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    observed_at = datetime.now(UTC).replace(microsecond=0)
    sources = catalog["sources"]
    urls = sorted({str(source["landing_page"]) for source in sources})
    receipts: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {
            executor.submit(_discover, url, observed_at): url for url in urls
        }
        for future in as_completed(pending):
            url = pending[future]
            try:
                receipts[url] = future.result()
            except Exception as error:
                receipts[url] = {
                    "source_url": url,
                    "observed_at": observed_at.isoformat(),
                    "outcome": "failed",
                    "observed_bytes": 0,
                    "rights_links": [],
                    "failure_reason": type(error).__name__,
                }
    entries = [
        {
            "source_id": source["source_id"],
            "authority": source["authority"],
            "jurisdictions": source["jurisdictions"],
            "catalogue_rights_status": source["rights_status"],
            "discovery": receipts[str(source["landing_page"])],
        }
        for source in sources
    ]
    return {
        "schema_id": "global-medicines-atlas.source-rights-discovery",
        "schema_version": 1,
        "observed_at": observed_at.isoformat(),
        "source_count": len(entries),
        "distinct_url_count": len(urls),
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    payload = build_live(workers=args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
