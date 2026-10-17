"""Export the exact admitted July 2025 MBS Gold candidate to local Parquet."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from qualify_australian_mbs_gold_real_silver import (
    ADMISSION_PATH,
    OUTPUT_PATH,
    ROOT,
    SEMANTIC_PATH,
    _download_objects,  # ruff: ignore[import-private-name] -- reuse qualifier  # pyright: ignore[reportPrivateUsage]
    _load_verified_inputs,  # ruff: ignore[import-private-name] -- reuse qualifier  # pyright: ignore[reportPrivateUsage]
    _read_json,  # ruff: ignore[import-private-name] -- reuse qualifier  # pyright: ignore[reportPrivateUsage]
    _run_negative_controls,  # ruff: ignore[import-private-name] -- reuse qualifier  # pyright: ignore[reportPrivateUsage]
    _sha256,  # ruff: ignore[import-private-name] -- reuse qualifier  # pyright: ignore[reportPrivateUsage]
)
from qualify_australian_mbs_gold_real_silver import (
    main as qualify_main,
)

from global_medicines_atlas.mbs_gold_candidate_export import (
    write_mbs_gold_candidate_edges,
)
from global_medicines_atlas.mbs_gold_graph import (
    MbsGoldAdmittedSilverInput,
    MbsGoldGraphCandidate,
    build_mbs_gold_graph_from_admitted_silver,
)
from global_medicines_atlas.mbs_gold_scalar_projection import (
    project_mbs_gold_scalar_candidate,
)
from global_medicines_atlas.receipts import RightsState, SourceReceipt

SOURCE_RECEIPT_PATH = Path(
    "quality/bronze/receipts/au-mbs/"
    "bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d.json"
)


def _write_scalar_candidate(
    graph: MbsGoldGraphCandidate, scalar_output: Path
) -> dict[str, object]:
    source_receipt = SourceReceipt.model_validate_json(
        (ROOT / SOURCE_RECEIPT_PATH).read_bytes()
    )
    scalar_table = project_mbs_gold_scalar_candidate(graph, source_receipt)
    parquet_module: Any = pq
    write_table: Any = parquet_module.write_table
    write_table(scalar_table, scalar_output)
    return {
        "candidate_only": True,
        "row_count": scalar_table.num_rows,
        "parquet_sha256": hashlib.sha256(
            scalar_output.read_bytes()
        ).hexdigest(),
        "consumer_admission_performed": False,
        "path": str(scalar_output.resolve()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New local Parquet path; an existing file is never replaced.",
    )
    parser.add_argument(
        "--scalar-output",
        type=Path,
        help="Optional candidate-only scalar Parquet path for engine canaries.",
    )
    args = parser.parse_args(argv)
    output = args.output.expanduser()
    if output.exists():
        raise SystemExit(
            "candidate edge output already exists; refusing overwrite"
        )
    if not output.parent.is_dir():
        raise SystemExit("candidate edge output directory must exist")
    scalar_output = (
        args.scalar_output.expanduser() if args.scalar_output else None
    )
    if (
        scalar_output is not None
        and scalar_output.resolve() == output.resolve()
    ):
        raise SystemExit("candidate edge and scalar outputs must be distinct")
    if scalar_output is not None and (
        scalar_output.exists() or not scalar_output.parent.is_dir()
    ):
        raise SystemExit(
            "candidate scalar output must be a new path in an existing directory"
        )

    # The first check is metadata-only and prevents downloads on stale inputs.
    qualify_main(["--check"])
    admission, semantic, parity, _ = _load_verified_inputs()
    qualification = _read_json(OUTPUT_PATH)
    tables = _download_objects(admission, semantic, parity)
    metadata = tables["services"].schema.metadata or {}
    source = MbsGoldAdmittedSilverInput(
        source_sha256=admission["source_identity"]["source_sha256"],
        receipt_sha256=metadata[b"source_receipt_sha256"].decode(),
        catalog_version=admission["source_identity"]["schema_era"],
        source_record_count=admission["source_identity"]["source_record_count"],
        source_effective_date=date.fromisoformat(
            admission["source_identity"]["effective_at"]
        ),
        retrieved_at=datetime.fromisoformat(metadata[b"retrieved_at"].decode()),
        rights_state=RightsState(metadata[b"rights_state"].decode()),
        admission_sha256=_sha256((ROOT / ADMISSION_PATH).read_bytes()),
        semantic_manifest_sha256=_sha256((ROOT / SEMANTIC_PATH).read_bytes()),
    )
    graph = build_mbs_gold_graph_from_admitted_silver(
        tables["services"], tables["benefits"], source
    )
    if graph.graph_sha256 != qualification["graph"]["graph_sha256"]:
        raise SystemExit("built candidate differs from the qualified graph")
    if (
        _run_negative_controls(tables, source)
        != qualification["negative_controls"]
    ):
        raise SystemExit(
            "candidate negative controls differ from qualification"
        )

    receipt = write_mbs_gold_candidate_edges(
        graph,
        output,
        expected_graph_sha256=qualification["graph"]["graph_sha256"],
    )
    scalar_receipt: dict[str, object] | None = None
    if scalar_output is not None:
        scalar_receipt = _write_scalar_candidate(graph, scalar_output)
    print(
        json.dumps(
            {
                "candidate_only": True,
                "edge_count": receipt.edge_count,
                "file_byte_count": receipt.file_byte_count,
                "file_sha256": receipt.file_sha256,
                "graph_sha256": receipt.graph_sha256,
                "path": str(receipt.path.resolve()),
                "publication_performed": False,
                "review_state": "not_reviewed",
                "source_payload_bytes_retained": False,
                "scalar_candidate": scalar_receipt,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
