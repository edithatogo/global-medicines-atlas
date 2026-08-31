"""Synthetic entity size-accounting comparison; no acquisition/publication.

Run with PYTHONPATH=.:src:tests. Both paths measure every native field first;
the former path then re-encodes those fields inside their enclosing entity.
Parsing and Arrow conversion are outside this isolated serialization timing.
"""

import json
import sys
from statistics import median
from time import perf_counter, process_time

from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE

from global_medicines_atlas import pbs_entities as entities
from global_medicines_atlas.adapters.au_pbs import PBS_V3_NAMESPACE
from global_medicines_atlas.pbs_historical_projections import (
    iter_pbs_historical_domain_batches,
)
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)


def main() -> None:
    """Measure paired serialization work with exact per-entity byte parity."""
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
        rows = list(
            entities._entities(
                iter_pbs_historical_domain_batches(
                    archive, member, parent, binding
                )
            )
        )
        samples: dict[str, list[float]] = {"reencoded": [], "reused": []}
        cpu_samples: dict[str, list[float]] = {"reencoded": [], "reused": []}
        for sample in range(5):
            order = (
                tuple(samples) if sample % 2 == 0 else tuple(reversed(samples))
            )
            for name in order:
                started = perf_counter()
                cpu_started = process_time()
                for _, row, expected in rows:
                    size = sum(
                        entities._encoded_size(field)
                        for field in row["native_fields"]
                    )
                    if name == "reencoded":
                        actual = entities._encoded_size(row)
                    else:
                        actual = (
                            entities._encoded_size({**row, "native_fields": []})
                            + size
                            + len(row["native_fields"])
                            - 1
                        )
                    if actual != expected:
                        raise ValueError("synthetic entity size parity failed")
                samples[name].append(perf_counter() - started)
                cpu_samples[name].append(process_time() - cpu_started)
        sys.stdout.write(
            json.dumps(
                {
                    "synthetic_items": items,
                    "entities": len(rows),
                    "member_bytes": len(member),
                    "samples_seconds": samples,
                    "cpu_samples_seconds": cpu_samples,
                    "cpu_median_seconds": {
                        name: median(values)
                        for name, values in cpu_samples.items()
                    },
                    "median_seconds": {
                        name: median(values) for name, values in samples.items()
                    },
                    "exact_byte_parity": True,
                    "corpus_qualified": False,
                },
                sort_keys=True,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
