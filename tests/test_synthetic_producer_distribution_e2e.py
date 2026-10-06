"""End-to-end reconciliation of the non-publishable four-layer fixture."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from global_medicines_atlas.federation_distribution import (
    ProducedObject,
    load_synthetic_producer_inventory,
    reconcile_distribution,
)

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = (
    ROOT / "quality/qualifications/australian-benefits-synthetic-producer.json"
)
V4_ROOT = ROOT / "contracts/medallion/v4"
SCHEMA = (V4_ROOT / "federation.schema.json").read_bytes()
CONTRACT_FIXTURE = json.loads((V4_ROOT / "fixtures/valid.json").read_bytes())


def _contract_for_object(
    obj: ProducedObject, dataset: str, producer_repository: str
) -> bytes:
    """Bind one inventory row to a structurally valid synthetic v4 contract."""
    document: dict[str, Any] = copy.deepcopy(CONTRACT_FIXTURE)
    document["authority"]["producer_repository"] = producer_repository
    document["publication"]["run"] = (
        f"https://github.com/{producer_repository}/actions/runs/1"
    )
    document["source"].update(
        source_id=obj.source_id,
        acquisition_id=obj.acquisition_id,
        layer=obj.layer,
        bronze_stratum=obj.bronze_stratum,
        representation="projection",
        schema_era="synthetic-producer-v1",
        comparison_cohort="synthetic",
        effective_date=None,
    )
    location = document["location"]
    location.update(
        dataset=dataset,
        path=obj.path,
        bytes=obj.byte_count,
        sha256=obj.sha256,
    )
    verification = document["verification"]
    verification.update(
        dataset=dataset,
        path=obj.path,
        bytes=obj.byte_count,
        sha256=obj.sha256,
    )
    document["rights"].update(
        dataset=dataset,
        path=obj.path,
        subject_sha256=obj.sha256,
    )
    document["lineage"]["inputs"] = [verification["receipt"]]
    if obj.layer != "bronze":
        document["lineage"]["promotion_receipt"] = verification["receipt"]
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def _contracts_for_inventory() -> tuple[
    tuple[ProducedObject, ...], list[bytes], str
]:
    inventory = load_synthetic_producer_inventory(INVENTORY_PATH.read_bytes())
    contracts = [
        _contract_for_object(
            obj, inventory.dataset, inventory.producer_repository
        )
        for obj in inventory.objects
    ]
    return inventory.objects, contracts, inventory.dataset


@pytest.mark.e2e
def test_synthetic_producer_reconciles_complete_four_layer_denominator() -> (
    None
):
    """Match every caller-inventoried object to one pinned v4 projection."""
    inventory = load_synthetic_producer_inventory(INVENTORY_PATH.read_bytes())
    contracts = [
        _contract_for_object(
            item, inventory.dataset, inventory.producer_repository
        )
        for item in inventory.objects
    ]
    destinations = dict.fromkeys(
        ("bronze", "silver", "gold", "platinum"), inventory.dataset
    )

    bindings = reconcile_distribution(
        inventory.objects,
        list(reversed(contracts)),
        schema=SCHEMA,
        destinations=destinations,
    )

    assert inventory.publishable is False
    assert all(item.evidence_kind == "synthetic" for item in inventory.objects)
    assert tuple(binding.object for binding in bindings) == inventory.objects
    assert len(bindings) == 4
    assert {binding.object.layer for binding in bindings} == {
        "bronze",
        "silver",
        "gold",
        "platinum",
    }
    assert all(binding.revision == "a" * 40 for binding in bindings)


@pytest.mark.e2e
@pytest.mark.parametrize("missing", ["object", "contract"])
def test_synthetic_distribution_fails_closed_on_partial_denominator(
    missing: str,
) -> None:
    """Reject omitted producer rows and omitted matching v4 contracts."""
    objects, contracts, dataset = _contracts_for_inventory()
    if missing == "object":
        objects = objects[:-1]
    else:
        contracts = contracts[:-1]

    with pytest.raises(ValueError, match="distribution"):
        reconcile_distribution(
            objects,
            contracts,
            schema=SCHEMA,
            destinations=dict.fromkeys(
                ("bronze", "silver", "gold", "platinum"), dataset
            ),
        )
