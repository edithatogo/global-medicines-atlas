"""Property tests for the preserved NZULM/NZMT FHIR adapter."""

from __future__ import annotations

import json
import string
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given, settings
from hypothesis import strategies as st

from sources.nz.nzulm_fhir import iter_fhir_resources

FHIR_IDS = st.text(
    alphabet=string.ascii_letters + string.digits + "-.",
    min_size=1,
    max_size=24,
)


@given(resource_ids=st.lists(FHIR_IDS, min_size=1, max_size=20, unique=True))
@settings(max_examples=40, deadline=None)
def test_bundle_round_trip_preserves_unique_resource_identities(
    resource_ids: list[str],
) -> None:
    document = {
        "resourceType": "Bundle",
        "id": "property-bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Medication",
                    "id": resource_id,
                }
            }
            for resource_id in resource_ids
        ],
    }
    with TemporaryDirectory() as directory:
        source_root = Path(directory)
        path = source_root / "bundle.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        records = tuple(iter_fhir_resources([path], source_root=source_root))

    assert records[0].resource_type == "Bundle"
    assert records[0].resource_id == "property-bundle"
    assert [record.resource_id for record in records[1:]] == resource_ids
    assert len({
        (record.resource_type, record.resource_id) for record in records
    }) == (len(resource_ids) + 1)
    assert all(record.source_path == "bundle.json" for record in records)
    assert len({record.source_sha256 for record in records}) == 1


@given(resource_ids=st.lists(FHIR_IDS, min_size=1, max_size=20, unique=True))
@settings(max_examples=40, deadline=None)
def test_input_path_order_does_not_change_output_order(
    resource_ids: list[str],
) -> None:
    with TemporaryDirectory() as directory:
        source_root = Path(directory)
        paths: list[Path] = []
        for index, resource_id in enumerate(resource_ids):
            path = source_root / f"{len(resource_ids) - index:03}.json"
            path.write_text(
                json.dumps({"resourceType": "Medication", "id": resource_id}),
                encoding="utf-8",
            )
            paths.append(path)

        forward = tuple(iter_fhir_resources(paths, source_root=source_root))
        reverse = tuple(
            iter_fhir_resources(reversed(paths), source_root=source_root)
        )

    assert [
        (record.resource_type, record.resource_id, record.source_path)
        for record in forward
    ] == [
        (record.resource_type, record.resource_id, record.source_path)
        for record in reverse
    ]
