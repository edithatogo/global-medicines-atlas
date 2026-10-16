#!/usr/bin/env python3
"""Anonymously verify the bounded MBS transport checkpoint fixture."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.platinum_checkpoint import (
    MBS_PUBLIC_FIXTURE,
    fetch_empty_machine_fixture,
)


def main() -> None:
    """Emit a public-safe, fail-closed transport preflight receipt."""
    policy = AcquisitionPolicy(allowed_hosts=HOSTS, timeout_seconds=30)
    with tempfile.TemporaryDirectory(prefix="gma-empty-workspace-") as fresh:
        root = Path(fresh)
        workspace, home = root / "workspace", root / "home"
        cache, data = root / "cache", root / "data"
        for directory in (workspace, home, cache, data):
            directory.mkdir()
        checked_paths = (data / "lake", cache / "duckdb")
        with (
            patch.dict(
                os.environ,
                {
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(cache),
                    "GMA_DATA_DIR": str(data),
                },
            ),
            chdir(workspace),
            httpx.Client(
                transport=BoundIPAddressTransport(policy=policy),
                trust_env=False,
                follow_redirects=False,
                timeout=30,
                headers={"Accept-Encoding": "identity"},
            ) as client,
        ):
            result = fetch_empty_machine_fixture(
                MBS_PUBLIC_FIXTURE, client, local_paths=checked_paths
            )
        workspace_files = sorted(path.name for path in workspace.iterdir())
        data_files = sorted(path.name for path in data.iterdir())
        cache_files = sorted(path.name for path in cache.iterdir())
        if workspace_files or data_files or cache_files:
            raise ValueError(
                "fixture preflight wrote local workspace artifacts"
            )
    observation = result.observation
    document = json.loads(observation.canonical_bytes)
    document["fresh_workspace"] = {
        "checked_locations": ["data/lake", "cache/duckdb"],
        "durable_local_lake_present": result.durable_local_lake_present,
        "workspace_files_after_query": workspace_files,
        "data_files_after_query": data_files,
        "cache_files_after_query": cache_files,
        "environment_redirected": ["HOME", "XDG_CACHE_HOME", "GMA_DATA_DIR"],
        "working_directory": "workspace",
        "scope": (
            "fresh temporary workspace, home, cache and data roots; the "
            "checkout and runtime are already installed"
        ),
    }
    canonical_receipt = json.dumps(
        document, sort_keys=True, separators=(",", ":")
    ).encode()
    document["receipt_sha256"] = hashlib.sha256(canonical_receipt).hexdigest()
    print(json.dumps(document, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
