"""Verify free hosted candidates; retain a fail-closed retired deployment CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from contextlib import suppress
from datetime import date as calendar_date
from importlib import import_module
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode

import httpx

from global_medicines_atlas.fda_action_evidence import REVIEWS

OWNER_MARKER = "GMA_DEPLOYMENT_OWNER=edithatogo/global-medicines-atlas"


def candidate_files(root: Path) -> list[Path]:
    """Restrict the transaction to a Dockerfile, card, lock export and wheel."""
    files = sorted(root.iterdir())
    names = {p.name for p in files}
    wheels = [
        p
        for p in files
        if p.name.startswith("global_medicines_atlas-") and p.suffix == ".whl"
    ]
    if len(wheels) != 1 or names != {
        "Dockerfile",
        "README.md",
        "LICENSE",
        "cacert.pem",
        "requirements.txt",
        wheels[0].name,
    }:
        raise ValueError("unexpected deployment candidate members")
    if any(not p.is_file() or p.is_symlink() for p in files):
        raise ValueError("candidate members must be regular files")
    if OWNER_MARKER not in (root / "README.md").read_text(encoding="utf-8"):
        raise ValueError("candidate ownership marker is absent")
    return files


def deploy(
    _exact: str, _root: Path, receipt: dict[str, Any], journal: Path
) -> None:
    """Reject the retired paid-plan path before loading credentials or a SDK."""
    receipt["phase"] = "free_only_policy"
    receipt["result"] = "blocked"
    receipt["blocker"] = (
        "New Docker Spaces require a paid plan; use the free Render Blueprint"
    )
    save_receipt(journal, receipt)


def ready_metadata(url: str) -> dict[str, Any]:
    """Read liveness-qualified revision metadata without account credentials."""
    response = httpx.get(url + "/api/v1/readiness", timeout=20)
    response.raise_for_status()
    response = httpx.get(url + "/deployment.json", timeout=30)
    response.raise_for_status()
    return cast("dict[str, Any]", response.json())


def http_metadata(url: str, expected_commit: str) -> dict[str, Any]:
    """Check the exact allowed endpoint and bound its source provenance."""
    if url != "http://127.0.0.1:7860" and not re.fullmatch(
        r"https://global-medicines-atlas(?:-[a-z0-9]+)?\.onrender\.com", url
    ):
        raise ValueError("unapproved service endpoint")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise ValueError("expected application commit is required")
    deadline = time.monotonic() + 600
    while True:
        try:
            metadata = ready_metadata(url)
            if metadata.get("application_commit") == expected_commit:
                break
        except httpx.HTTPError:
            pass
        if time.monotonic() >= deadline:
            raise ValueError(
                "desired runtime revision readiness deadline exceeded"
            )
        time.sleep(10)
    for path in [
        "/api/v1/health",
        "/api/v1/readiness",
        "/api/v1/openapi.json",
        "/static/atlas.css",
    ]:
        response = httpx.get(url + path, timeout=30)
        response.raise_for_status()
    profile = cast(
        "Any", import_module("global_medicines_atlas.hosted_service")
    )
    if metadata.get("python_version") != "3.15.1":
        raise ValueError("deployed Python runtime differs from 3.15.1")
    if (
        metadata["dataset"] != profile.DATASET
        or metadata["revision"] != profile.REVISION
        or metadata["source_sha256"] != profile.PAYLOAD_SHA
    ):
        raise ValueError("deployed provenance differs")
    verify_approval_events(url, expected_commit, metadata)
    verify_submission_events(url, expected_commit, metadata)
    verify_reviewed_product_actions(url, expected_commit, metadata)
    return metadata


def verify_reviewed_product_actions(
    url: str, commit: str, metadata: dict[str, Any]
) -> None:
    """Read back the reviewed mappings and rehash each public FDA letter."""
    response = httpx.get(url + "/reviewed-product-actions.json", timeout=30)
    response.raise_for_status()
    document = response.json()
    events = document["events"]
    expected = {
        f"us-drugsfda:{review['application_number']}:{number}": (
            review["submission_status"],
            review["submission_status_date"],
            review["letter_sha256"],
            review["letter_url"],
            strength,
            review["application_number"],
            "ORIG",
            "1",
            review["letter_bytes"],
            review["letter_pages"],
            review.get("withdrawal"),
        )
        for review in REVIEWS
        for number, strength in review["product_strengths"].items()
    }
    if (
        document["application_commit"] != commit
        or len(events) != len(expected)
        or metadata["reviewed_action_mapping_count"] != len(expected)
    ):
        raise ValueError("reviewed action coverage differs")
    observed = {}
    for event in events:
        if (
            event["continuing_status_established"] is not False
            or event["validity_interval"] is not None
        ):
            raise ValueError("reviewed action promoted to a status interval")
        concept = event["concept_id"]
        if concept in observed:
            raise ValueError("duplicate reviewed action")
        observed[concept] = (
            event["action_status"],
            event["action_date"],
            event["letter_sha256"],
            event["letter_url"],
            event["product_strength_native"],
            event["application_number"],
            event["submission_type"],
            event["submission_number"],
            event["letter_bytes"],
            event["letter_pages"],
            event["withdrawal"],
        )
    if observed != expected:
        raise ValueError("reviewed action evidence differs")
    for review in REVIEWS:
        sources = [
            (
                review["letter_url"],
                review["letter_bytes"],
                review["letter_sha256"],
            )
        ]
        if review.get("withdrawal"):
            withdrawal = review["withdrawal"]
            sources.append((
                withdrawal["source_uri"],
                withdrawal["source_bytes"],
                withdrawal["source_sha256"],
            ))
        for source_url, expected_bytes, expected_digest in sources:
            verify_evidence_bytes(source_url, expected_bytes, expected_digest)


def verify_evidence_bytes(
    url: str, expected_bytes: int, expected_digest: str
) -> None:
    """Bound and hash a referenced public source without retaining its bytes."""
    with httpx.stream("GET", url, timeout=60, follow_redirects=False) as source:
        source.raise_for_status()
        digest = hashlib.sha256()
        size = 0
        for chunk in source.iter_bytes():
            size += len(chunk)
            if size > expected_bytes:
                raise ValueError("FDA letter size differs")
            digest.update(chunk)
    if size != expected_bytes or digest.hexdigest() != expected_digest:
        raise ValueError("FDA letter digest differs")


def verify_approval_bound(event: dict[str, Any]) -> None:
    """Reject a historical bound unsupported by the exact native phrase."""
    bound = event.get("approval_before_date")
    if bound is not None:
        native_dates = event.get("native_approval_dates", [])
        if (
            bound != "1982-01-01"
            or event["qualification"] != "non_exact_native_date"
            or len(native_dates) != 1
            or " ".join(native_dates[0].casefold().split())
            != "approved prior to jan 1, 1982"
        ):
            raise ValueError("approval event date bound lacks source evidence")


def verify_approval_events(
    url: str, expected_commit: str, metadata: dict[str, Any]
) -> None:
    """Verify exact dated events without promoting unknown validity intervals."""
    orange = cast(
        "Any", import_module("global_medicines_atlas.orange_book_events")
    )
    response = httpx.get(url + "/approval-events.json", timeout=30)
    response.raise_for_status()
    event_document = response.json()
    events = event_document["events"]
    if (
        event_document["application_commit"] != expected_commit
        or len(events) != metadata["product_count"]
    ):
        raise ValueError("approval event deployment or denominator differs")
    if len({e["concept_id"] for e in events}) != len(events):
        raise ValueError("duplicate product approval event")
    exact_count = 0
    for event in events:
        if (
            event["source_sha256"] != orange.SHA256
            or event["source_revision"] != orange.REVISION
            or event["source_uri"] != orange.URI
        ):
            raise ValueError("approval event provenance differs")
        if (
            event["continuing_approval_established"] is not False
            or event["validity_interval"] is not None
        ):
            raise ValueError("approval event promoted to continuing status")
        verify_approval_bound(event)
        if event["qualification"] == "exact_product_approval_date":
            if not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", event.get("approval_date") or ""
            ):
                raise ValueError("qualified event date unavailable")
            exact_count += 1
        elif event["approval_date"] is not None:
            raise ValueError("unqualified event contains exact date")
    coverage = metadata["approval_event_coverage"]
    for state, observed in coverage.items():
        if observed != sum(e["qualification"] == state for e in events):
            raise ValueError("approval event coverage differs from database")
    if sum(coverage.values()) != len(events):
        raise ValueError("approval event coverage denominator differs")
    summary = metadata["approval_event_summary"]
    if (
        exact_count == 0
        or summary["matched_exact_date_count"] != exact_count
        or summary.get("bounded_before_1982_count", 0)
        != sum(e.get("approval_before_date") == "1982-01-01" for e in events)
        or summary["effective_rights_state"] != "permitted"
    ):
        raise ValueError("approval event qualification differs")


def verify_submission_events(
    url: str, expected_commit: str, metadata: dict[str, Any]
) -> None:
    """Verify all bounded application-submission events and their provenance."""
    summary = metadata["submission_event_summary"]
    if (
        summary["application_denominator"] != metadata["application_count"]
        or summary["submission_count"] <= 0
    ):
        raise ValueError("submission source denominator differs")
    if (
        summary["applications_with_submissions"]
        + summary["applications_without_submissions"]
        != summary["application_denominator"]
    ):
        raise ValueError("submission application coverage differs")
    source = cast("Any", import_module("global_medicines_atlas.hosted_service"))
    counts = {"exact_date": 0, "missing": 0, "invalid": 0}
    paths: set[str] = set()
    applications: set[str] = set()
    offset = 0
    while True:
        response = httpx.get(
            url + "/submission-events.json",
            params={"offset": offset, "limit": source.MAX_SUBMISSION_PAGE},
            timeout=30,
        )
        response.raise_for_status()
        page = response.json()
        if (
            page["application_commit"] != expected_commit
            or page["offset"] != offset
            or page["total"] != summary["submission_count"]
        ):
            raise ValueError("submission page identity differs")
        records = page["events"]
        if not records or len(records) > source.MAX_SUBMISSION_PAGE:
            raise ValueError("submission page size differs")
        for record in records:
            verify_submission_record(record, source)
            if record["source_path"] in paths:
                raise ValueError("duplicate submission source path")
            paths.add(record["source_path"])
            applications.add(record["application_number"])
            counts[record["date_qualification"]] += 1
        next_offset = page["next_offset"]
        offset += len(records)
        if next_offset is None:
            break
        if next_offset != offset or offset >= summary["submission_count"]:
            raise ValueError("submission pagination differs")
    if (
        offset != summary["submission_count"]
        or len(applications) != summary["applications_with_submissions"]
    ):
        raise ValueError("submission event coverage differs")
    summary_keys = {
        "exact_date": "exact_date_count",
        "missing": "missing_date_count",
        "invalid": "invalid_date_count",
    }
    if any(
        counts[state] != summary[key] for state, key in summary_keys.items()
    ):
        raise ValueError("submission date coverage differs")


def verify_submission_record(record: dict[str, Any], source: Any) -> None:
    """Reject altered provenance, date claims, and product-status promotion."""
    if (
        record["source_id"] != source.SOURCE
        or record["source_uri"] != source.BASE + "data/us-openfda-drugsfda.json"
        or record["source_revision"] != source.REVISION
        or record["source_sha256"] != source.PAYLOAD_SHA
    ):
        raise ValueError("submission provenance differs")
    if (
        record["product_status_inferred"] is not False
        or record["continuing_status_established"] is not False
    ):
        raise ValueError("submission promoted to product or continuing status")
    app_index = record["application_ordinal"]
    submission_index = record["submission_ordinal"]
    if (
        type(app_index) is not int
        or type(submission_index) is not int
        or app_index < 0
        or submission_index < 0
        or record["source_path"]
        != f"/results/{app_index}/submissions/{submission_index}"
    ):
        raise ValueError("submission source path differs")
    native = record["native_submission"]
    for key in ("submission_type", "submission_number", "submission_status"):
        if record[key] != native.get(key):
            raise ValueError("submission native field differs")
    if record["submission_status_date_native"] != native.get(
        "submission_status_date"
    ):
        raise ValueError("submission native date differs")
    verify_submission_date(record)


def verify_submission_date(record: dict[str, Any]) -> None:
    """Require date qualification to agree with the native field."""
    raw = record["submission_status_date_native"]
    if raw is not None and not isinstance(raw, str):
        raise ValueError("submission native date type differs")
    parsed = None
    if isinstance(raw, str) and re.fullmatch(r"\d{8}", raw):
        with suppress(ValueError):
            parsed = calendar_date.strptime(raw, "%Y%m%d").isoformat()
    expected_state = (
        "exact_date" if parsed else "missing" if not raw else "invalid"
    )
    if (
        record["date_qualification"] != expected_state
        or record["submission_status_date"] != parsed
    ):
        raise ValueError("submission date qualification differs")


def verify(url: str, receipt: dict[str, Any], exact: str) -> None:
    """Collect bounded live HTTP and Chromium evidence, never claim full WCAG."""
    receipt["phase"] = "http_and_provenance"
    receipt["data"] = http_metadata(url, exact)
    receipt["phase"] = "chromium"
    playwright = cast("Any", import_module("playwright.sync_api"))
    with playwright.sync_playwright() as browser_api:
        browser = browser_api.chromium.launch()
        try:
            page = browser.new_page()
            for width in [360, 1280]:
                page.set_viewport_size({"width": width, "height": 800})
                page.goto(
                    url
                    + "?"
                    + urlencode({
                        "concept_search": receipt["data"]["canary_concept_id"]
                    }),
                    wait_until="networkidle",
                )
                if (
                    page.get_by_role("heading", level=1).count() != 1
                    or page.get_by_role("main").count() != 1
                ):
                    raise ValueError("deployed page landmarks differ")
                if (
                    "Historical FDA catalogue candidate"
                    not in page.get_by_role("note").inner_text()
                ):
                    raise ValueError("qualification scope is not visible")
                if not page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ):
                    raise ValueError("horizontal page overflow")
                if page.locator("[data-concept-id]").count() == 0:
                    raise ValueError(
                        "default Atlas search omitted the source catalogue"
                    )
                page.keyboard.press("Tab")
                if not page.evaluate(
                    "['A','INPUT','BUTTON','SELECT'].includes(document.activeElement.tagName)"
                ):
                    raise ValueError("keyboard focus does not reach a control")
            receipt["browser"] = {
                "chromium": "passed",
                "viewports": [360, 1280],
                "keyboard_and_landmarks": "passed",
                "full_wcag_audit": False,
            }
        finally:
            browser.close()
    receipt["result"] = "bounded_hosted_candidate_verified"
    receipt["issue_61_complete"] = False


def save_receipt(path: Path, receipt: dict[str, Any]) -> None:
    """Persist phase and exact native identity before and after a mutation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def execute(args: argparse.Namespace, receipt: dict[str, Any]) -> None:
    """Select read-only verification or the guarded native deployment."""
    if args.url and getattr(args, "http_only", False):
        receipt["phase"] = "http_and_provenance"
        receipt["data"] = http_metadata(args.url, args.exact_commit or "")
        receipt["verification_scope"] = "http_only"
        receipt["result"] = "bounded_hosted_candidate_verified"
        receipt["issue_61_complete"] = False
    elif args.url:
        verify(args.url, receipt, args.exact_commit or "")
    else:
        if getattr(args, "http_only", False):
            raise ValueError("HTTP-only verification requires an endpoint")
        if not args.exact_commit or args.candidate is None:
            raise ValueError("exact commit and candidate are required")
        deploy(args.exact_commit, args.candidate, receipt, args.receipt)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--http-only", action="store_true")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt: dict[str, Any] = {
        "endpoint": args.url,
        "source_commit": args.exact_commit,
        "result": "failed",
        "phase": "initialization",
    }
    try:
        execute(args, receipt)
    except Exception as error:
        # Preserve phase and type, never credentials, raw responses or source values.
        receipt["error_type"] = type(error).__name__
        if isinstance(error, httpx.HTTPStatusError):
            receipt["http_status"] = error.response.status_code
            host = error.request.url.host
            receipt["http_host"] = (
                host
                if host
                in {
                    "127.0.0.1",
                    "www.accessdata.fda.gov",
                    "www.govinfo.gov",
                    "global-medicines-atlas.onrender.com",
                }
                else "other"
            )
    finally:
        save_receipt(args.receipt, receipt)
    print(json.dumps({"result": receipt["result"], "phase": receipt["phase"]}))
    # A retired deployment command remains a nonzero policy rejection.
    return 0 if receipt["result"] == "bounded_hosted_candidate_verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
