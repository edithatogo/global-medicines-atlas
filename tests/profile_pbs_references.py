"""Synthetic full-path PBS reference assembly profile.

Run with PYTHONPATH=.:src:tests.  The workload creates only synthetic PBS XML,
then exercises entity Arrow assembly, literal-reference conversion, bounded
output slicing, Parquet write/read and metadata-aware equality.  It never reads
the public corpus, performs resolution, or qualifies a source.
"""

from __future__ import annotations

import json
import sys
from io import BytesIO
from statistics import median
from time import perf_counter

import pyarrow as pa
import pyarrow.parquet as pq
from test_au_pbs_v3 import _xml  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)

from global_medicines_atlas import pbs_references
from global_medicines_atlas.pbs_entities import iter_pbs_entity_batches


def _payload(items: int) -> bytes:
    template = _xml()
    start = template.index(b"<pbs:pharmaceutical-item")
    stop = template.index(b"</pbs:pharmaceutical-item>") + len(
        b"</pbs:pharmaceutical-item>"
    )
    item = template[start:stop]
    return template[:start] + item * items + template[stop:]


def _run(payload: bytes) -> tuple[int, int]:
    receipt = _receipt(payload, "au-pbs")

    def batches():  # type: ignore[no-untyped-def]
        return iter_pbs_entity_batches(payload, receipt, rows_per_batch=4096)

    rows = output_batches = 0
    for batch in pbs_references._reference_batches(  # pyright: ignore[reportPrivateUsage]
        batches(), batches(), 4096
    ):
        table = pa.Table.from_batches([batch])
        parquet = BytesIO()
        pq.write_table(table, parquet)  # pyright: ignore[reportUnknownMemberType]
        restored = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
            BytesIO(parquet.getvalue())
        )
        if not table.equals(restored, check_metadata=True):
            raise ValueError("synthetic reference Parquet parity failed")
        rows += batch.num_rows
        output_batches += 1
    return rows, output_batches


def main() -> None:
    """Measure alternating bounded samples and emit aggregate JSON only."""
    for items in (100, 1000):
        payload = _payload(items)
        samples = []
        result = (0, 0)
        for _ in range(3):
            started = perf_counter()
            result = _run(payload)
            samples.append(perf_counter() - started)
        sys.stdout.write(
            json.dumps(
                {
                    "synthetic_items": items,
                    "member_bytes": len(payload),
                    "reference_rows": result[0],
                    "output_batches": result[1],
                    "samples_seconds": samples,
                    "median_seconds": median(samples),
                    "full_arrow_conversion": True,
                    "parquet_roundtrip_verified": True,
                    "corpus_qualified": False,
                },
                sort_keys=True,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
