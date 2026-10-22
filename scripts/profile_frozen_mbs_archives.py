"""Stream one exact frozen historical archive and emit bounded member metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import quote

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_archive_formats import profile_archive_formats
from global_medicines_atlas.mbs_archive_inventory import (
    DATASET,
    EXPECTED_ARCHIVES,
    REVISION,
    BoundArchive,
    load_archives,
)
from global_medicines_atlas.mbs_archive_members import (
    MAX_REPORT_BYTES,
    archive_policy,
    profile_archive_members,
)

if __package__:
    from scripts.profile_frozen_mbs_sidecars import (
        classify_inventory_failure,
        read_bounded_metadata,
        require_main_actions,
    )
else:
    from profile_frozen_mbs_sidecars import (
        classify_inventory_failure,
        read_bounded_metadata,
        require_main_actions,
    )

ROOT = Path(__file__).resolve().parents[1]
INFO_URL = f"https://huggingface.co/api/datasets/{DATASET}/revision/{REVISION}"
METADATA_LIMIT = 1024 * 1024


def _public(client: httpx.Client) -> None:
    info = json.loads(read_bounded_metadata(client, INFO_URL, METADATA_LIMIT))
    if (
        info.get("id") != DATASET
        or info.get("sha") != REVISION
        or info.get("private") is not False
        or info.get("gated") is not False
    ):
        raise ValueError("MBS archive exact public revision differs")


def _stage(
    client: httpx.Client, source: BoundArchive, destination: Path
) -> None:
    limit = archive_policy(source).max_archive_bytes
    if (
        type(source.source_bytes) is not int
        or not 0 < source.source_bytes <= limit
    ):
        raise ValueError("MBS archive source byte bound differs")
    url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{quote(source.source_path, safe='/')}?download=true"
    digest = hashlib.sha256()
    count = 0
    client.cookies.clear()
    with client.stream("GET", url) as response:
        response.raise_for_status()
        if response.headers.get("content-encoding", "identity") != "identity":
            raise ValueError("MBS archive response encoding differs")
        with destination.open("xb") as output:
            for chunk in response.iter_bytes(1024 * 1024):
                count += len(chunk)
                if count > source.source_bytes:
                    raise ValueError("MBS archive streamed byte bound exceeded")
                digest.update(chunk)
                output.write(chunk)
    if (
        count != source.source_bytes
        or digest.hexdigest() != source.source_sha256
    ):
        raise ValueError("MBS archive streamed identity differs")
    destination.chmod(0o400)


def qualify(
    exact_commit: str,
    archive_index: int,
    *,
    transport: httpx.BaseTransport | None = None,
    native_formats: bool = False,
) -> dict[str, Any]:
    """Read only the frozen cohort on exact main; stage privately without extraction."""
    require_main_actions(exact_commit)
    if (
        type(archive_index) is not int
        or not 0 <= archive_index < EXPECTED_ARCHIVES
    ):
        raise ValueError("MBS archive index is outside the frozen cohort")
    source = load_archives(ROOT)[archive_index]
    if source.dataset != DATASET or source.revision != REVISION:
        raise ValueError("MBS archive transport source identity differs")
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=120,
        max_bytes=archive_policy(source).max_archive_bytes,
        max_attempts=1,
        max_redirects=3,
    )
    with TemporaryDirectory(prefix="mbs-archive-inventory-") as temporary:
        path = Path(temporary) / "source.zip"
        with httpx.Client(
            transport=transport or BoundIPAddressTransport(policy=policy),
            trust_env=False,
            follow_redirects=True,
            max_redirects=3,
            timeout=120,
            headers={"Accept-Encoding": "identity"},
        ) as client:
            _public(client)
            _stage(client, source, path)
            report = (
                profile_archive_formats(path, source)
                if native_formats
                else profile_archive_members(path, source)
            )
            _public(client)
    return {
        "schema_version": 1,
        "status": "passed",
        "workflow_commit": exact_commit,
        "dataset": DATASET,
        "revision": REVISION,
        "archive_index": archive_index,
        "result": report,
        "temporary_source_removed": True,
        "member_formats_qualified": False,
        "native_format_profiles_executed": native_formats,
        "source_faithful_tables_qualified": False,
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
        "rights_conclusion_changed": False,
    }


def _encoded(report: dict[str, Any]) -> bytes:
    payload = (
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError("MBS archive aggregate byte bound exceeded")
    return payload


def main(argv: list[str] | None = None) -> int:
    """Preserve coded failure evidence while withholding source exception text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument(
        "--archive-index",
        type=int,
        choices=range(EXPECTED_ARCHIVES),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--formats", action="store_true")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("existing archive receipt must be preserved")
    try:
        report = (
            qualify(args.exact_commit, args.archive_index, native_formats=True)
            if args.formats
            else qualify(args.exact_commit, args.archive_index)
        )
        payload = _encoded(report)
    except Exception as error:
        report = {
            "schema_version": 1,
            "status": "failed",
            "reason": "archive-inventory-did-not-complete",
            "archive_index": args.archive_index,
            "failure_category": classify_inventory_failure(error),
            "new_admissions": 0,
            "publications": 0,
        }
        payload = (json.dumps(report, sort_keys=True) + "\n").encode()
    args.output.write_bytes(payload)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
