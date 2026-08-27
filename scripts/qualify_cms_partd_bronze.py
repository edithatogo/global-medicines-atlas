#!/usr/bin/env python3
"""Qualify the exact approved CMS Part D corpus without copying source bytes."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import pyarrow as pa
import pyarrow.parquet as pq

from global_medicines_atlas.cms_partd_acquisition import (
    CMSPartDAuthorization,
    CMSPartDInventory,
    inspect_cms_partd_payload,
    parse_cms_partd_inventory,
)

if TYPE_CHECKING:
    from pydantic import AnyHttpUrl

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT / "quality/qualifications/cms-partd-acquisition-authorization.json"
)
QUALIFICATION = ROOT / "quality/qualifications/cms-partd-bronze-20260827.json"


def _download_path(corpus: Path, url: str) -> Path:
    identity = sha256(url.encode()).hexdigest()
    return corpus / "payloads" / identity


def _load_inventory(corpus: Path) -> CMSPartDInventory:
    authorization = CMSPartDAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    authorization.require_payload_authority()
    authorization.require_publication_authority()
    return parse_cms_partd_inventory(
        (corpus / "formulary-data-gov.html").read_bytes(),
        (corpus / "spending-data-gov.html").read_bytes(),
        authorization=authorization,
    )


def qualify(corpus: Path, output: Path) -> dict[str, object]:
    """Verify every exact payload and emit rebuildable JSON/Parquet evidence."""
    inventory = _load_inventory(corpus)
    payload_rows: list[dict[str, object]] = []
    member_rows: list[dict[str, object]] = []
    total_bytes = 0
    families: tuple[
        tuple[Literal["formulary", "spending"], tuple[AnyHttpUrl, ...]], ...
    ] = (
        ("formulary", inventory.formulary_urls),
        ("spending", inventory.spending_urls),
    )
    for family, urls in families:
        for url in urls:
            path = _download_path(corpus, str(url))
            if not path.is_file():
                raise FileNotFoundError(f"CMS Part D payload missing: {url}")
            evidence = inspect_cms_partd_payload(path, url=url, family=family)
            total_bytes += evidence.byte_count
            payload_rows.append({
                "family": family,
                "url": str(url),
                "sha256": evidence.sha256,
                "byte_count": evidence.byte_count,
                "archive_member_count": len(evidence.archive_members),
            })
            member_rows.extend({
                "payload_sha256": evidence.sha256,
                "source_url": str(url),
                **member.model_dump(mode="json"),
            } for member in evidence.archive_members)
    output.mkdir(parents=True, exist_ok=True)
    payload_parquet = output / "cms-partd-payload-manifest.parquet"
    member_parquet = output / "cms-partd-archive-members.parquet"
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        pa.Table.from_pylist(payload_rows), payload_parquet
    )
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        pa.Table.from_pylist(member_rows), member_parquet
    )
    report: dict[str, object] = {
        "schema_id": "global-medicines-atlas.cms-partd-bronze-qualification",
        "schema_version": 1,
        "qualified_at": datetime.now(UTC).isoformat(),
        "prompt_id": 31,
        "source_ids": ["us-cms-partd-formulary", "us-cms-partd-spending"],
        "decision_status": "approved_public",
        "formulary_release_count": inventory.formulary_release_count,
        "spending_resource_count": inventory.spending_resource_count,
        "payload_count": len(payload_rows),
        "payload_byte_count": total_bytes,
        "archive_member_count": len(member_rows),
        "payload_manifest_sha256": sha256(payload_parquet.read_bytes()).hexdigest(),
        "archive_member_manifest_sha256": sha256(member_parquet.read_bytes()).hexdigest(),
        "source_bytes_committed": False,
        "publication_performed": False,
        "agreement_for_use_applies": True,
        "accurate_and_non_misleading_use_required": True,
        "total_us_utilisation_claimed": False,
        "net_price_claimed": False,
        "cross_plan_year_schema_equivalence_claimed": False,
        "payloads": payload_rows,
    }
    (output / "qualification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    report = qualify(args.corpus, args.output)
    if args.commit:
        QUALIFICATION.write_text(
            json.dumps(report, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
