"""Repository context and traceability tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from scripts import validate_context as context_module
from scripts.validate_context import validate_context


def test_context_manifest_resolves_repository_truth() -> None:
    receipt = validate_context()

    assert receipt["status"] == "pass"
    assert receipt["tracks"] >= 2
    assert receipt["autonomous_tracks"] == receipt["tracks"]
    assert receipt["archived_tracks"] >= 1
    assert receipt["registered_tracks"] == (
        receipt["tracks"] + receipt["archived_tracks"]
    )
    assert receipt["requirements"] >= 30
    assert receipt["harness_profiles"] >= 14
    assert receipt["human_gates"] >= 6
    assert receipt["releases"] == 10


@pytest.fixture
def system_plan_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate planning drift without modifying acceptance evidence."""
    root = context_module.PROJECT_ROOT
    for relative in (
        "conductor/system-completion.json",
        "quality/qualifications/stable-v1-contract.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / relative).read_bytes())
    monkeypatch.setattr(context_module, "PROJECT_ROOT", tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "guardrail",
    tuple(context_module.SYSTEM_COMPLETION_GUARDRAILS),
)
@pytest.mark.parametrize("unauthorized", [True, 0])
def test_system_plan_rejects_scope_or_gate_weakening(
    system_plan_root: Path, guardrail: str, unauthorized: object
) -> None:
    plan_path = system_plan_root / "conductor/system-completion.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["guardrails"][guardrail] = unauthorized
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(ValueError, match="guardrail drift"):
        context_module.validate_system_completion(())


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("acceptance_claim", "unknown or missing keys"),
        ("acceptance_purpose", "cannot grant acceptance"),
        ("alternate_contract", "reuse the Stable v1 contract"),
        ("unknown_gate", "existing release gate"),
        ("unknown_track", "registered track"),
        ("no_stop_condition", "complete bounded plan"),
        ("empty_failure", "complete bounded plan"),
        ("duplicate_stage", "stage order or denominator drift"),
        ("unknown_selection", "Selected system stage"),
        ("integer_version_as_bool", "Unknown system completion plan version"),
        ("nonobject_plan", "must be an object"),
        ("missing_guardrail", "missing or unknown"),
        ("nonobject_guardrails", "missing or unknown"),
        ("nonlist_stages", "stages must be a list"),
        ("nonobject_stage", "stage must be an object"),
    ],
)
def test_system_plan_requires_actionable_tasks_on_existing_gates(
    system_plan_root: Path, change: str, message: str
) -> None:
    plan_path = system_plan_root / "conductor/system-completion.json"
    plan: dict[str, Any] = json.loads(plan_path.read_text(encoding="utf-8"))
    changes = {
        "acceptance_claim": lambda: plan.update(system_complete=True),
        "acceptance_purpose": lambda: plan.update(purpose="qualification"),
        "alternate_contract": lambda: plan.update(
            qualification_contract="alternate.json"
        ),
        "unknown_gate": lambda: plan["stages"][0].update(release_gate="new"),
        "unknown_track": lambda: plan["stages"][0].update(track="missing"),
        "no_stop_condition": lambda: plan["stages"][0].pop("stop_condition"),
        "empty_failure": lambda: plan["stages"][0].update(current_failure=" "),
        "duplicate_stage": lambda: plan["stages"].append(plan["stages"][0]),
        "unknown_selection": lambda: plan.update(selected_stage="new-source"),
        "integer_version_as_bool": lambda: plan.update(schema_version=True),
        "nonobject_plan": plan.clear,
        "missing_guardrail": lambda: plan["guardrails"].pop(
            "new_source_acquisition"
        ),
        "nonobject_guardrails": lambda: plan.update(guardrails=[]),
        "nonlist_stages": lambda: plan.update(stages={}),
        "nonobject_stage": lambda: plan["stages"].__setitem__(0, "bad"),
    }
    changes[change]()
    serialized = json.dumps([] if change == "nonobject_plan" else plan)
    plan_path.write_text(serialized, encoding="utf-8")
    tracks = tuple(
        Path("conductor/tracks") / stage["track"] / "index.md"
        for stage in json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "conductor/system-completion.json"
            ).read_text(encoding="utf-8")
        )["stages"]
    )

    with pytest.raises((TypeError, ValueError), match=message):
        context_module.validate_system_completion(tracks)


def test_planning_validation_does_not_rewrite_release_evidence(
    system_plan_root: Path,
) -> None:
    contract = (
        system_plan_root / "quality/qualifications/stable-v1-contract.json"
    )
    before = contract.read_bytes()
    root = Path(__file__).resolve().parents[1]
    tracks = tuple((root / "conductor/tracks").glob("*/index.md"))

    context_module.validate_system_completion(tracks)

    assert contract.read_bytes() == before


def test_context_retains_archived_track_authority_for_system_planning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Path] = []
    original_validator = context_module.validate_system_completion

    def capture_tracks(indexes: tuple[Path, ...]) -> None:
        seen.extend(indexes)
        original_validator(indexes)

    monkeypatch.setattr(
        context_module, "validate_system_completion", capture_tracks
    )

    assert validate_context()["status"] == "pass"
    assert any(index.parent.parent.name == "archive" for index in seen)
    assert any(index.parent.parent.name == "tracks" for index in seen)
