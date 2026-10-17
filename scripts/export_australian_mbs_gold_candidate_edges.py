"""Export the exact admitted July 2025 MBS Gold candidate to local Parquet."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

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
    build_mbs_gold_graph_from_admitted_silver,
)
from global_medicines_atlas.receipts import RightsState


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New local Parquet path; an existing file is never replaced.",
    )
    args = parser.parse_args(argv)
    output = args.output.expanduser()
    if output.exists():
        raise SystemExit(
            "candidate edge output already exists; refusing overwrite"
        )
    if not output.parent.is_dir():
        raise SystemExit("candidate edge output directory must exist")

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
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
