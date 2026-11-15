"""Reproduce four existing MBS outputs from a classified public source in memory.

This bounded replay writes only value-free metadata. It never downloads the
archived Parquet files, retains source or output bytes, adds a source, changes
rights, admits data, runs consumers, or publishes a dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- Fixed Git objects only.
import sys
import tomllib
from datetime import UTC, datetime
from operator import itemgetter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import scripts.qualify_australian_schedule_source_privacy as source_privacy
import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_four_projection_dossiers as dossiers

from global_medicines_atlas.adapters.au_mbs import parse_mbs_source_xml
from global_medicines_atlas.mbs_release import mbs_source_parquet
from global_medicines_atlas.receipts import SourceReceipt

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_LOCK_SHA256 = (
    "fda3136b32e7409561a2c532cd978d840d146779b6fed1b4b1d9b18ae39950cb"
)
OLD_MARKER = b"parquet-cpp-arrow version 25.0.0"
NEW_MARKER = b"parquet-cpp-arrow version 26.0.0"
PARQUET_MAGIC = b"PAR1"
TRAILER_BYTES = 8
EVENT_ID = "f5626f2deb09f4301989480f112ec117ccad9efafc54c04d161100d6c5ca08e1"
SOURCE_REVISION = "b925a8a80b0f90db09513e7ce1378045461b05c0"
SOURCE_URL = (
    "https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/"
    f"resolve/{SOURCE_REVISION}/{source_privacy.SOURCE_PATH}"
)
CODE_PATHS = (
    "scripts/reconcile_mbs_privacy_replay.py",
    "src/global_medicines_atlas/adapters/au_mbs.py",
    "src/global_medicines_atlas/mbs_release.py",
    "src/global_medicines_atlas/adapters/_receipt.py",
    "src/global_medicines_atlas/mbs_compatibility.py",
)


def adjusted_writer_footer(payload: bytes) -> tuple[bytes, dict[str, int]]:
    """Change one equal-length writer marker, only within a Parquet footer."""
    if (
        len(payload) < TRAILER_BYTES + len(PARQUET_MAGIC)
        or payload[:4] != PARQUET_MAGIC
        or payload[-4:] != PARQUET_MAGIC
        or len(OLD_MARKER) != len(NEW_MARKER)
    ):
        raise ValueError("invalid generated Parquet boundaries")
    footer_bytes = int.from_bytes(payload[-8:-4], "little")
    footer_start = len(payload) - TRAILER_BYTES - footer_bytes
    marker_at = payload.find(NEW_MARKER)
    if (
        footer_start < len(PARQUET_MAGIC)
        or payload.count(NEW_MARKER) != 1
        or marker_at < footer_start
        or marker_at + len(NEW_MARKER) > len(payload) - TRAILER_BYTES
    ):
        raise ValueError("generated writer marker is not unique in the footer")
    adjusted = (
        payload[:marker_at]
        + OLD_MARKER
        + payload[marker_at + len(NEW_MARKER) :]
    )
    return adjusted, {"footer_start": footer_start, "marker_offset": marker_at}


def check_historical_locks(root: Path = ROOT) -> dict[str, str]:
    """Check both historical lock bytes and their actual PyArrow pin."""
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git is required for historical lock checks")
    commits: dict[str, str] = {}
    for name, product in dossiers.PRODUCTS.items():
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- Fixed commit and path.
            [git, "show", f"{product['commit']}:uv.lock"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        if hashlib.sha256(result.stdout).hexdigest() != HISTORICAL_LOCK_SHA256:
            raise ValueError("historical producer lock digest differs")
        lock = tomllib.loads(result.stdout.decode())
        versions = [
            p["version"] for p in lock["package"] if p["name"] == "pyarrow"
        ]
        if versions != ["25.0.0"]:
            raise ValueError("historical producer PyArrow pin differs")
        commits[name] = str(product["commit"])
    return commits


def classified_inputs(
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, SourceReceipt]]:
    """Fail closed before source access unless each input is exactly bound."""
    report = dossiers.build_report(root)
    event = bounded.read_bound_metadata(
        root, *source_privacy.SOURCE_RECEIPTS[EVENT_ID]
    )
    sensitivity = event["sensitivity"]
    if not all((
        event.get("schema_id")
        == "global-medicines-atlas.bronze-acquisition-event",
        event.get("schema_version") == source_privacy.EVENT_SCHEMA_VERSION,
        event.get("source_id") == "au-mbs",
        event.get("source_version") == "2026-08-01",
        event.get("evidence_class") == "live",
        event.get("payload_sha256")
        == event.get("content_id")
        == source_privacy.SOURCE_SHA,
        event.get("acquisition_id") == EVENT_ID,
        event["retrieval"]["status"] == "succeeded",
        sensitivity.get("schema_id")
        == "global-medicines-atlas.bronze-sensitivity-classification",
        sensitivity.get("schema_version") == 1,
        sensitivity.get("data_sensitivity") == "non_sensitive",
        sensitivity.get("personal_data") == "none",
        sensitivity.get("publication") == "permitted",
        set(sensitivity.get("reason_codes", []))
        == {"qualified_official_mbs_schedule", "exact_release_approval"},
        event["retrieval"]["http"]["observed_byte_length"]
        == source_privacy.SOURCE_BYTES,
    )):
        raise ValueError("MBS source classification is not exact")
    receipts: dict[str, SourceReceipt] = {}
    for name in dossiers.PRODUCTS:
        path, digest = dossiers.INPUTS[f"{name}_receipt"]
        value = bounded.read_bound_metadata(root, path, digest)
        uri_text: object = value["retrieval"]["uri"]
        if not isinstance(uri_text, str):
            raise TypeError("MBS producer receipt URI differs")
        uri = urlsplit(uri_text)
        if not all((
            uri.scheme == "https",
            uri.hostname == "www.mbsonline.gov.au",
            uri.username is None,
            uri.password is None,
            not uri.query,
            not uri.fragment,
            value["payload"]["sha256"] == source_privacy.SOURCE_SHA,
            value["payload"]["byte_count"] == source_privacy.SOURCE_BYTES,
            value["sensitivity"]["data_sensitivity"] == "non_sensitive",
            value["sensitivity"]["personal_data"] == "none",
        )):
            raise ValueError("MBS producer receipt is not exactly classified")
        receipts[name] = SourceReceipt.model_validate(value)
    return report, receipts


def read_classified_source(root: Path = ROOT) -> bytes:
    """Stream only the prequalified archive object into bounded memory."""
    classified_inputs(root)
    raw = bytearray()
    with (
        httpx.Client(
            follow_redirects=True,
            timeout=90,
            headers={"Accept-Encoding": "identity"},
        ) as client,
        client.stream("GET", SOURCE_URL) as response,
    ):
        response.raise_for_status()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
            if len(raw) > source_privacy.SOURCE_BYTES:
                raise ValueError("classified MBS source exceeds its bound")
    if (
        len(raw) != source_privacy.SOURCE_BYTES
        or hashlib.sha256(raw).hexdigest() != source_privacy.SOURCE_SHA
    ):
        raise ValueError("classified MBS source identity differs")
    return bytes(raw)


def replay(root: Path = ROOT) -> dict[str, Any]:
    """Replay known public schedule projections without disclosing their rows."""
    if (
        sys.version_info[:3] != (3, 15, 1)
        or importlib.metadata.version("pyarrow") != "26.0.0"
    ):
        raise RuntimeError(
            "replay requires the exact qualified Python and PyArrow"
        )
    report, receipts = classified_inputs(root)
    commits = check_historical_locks(root)
    source = read_classified_source(root)
    results: list[dict[str, Any]] = []
    for name, receipt in receipts.items():
        batch = parse_mbs_source_xml(source, receipt)
        if batch.record_count != dossiers.SOURCE_RECORDS:
            raise ValueError("MBS schedule record count differs")
        for only_p7 in (False, True):
            filename = "p7.parquet" if only_p7 else "source.parquet"
            targets = [
                r
                for r in report["dossiers"]
                if r["producer"] == name and r["path"].endswith("/" + filename)
            ]
            if len(targets) != 1:
                raise ValueError("MBS replay target differs")
            target = targets[0]
            generated = mbs_source_parquet(batch, only_p7=only_p7)
            direct_sha = hashlib.sha256(generated).hexdigest()
            adjusted, footer = adjusted_writer_footer(generated)
            adjusted_sha = hashlib.sha256(adjusted).hexdigest()
            if (
                len(adjusted) != target["byte_count"]
                or adjusted_sha != target["sha256"]
            ):
                raise ValueError(
                    "footer-adjusted MBS replay does not match exact object"
                )
            results.append({
                "dataset": target["dataset"],
                "revision": target["revision"],
                "path": target["path"],
                "sha256": target["sha256"],
                "byte_count": target["byte_count"],
                "producer": name,
                "unadjusted_sha256": direct_sha,
                "footer_adjusted_sha256": adjusted_sha,
                "footer_start": footer["footer_start"],
                "marker_offset": footer["marker_offset"],
                "writer_marker_occurrences": 1,
                "exact_digest_after_footer_substitution": True,
            })
            del generated, adjusted
        del batch
    del source
    return {
        "schema_id": "global-medicines-atlas.mbs-classified-schedule-in-memory-replay",
        "schema_version": 1,
        "observed_at": datetime.now(UTC).isoformat(),
        "source": {
            "dataset": dossiers.existing.DATASET,
            "revision": SOURCE_REVISION,
            "path": source_privacy.SOURCE_PATH,
            "sha256": source_privacy.SOURCE_SHA,
            "byte_count": source_privacy.SOURCE_BYTES,
            "classification_event": EVENT_ID,
        },
        "writer": {
            "python": "3.15.1",
            "current_pyarrow": "26.0.0",
            "historical_pyarrow": "25.0.0",
            "historical_lock_sha256": HISTORICAL_LOCK_SHA256,
            "historical_commits": commits,
            "method": "one equal-length writer-version marker changed in generated Parquet footer; no historical writer executed",
        },
        "implementation_sha256": {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest()
            for path in CODE_PATHS
        },
        "objects": sorted(results, key=itemgetter("path")),
        "boundaries": {
            "classified_source_read_in_memory": True,
            "source_or_output_bytes_written": False,
            "source_values_emitted": False,
            "participant_or_cohort_data_accessed": False,
            "new_source_added": False,
            "dataset_published": False,
            "rights_changed": False,
            "v4_admission": False,
            "consumer_check": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = replay()
    with args.report.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print(
        json.dumps({
            "objects_matched": len(result["objects"]),
            "source_or_output_bytes_written": False,
        })
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
