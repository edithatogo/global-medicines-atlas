"""One hosted-only, parent-bound code deployment; never upload source data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed argv, no shell; exact checkout guard
import time
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import httpx
from playwright.sync_api import sync_playwright

from global_medicines_atlas.hosted_service import DATASET, PAYLOAD_SHA, REVISION

SPACE = "edithatogo/global-medicines-atlas"
REPOSITORY = "edithatogo/global-medicines-atlas"
OWNER_MARKER = "GMA_DEPLOYMENT_OWNER=edithatogo/global-medicines-atlas"


def require_hosted_main(exact: str) -> None:
    """Refuse local uploads and any unrelated, stale or unreviewed revision."""
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": exact,
    }
    if not re.fullmatch(r"[0-9a-f]{40}", exact) or any(
        os.environ.get(k) != v for k, v in expected.items()
    ):
        raise ValueError("deployment requires the exact approved hosted main")
    git = shutil.which("git")
    gh = shutil.which("gh")
    if git is None or gh is None:
        raise ValueError("qualified Git and GitHub CLIs are required")
    checkout = subprocess.check_output(  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed argv, qualified executable, no shell
        [git, "rev-parse", "HEAD"], text=True, shell=False
    ).strip()
    current = subprocess.check_output(  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed argv, qualified executable, no shell
        [gh, "api", f"repos/{REPOSITORY}/commits/main", "--jq", ".sha"],
        text=True,
        shell=False,
    ).strip()
    if checkout != exact or current != exact:
        raise ValueError("checkout is not current exact main")


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


def deploy(exact: str, root: Path, receipt: dict[str, Any]) -> None:
    """Use the existing workflow token once per native mutation, without retries."""
    sdk = cast("Any", import_module("huggingface_hub"))
    errors = cast("Any", import_module("huggingface_hub.errors"))
    not_found = cast("type[Exception]", errors.RepositoryNotFoundError)
    http_error = cast("type[Exception]", errors.HfHubHTTPError)

    require_hosted_main(exact)
    files = candidate_files(root)
    api = sdk.HfApi(token=os.environ["HF_TOKEN"])
    identity = api.whoami()
    if identity.get("name") != "edithatogo":
        raise ValueError("unexpected native account")
    receipt["account_pro"] = identity.get("isPro")
    receipt["phase"] = "resolve_target"
    try:
        info = api.repo_info(SPACE, repo_type="space")
    except not_found:
        receipt["phase"] = "create_space"
        try:
            api.create_repo(
                repo_id=SPACE,
                repo_type="space",
                space_sdk="docker",
                private=False,
                exist_ok=False,
            )
        except http_error as error:
            receipt["result"] = "blocked"
            receipt["http_status"] = cast("Any", error).response.status_code
            receipt["blocker"] = (
                "exact-target Space creation denied; account entitlement or workflow-token create permission required"
            )
            return
        receipt["space_created"] = True
        info = api.repo_info(SPACE, repo_type="space")
    else:
        if info.private or getattr(info, "sdk", None) != "docker":
            raise ValueError(
                "existing target has incompatible visibility or SDK"
            )
        response = httpx.get(
            sdk.hf_hub_url(
                SPACE, "README.md", repo_type="space", revision=info.sha
            ),
            timeout=30,
            follow_redirects=True,
        )
        response.raise_for_status()
        if OWNER_MARKER not in response.text:
            raise ValueError("existing Space has another native owner")
    receipt["parent"] = info.sha
    receipt["phase"] = "commit_code"
    # Recheck main at the native mutation boundary; do not retry a POST.
    require_hosted_main(exact)
    commit = api.create_commit(
        repo_id=SPACE,
        repo_type="space",
        parent_commit=info.sha,
        commit_message=f"Deploy reviewed GMA candidate {exact}",
        operations=[
            sdk.CommitOperationAdd(path_in_repo=p.name, path_or_fileobj=p)
            for p in files
        ],
    )
    receipt["space_revision"] = commit.oid
    receipt["phase"] = "anonymous_digest_verification"
    verified: list[dict[str, str]] = []
    for path in files:
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        response = httpx.get(
            sdk.hf_hub_url(
                SPACE, path.name, repo_type="space", revision=commit.oid
            ),
            timeout=60,
            follow_redirects=True,
        )
        response.raise_for_status()
        digest = hashlib.sha256(response.content).hexdigest()
        if digest != expected:
            raise ValueError("anonymous deployed code digest differs")
        verified.append({"path": path.name, "sha256": digest})
    receipt["verified_files"] = verified
    receipt["endpoint"] = "https://edithatogo-global-medicines-atlas.hf.space"
    receipt["result"] = "code_deployed_and_anonymously_verified"


def http_metadata(url: str) -> dict[str, Any]:
    """Check the exact allowed endpoint and bound its source provenance."""
    if url not in {
        "http://127.0.0.1:7860",
        "https://edithatogo-global-medicines-atlas.hf.space",
    }:
        raise ValueError("unapproved service endpoint")
    deadline = time.monotonic() + 600
    while True:
        try:
            response = httpx.get(url + "/api/v1/readiness", timeout=20)
            response.raise_for_status()
            break
        except httpx.HTTPError:
            if time.monotonic() >= deadline:
                raise ValueError(
                    "service readiness deadline exceeded"
                ) from None
        time.sleep(10)
    for path in [
        "/api/v1/health",
        "/api/v1/readiness",
        "/api/v1/openapi.json",
        "/static/atlas.css",
    ]:
        response = httpx.get(url + path, timeout=30)
        response.raise_for_status()
    response = httpx.get(url + "/deployment.json", timeout=30)
    response.raise_for_status()
    metadata = cast("dict[str, Any]", response.json())
    if (
        metadata["dataset"] != DATASET
        or metadata["revision"] != REVISION
        or metadata["source_sha256"] != PAYLOAD_SHA
    ):
        raise ValueError("deployed provenance differs")
    return metadata


def verify(url: str, receipt: dict[str, Any]) -> None:
    """Collect bounded live HTTP and Chromium evidence, never claim full WCAG."""
    receipt["phase"] = "http_and_provenance"
    receipt["data"] = http_metadata(url)
    receipt["phase"] = "chromium"
    with sync_playwright() as browser_api:
        browser = browser_api.chromium.launch()
        try:
            page = browser.new_page()
            for width in [360, 1280]:
                page.set_viewport_size({"width": width, "height": 800})
                page.goto(url, wait_until="networkidle")
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


def execute(args: argparse.Namespace, receipt: dict[str, Any]) -> None:
    """Select read-only verification or the guarded native deployment."""
    if args.url:
        verify(args.url, receipt)
    else:
        if not args.exact_commit or args.candidate is None:
            raise ValueError("exact commit and candidate are required")
        deploy(args.exact_commit, args.candidate, receipt)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt: dict[str, Any] = {
        "space": SPACE,
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
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({"result": receipt["result"], "phase": receipt["phase"]}))
    return (
        0
        if receipt["result"]
        in {
            "code_deployed_and_anonymously_verified",
            "bounded_hosted_candidate_verified",
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
