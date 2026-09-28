#!/usr/bin/env python3
"""Write a bounded receipt for an exact-main HEAD-only MBS egress probe."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx

from global_medicines_atlas.australian_mbs_head_preflight import (
    preflight_medicare_workbook_urls,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = asyncio.run(
            preflight_medicare_workbook_urls(
                exact_commit=args.exact_commit,
                workflow_commit=os.environ.get("GITHUB_SHA", ""),
                workflow_ref=os.environ.get("GITHUB_REF", ""),
                run_id=os.environ.get("GITHUB_RUN_ID", "unavailable"),
            )
        )
    except ValueError, httpx.HTTPError:
        report = {
            "schema_version": 1,
            "status": "incomplete",
            "reason": "preflight-context-or-transport-invalid",
            "publication_performed": False,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
