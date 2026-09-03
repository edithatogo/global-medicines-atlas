#!/usr/bin/env python3
"""Anonymously verify the bounded MBS transport checkpoint fixture."""

from __future__ import annotations

import json

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.platinum_checkpoint import (
    MBS_PUBLIC_FIXTURE,
    fetch_unadmitted_public_fixture,
)


def main() -> None:
    """Emit a public-safe, fail-closed transport preflight receipt."""
    policy = AcquisitionPolicy(allowed_hosts=HOSTS, timeout_seconds=30)
    with httpx.Client(
        transport=BoundIPAddressTransport(policy=policy),
        trust_env=False,
        follow_redirects=False,
        timeout=30,
        headers={"Accept-Encoding": "identity"},
    ) as client:
        result = fetch_unadmitted_public_fixture(MBS_PUBLIC_FIXTURE, client)
    document = json.loads(result.canonical_bytes)
    document["receipt_sha256"] = result.receipt_sha256
    print(json.dumps(document, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
