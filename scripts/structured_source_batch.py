"""Execute finite structured-source recipes once, preserving explicit failures."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)

MIN_TABLE_ROWS = 3
MIN_TABLE_COLUMNS = 2
LIMIT = 64 * 1024 * 1024
STRUCTURED = re.compile(r"\.(csv|xlsx?|json|rss|xml)(?:[?#]|$)", re.IGNORECASE)
MEDICINE = re.compile(
    r"medic|drug|pharma|product|register|regist|price|reimburs|formul|subsid|recall|safety",
    re.IGNORECASE,
)


def structured_tables(data: bytes) -> list[str]:
    """Extract multi-column medicine tables, excluding navigation tables."""
    soup = BeautifulSoup(bytes(data), "html.parser")
    outputs: list[str] = []
    for table in soup.select("table"):
        rows = [
            [c.get_text(" ", strip=True) for c in r.select("th,td")]
            for r in table.select("tr")
        ]
        if (
            len(rows) < MIN_TABLE_ROWS
            or max(map(len, rows), default=0) < MIN_TABLE_COLUMNS
        ):
            continue
        if not MEDICINE.search(" ".join(rows[0])):
            continue
        stream = io.StringIO(newline="")
        csv.writer(stream, lineterminator="\n").writerows(rows)
        outputs.append(stream.getvalue())
    return outputs


def fetch(client: httpx.Client, url: str) -> tuple[bytes, str]:
    """Read one bounded response with no retries."""
    with client.stream("GET", url) as response:
        response.raise_for_status()
        chunks = bytearray()
        for chunk in response.iter_bytes():
            chunks.extend(chunk)
            if len(chunks) > LIMIT:
                raise ValueError("64 MiB acquisition bound exceeded")
        return bytes(chunks), response.headers.get("content-type", "").lower()


def export_link(data: bytes, url: str, hosts: tuple[str, ...]) -> str | None:
    soup = BeautifulSoup(data, "html.parser")
    for anchor in soup.select("a[href],link[rel='alternate']"):
        target = urljoin(url, str(anchor.get("href", "")))
        parsed = urlsplit(target)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in hosts
            or parsed.username
            or parsed.password
        ):
            continue
        if re.search(
            r"/comments/|sitemap|oembed|wp-json", target, re.IGNORECASE
        ):
            continue
        if STRUCTURED.search(target) and MEDICINE.search(
            target + " " + anchor.get_text()
        ):
            return target
    return None


def write_payload(directory: Path, data: bytes, content_type: str) -> list[str]:
    if "html" in content_type or not any(
        t in content_type
        for t in ("json", "csv", "xml", "excel", "spreadsheet", "octet-stream")
    ):
        raise ValueError("Response is not a supported structured format")
    (directory / "payload.bin").write_bytes(data)
    return ["payload.bin"]


def execute_recipe(recipe: dict[str, Any], directory: Path) -> list[str]:
    hosts = tuple(recipe["allowed_hosts"])
    transport = BoundIPAddressTransport(
        policy=AcquisitionPolicy(allowed_hosts=hosts)
    )
    with httpx.Client(
        transport=transport,
        trust_env=False,
        timeout=30,
        follow_redirects=True,
        max_redirects=3,
    ) as client:
        data, content_type = fetch(client, recipe["url"])
        if "html" not in content_type and not data.lstrip().lower().startswith((
            b"<!doctype html",
            b"<html",
        )):
            return write_payload(directory, data, content_type)
        tables = structured_tables(data)
        names: list[str] = []
        for index, table in enumerate(tables):
            path = directory / f"table-{index}.csv"
            path.write_text(table)
            names.append(path.name)
        if names:
            return names
        target = export_link(data, recipe["url"], hosts)
        if target is None:
            return []
        data, content_type = fetch(client, target)
        return write_payload(directory, data, content_type)


def acquire(recipe: dict[str, Any], output: Path) -> dict[str, Any]:
    """One source recipe; explicit failures, no retries or publication."""
    directory = output / recipe["source_id"]
    directory.mkdir()
    result: dict[str, Any] = {
        "source_id": recipe["source_id"],
        "state": "failed",
        "objects": [],
    }
    try:
        objects = execute_recipe(recipe, directory)
    except Exception as error:
        result.update(error=type(error).__name__, detail=str(error)[:500])
    else:
        result.update(
            state="downloaded_local"
            if objects
            else "needs_source_specific_adapter",
            objects=objects,
        )
        result["digests"] = {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in objects
        }
    (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    recipes: list[dict[str, Any]] = json.loads(args.manifest.read_text())[
        "sources"
    ]
    ids = [r["source_id"] for r in recipes]
    if len(ids) != len(set(ids)) or any(
        not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", sid) for sid in ids
    ):
        raise ValueError("Source IDs must be unique and path-safe")
    for recipe in recipes:
        parsed = urlsplit(str(recipe["url"]))
        if (
            parsed.scheme != "https"
            or parsed.hostname not in recipe["allowed_hosts"]
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Invalid recipe destination")
    if not args.execute:
        print(
            json.dumps({
                "sources": len(recipes),
                "state": "validated",
                "network_requests": 0,
            })
        )
        return
    if not args.output.resolve().is_relative_to(
        (Path(__file__).resolve().parents[1] / "build").resolve()
    ):
        raise ValueError("Output must be a fresh directory under build/")
    args.output.mkdir(exist_ok=False, parents=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(acquire, recipes, repeat(args.output)))
    (args.output / "results.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
