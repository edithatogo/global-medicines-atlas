#!/usr/bin/env python3
"""Anonymously verify the bounded MBS transport checkpoint fixture."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

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
        checked_paths = (root / "lake", root / ".cache" / "duckdb")
        with httpx.Client(
            transport=BoundIPAddressTransport(policy=policy),
            trust_env=False,
            follow_redirects=False,
            timeout=30,
            headers={"Accept-Encoding": "identity"},
        ) as client:
            result = fetch_empty_machine_fixture(
                MBS_PUBLIC_FIXTURE, client, local_paths=checked_paths
            )
    observation = result.observation
    document = json.loads(observation.canonical_bytes)
    document["fresh_workspace"] = {
        "checked_locations": ["workspace/lake", "workspace/.cache/duckdb"],
        "durable_local_lake_present": result.durable_local_lake_present,
        "scope": (
            "fresh temporary workspace paths; the checkout and runtime are "
            "already installed"
        ),
    }
    canonical_receipt = json.dumps(
        document, sort_keys=True, separators=(",", ":")
    ).encode()
    document["receipt_sha256"] = hashlib.sha256(canonical_receipt).hexdigest()
    print(json.dumps(document, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
