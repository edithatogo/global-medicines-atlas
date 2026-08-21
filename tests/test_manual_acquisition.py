"""Executable contract for reproducible manual acquisition."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from global_medicines_atlas.manual_acquisition import REDACTED as REDACTED_VALUE
from global_medicines_atlas.manual_acquisition import (
    ManualAcquisitionReceipt,
    ManualAcquisitionRecipe,
    generate_manual_recipes,
    validate_receipt_files,
)
from global_medicines_atlas.source_catalog import load_catalog
from global_medicines_atlas.source_landing_factory import (
    LandingDisposition,
    LandingOverrides,
    build_source_landing_queue,
)


def test_every_manual_queue_item_has_a_deterministic_recipe() -> None:
    queue = build_source_landing_queue(load_catalog(), LandingOverrides.load())
    manual = [
        item
        for item in queue.items
        if item.state is LandingDisposition.MANUAL_ONLY
    ]
    recipes = generate_manual_recipes(queue)
    assert len(recipes) == len(manual)
    assert [recipe.recipe_id for recipe in recipes] == [
        recipe.recipe_id for recipe in generate_manual_recipes(queue)
    ]
    assert len({recipe.source_id for recipe in recipes}) == len(recipes)
    assert all(recipe.authoritative_location for recipe in recipes)


def test_receipt_requires_rights_reuse_and_redacts_parameters(
    tmp_path: Path,
) -> None:
    output = tmp_path / "export.csv"
    output.write_bytes(b"id,name\n1,aspirin\n")
    recipe = ManualAcquisitionRecipe(
        source_id="example",
        authoritative_location="https://example.test/export",
        navigation_steps=("Open the public export",),
        expected_output_names=("export.csv",),
        expected_media_types=("text/csv",),
    )
    receipt = ManualAcquisitionReceipt(
        recipe_id=recipe.recipe_id,
        source_id=recipe.source_id,
        acquisition_id="acq-example-1",
        content_ids=("sha256:" + "a" * 64,),
        executed_at=datetime.now(UTC),
        tool_version="test",
        actual_parameters={"query": "aspirin", "token": "[REDACTED]"},
        output_files=(),
        reuse_discovery_snapshot_id="sha256:" + "b" * 64,
        rights_state="permitted",
        admission_state="pending",
        operator_state="self_recorded",
    )
    assert receipt.actual_parameters["token"] == REDACTED_VALUE
    with pytest.raises(ValueError, match="output"):
        validate_receipt_files(recipe, receipt, tmp_path)


def test_receipt_validation_hashes_files_and_detects_missing_output(
    tmp_path: Path,
) -> None:
    output = tmp_path / "export.csv"
    output.write_bytes(b"id,name\n1,aspirin\n")
    recipe = ManualAcquisitionRecipe(
        source_id="example",
        authoritative_location="https://example.test/export",
        expected_output_names=("export.csv",),
        expected_media_types=("text/csv",),
    )
    receipt = ManualAcquisitionReceipt(
        recipe_id=recipe.recipe_id,
        source_id=recipe.source_id,
        acquisition_id="acq-example-1",
        content_ids=(),
        executed_at=datetime.now(UTC),
        tool_version="test",
        output_files=(),
        reuse_discovery_snapshot_id="sha256:" + "b" * 64,
        rights_state="permitted",
        admission_state="accepted",
        operator_state="self_recorded",
    )
    completed = validate_receipt_files(recipe, receipt, tmp_path)
    assert completed.output_files[0].sha256.startswith("sha256:")
    assert completed.content_ids == (completed.output_files[0].sha256,)


def test_redaction_recurses_through_lists_and_rejects_bad_recipe_id() -> None:
    assert redact_parameters({"items": [{"api_key": "secret"}]}) == {
        "items": [{"api_key": REDACTED_VALUE}]
    }
    with pytest.raises(ValueError, match="recipe_id"):
        ManualAcquisitionRecipe.model_validate({
            "recipe_id": "not-a-digest",
            "source_id": "example",
            "authoritative_location": "https://example.test",
        })


def test_receipt_validation_rejects_unpermitted_and_missing_files(
    tmp_path: Path,
) -> None:
    recipe = ManualAcquisitionRecipe(
        source_id="example",
        authoritative_location="https://example.test",
        expected_output_names=("export.csv",),
    )
    receipt = ManualAcquisitionReceipt(
        recipe_id=recipe.recipe_id,
        source_id=recipe.source_id,
        acquisition_id="acq-example-1",
        executed_at=datetime.now(UTC),
        tool_version="test",
        reuse_discovery_snapshot_id="sha256:" + "b" * 64,
        rights_state="review",
        admission_state="pending",
    )
    with pytest.raises(ValueError, match="rights"):
        validate_receipt_files(recipe, receipt, tmp_path)
