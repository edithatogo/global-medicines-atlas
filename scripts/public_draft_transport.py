"""Read exact public publisher copies from an unpublished draft transport."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from typing import Any
from urllib.parse import urlparse

import httpx

API = "https://api.github.com/repos/edithatogo/global-medicines-atlas"
ASSET_HOST = "release-assets.githubusercontent.com"
MAX_METADATA = 2 * 1024**2
MAX_PAYLOAD = 512 * 1024**2


def bounded_body(response: httpx.Response, limit: int) -> bytes:
    """Require a full, bounded success without exposing response URLs."""
    if response.status_code != HTTPStatus.OK:
        raise ValueError("Draft transport did not return a complete object")
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > limit:
            raise ValueError("Draft transport exceeds reviewed byte bound")
        chunks.append(chunk)
    return b"".join(chunks)


def _read_draft_payload(item: dict[str, Any]) -> bytes:
    """Accept one immutable asset from the committed unpublished draft only."""
    transport = item["draft_transport"]
    release_id = transport["release_id"]
    asset_id = transport["asset_id"]
    if (
        type(release_id) is not int
        or type(asset_id) is not int
        or release_id <= 0
        or asset_id <= 0
        or not 0 < item["bytes"] <= MAX_PAYLOAD
    ):
        raise ValueError("Invalid committed draft transport identity")
    headers = {
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json",
    }
    with httpx.Client(timeout=180, follow_redirects=False) as client:
        with client.stream(
            "GET", f"{API}/releases/{release_id}", headers=headers
        ) as response:
            release = json.loads(bounded_body(response, MAX_METADATA))
        required_release = {
            "id": release_id,
            "published_at": None,
            "tag_name": transport["tag_name"],
            "target_commitish": transport["target_commitish"],
        }
        if (
            release.get("draft") is not True
            or any(release.get(k) != v for k, v in required_release.items())
            or release.get("author", {}).get("login") != "edithatogo"
        ):
            raise ValueError("Draft transport ownership or state changed")
        assets = [
            asset for asset in release["assets"] if asset["id"] == asset_id
        ]
        if len(assets) != 1:
            raise ValueError("Committed draft asset missing or ambiguous")
        asset = assets[0]
        if (
            asset.get("name") != transport["asset_name"]
            or asset.get("state") != "uploaded"
            or asset.get("size") != item["bytes"]
            or asset.get("digest") != "sha256:" + item["sha256"]
            or asset.get("url") != f"{API}/releases/assets/{asset_id}"
        ):
            raise ValueError("Draft asset metadata differs from review")
        binary_headers = dict(headers, Accept="application/octet-stream")
        with client.stream(
            "GET", asset["url"], headers=binary_headers
        ) as response:
            if response.status_code == HTTPStatus.OK:
                payload = bounded_body(response, item["bytes"])
            elif response.status_code == HTTPStatus.FOUND:
                target = response.headers["location"]
                try:
                    parsed = urlparse(target)
                except ValueError:
                    raise ValueError(
                        "Draft asset redirect target denied"
                    ) from None
                if (
                    parsed.scheme != "https"
                    or parsed.netloc != ASSET_HOST
                    or parsed.username is not None
                    or parsed.fragment
                ):
                    raise ValueError("Draft asset redirect target denied")
                # Only the repository API receives a bearer. Never log the
                # short-lived asset URL or carry credentials to its host.
                with client.stream("GET", target) as download:
                    payload = bounded_body(download, item["bytes"])
            else:
                raise ValueError("Draft asset unavailable; URL withheld")
    if len(payload) != item["bytes"]:
        raise ValueError("Draft asset length differs from review")
    return payload


def read_draft_payload(item: dict[str, Any]) -> bytes:
    """Withhold signed URLs from transport-error tracebacks and logs."""
    try:
        return _read_draft_payload(item)
    except httpx.HTTPError, KeyError, json.JSONDecodeError:
        raise RuntimeError(
            "Draft transport unavailable; URLs withheld"
        ) from None
