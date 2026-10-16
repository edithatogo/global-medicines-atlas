"""Verify exact public MBS six-table B2-to-Silver value parity in memory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from global_medicines_atlas.mbs_source_silver_parity import (
    DATASET,
    MBS_SILVER_OBJECTS,
    SILVER_DATASET_REVISION,
    SOURCE_DATASET_REVISION,
    SOURCE_OBJECT_BYTES,
    SOURCE_OBJECT_PATH,
    MbsSourceSilverTablesParityReceipt,
    verify_mbs_source_silver_tables_parity,
)
from global_medicines_atlas.receipts import SourceReceipt

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = (
    f"https://huggingface.co/datasets/{DATASET}/resolve/"
    f"{SOURCE_DATASET_REVISION}/{SOURCE_OBJECT_PATH}"
)
SOURCE_RECEIPT = ROOT / (
    "quality/bronze/receipts/au-mbs/"
    "bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d.json"
)


def _fetch(client: httpx.Client, url: str, expected_size: int) -> bytes:
    with client.stream("GET", url) as response:
        response.raise_for_status()
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > expected_size:
                raise ValueError(
                    "pinned public object exceeds expected byte count"
                )
            chunks.append(chunk)
    if size != expected_size:
        raise ValueError("pinned public object byte count differs")
    return b"".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_receipt = SourceReceipt.model_validate_json(
        SOURCE_RECEIPT.read_bytes()
    )
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        source_payload = _fetch(client, SOURCE_URL, SOURCE_OBJECT_BYTES)
        silver_payloads = {
            table: _fetch(
                client,
                f"https://huggingface.co/datasets/{DATASET}/resolve/"
                f"{SILVER_DATASET_REVISION}/{obj.path}",
                obj.byte_count,
            )
            for table, obj in MBS_SILVER_OBJECTS.items()
        }
    result: MbsSourceSilverTablesParityReceipt = (
        verify_mbs_source_silver_tables_parity(
            source_payload, source_receipt, silver_payloads
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
