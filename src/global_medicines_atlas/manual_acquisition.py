"""Deterministic, rights-gated contracts for documented manual acquisition.

Recipes are projections of the exhaustive source-landing queue.  Receipts are
operator evidence which can be validated and handed to the ordinary Bronze
landing path; this module never performs network access or stores credentials.
"""

from __future__ import annotations

import json
import mimetypes
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from .models import FrozenModel
from .source_landing_factory import (
    LandingDisposition,
    SourceLandingQueue,
)

SCHEMA_VERSION = 1
REDACTED = "[REDACTED]"
_SECRET_KEY = re.compile(r"(token|secret|password|cookie|authorization|api[_-]?key|credential)", re.IGNORECASE)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value)).hexdigest()


def redact_parameters(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a recursively redacted copy suitable for an evidence receipt."""
    def clean(item: Any, key: str = "") -> Any:
        if _SECRET_KEY.search(key):
            return REDACTED
        if isinstance(item, Mapping):
            return {str(k): clean(v, str(k)) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [clean(v, key) for v in item]
        return item
    return clean(value)


class ManualAcquisitionRecipe(FrozenModel):
    schema_id: Literal["global-medicines-atlas.manual-acquisition-recipe"] = (
        "global-medicines-atlas.manual-acquisition-recipe"
    )
    schema_version: Literal[1] = SCHEMA_VERSION
    recipe_id: str = ""
    source_id: str = Field(min_length=1)
    authoritative_location: str = Field(min_length=1)
    rights_prerequisites: tuple[str, ...] = ("rights_permitted",)
    reuse_prerequisites: tuple[str, ...] = ("pinned_discovery_snapshot",)
    public_interface: str | None = None
    navigation_steps: tuple[str, ...] = ("Open the authoritative public interface.",)
    search_terms: tuple[str, ...] = ()
    filters: Mapping[str, Any] = {}
    locale: str | None = None
    sort_order: str | None = None
    pagination_procedure: str = "Record every page or export and verify completeness."
    expected_export_format: str | None = None
    expected_scope: str = "Record the bounded scope actually exported."
    permitted_automation: Literal["none", "assistive", "public_export"] = "assistive"
    expected_output_names: tuple[str, ...] = ()
    expected_media_types: tuple[str, ...] = ()
    source_version_capture: str = "Record source-published and effective dates when supplied."
    failure_handling: str = "Record unavailable or blocked state; do not bypass controls."
    status: Literal["pending", "complete", "blocked", "temporarily_unavailable", "superseded"] = "pending"

    @model_validator(mode="before")
    @classmethod
    def assign_deterministic_id(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("recipe_id"):
            payload = {key: value for key, value in data.items() if key != "recipe_id"}
            data = dict(data)
            data["recipe_id"] = _digest(payload)
        return data

    @model_validator(mode="after")
    def validate_id(self) -> ManualAcquisitionRecipe:
        if not self.recipe_id or not self.recipe_id.startswith("sha256:"):
            raise ValueError("recipe_id must be a sha256 digest")
        return self


class ManualOutputFile(FrozenModel):
    name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)
    media_type: str = Field(min_length=1)


class ManualAcquisitionReceipt(FrozenModel):
    schema_id: Literal["global-medicines-atlas.manual-acquisition-receipt"] = (
        "global-medicines-atlas.manual-acquisition-receipt"
    )
    schema_version: Literal[1] = SCHEMA_VERSION
    receipt_id: str | None = None
    recipe_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_id: str = Field(min_length=1)
    acquisition_id: str = Field(min_length=1)
    content_ids: tuple[str, ...] = ()
    executed_at: AwareDatetime
    environment: str = "local"
    tool_version: str = Field(min_length=1)
    actual_parameters: Mapping[str, Any] = {}
    page_count: int | None = Field(default=None, ge=0)
    export_count: int | None = Field(default=None, ge=0)
    output_files: tuple[ManualOutputFile, ...] = ()
    source_published_at: AwareDatetime | None = None
    source_effective_at: AwareDatetime | None = None
    retrieved_at: AwareDatetime | None = None
    reuse_discovery_snapshot_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    rights_state: Literal["permitted", "review", "blocked"]
    admission_state: Literal["pending", "accepted", "quarantined", "blocked"]
    deviations: tuple[str, ...] = ()
    operator_state: Literal["self_recorded", "blocked", "unavailable"] = "self_recorded"
    reviewer_state: Literal["not_reviewed", "reviewed", "rejected"] = "not_reviewed"
    status: Literal["session", "complete", "blocked", "temporarily_unavailable", "superseded"] = "session"

    @model_validator(mode="before")
    @classmethod
    def redact_and_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            payload = dict(data)
            payload["actual_parameters"] = redact_parameters(payload.get("actual_parameters", {}))
            if payload.get("receipt_id") is None:
                identity = {k: v for k, v in payload.items() if k != "receipt_id"}
                payload["receipt_id"] = _digest(identity)
            return payload
        return data


def generate_manual_recipes(
    queue: SourceLandingQueue,
    overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[ManualAcquisitionRecipe, ...]:
    """Generate one recipe for every current manual-only queue item."""
    overrides = overrides or {}
    recipes: list[ManualAcquisitionRecipe] = []
    for item in sorted(queue.items, key=lambda value: value.source_id):
        if item.state is not LandingDisposition.MANUAL_ONLY:
            continue
        data: dict[str, Any] = {
            "source_id": item.source_id,
            "authoritative_location": item.endpoint,
            "public_interface": item.adapter.family.value,
            "navigation_steps": (item.adapter.acquisition_instructions,),
            "expected_export_format": item.adapter.formats[0] if item.adapter.formats else None,
            "expected_scope": item.reason,
        }
        data.update(overrides.get(item.source_id, {}))
        recipes.append(ManualAcquisitionRecipe.model_validate(data))
    return tuple(recipes)


def validate_receipt_files(
    recipe: ManualAcquisitionRecipe,
    receipt: ManualAcquisitionReceipt,
    files_root: Path,
) -> ManualAcquisitionReceipt:
    """Hash declared output files and return a completed immutable receipt."""
    if receipt.recipe_id != recipe.recipe_id or receipt.source_id != recipe.source_id:
        raise ValueError("receipt is not bound to recipe")
    if receipt.rights_state != "permitted":
        raise ValueError("rights prerequisite is not permitted")
    names = recipe.expected_output_names or tuple(path.name for path in files_root.iterdir() if path.is_file())
    outputs: list[ManualOutputFile] = []
    for name in names:
        path = files_root / name
        if not path.is_file():
            raise ValueError(f"missing output file: {name}")
        raw = path.read_bytes()
        media = mimetypes.guess_type(name)[0] or "application/octet-stream"
        outputs.append(ManualOutputFile(name=name, sha256="sha256:" + sha256(raw).hexdigest(), byte_count=len(raw), media_type=media))
    computed_ids = tuple(item.sha256 for item in outputs)
    if receipt.content_ids and receipt.content_ids != computed_ids:
        raise ValueError("output content_ids do not match downloaded files")
    return receipt.model_copy(update={"output_files": tuple(outputs), "content_ids": computed_ids, "status": "complete", "retrieved_at": receipt.retrieved_at or datetime.now(UTC)})
