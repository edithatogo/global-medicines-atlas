"""Merge expansion sources into the single medicine source catalog."""

from __future__ import annotations

import json
from pathlib import Path

from global_medicines_atlas.source_catalog import SourceCatalog
from global_medicines_atlas.source_expansion_catalog import (
    apply_expansion_to_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"


def main() -> None:
    document = json.loads(CATALOG.read_text(encoding="utf-8"))
    merged = apply_expansion_to_catalog(document)
    SourceCatalog.model_validate(merged)
    CATALOG.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
