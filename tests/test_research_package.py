from __future__ import annotations

import pytest

from global_medicines_atlas.research_package import (
    CrateDistribution,
    build_research_crate,
)


def _distribution(identifier: str = "data.parquet") -> CrateDistribution:
    return CrateDistribution(
        identifier=identifier,
        name=identifier,
        content_url=f"https://huggingface.co/datasets/example/resolve/main/{identifier}",
        media_type="application/vnd.apache.parquet",
        sha256="a" * 64,
    )


def test_crate_is_deterministic_and_metadata_only() -> None:
    crate = build_research_crate(
        identifier="example@abc",
        name="Example",
        version="abc",
        dataset_url="https://huggingface.co/datasets/example",
        distributions=(_distribution("z.parquet"), _distribution()),
    )
    assert crate.payloads_embedded is False
    assert [item["@id"] for item in crate.jsonld()["@graph"]] == [
        "./",
        "data.parquet",
        "z.parquet",
    ]
    assert crate.canonical_jsonld_bytes() == crate.canonical_jsonld_bytes()
    assert len(crate.jsonld_sha256()) == 64


def test_duplicate_distribution_identifier_is_rejected() -> None:
    with pytest.raises(ValueError, match="identifiers must be unique"):
        build_research_crate(
            identifier="example@abc",
            name="Example",
            version="abc",
            dataset_url="https://huggingface.co/datasets/example",
            distributions=(_distribution(), _distribution()),
        )


def test_croissant_is_deterministic_and_payload_free() -> None:
    crate = build_research_crate(
        identifier="example@abc",
        name="Example",
        version="abc",
        dataset_url="https://huggingface.co/datasets/example",
        distributions=(_distribution("z.parquet"), _distribution()),
    )
    descriptor = crate.croissant()
    assert descriptor["@type"] == "Dataset"
    assert descriptor["cr:metadataOnly"] is True
    assert "recordSet" not in descriptor
    distributions = descriptor["distribution"]
    assert isinstance(distributions, list)
    assert [item["name"] for item in distributions] == [
        "data.parquet",
        "z.parquet",
    ]
    assert all("sha256" in item and "contentUrl" in item for item in distributions)
    assert crate.canonical_croissant_bytes() == crate.canonical_croissant_bytes()
    assert len(crate.croissant_sha256()) == 64
