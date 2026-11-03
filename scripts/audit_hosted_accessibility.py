"""Audit the live candidate with axe and preserve unresolved manual checks."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from deploy_hf_space import http_metadata
from playwright.sync_api import sync_playwright

from global_medicines_atlas.hosted_service import PAYLOAD_SHA, verified_download


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--url", default="https://global-medicines-atlas.onrender.com")
    parser.add_argument("--axe", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    url = args.url
    metadata = http_metadata(url, args.commit)
    source = json.loads(
        verified_download("data/us-openfda-drugsfda.json", PAYLOAD_SHA)
    )
    submissions = [
        s for app in source["results"] for s in app.get("submissions", [])
    ]
    report: dict[str, Any] = {
        "endpoint": url,
        "deployment": metadata,
        "scans": [],
        "temporal_source_assessment": {
            "applications": len(source["results"]),
            "submissions": len(submissions),
            "dated_submissions": sum(
                bool(s.get("submission_status_date")) for s in submissions
            ),
            "submission_types": dict(
                Counter(
                    s.get("submission_type", "missing") for s in submissions
                )
            ),
            "submission_statuses": dict(
                Counter(
                    s.get("submission_status", "missing") for s in submissions
                )
            ),
            "boundary": "Application submission action dates do not establish product-level validity intervals or continued approval; do not propagate them to all products.",
        },
    }
    with sync_playwright() as api:
        browser = api.chromium.launch()
        try:
            page = browser.new_page()
            for width in (320, 360, 1280):
                page.set_viewport_size({"width": width, "height": 800})
                for query in (
                    "",
                    "?concept_search=ANDA040104",
                    "?concept_search=no-such-medicine",
                ):
                    page.goto(url + "/" + query, wait_until="networkidle")
                    page.add_script_tag(path=str(args.axe))
                    result = page.evaluate("""async () => {
                        const r = await axe.run(document, {runOnly: {type: 'tag',
                          values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}});
                        return {version:r.testEngine.version, violations:r.violations,
                          incomplete:r.incomplete, passes:r.passes.map(x=>x.id)};
                    }""")
                    report["scans"].append({
                        "width": width,
                        "query": query,
                        **result,
                    })
        finally:
            browser.close()
    report["full_wcag_conformance"] = False
    report["manual_checks_pending"] = [
        "screen-reader task traversal",
        "all applicable WCAG criteria and incomplete axe findings",
    ]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(report, indent=2) + "\n")
    return int(any(scan["violations"] for scan in report["scans"]))


if __name__ == "__main__":
    raise SystemExit(main())
