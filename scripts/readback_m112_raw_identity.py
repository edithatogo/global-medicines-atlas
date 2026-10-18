"""Hash remaining frozen M-112 raw objects by anonymous streaming readback."""

from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from operator import itemgetter
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
INPUT = (
    ROOT
    / "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261018.json"
)
OUTPUT = (
    ROOT
    / "quality/qualifications/australian-m112-raw-identity-readback-20261018.json"
)
EXPECTED_RAW_GAPS = 92
EXPECTED_DATASET = "edithatogo/reimbursement-atlas"
EXPECTED_REVISION = "8e062578f14e12cf3238700a93946339da9c5d88"
CONTENT_ADDRESSED_NAME = re.compile(r"/([0-9a-f]{64})\.[^/]+$")
HTTP_OK = 200


def _read_object(row: dict[str, Any]) -> dict[str, Any]:
    path = row["path"]
    url = (
        f"https://huggingface.co/datasets/{row['dataset']}/resolve/"
        f"{row['revision']}/{path}"
    )
    if not url.startswith("https://huggingface.co/datasets/"):
        raise ValueError(
            "identity readback URL must use the Hugging Face HTTPS endpoint"
        )
    request = Request(
        url, headers={"User-Agent": "global-medicines-atlas-m112-identity/1"}
    )
    digest = hashlib.sha256()
    byte_count = 0
    # The endpoint is constructed above from a pinned public dataset identity.
    with urlopen(request, timeout=45) as response:  # ruff: ignore[suspicious-url-open-usage] -- request URL is fixed to the pinned public HTTPS dataset endpoint above
        if response.status != HTTP_OK:
            raise RuntimeError(
                f"anonymous readback returned HTTP {response.status}: {path}"
            )
        while chunk := response.read(256 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    expected = row["identity"]["byte_count"]
    path_digest_match = CONTENT_ADDRESSED_NAME.search(path)
    if byte_count != expected:
        raise RuntimeError(
            f"byte count mismatch for {path}: expected {expected}, got {byte_count}"
        )
    if (
        path_digest_match is None
        or path_digest_match.group(1) != digest.hexdigest()
    ):
        raise RuntimeError(
            f"content-addressed filename SHA-256 mismatch: {path}"
        )
    return {
        "dataset": row["dataset"],
        "revision": row["revision"],
        "path": path,
        "byte_count": byte_count,
        "sha256": digest.hexdigest(),
        "path_basename_sha256": path_digest_match.group(1),
        "path_basename_sha256_matches": True,
        "anonymous_readback": True,
        "byte_count_match": True,
        "payload_values_inspected": False,
        "bytes_persisted_locally": False,
    }


def main() -> None:
    source = json.loads(INPUT.read_text(encoding="utf-8"))
    rows = [
        row
        for row in source["objects"]
        if row["candidate_class"] == "raw_source_payload"
        and row["dataset"] == EXPECTED_DATASET
        and not row["identity"].get("sha256")
    ]
    if len(rows) != EXPECTED_RAW_GAPS or any(
        row["dataset"] != EXPECTED_DATASET
        or row["revision"] != EXPECTED_REVISION
        for row in rows
    ):
        raise RuntimeError("the exact frozen 92-object PBS raw gap changed")

    with ThreadPoolExecutor(max_workers=4) as pool:
        observed = list(pool.map(_read_object, rows))
    if len(observed) != EXPECTED_RAW_GAPS:
        raise RuntimeError("not every expected raw object was read back")

    receipt = {
        "schema_id": "global-medicines-atlas.australian-m112-raw-identity-readback",
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "purpose": "Bind the remaining frozen PBS raw paths to anonymous SHA-256 readbacks without changing rights, lineage, admission, or release decisions.",
        "method": {
            "transport": "HTTPS resolve endpoint at the exact immutable Hugging Face dataset revision",
            "requests_authenticated": False,
            "stream_chunk_bytes": 262144,
            "bytes_persisted_locally": False,
            "payload_values_inspected": False,
            "rights_or_licensing_conclusion": False,
            "content_addressed_basename_verified_against_streamed_sha256": True,
        },
        "scope": {
            "dataset": EXPECTED_DATASET,
            "revision": EXPECTED_REVISION,
            "raw_path_count": len(observed),
            "bytes_streamed": sum(row["byte_count"] for row in observed),
            "approved_denominator_changed": False,
        },
        "evidence_input": {
            "path": str(INPUT.relative_to(ROOT)),
            "sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        },
        "objects": sorted(observed, key=itemgetter("path")),
    }
    OUTPUT.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
