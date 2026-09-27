#!/usr/bin/env python3
"""Probe approved OpenPrescribing endpoints with HEAD requests only."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from global_medicines_atlas.openprescribing_acquisition import (
    OpenPrescribingAuthorization,
    OpenPrescribingEndpoint,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/openprescribing-acquisition-authorization.json"
)
USER_AGENT = (
    "global-medicines-atlas/1.0 "
    "(+https://github.com/edithatogo/global-medicines-atlas)"
)


def _params(
    endpoint: OpenPrescribingEndpoint, date_partition: date
) -> dict[str, str]:
    params = {"format": "json"}
    if endpoint.role == "utilisation":
        params["date"] = date_partition.isoformat()
    return params


def probe(
    date_partition: date,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, object]:
    """Record response headers without reading response bodies."""
    authorization = OpenPrescribingAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    authorization.require_payload_authority()
    authorization.require_publication_authority()
    authorization.require_reproducible_partition(date_partition=date_partition)
    observed_at = datetime.now(UTC)
    observations: list[dict[str, object]] = []
    with httpx.Client(
        transport=transport,
        follow_redirects=False,
        timeout=15,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for endpoint in authorization.endpoints:
            params = _params(endpoint, date_partition)
            try:
                with client.stream(
                    "HEAD", str(endpoint.url), params=params
                ) as response:
                    observations.append({
                        "endpoint": endpoint.name,
                        "role": endpoint.role,
                        "query": params,
                        "http_status": response.status_code,
                        "content_type": response.headers.get("content-type"),
                        "server": response.headers.get("server"),
                        "cf_mitigated": response.headers.get("cf-mitigated"),
                        "redirect_location_present": (
                            "location" in response.headers
                        ),
                    })
            except httpx.RequestError as error:
                observations.append({
                    "endpoint": endpoint.name,
                    "role": endpoint.role,
                    "query": params,
                    "http_status": None,
                    "error_type": type(error).__name__,
                })
    return {
        "schema_id": (
            "global-medicines-atlas.openprescribing-head-availability"
        ),
        "schema_version": 1,
        "observed_at": observed_at.isoformat(),
        "source_id": "gb-openprescribing",
        "date_partition": date_partition.isoformat(),
        "probe_policy": "one_head_per_authorized_endpoint_no_redirects",
        "endpoint_count": len(observations),
        "observations": observations,
        "response_bodies_read": False,
        "payloads_acquired": False,
        "external_publication_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date-partition", type=date.fromisoformat, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.date_partition)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
