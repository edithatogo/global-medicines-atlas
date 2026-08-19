"""Write the versioned global medicines-data source index."""

from __future__ import annotations

from pathlib import Path

from global_medicines_atlas.source_expansion import write_source_index

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "src"
    / "global_medicines_atlas"
    / "data"
    / "source_coverage_index_v1.json"
)


def main() -> None:
    write_source_index(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
