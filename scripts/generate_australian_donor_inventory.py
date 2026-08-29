#!/usr/bin/env python3
"""Generate the pinned Australian donor completeness inventory and schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.australian_donor_inventory import (
    AustralianDonorInventory,
    DonorRepository,
    build_inventory,
    validate_inventory,
)

GRAPH_REPOSITORY = "edithatogo/aus_mbs_pbs_graph"
GRAPH_REVISION = "64e764cebeb3826f98ce672cbb4affc65d06a92f"
SCRAPER_REPOSITORY = "edithatogo/aus-health-data-scraper"
SCRAPER_REVISION = "931da0b9b6ae3e3cec0743568abb71a50d62b7cf"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph-repo", type=Path, required=True)
    parser.add_argument("--scraper-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--schema-output", type=Path, required=True)
    arguments = parser.parse_args()
    donors = (
        DonorRepository(
            repository=GRAPH_REPOSITORY,
            revision=GRAPH_REVISION,
            git_dir=arguments.graph_repo.resolve(),
        ),
        DonorRepository(
            repository=SCRAPER_REPOSITORY,
            revision=SCRAPER_REVISION,
            git_dir=arguments.scraper_repo.resolve(),
        ),
    )
    inventory = build_inventory(donors)
    result = validate_inventory(inventory, donors)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.schema_output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(inventory.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    )
    arguments.schema_output.write_text(
        json.dumps(
            AustralianDonorInventory.model_json_schema(),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(result.model_dump_json())


if __name__ == "__main__":
    main()
