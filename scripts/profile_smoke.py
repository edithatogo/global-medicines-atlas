"""Deterministic, network-free workload for Scalene regression profiling."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from global_medicines_atlas.nz import (
    project_nz_fhir_records,
)
from global_medicines_atlas.source_catalog import (
    load_source_catalog,
)
from sources.nz.nzulm_fhir import (
    load_upstream_fixture_records,
)


def main() -> None:
    records = load_upstream_fixture_records(PROJECT_ROOT)
    canonical = ()
    for _ in range(5_000):
        canonical = project_nz_fhir_records(records)

    assert canonical
    assert load_source_catalog()


if __name__ == "__main__":
    main()
