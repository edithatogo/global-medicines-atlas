"""Iceberg REST and v3 capability experiment tests."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from global_medicines_atlas.iceberg_interop import (
    ICEBERG_REST_FIXTURE_IMAGE,
    V3_CAPABILITY_SYMBOLS,
    assert_disposable_rest_uri,
    assess_v3_capabilities,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.unit
def test_rest_fixture_image_is_digest_pinned() -> None:
    assert ICEBERG_REST_FIXTURE_IMAGE.startswith(
        "apache/iceberg-rest-fixture@sha256:"
    )
    assert len(ICEBERG_REST_FIXTURE_IMAGE.rsplit(":", maxsplit=1)[-1]) == 64


@pytest.mark.unit
@pytest.mark.parametrize(
    "uri",
    [
        "https://127.0.0.1:8181",
        "http://catalog.example:8181",
        "http://user:secret@127.0.0.1:8181",
        "http://127.0.0.1:8181?token=secret",
        "http://127.0.0.1:8181/#fragment",
    ],
)
def test_rest_experiment_rejects_non_disposable_or_secret_bearing_uri(
    uri: str,
) -> None:
    with pytest.raises(ValueError, match="loopback"):
        assert_disposable_rest_uri(uri)


@pytest.mark.unit
def test_rest_experiment_accepts_loopback_http() -> None:
    assert_disposable_rest_uri("http://127.0.0.1:8181")
    assert_disposable_rest_uri("http://localhost:8181")


@pytest.mark.unit
def test_v3_capability_assessment_is_explicit_and_does_not_infer() -> None:
    symbols = {
        symbol
        for capability in ("nanosecond_timestamps", "row_lineage")
        for symbol in V3_CAPABILITY_SYMBOLS[capability]
    }

    results = assess_v3_capabilities(symbols)
    by_name = {result.capability: result for result in results}

    assert by_name["nanosecond_timestamps"].supported is True
    assert by_name["row_lineage"].supported is True
    assert by_name["deletion_vectors"].supported is False
    assert by_name["deletion_vectors"].missing_symbols == (
        "DataFileContent.DELETION_VECTOR",
    )
    assert set(by_name) == set(V3_CAPABILITY_SYMBOLS)


@pytest.mark.unit
def test_pyiceberg_remains_an_optional_extra() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert not any(
        "pyiceberg" in dependency
        for dependency in project["project"]["dependencies"]
    )
    assert project["project"]["optional-dependencies"]["iceberg"] == [
        "pyiceberg>=0.10"
    ]
