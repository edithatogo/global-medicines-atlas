"""Verify free hosted candidates; retain a fail-closed retired deployment CLI."""

from __future__ import annotations

import argparse
import json
import re
import time
from importlib import import_module
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode

import httpx

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
    return metadata


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
    if args.url:
        verify(args.url, receipt, args.exact_commit or "")
    else:
        if not args.exact_commit or args.candidate is None:
            raise ValueError("exact commit and candidate are required")
        deploy(args.exact_commit, args.candidate, receipt, args.receipt)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--url")
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
    finally:
        save_receipt(args.receipt, receipt)
    print(json.dumps({"result": receipt["result"], "phase": receipt["phase"]}))
    # A retired deployment command remains a nonzero policy rejection.
    return 0 if receipt["result"] == "bounded_hosted_candidate_verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
