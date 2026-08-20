"""Bind executable governed-fixture landing evidence into the source catalog."""

from __future__ import annotations

import json
from pathlib import Path

from global_medicines_atlas.bronze_fixture_landing import (
    apply_fixture_qualification_to_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (
    ROOT
    / "src"
    / "global_medicines_atlas"
    / "data"
    / "medicine_source_catalog.json"
)


def main() -> None:
    """Rewrite the governed catalog deterministically."""

    document = json.loads(CATALOG.read_text(encoding="utf-8"))
    updated = apply_fixture_qualification_to_catalog(document)
    CATALOG.write_text(
        json.dumps(updated, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(CATALOG.relative_to(ROOT))


if __name__ == "__main__":
    main()
