"""Synthetic fixture-only PBS microbenchmark, not corpus qualification.

Run with PYTHONPATH=.:src:tests. Test builders supply synthetic archive lineage;
no source is acquired or published. Keep the former row algorithm only here
as a measurement/parity oracle, never as a second production route.
"""

from __future__ import annotations

import json
import sys
from statistics import median
from time import perf_counter

import pyarrow as pa
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE

from global_medicines_atlas import pbs_domain as domain
from global_medicines_atlas.adapters.au_pbs import PBS_V3_NAMESPACE
from global_medicines_atlas.pbs_historical_silver import (
    iter_pbs_historical_silver_batches,
)
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)


def row_reference(batch: pa.RecordBatch) -> pa.RecordBatch:
    """Retain the pre-optimization algorithm solely as a synthetic oracle."""
    schema = batch.schema
    for field in domain._ADDITIONS:
        schema = schema.append(field)  # pyright: ignore[reportUnknownMemberType]
    metadata = dict(schema.metadata or {})
    metadata.update({
        b"schema_name": b"global-medicines-atlas.pbs-silver.domain-fields",
        b"mapping_profile": b"pbs-adapter-structural-v2",
    })
    schema = schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]
    return pa.RecordBatch.from_pylist(
        [{**row, **domain._mapping(row)} for row in batch.to_pylist()],
        schema=schema,
    )


def main() -> None:
    """Measure five alternating paired samples with exact synthetic parity."""
    for items in (100, 1000):
        member = (
            f'<schedule xmlns="{PBS_V3_NAMESPACE}">'
            + "".join(
                f'<pharmaceutical-item xml:id="{index}"><code>{index}</code>'
                f"<name>Synthetic {index}</name></pharmaceutical-item>"
                for index in range(items)
            )
            + "</schedule>"
        ).encode()
        archive = _zip([(PATH, member)])
        parent = _receipt(archive, SOURCE)
        binding = build_pbs_xml_member_binding(archive, parent)
        batches = list(
            iter_pbs_historical_silver_batches(archive, member, parent, binding)
        )
        for batch in batches:
            actual = next(domain._domain_batches(iter([batch])))
            if not actual.equals(row_reference(batch), check_metadata=True):
                raise ValueError("synthetic domain parity failed")
        samples: dict[str, list[float]] = {"row_reference": [], "columnar": []}
        for sample in range(5):
            order = (
                tuple(samples) if sample % 2 == 0 else tuple(reversed(samples))
            )
            for name in order:
                started = perf_counter()
                if name == "row_reference":
                    for batch in batches:
                        row_reference(batch)
                else:
                    for _batch in domain._domain_batches(iter(batches)):
                        pass
                samples[name].append(perf_counter() - started)
        sys.stdout.write(
            json.dumps(
                {
                    "synthetic_items": items,
                    "member_bytes": len(member),
                    "native_rows": sum(batch.num_rows for batch in batches),
                    "batches": len(batches),
                    "samples_seconds": samples,
                    "median_seconds": {
                        name: median(values) for name, values in samples.items()
                    },
                    "exact_metadata_parity": True,
                    "corpus_qualified": False,
                },
                sort_keys=True,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
