"""Observe source editions and public archive inventories without publishing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import httpx
from scripts import publish_bulk_archive, publish_october_openfda_hosted

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
    DestinationPolicyError,
)
from global_medicines_atlas.faers_acquisition import (
    discover_faers_ascii_releases,
)
from global_medicines_atlas.publication_transport import (
    ArtifactBinding,
    ArtifactVerification,
    PublicationPlan,
    PublicationTransportReceipt,
)

BATCHES = publish_bulk_archive.BATCHES
AEMS_INDEX = "https://fis.fda.gov/extensions/fpd-qde-faers/fpd-qde-faers.html"
NADAC_INDEX = (
    "https://data.medicaid.gov/api/1/metastore/schemas/dataset/items/"
    "fbb83258-11c7-47f5-8b18-5f8e79f7e704"
)
NADAC_FILENAME = (
    r"https://download\.medicaid\.gov/data/"
    r"nadac-national-average-drug-acquisition-cost-\d{2}-\d{2}-\d{4}\.csv"
)
CMS_BASELINE = BATCHES / "cms-medicaid-20261030"
EMA_BASELINE = BATCHES / "ema-tables-20261030"
HUB = "https://huggingface.co/api/datasets/"
METADATA_LIMIT = 4 * 1024**2
MONITORED_HOSTS = (
    "huggingface.co",
    "fis.fda.gov",
    "data.medicaid.gov",
    "www.ema.europa.eu",
)
OBSERVATION_ERRORS = (
    OSError,
    LookupError,
    ValueError,
    TypeError,
    httpx.HTTPError,
    DestinationPolicyError,
)


def response_chunks(
    client: httpx.Client, url: str, limit: int
) -> Iterable[bytes]:
    """Stream one complete public response with an explicit byte bound."""
    size = 0
    with client.stream(
        "GET", url, headers={"Accept-Encoding": "identity"}
    ) as response:
        response.raise_for_status()
        if response.status_code != HTTPStatus.OK:
            raise ValueError("Expected a complete source response")
        for chunk in response.iter_bytes(chunk_size=128 * 1024):
            size += len(chunk)
            if size > limit:
                raise ValueError("Source observation exceeded its byte limit")
            yield chunk


def metadata(client: httpx.Client, url: str) -> bytes:
    """Collect only the bounded metadata body."""
    return b"".join(response_chunks(client, url, METADATA_LIMIT))


def hub_info(
    client: httpx.Client, repository: str, revision: str
) -> dict[str, Any]:
    """Read a public Hub revision with its path, size and LFS inventory."""
    info = cast(
        "dict[str, Any]",
        json.loads(
            metadata(
                client,
                f"{HUB}{repository}/revision/{quote(revision, safe='')}?blobs=true",
            )
        ),
    )
    if info["private"] is not False or not re.fullmatch(
        r"[0-9a-f]{40}", info["sha"]
    ):
        raise ValueError("Expected a public immutable Hub revision")
    if (
        revision not in {"main", publish_bulk_archive.ARCHIVE_TAG}
        and info["sha"] != revision
    ):
        raise ValueError("Hub returned a different pinned revision")
    return info


def compare_inventory(
    info: dict[str, Any],
    expected: Iterable[ArtifactBinding | ArtifactVerification],
) -> dict[str, Any]:
    """Compare all paths and sizes, and SHA-256 where exposed by the Hub."""
    files = {item["rfilename"]: item for item in info["siblings"]}
    missing: list[str] = []
    drifted: list[str] = []
    observed_digests = 0
    for artifact in expected:
        item = files.get(artifact.relative_path)
        if item is None:
            missing.append(artifact.relative_path)
            continue
        lfs = item.get("lfs")
        if item.get("size") != artifact.size or (
            lfs is not None
            and (lfs["size"], lfs["sha256"]) != (artifact.size, artifact.sha256)
        ):
            drifted.append(artifact.relative_path)
        elif lfs is not None:
            observed_digests += 1
    return {
        "revision": info["sha"],
        "missing": missing,
        "drifted": drifted,
        "hub_digests_matched": observed_digests,
    }


def unavailable(error: Exception) -> dict[str, str | int]:
    """Keep failures visible without logging full remote responses."""
    result: dict[str, str | int] = {
        "state": "unavailable",
        "reason": type(error).__name__,
    }
    if isinstance(error, httpx.HTTPStatusError):
        result["http_status"] = error.response.status_code
    return result


def reconcile_batch(client: httpx.Client, folder: Path) -> dict[str, Any]:
    """Recheck inventory against a prior receipt of full anonymous verification."""
    receipt = PublicationTransportReceipt.model_validate_json(
        (folder / "verified.json").read_bytes()
    )
    if receipt.state.value != "public" or receipt.remote_revision is None:
        raise ValueError("No pinned public receipt")
    info = hub_info(client, receipt.target.repository, receipt.remote_revision)
    review = compare_inventory(info, receipt.verified_artifacts)
    return review | {
        "state": "drifted"
        if review["missing"] or review["drifted"]
        else "inventory_matches",
        "repository": receipt.target.repository,
        "receipt_objects": len(receipt.verified_artifacts),
    }


def october_status(client: httpx.Client) -> dict[str, Any]:
    """Reconcile the current partial mirror with its frozen, checksum-bound plan."""
    october = publish_october_openfda_hosted
    plan = PublicationPlan.model_validate_json(
        (BATCHES / october.BATCH / "publication-plan.json").read_bytes()
    )
    if plan.sha256() != october.PLAN_SHA256:
        raise ValueError("October plan differs from its recorded hash")
    info = hub_info(client, plan.target.repository, "main")
    review = compare_inventory(info, plan.artifacts)
    missing_zips = sum(path.endswith(".json.zip") for path in review["missing"])
    state = "incomplete" if review["missing"] else "inventory_matches"
    return review | {
        "state": "drifted" if review["drifted"] else state,
        "repository": plan.target.repository,
        "missing_zips": missing_zips,
        "missing_metadata": len(review["missing"]) - missing_zips,
    }


def aems_status(client: httpx.Client) -> dict[str, Any]:
    """Discover the latest FDA ASCII quarter and check its verification tag."""
    release = discover_faers_ascii_releases(
        metadata(client, AEMS_INDEX), AEMS_INDEX
    )[-1]
    batch = f"aems-{release.release_id.replace('-', '').lower()}"
    repository = f"edithatogo/global-medicines-atlas-{batch}"
    edition = {
        "edition": release.release_id,
        "source_url": str(release.url),
        "repository": repository,
    }
    try:
        info = hub_info(client, repository, publish_bulk_archive.ARCHIVE_TAG)
    except httpx.HTTPStatusError as error:
        if error.response.status_code not in {401, 404}:
            raise
        return edition | {"state": "no_public_verification_tag"}
    return edition | {
        "state": "public_verification_tag",
        "revision": info["sha"],
    }


def nadac_status(client: httpx.Client) -> dict[str, Any]:
    """Read the official release URL and compare it to the archived selection."""
    document = json.loads(metadata(client, NADAC_INDEX))
    url = next(
        entry["downloadURL"]
        for entry in document["distribution"]
        if re.fullmatch(NADAC_FILENAME, entry.get("downloadURL") or "")
    )
    baseline = next(
        entry["expected_url"]
        for entry in json.loads((CMS_BASELINE / "batch.json").read_bytes())
        if entry["source_id"] == "us-cms-nadac"
    )
    return {
        "state": "candidate" if url != baseline else "same_edition",
        "source_url": url,
        "baseline_url": baseline,
        "metadata_modified": document.get("modified"),
    }


def ema_status(client: httpx.Client) -> dict[str, Any]:
    """Compare the three approved EMA table URLs to their pinned source digests."""
    receipt = PublicationTransportReceipt.model_validate_json(
        (EMA_BASELINE / "verified.json").read_bytes()
    )
    artifacts = {
        item.relative_path: item for item in receipt.verified_artifacts
    }
    results: dict[str, Any] = {}
    for selection in json.loads((EMA_BASELINE / "batch.json").read_bytes()):
        source = selection["source_id"]
        url = selection["expected_url"]
        prior = artifacts[f"{source}/payload.bin"]
        size = 0
        checksum = hashlib.sha256()
        try:
            for chunk in response_chunks(client, url, selection["max_bytes"]):
                if size == 0 and not chunk.startswith(b"PK\x03\x04"):
                    raise ValueError("EMA did not return an XLSX workbook")
                size += len(chunk)
                checksum.update(chunk)
        except OBSERVATION_ERRORS as error:
            results[source] = {"source_url": url} | unavailable(error)
            continue
        if size == 0:
            results[source] = {
                "source_url": url,
                "state": "unavailable",
                "reason": "empty_response",
            }
            continue
        sha256 = checksum.hexdigest()
        results[source] = {
            "state": "same_bytes"
            if (size, sha256) == (prior.size, prior.sha256)
            else "candidate",
            "source_url": url,
            "size": size,
            "sha256": sha256,
            "baseline_revision": receipt.remote_revision,
        }
    return results


def archive_status(client: httpx.Client) -> dict[str, Any]:
    """Capture every source outcome independently."""
    report: dict[str, Any] = {"observed_at": datetime.now(UTC).isoformat()}
    for key, probe in (
        ("aems", aems_status),
        ("nadac", nadac_status),
        ("ema", ema_status),
        ("october_openfda", october_status),
    ):
        try:
            report[key] = probe(client)
        except (*OBSERVATION_ERRORS, StopIteration) as error:
            report[key] = unavailable(error)
    batches: dict[str, Any] = {}
    for path in json.loads((BATCHES / "archive-all.json").read_bytes())[
        "batches"
    ]:
        folder = publish_bulk_archive.ROOT / Path(path).parent
        try:
            batches[folder.name] = reconcile_batch(client, folder)
        except OBSERVATION_ERRORS as error:
            batches[folder.name] = unavailable(error)
    report["receipt_batches"] = batches
    return report


def summarize(report: dict[str, Any]) -> str:
    """Render the operator's next decisions from the observation."""
    aems, nadac, october = (
        report[key] for key in ("aems", "nadac", "october_openfda")
    )
    batches = report["receipt_batches"]
    healthy = sum(
        item["state"] == "inventory_matches" for item in batches.values()
    )
    lines = [
        "## Public archive status",
        "",
        f"- AEMS {aems.get('edition', '')}: {aems['state']}.",
        f"- CMS NADAC: {nadac['state']}. {nadac.get('source_url', '')}",
    ]
    for source, row in report["ema"].items():
        if isinstance(row, dict):
            lines.append(f"- EMA {source}: {row['state']}.")
    if report["ema"].get("state") == "unavailable":
        lines.append("- EMA observation unavailable.")
    lines.append(f"- October openFDA: {october['state']}.")
    if "missing_zips" in october:
        lines.append(
            f"  Missing {october['missing_zips']} ZIPs and {october['missing_metadata']} metadata files."
        )
    lines.append(
        f"- {healthy}/{len(batches)} earlier verified batches match their pinned inventories."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    """Write the report and GitHub job summary without publishing data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = AcquisitionPolicy(allowed_hosts=MONITORED_HOSTS, max_redirects=0)
    with httpx.Client(
        transport=BoundIPAddressTransport(policy=policy),
        timeout=30,
        trust_env=False,
    ) as client:
        report = archive_status(client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    summary = summarize(report)
    print(summary)
    if destination := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(destination).open("a", encoding="utf-8") as stream:
            stream.write(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
