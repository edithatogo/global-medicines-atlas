"""Planning contracts for the medallion datahouse bronze horizon."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACK = ROOT / "conductor/tracks/bronze_medallion_completion_20260819"
BRONZE_MUST = {"M-092", "M-093", "M-094", "M-095", "M-096", "M-097"}
BRONZE_SHOULD = {"S-011", "S-012"}
BRONZE_WONT = {"W-007", "W-008"}
WONT_HEADING = "## Won't Have in the Initial Increment"


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _requirement_ids(section: str) -> set[str]:
    return set(re.findall(r"\*\*([MSCW]-\d{3}):\*\*", section))


def test_product_adds_medallion_vision_mission_and_purpose() -> None:
    product = _text("conductor/product.md")
    assert "## Product Vision" in product
    assert "medallion datahouse" in product
    assert "## Product Mission" in product
    assert "## Product Purpose" in product
    assert "Hugging Face archives reviewed public bronze outputs" in product
    title = "Global Medicines Registration and Funding Comparison System"
    assert title in product


def test_guidelines_keep_bronze_distinct_from_later_layers() -> None:
    guidelines = _text("conductor/product-guidelines.md")
    assert "source-native landed records" in guidelines
    assert "raw-as-landed" in guidelines


def test_requirements_place_bronze_in_must_and_later_layers_in_wont() -> None:
    requirements = _text("conductor/requirements.md")
    must_section, rest = requirements.split("## Should Have", maxsplit=1)
    should_section, rest = rest.split("## Could Have", maxsplit=1)
    wont_section = rest.split(WONT_HEADING, maxsplit=1)[1]
    must_ids = _requirement_ids(must_section)
    should_ids = _requirement_ids(should_section)
    wont_ids = _requirement_ids(wont_section)
    assert must_ids >= BRONZE_MUST
    assert should_ids >= BRONZE_SHOULD
    assert wont_ids >= BRONZE_WONT
    assert "regenerable derivatives" in must_section
    assert "archive and output boundary" in must_section


def test_design_documents_full_medallion_and_detailed_bronze() -> None:
    design = _text("conductor/design.md")
    assert "## Medallion Datahouse" in design
    assert "### Bronze landing" in design
    assert "### Later layers (sketch only)" in design
    assert "```mermaid" in design
    assert "Partitioned Arrow/Parquet portable truth" in design
    assert "Hugging Face public bronze archive" in design
    assert "not an ingest origin" in design
    assert "Silver: typed source-faithful tables" in design


def test_bronze_track_artifacts_are_complete_and_tdd_shaped() -> None:
    metadata = json.loads((TRACK / "metadata.json").read_text(encoding="utf-8"))
    spec = (TRACK / "spec.md").read_text(encoding="utf-8")
    plan = (TRACK / "plan.md").read_text(encoding="utf-8")
    evidence_record = json.loads(
        (TRACK / "evidence.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    registry = _text("conductor/tracks.md")
    failure_note = "Confirm the intended failure before implementation"

    assert metadata["track_id"] == "bronze_medallion_completion_20260819"
    assert metadata["status"] == "new"
    assert metadata["github_issue"].endswith("/issues/167")
    assert set(metadata["requirements"]) >= BRONZE_MUST
    assert "Write failing tests" in plan
    assert plan.count("Write failing tests") >= 4
    assert plan.count(failure_note) == 4
    assert "Phase Verification & Checkpoint" in plan
    assert "W-007" in spec
    assert "archive and output boundary" in spec
    assert evidence_record["kind"] == "track_initialized"
    assert "bronze_medallion_completion_20260819/index.md" in registry
