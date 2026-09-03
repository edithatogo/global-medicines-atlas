"""Synthetic Australian benefits producer denominator contract."""

import json
from pathlib import Path

import pytest

FIXTURE = (
    Path(__file__).parents[1]
    / "quality/qualifications/australian-benefits-synthetic-producer.json"
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
            assert item["bronze_stratum"] == "B2"
        else:
            assert item["bronze_stratum"] is None
