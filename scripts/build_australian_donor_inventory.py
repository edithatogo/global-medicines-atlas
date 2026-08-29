#!/usr/bin/env python3
"""Build the pinned Australian donor inventory qualification document."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

from global_medicines_atlas.donor_inventory import build_donor_inventory

GRAPH_COMMIT = "64e764cebeb3826f98ce672cbb4affc65d06a92f"
SCRAPER_COMMIT = "931da0b9b6ae3e3cec0743568abb71a50d62b7cf"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph-repository", required=True, type=Path)
    parser.add_argument("--scraper-repository", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _file_index(
    repositories: list[dict[str, object]],
) -> dict[tuple[str, str], dict[str, object]]:
    index: dict[tuple[str, str], dict[str, object]] = {}
    for repository in repositories:
        name = cast("str", repository["repository"])
        files = cast("list[dict[str, object]]", repository["files"])
        for file_entry in files:
            index[name, cast("str", file_entry["path"])] = file_entry
    return index


def _findings(
    repositories: list[dict[str, object]],
) -> list[dict[str, object]]:
    files = _file_index(repositories)

    def evidence(repository: str, path: str) -> dict[str, object]:
        entry = files[repository, path]
        return {
            "repository": repository,
            "path": path,
            "sha256": entry["sha256"],
        }

    return [
        {
            "id": "graph-mbs-guessed-record-tag",
            "state": "replace_and_preserve_legacy",
            "summary": (
                "Parser guesses MBSItem, while the retained payload uses "
                "MBS_XML/Data records."
            ),
            "evidence": [
                evidence(
                    "edithatogo/aus_mbs_pbs_graph",
                    "scripts/parsing/parse_mbs_xml.py",
                ),
                evidence(
                    "edithatogo/aus_mbs_pbs_graph",
                    "scripts/parsing/MBS-XML-20250701 Version 3.XML",
                ),
            ],
        },
        {
            "id": "graph-pbs-parser-invalid-syntax",
            "state": "replace_and_preserve_legacy",
            "summary": "The PBS parser is not valid Python at the pinned commit.",
            "evidence": [
                evidence(
                    "edithatogo/aus_mbs_pbs_graph",
                    "scripts/parsing/parse_pbs_xml.py",
                )
            ],
        },
        {
            "id": "scraper-output-path-type-mismatch",
            "state": "replace_and_preserve_legacy",
            "summary": (
                "The caller supplies a CSV file path where the processor expects "
                "an output directory and appends dataset.csv."
            ),
            "evidence": [
                evidence("edithatogo/aus-health-data-scraper", "src/main.py"),
                evidence(
                    "edithatogo/aus-health-data-scraper", "src/processor.py"
                ),
            ],
        },
        {
            "id": "scraper-zero-byte-artifacts",
            "state": "retain_legacy_evidence",
            "summary": (
                "Seven notebooks and three package/data sentinels are zero-byte "
                "history, not data coverage."
            ),
            "evidence": [
                {
                    "repository": "edithatogo/aus-health-data-scraper",
                    "paths": sorted(
                        cast("str", entry["path"])
                        for entry in cast(
                            "list[dict[str, object]]",
                            repositories[1]["files"],
                        )
                        if entry["implementation_state"] == "zero_byte"
                    ),
                }
            ],
        },
        {
            "id": "scraper-green-with-no-data",
            "state": "source_drift_evidence",
            "summary": (
                "The 2026-08-01 scheduled run completed successfully after six "
                "HTTP 404 responses and produced no acquired files or commit."
            ),
            "external_evidence": {
                "actions_run": "https://github.com/edithatogo/aus-health-data-scraper/actions/runs/30677814193",
                "observed_http_404_count": 6,
                "produced_file_count": 0,
                "produced_commit": False,
            },
        },
    ]


def main() -> None:
    """Build and write the deterministic combined inventory."""
    arguments = _arguments()
    repositories = [
        build_donor_inventory(
            arguments.graph_repository,
            repository_name="edithatogo/aus_mbs_pbs_graph",
            expected_commit=GRAPH_COMMIT,
            source_url="https://github.com/edithatogo/aus_mbs_pbs_graph",
        ),
        build_donor_inventory(
            arguments.scraper_repository,
            repository_name="edithatogo/aus-health-data-scraper",
            expected_commit=SCRAPER_COMMIT,
            source_url="https://github.com/edithatogo/aus-health-data-scraper",
        ),
    ]
    denominator = {
        "repositories": repositories,
        "tracked_blob_count": sum(
            cast("int", repository["tracked_blob_count"])
            for repository in repositories
        ),
        "total_blob_bytes": sum(
            cast("int", repository["total_blob_bytes"])
            for repository in repositories
        ),
    }
    document: dict[str, object] = {
        "schema_version": "1.0",
        "qualification": "australian-health-donor-inventory",
        "denominator": denominator,
        "denominator_sha256": hashlib.sha256(
            _canonical_bytes(denominator)
        ).hexdigest(),
        "findings": _findings(repositories),
        "coverage_policy": {
            "all_legacy_data_included": True,
            "zero_byte_artifacts_are_coverage": False,
            "raw_payload_destination": "public_hugging_face_dataset",
            "repository_is_durable_raw_storage": False,
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
