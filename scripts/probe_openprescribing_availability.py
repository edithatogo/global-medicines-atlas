#!/usr/bin/env python3
"""Probe the approved OpenPrescribing API scope without retaining payloads."""

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
HTTP_FORBIDDEN = 403


def _params(
    endpoint: OpenPrescribingEndpoint, date_partition: date
) -> dict[str, str]:
    params = {"format": "json"}
    if endpoint.role == "utilisation":
        params["date"] = date_partition.isoformat()
    return params


def _availability(response: httpx.Response) -> str:
    if response.is_success:
        return "available_not_acquired_by_probe"
    if (
        response.status_code == HTTP_FORBIDDEN
        and response.headers.get("cf-mitigated") == "challenge"
    ):
        return "cloudflare_challenge_from_current_environment"
    return "http_unavailable"


def probe(
    date_partition: date,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, object]:
    """Attempt each authorized endpoint once and retain metadata only."""
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
        follow_redirects=True,
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for endpoint in authorization.endpoints:
            params = _params(endpoint, date_partition)
            try:
                response = client.get(str(endpoint.url), params=params)
            except httpx.RequestError as error:
                observations.append({
                    "endpoint": endpoint.name,
                    "role": endpoint.role,
                    "query": params,
                    "http_status": None,
                    "availability": "transport_error",
                    "error_type": type(error).__name__,
                })
                continue
            observations.append({
                "endpoint": endpoint.name,
                "role": endpoint.role,
                "query": params,
                "http_status": response.status_code,
                "availability": _availability(response),
                "content_type": response.headers.get("content-type"),
                "server": response.headers.get("server"),
                "cf_mitigated": response.headers.get("cf-mitigated"),
            })
    return {
        "schema_id": (
            "global-medicines-atlas.openprescribing-availability-receipt"
        ),
        "schema_version": 1,
        "observed_at": observed_at.isoformat(),
        "source_id": "gb-openprescribing",
        "prompt_id": 30,
        "authorization": str(AUTHORIZATION.relative_to(ROOT)),
        "decision_status": authorization.decision_status,
        "date_partition": date_partition.isoformat(),
        "probe_policy": "one_attempt_per_documented_endpoint_no_retry",
        "endpoint_count": len(observations),
        "observations": observations,
        "payload_bytes_retained": False,
        "payloads_acquired": False,
        "external_publication_performed": False,
        "challenge_bodies_retained": False,
        "unbounded_api_crawl_performed": False,
        "upstream_monthly_epd_substitution_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date-partition", type=date.fromisoformat, required=True
    )
    args = parser.parse_args()
    print(json.dumps(probe(args.date_partition), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
