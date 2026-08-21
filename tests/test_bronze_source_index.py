"""Contracts for the deterministic B0 Source Index projection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from global_medicines_atlas.bronze_source_index import (
    B0SourceIndexRow,
    build_b0_source_index,
    build_b0_source_index_dataset_metadata,
    render_b0_source_index_markdown,
    source_index_parquet_bytes,
)
from global_medicines_atlas.source_catalog import load_catalog
from global_medicines_atlas.source_landing_factory import (
    LandingDisposition,
    LandingOverrides,
    build_source_landing_queue,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "quality/qualifications/bronze-source-index-v1.json"
PARQUET_PATH = ROOT / "quality/qualifications/bronze-source-index-v1.parquet"
SCHEMA_PATH = ROOT / "schemas/bronze-source-index-v1.json"
METADATA_PATH = (
    ROOT / "quality/qualifications/bronze-source-index-dataset-metadata.json"
)
DOCUMENTATION_PATH = ROOT / "docs/data-sources/bronze-source-index.md"


def _build():
    catalog = load_catalog()
    queue = build_source_landing_queue(catalog, LandingOverrides.load())
    return build_b0_source_index(catalog, queue)


@pytest.mark.unit
def test_b0_index_is_exhaustive_unique_and_referentially_integral() -> None:
    catalog = load_catalog()
    queue = build_source_landing_queue(catalog, LandingOverrides.load())
    index = _build()
    catalog_ids = {source.source_id for source in catalog.sources}
    index_ids = [source.source_id for source in index.sources]
    catalog_by_id = {source.source_id: source for source in catalog.sources}
    queue_by_id = {item.source_id: item for item in queue.items}

    assert index.source_count == len(catalog.sources) == 172
    assert len(index_ids) == len(set(index_ids))
    assert set(index_ids) == catalog_ids
    assert all(source.jurisdictions for source in index.sources)
    assert all(source.authority for source in index.sources)
    for source in index.sources:
        catalog_source = catalog_by_id[source.source_id]
        queue_item = queue_by_id[source.source_id]
        assert source.qualification_references == (
            catalog_source.qualification_references
        )
        assert source.last_verified_at == (
            catalog_source.last_verified_at.isoformat()
        )
        assert source.acquisition_family == queue_item.adapter.family.value
        assert source.current_landing_disposition == queue_item.state.value
        assert source.evidence_scope == queue_item.evidence_scope
    coverage = json.loads(
        (
            ROOT
            / "src/global_medicines_atlas/data/source_coverage_index_v1.json"
        ).read_text(encoding="utf-8")
    )
    coverage_ids = {
        source_id
        for track in coverage["tracks"]
        for source_id in track["source_ids"]
    }
    assert coverage_ids - set(index_ids) == {index.dataset_id}


@pytest.mark.unit
def test_b0_states_do_not_collapse_evidence_or_qualification() -> None:
    index = _build()

    assert index.index_presence_implies_coverage is False
    assert index.missing_source_is_negative_evidence is False
    assert any(not source.metadata_verified for source in index.sources)
    assert any(
        source.metadata_verified and source.evidence_scope == "none"
        for source in index.sources
    )
    assert any(
        source.evidence_scope == "governed_fixture" for source in index.sources
    )
    assert any(
        source.evidence_scope == "live_receipt" for source in index.sources
    )

    declared = next(
        source for source in index.sources if source.evidence_scope == "none"
    )
    independent = B0SourceIndexRow.model_validate({
        **declared.model_dump(mode="json"),
        "evidence_scope": "governed_fixture",
        "qualification_state": "declared",
        "qualification_references": [],
    })
    assert independent.evidence_scope == "governed_fixture"
    assert independent.qualification_state == "declared"


@pytest.mark.unit
def test_b0_rejects_unstable_ids_state_collapse_and_reference_drift() -> None:
    catalog = load_catalog()
    queue = build_source_landing_queue(catalog, LandingOverrides.load())
    row = _build().sources[0]

    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        B0SourceIndexRow.model_validate({
            **row.model_dump(mode="json"),
            "source_id": "Unstable Source ID",
        })
    with pytest.raises(ValidationError, match="metadata_verified"):
        B0SourceIndexRow.model_validate({
            **row.model_dump(mode="json"),
            "metadata_verified": not row.metadata_verified,
        })
    with pytest.raises(ValueError, match="IDs must match"):
        build_b0_source_index(
            catalog.model_copy(update={"sources": catalog.sources[:-1]}),
            queue,
        )


@pytest.mark.unit
def test_b0_rejects_snapshot_identity_and_count_drift() -> None:
    index = _build()
    payload = index.model_dump(mode="json")

    mutations = (
        (
            {
                "sources": [
                    payload["sources"][1],
                    payload["sources"][0],
                    *payload["sources"][2:],
                ]
            },
            "unique sorted",
        ),
        ({"source_count": index.source_count + 1}, "source_count"),
        (
            {
                "discovery_state_counts": {
                    **index.discovery_state_counts,
                    "discovery_only": 0,
                }
            },
            "discovery_state",
        ),
        ({"snapshot_sha256": "0" * 64}, "snapshot digest"),
        ({"snapshot_id": f"sha256:{'0' * 64}"}, "snapshot ID"),
    )
    for update, message in mutations:
        with pytest.raises(ValidationError, match=message):
            type(index).model_validate({**payload, **update})


@pytest.mark.unit
def test_b0_records_reused_source_reference() -> None:
    catalog = load_catalog()
    queue = build_source_landing_queue(catalog, LandingOverrides.load())
    first = queue.items[0].model_copy(
        update={
            "state": LandingDisposition.SUPERSEDED_BY_REUSE,
            "evidence_references": ("https://example.test/reused-source",),
        }
    )
    reused_queue = queue.model_copy(
        update={
            "items": (first, *queue.items[1:]),
        }
    )

    index = build_b0_source_index(catalog, reused_queue)

    assert index.sources[0].supersession_or_reuse_reference == (
        "https://example.test/reused-source"
    )


@pytest.mark.unit
def test_b0_snapshot_identity_and_every_projection_are_deterministic() -> None:
    first = _build()
    second = _build()

    assert first == second
    assert first.snapshot_sha256 == second.snapshot_sha256
    assert first.snapshot_id == f"sha256:{first.snapshot_sha256}"
    assert source_index_parquet_bytes(first) == source_index_parquet_bytes(
        second
    )
    assert render_b0_source_index_markdown(first) == (
        render_b0_source_index_markdown(second)
    )


@pytest.mark.unit
def test_committed_b0_projections_validate_and_regenerate(
    tmp_path: Path,
) -> None:
    index = _build()
    committed = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
        committed
    )
    assert committed == index.model_dump(mode="json")
    assert PARQUET_PATH.read_bytes() == source_index_parquet_bytes(index)
    assert DOCUMENTATION_PATH.read_text(encoding="utf-8") == (
        render_b0_source_index_markdown(index)
    )

    parquet_copy = tmp_path / "index.parquet"
    parquet_copy.write_bytes(PARQUET_PATH.read_bytes())
    table = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        parquet_copy
    )
    assert table.num_rows == index.source_count
    assert table.schema.metadata[b"snapshot_sha256"].decode() == (
        index.snapshot_sha256
    )
    assert table.column("source_id").to_pylist() == sorted(
        source.source_id for source in index.sources
    )


@pytest.mark.unit
def test_b0_dataset_metadata_is_citable_but_not_published() -> None:
    index = _build()
    json_digest = hashlib.sha256(INDEX_PATH.read_bytes()).hexdigest()
    parquet_digest = hashlib.sha256(PARQUET_PATH.read_bytes()).hexdigest()
    expected = build_b0_source_index_dataset_metadata(
        index,
        json_sha256=json_digest,
        parquet_sha256=parquet_digest,
    )
    committed = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    assert committed == expected
    assert committed["snapshot_id"] == index.snapshot_id
    assert committed["external_publication_performed"] is False
    assert committed["related_catalogue_archive"]["snapshot_published"] is False
    assert committed["related_catalogue_archive"]["url"] == (
        "https://huggingface.co/datasets/"
        "edithatogo/global-medicines-atlas-catalogue"
    )
    assert committed["citation"]["repository"] == (
        "https://github.com/edithatogo/global-medicines-atlas"
    )
    assert {item["format"] for item in committed["distributions"]} == {
        "JSON",
        "Parquet",
    }
