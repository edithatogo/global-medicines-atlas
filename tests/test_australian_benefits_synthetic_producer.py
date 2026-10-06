"""Synthetic Australian benefits producer denominator contract."""

import json
from pathlib import Path

import pytest

from global_medicines_atlas.federation_distribution import (
    load_synthetic_producer_inventory,
)
from global_medicines_atlas.federation_reader import METADATA_BYTES

ROOT = Path(__file__).parents[1]
FIXTURE = (
    ROOT / "quality/qualifications/australian-benefits-synthetic-producer.json"
)


@pytest.mark.unit
def test_synthetic_producer_is_complete_non_publishable_and_layered() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    objects = document["objects"]

    assert (
        document["schema_id"]
        == "global-medicines-atlas.synthetic-producer-inventory"
    )
    assert document["evidence_kind"] == "synthetic"
    assert document["publishable"] is False
    assert {item["layer"] for item in objects} == {
        "bronze",
        "silver",
        "gold",
        "platinum",
    }
    assert all(item["byte_count"] > 0 for item in objects)
    identities = {
        (item["source_id"], item["acquisition_id"], item["layer"], item["path"])
        for item in objects
    }
    assert len(identities) == len(objects)


@pytest.mark.unit
def test_synthetic_producer_contains_no_remote_or_payload_claims() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    assert "http://" not in text
    assert "https://" not in text
    assert "payload" not in text.lower()


@pytest.mark.unit
def test_synthetic_objects_have_content_addressable_layer_paths() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))

    for item in document["objects"]:
        assert len(item["sha256"]) == 64
        assert all(
            character in "0123456789abcdef" for character in item["sha256"]
        )
        assert item["path"].startswith(f"{item['layer']}/")
        assert item["path"].rsplit(".", 1)[-1] in {"json", "parquet"}
        if item["layer"] == "bronze":
            # Bronze is the three-stratum evidentiary boundary.  A complete
            # producer may legitimately contribute a source index (B0),
            # acquisition metadata (B1), or raw evidence (B2); do not make
            # the denominator silently equate Bronze with B2.
            assert item["bronze_stratum"] in {"B0", "B1", "B2"}
        else:
            assert item["bronze_stratum"] is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw",
    [
        b"",
        bytearray(b"{}"),
        b"x" * (METADATA_BYTES + 1),
        b"not-json",
        b"[]",
        b'{"schema_id":"wrong"}',
        b'{"schema_id":"duplicate","schema_id":"duplicate"}',
    ],
)
def test_synthetic_inventory_loader_rejects_malformed_documents(
    raw: bytes,
) -> None:
    with pytest.raises(ValueError, match="inventory"):
        load_synthetic_producer_inventory(raw)


@pytest.mark.unit
@pytest.mark.parametrize("field_value", [True, None])
def test_synthetic_inventory_loader_rejects_publishable_or_unset_claim(
    field_value: object,
) -> None:
    document = json.loads(FIXTURE.read_bytes())
    document["publishable"] = field_value
    with pytest.raises(ValueError, match="inventory"):
        load_synthetic_producer_inventory(
            json.dumps(document, separators=(",", ":")).encode()
        )


@pytest.mark.unit
def test_synthetic_inventory_loader_rejects_wrong_layer_stratum_and_path() -> (
    None
):
    document = json.loads(FIXTURE.read_bytes())
    document["objects"][0]["bronze_stratum"] = None
    with pytest.raises(ValueError, match="inventory"):
        load_synthetic_producer_inventory(
            json.dumps(document, separators=(",", ":")).encode()
        )

    document = json.loads(FIXTURE.read_bytes())
    document["objects"][1]["bronze_stratum"] = "B2"
    with pytest.raises(ValueError, match="inventory"):
        load_synthetic_producer_inventory(
            json.dumps(document, separators=(",", ":")).encode()
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    ["other/path.parquet", "bronze/sub\\escaped.json"],
)
def test_synthetic_inventory_loader_rejects_nonportable_paths(
    path: str,
) -> None:
    document = json.loads(FIXTURE.read_bytes())
    document["objects"][0]["path"] = path
    with pytest.raises(ValueError, match="inventory"):
        load_synthetic_producer_inventory(
            json.dumps(document, separators=(",", ":")).encode()
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("producer_repository", "malformed"),
        ("dataset", "malformed"),
    ],
)
def test_synthetic_inventory_loader_rejects_unscoped_authority(
    field: str,
    value: str,
) -> None:
    document = json.loads(FIXTURE.read_bytes())
    document[field] = value
    with pytest.raises(ValueError, match="inventory"):
        load_synthetic_producer_inventory(
            json.dumps(document, separators=(",", ":")).encode()
        )


@pytest.mark.unit
@pytest.mark.parametrize("duplicate_field", ["identity", "path"])
def test_synthetic_inventory_loader_rejects_duplicate_objects(
    duplicate_field: str,
) -> None:
    document = json.loads(FIXTURE.read_bytes())
    duplicate = dict(document["objects"][0])
    if duplicate_field == "path":
        duplicate["source_id"] = "synthetic-other"
        duplicate["acquisition_id"] = "synthetic-other-v1"
    document["objects"].append(duplicate)

    with pytest.raises(ValueError, match="inventory"):
        load_synthetic_producer_inventory(
            json.dumps(document, separators=(",", ":")).encode()
        )
