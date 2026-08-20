"""Source-family Bronze landing factory and generated work queue contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from global_medicines_atlas.source_catalog import (
    AccessMode,
    IntegrationLayer,
    load_catalog,
)
from global_medicines_atlas.source_landing_factory import (
    LandingAdapterFamily,
    LandingDisposition,
    LandingOverride,
    LandingOverrides,
    SourceLandingQueue,
    build_source_landing_queue,
    family_for_source,
    load_override_document,
    render_conductor_queue,
)

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = (
    ROOT / "quality" / "qualifications" / "bronze-source-landing-queue.json"
)
SCHEMA_PATH = ROOT / "schemas" / "bronze-source-landing-queue-v1.json"
MARKDOWN_PATH = (
    ROOT / "conductor" / "generated" / "bronze-source-landing-queue.md"
)


def _source(source_id: str):
    return next(
        source
        for source in load_catalog().sources
        if source.source_id == source_id
    )


@pytest.mark.unit
def test_factory_covers_requested_adapter_families() -> None:
    base = _source("ae-dha-prices")

    assert (
        family_for_source(
            base.model_copy(
                update={"access_mode": AccessMode.DOWNLOAD, "formats": ("csv",)}
            )
        )
        is LandingAdapterFamily.STATIC_FILE_DOWNLOAD
    )
    assert (
        family_for_source(
            base.model_copy(
                update={"access_mode": AccessMode.DOWNLOAD, "formats": ("zip",)}
            )
        )
        is LandingAdapterFamily.ARCHIVE_RELEASE
    )
    assert (
        family_for_source(
            base.model_copy(
                update={"access_mode": AccessMode.API, "formats": ("json",)}
            )
        )
        is LandingAdapterFamily.PAGINATED_REST_API
    )
    assert (
        family_for_source(
            base.model_copy(update={"access_mode": AccessMode.WEB_SEARCH})
        )
        is LandingAdapterFamily.REGULATOR_SEARCH_EXPORT
    )
    assert (
        family_for_source(
            base.model_copy(
                update={"access_mode": AccessMode.DOCUMENT, "formats": ("pdf",)}
            )
        )
        is LandingAdapterFamily.DOCUMENT_COLLECTION
    )
    assert (
        family_for_source(
            base,
            LandingOverride(
                source_id=base.source_id,
                family=LandingAdapterFamily.MANUAL_REPRODUCIBLE_EXPORT,
                state=LandingDisposition.MANUAL_ONLY,
                reason="public export requires a reproducible human step",
                manual_instructions="Export the public result and record filters.",
            ),
        )
        is LandingAdapterFamily.MANUAL_REPRODUCIBLE_EXPORT
    )


@pytest.mark.unit
def test_every_catalog_source_resolves_to_exactly_one_state() -> None:
    catalog = load_catalog()
    queue = build_source_landing_queue(catalog, LandingOverrides())

    assert queue.source_count == len(catalog.sources) == 172
    assert len(queue.items) == queue.source_count
    assert len({item.source_id for item in queue.items}) == queue.source_count
    assert sum(queue.state_counts.values()) == queue.source_count
    assert set(queue.state_counts) == set(LandingDisposition)
    assert all(item.state in LandingDisposition for item in queue.items)


@pytest.mark.unit
def test_queue_states_are_fail_closed_and_evidence_scoped() -> None:
    queue = build_source_landing_queue(load_catalog(), LandingOverrides())
    by_id = {item.source_id: item for item in queue.items}

    assert by_id["au-artg"].state is LandingDisposition.LANDED
    assert by_id["au-artg"].evidence_scope == "governed_fixture"
    assert by_id["au-amt-rf2"].state is (
        LandingDisposition.CREDENTIALED_EXCLUDED
    )
    assert by_id["ae-ede-register"].state is LandingDisposition.MANUAL_ONLY
    assert "search filters" in (
        by_id["ae-ede-register"].adapter.acquisition_instructions
    )
    assert by_id["ae-dha-prices"].state is LandingDisposition.RIGHTS_BLOCKED
    assert all(
        item.evidence_references
        for item in queue.items
        if item.state is LandingDisposition.LANDED
    )
    assert all("@" not in item.endpoint for item in queue.items)


@pytest.mark.unit
def test_exception_states_require_machine_readable_evidence() -> None:
    with pytest.raises(ValidationError, match="failure receipt"):
        LandingOverride(
            source_id="example",
            state=LandingDisposition.TEMPORARILY_UNAVAILABLE,
            reason="endpoint failed",
        )
    with pytest.raises(ValidationError, match="reuse reference"):
        LandingOverride(
            source_id="example",
            state=LandingDisposition.SUPERSEDED_BY_REUSE,
            reason="reuse preferred",
        )
    with pytest.raises(ValidationError, match="manual instructions"):
        LandingOverride(
            source_id="example",
            state=LandingDisposition.MANUAL_ONLY,
            reason="manual export",
        )
    with pytest.raises(ValidationError, match="landed override"):
        LandingOverride(
            source_id="example",
            state=LandingDisposition.LANDED,
            reason="landed",
        )


@pytest.mark.unit
def test_overrides_are_sparse_unique_and_cannot_name_unknown_sources() -> None:
    with pytest.raises(ValidationError, match="duplicate source override"):
        LandingOverrides(
            overrides=(
                LandingOverride(
                    source_id="example",
                    state=LandingDisposition.NOT_YET_IMPLEMENTED,
                    reason="pending",
                ),
                LandingOverride(
                    source_id="example",
                    state=LandingDisposition.NOT_YET_IMPLEMENTED,
                    reason="still pending",
                ),
            )
        )

    overrides = LandingOverrides(
        overrides=(
            LandingOverride(
                source_id="unknown-source",
                state=LandingDisposition.NOT_YET_IMPLEMENTED,
                reason="pending",
            ),
        )
    )
    with pytest.raises(ValueError, match="unknown catalog sources"):
        build_source_landing_queue(load_catalog(), overrides)


@pytest.mark.unit
def test_generated_queue_schema_and_conductor_projection_are_current() -> None:
    catalog = load_catalog()
    queue = build_source_landing_queue(catalog, LandingOverrides.load())
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    committed = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
        committed
    )
    assert committed == queue.model_dump(mode="json")
    assert MARKDOWN_PATH.read_text(encoding="utf-8") == (
        render_conductor_queue(queue)
    )
    markdown = render_conductor_queue(queue)
    assert markdown.count("`ae-dha-prices`") == 1
    assert "Generated from `medicine_source_catalog.json`" in markdown
    assert "Do not edit this file by hand" in markdown


@pytest.mark.unit
def test_queue_validation_rejects_inconsistent_counts_and_items() -> None:
    queue = build_source_landing_queue(load_catalog(), LandingOverrides())
    document = queue.model_dump(mode="python")

    with pytest.raises(ValidationError, match="each source exactly once"):
        SourceLandingQueue.model_validate({
            **document,
            "items": queue.items[:-1],
        })
    with pytest.raises(ValidationError, match="state counts must cover"):
        SourceLandingQueue.model_validate({
            **document,
            "state_counts": {LandingDisposition.LANDED: 0},
        })
    with pytest.raises(ValidationError, match="family counts must cover"):
        SourceLandingQueue.model_validate({
            **document,
            "family_counts": {LandingAdapterFamily.STATIC_FILE_DOWNLOAD: 0},
        })

    incomplete_states = dict(queue.state_counts)
    incomplete_states.pop(LandingDisposition.TEMPORARILY_UNAVAILABLE)
    with pytest.raises(ValidationError, match="every disposition"):
        SourceLandingQueue.model_validate({
            **document,
            "state_counts": incomplete_states,
        })

    incomplete_families = dict(queue.family_counts)
    removed_family, removed_count = incomplete_families.popitem()
    replacement_family = next(iter(incomplete_families))
    incomplete_families[replacement_family] += removed_count
    assert removed_family not in incomplete_families
    with pytest.raises(ValidationError, match="every adapter family"):
        SourceLandingQueue.model_validate({
            **document,
            "family_counts": incomplete_families,
        })


@pytest.mark.unit
def test_overrides_drive_manual_instructions_and_enforce_credentials() -> None:
    catalog = load_catalog()
    base = _source("ae-dha-prices")
    manual = LandingOverride(
        source_id=base.source_id,
        family=LandingAdapterFamily.MANUAL_REPRODUCIBLE_EXPORT,
        state=LandingDisposition.MANUAL_ONLY,
        reason="manual public export",
        manual_instructions="Export with the recorded public filters.",
    )
    queue = build_source_landing_queue(
        catalog.model_copy(update={"sources": (base,)}),
        LandingOverrides(overrides=(manual,)),
    )
    assert queue.items[0].reason == manual.reason
    assert queue.items[0].adapter.acquisition_instructions == (
        manual.manual_instructions
    )

    credentialed = _source("au-amt-rf2")
    invalid_landing = LandingOverride(
        source_id=credentialed.source_id,
        state=LandingDisposition.LANDED,
        reason="invalid credential bypass",
        evidence_references=("receipt:test",),
    )
    with pytest.raises(ValueError, match="credentialed source"):
        build_source_landing_queue(
            catalog.model_copy(update={"sources": (credentialed,)}),
            LandingOverrides(overrides=(invalid_landing,)),
        )


@pytest.mark.unit
def test_synthetic_sources_cover_remaining_state_and_evidence_scopes() -> None:
    catalog = load_catalog()
    base = _source("ae-dha-prices")
    public_file = base.model_copy(
        update={
            "access_mode": AccessMode.DOWNLOAD,
            "formats": ("csv",),
            "rights_status": "public domain",
            "implemented_ingestion": False,
            "qualification_references": (),
        }
    )
    queue = build_source_landing_queue(
        catalog.model_copy(update={"sources": (public_file,)}),
        LandingOverrides(),
    )
    assert queue.items[0].state is LandingDisposition.NOT_YET_IMPLEMENTED

    for integration_layer, expected_scope in (
        (IntegrationLayer.LIVE_RECEIPT, "live_receipt"),
        (IntegrationLayer.CATALOGUED, "none"),
    ):
        source = public_file.model_copy(
            update={"integration_layer": integration_layer}
        )
        override = LandingOverride(
            source_id=source.source_id,
            state=LandingDisposition.LANDED,
            reason="scope probe",
            evidence_references=("receipt:scope-probe",),
        )
        scoped = build_source_landing_queue(
            catalog.model_copy(update={"sources": (source,)}),
            LandingOverrides(overrides=(override,)),
        )
        assert scoped.items[0].evidence_scope == expected_scope


@pytest.mark.unit
def test_override_document_loader_rejects_non_objects(tmp_path: Path) -> None:
    object_path = tmp_path / "object.json"
    object_path.write_text('{"schema_version": 1}', encoding="utf-8")
    assert load_override_document(object_path) == {"schema_version": 1}

    array_path = tmp_path / "array.json"
    array_path.write_text("[]", encoding="utf-8")
    with pytest.raises(TypeError, match="must be a JSON object"):
        load_override_document(array_path)
