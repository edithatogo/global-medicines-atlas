"""Validate repository context, track links, and harness declarations."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import NamedTuple, TypedDict, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_FILE = PROJECT_ROOT / ".context" / "project.toml"
TRACK_PATTERN = re.compile(
    r"\((?P<path>\./(?P<location>tracks|archive)/[^)]+/index\.md)\)"
)
REQUIREMENT_PATTERN = re.compile(r"\*\*(?P<id>[MSCW]-\d{3}):\*\*")
MINIMUM_RELEASES = 10
EXECUTION_POLICY = {
    "mode": "autonomous",
    "interaction": "decision_gates_only",
    "decision_protocol": "options_recommendation_rationale",
    "phase_checkpoints": "automatic_evidence_gated",
    "failure_recovery": "bounded_self_correction",
    "max_identical_failures": 3,
    "merge_policy": "required_checks_then_merge",
}
SYSTEM_COMPLETION_GUARDRAILS = {
    "new_source_acquisition": False,
    "expand_frozen_inventory": False,
    "require_every_value_interpreted": False,
    "waive_existing_acceptance": False,
    "promote_optional_previews": False,
    "full_local_suite_per_dataset": False,
}
SYSTEM_COMPLETION_STAGES = (
    "silver-gold",
    "admitted-delivery",
    "consumers",
    "recovery",
    "release",
)


class ContextReceipt(TypedDict):
    schema_version: int
    repository: str
    context_files: int
    manifests: int
    tracks: int
    archived_tracks: int
    registered_tracks: int
    autonomous_tracks: int
    requirements: int
    harness_profiles: int
    human_gates: int
    releases: int
    status: str


class TrackIndexes(NamedTuple):
    """Registered Conductor indexes grouped by lifecycle location."""

    all: tuple[Path, ...]
    active: tuple[Path, ...]
    archived: tuple[Path, ...]


class ReleaseGateReference(TypedDict):
    gate_id: str


class ReleaseGateInventory(TypedDict):
    release_gates: list[ReleaseGateReference]


def _read_context() -> dict[str, object]:
    with CONTEXT_FILE.open("rb") as stream:
        return tomllib.load(stream)


def _strings(context: dict[str, object], key: str) -> tuple[str, ...]:
    value = context.get(key)
    if not isinstance(value, list):
        raise TypeError(f"{key} must be a list of strings")
    strings: list[str] = []
    for item in cast("list[object]", value):
        if not isinstance(item, str):
            raise TypeError(f"{key} must be a list of strings")
        strings.append(item)
    return tuple(strings)


def _validate_maturity(track_indexes: tuple[Path, ...]) -> int:
    maturity = cast(
        "dict[str, object]",
        json.loads(
            (PROJECT_ROOT / "conductor" / "maturity-model.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    raw_releases = maturity.get("releases")
    if not isinstance(raw_releases, list):
        raise TypeError("Maturity releases must be a list")
    releases = cast("list[object]", raw_releases)
    if len(releases) < MINIMUM_RELEASES:
        raise ValueError(
            "Maturity model must define the v0.1-to-v1.0 release train"
        )
    versions: set[str] = set()
    for raw_release in releases:
        if not isinstance(raw_release, dict):
            raise TypeError("Every release must be an object")
        version = cast("dict[str, object]", raw_release).get("version")
        if not isinstance(version, str):
            raise TypeError("Every release requires a string version")
        versions.add(version)
    if len(versions) != len(releases) or "1.0.0" not in versions:
        raise ValueError(
            "Release versions must be unique and include stable 1.0.0"
        )
    for index in track_indexes:
        metadata = cast(
            "dict[str, object]",
            json.loads(
                (index.parent / "metadata.json").read_text(encoding="utf-8")
            ),
        )
        if not metadata.get("github_issue"):
            raise ValueError(
                f"{index.parent.name} requires a GitHub parent issue"
            )
        targets = metadata.get("target_versions", [])
        if not isinstance(targets, list):
            raise TypeError(
                f"{index.parent.name} target_versions must be a list"
            )
        if any(
            target not in versions for target in cast("list[object]", targets)
        ):
            raise ValueError(
                f"{index.parent.name} targets an undefined release"
            )
    return len(releases)


def _validate_track_requirements(
    track_indexes: tuple[Path, ...], requirement_ids: set[str]
) -> None:
    for index in track_indexes:
        metadata = cast(
            "dict[str, object]",
            json.loads(
                (index.parent / "metadata.json").read_text(encoding="utf-8")
            ),
        )
        references = metadata.get("requirements", [])
        if not isinstance(references, list):
            raise TypeError(f"{index.parent.name} requirements must be a list")
        unknown = {
            reference
            for reference in cast("list[object]", references)
            if not isinstance(reference, str)
            or reference not in requirement_ids
        }
        if unknown:
            raise ValueError(
                f"{index.parent.name} references unknown requirements: {unknown}"
            )


def _validate_execution_policies(track_indexes: tuple[Path, ...]) -> int:
    for index in track_indexes:
        metadata = cast(
            "dict[str, object]",
            json.loads(
                (index.parent / "metadata.json").read_text(encoding="utf-8")
            ),
        )
        raw_policy = metadata.get("execution_policy")
        if not isinstance(raw_policy, dict):
            raise TypeError(
                f"{index.parent.name} execution_policy must be an object"
            )
        policy = cast("dict[str, object]", raw_policy)
        drift = {
            key: {"expected": expected, "actual": policy.get(key)}
            for key, expected in EXECUTION_POLICY.items()
            if policy.get(key) != expected
        }
        if drift:
            raise ValueError(
                f"{index.parent.name} execution policy drift: {drift}"
            )
    return len(track_indexes)


def _registered_track_indexes(
    tracks_text: str,
) -> TrackIndexes:
    """Resolve all registered track indexes by active and archive location."""
    matches = tuple(TRACK_PATTERN.finditer(tracks_text))
    track_indexes = tuple(
        PROJECT_ROOT / "conductor" / match.group("path").removeprefix("./")
        for match in matches
    )
    active_track_indexes = tuple(
        path
        for match, path in zip(matches, track_indexes, strict=True)
        if match.group("location") == "tracks"
    )
    archived_track_indexes = tuple(
        path
        for match, path in zip(matches, track_indexes, strict=True)
        if match.group("location") == "archive"
    )
    return TrackIndexes(
        all=track_indexes,
        active=active_track_indexes,
        archived=archived_track_indexes,
    )


def validate_system_completion(track_indexes: tuple[Path, ...]) -> None:
    """Validate execution focus without granting qualification or release."""
    raw_plan = json.loads(
        (PROJECT_ROOT / "conductor/system-completion.json").read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(raw_plan, dict):
        raise TypeError("System completion plan must be an object")
    plan = cast("dict[str, object]", raw_plan)
    expected_keys = {
        "schema_version",
        "purpose",
        "qualification_contract",
        "guardrails",
        "selected_stage",
        "stages",
    }
    if set(plan) != expected_keys:
        raise ValueError("System completion plan has unknown or missing keys")
    if type(plan["schema_version"]) is not int or plan["schema_version"] != 1:
        raise ValueError("Unknown system completion plan version")
    if plan["purpose"] != "execution_priority_only":
        raise ValueError("Scheduling policy cannot grant acceptance")
    contract_path = "quality/qualifications/stable-v1-contract.json"
    if plan["qualification_contract"] != contract_path:
        raise ValueError("System completion must reuse the Stable v1 contract")
    guards = plan["guardrails"]
    if not isinstance(guards, dict):
        raise TypeError("System completion guardrails are missing or unknown")
    guard_map = cast("dict[str, object]", guards)
    if set(guard_map) != set(SYSTEM_COMPLETION_GUARDRAILS):
        raise ValueError("System completion guardrails are missing or unknown")
    if any(
        guard_map[key] is not expected
        for key, expected in SYSTEM_COMPLETION_GUARDRAILS.items()
    ):
        raise ValueError(
            "System completion scope or acceptance guardrail drift"
        )
    contract = cast(
        "ReleaseGateInventory",
        json.loads((PROJECT_ROOT / contract_path).read_text(encoding="utf-8")),
    )
    gate_ids = {gate["gate_id"] for gate in contract["release_gates"]}
    tracks = {index.parent.name for index in track_indexes}
    _validate_system_stages(plan, tracks, gate_ids)


def _validate_system_stages(
    plan: dict[str, object], tracks: set[str], gate_ids: set[str]
) -> None:
    """Require bounded system tasks that reference existing authority."""
    raw_stages = plan["stages"]
    if not isinstance(raw_stages, list):
        raise TypeError("System completion stages must be a list")
    stage_keys = {
        "id",
        "track",
        "release_gate",
        "capability",
        "current_failure",
        "next_action",
        "completion_evidence",
        "stop_condition",
        "validation",
    }
    stage_ids: list[str] = []
    for raw_stage in cast("list[object]", raw_stages):
        if not isinstance(raw_stage, dict):
            raise TypeError("System completion stage must be an object")
        stage = cast("dict[str, object]", raw_stage)
        if set(stage) != stage_keys or any(
            not isinstance(value, str) or not value.strip()
            for value in stage.values()
        ):
            raise ValueError(
                "Each system task requires a complete bounded plan"
            )
        if stage["track"] not in tracks:
            raise ValueError("System task must belong to a registered track")
        if stage["release_gate"] not in gate_ids:
            raise ValueError("System task must name an existing release gate")
        stage_ids.append(cast("str", stage["id"]))
    if tuple(stage_ids) != SYSTEM_COMPLETION_STAGES:
        raise ValueError("System completion stage order or denominator drift")
    if plan["selected_stage"] not in stage_ids:
        raise ValueError("Selected system stage is not in the completion plan")


def validate_context() -> ContextReceipt:
    """Return a bounded receipt or raise for context drift."""
    context = _read_context()
    required_context = _strings(context, "required_context")
    required_manifests = _strings(context, "required_manifests")
    profiles = _strings(context, "required_harness_profiles")
    human_gates = _strings(context, "human_gates")
    missing = [
        relative
        for relative in (*required_context, *required_manifests)
        if not (PROJECT_ROOT / relative).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"Missing governed files: {', '.join(missing)}")

    tracks_text = (PROJECT_ROOT / "conductor" / "tracks.md").read_text(
        encoding="utf-8"
    )
    track_indexes = _registered_track_indexes(tracks_text)
    if not track_indexes.active or any(
        not path.is_file() for path in track_indexes.all
    ):
        raise ValueError("Every registered track must resolve to an index")
    for index in track_indexes.all:
        track_root = index.parent
        for filename in (
            "spec.md",
            "plan.md",
            "metadata.json",
            "evidence.jsonl",
        ):
            if not (track_root / filename).is_file():
                raise FileNotFoundError(
                    f"{index.parent.name} missing {filename}"
                )

    release_count = _validate_maturity(track_indexes.active)

    requirement_ids = REQUIREMENT_PATTERN.findall(
        (PROJECT_ROOT / "conductor" / "requirements.md").read_text(
            encoding="utf-8"
        )
    )
    if not requirement_ids or len(requirement_ids) != len(set(requirement_ids)):
        raise ValueError("Requirement identifiers must exist and be unique")
    _validate_track_requirements(track_indexes.all, set(requirement_ids))
    autonomous_track_count = _validate_execution_policies(track_indexes.active)
    validate_system_completion(track_indexes.all)

    harness_text = (PROJECT_ROOT / "scripts" / "test_goblin.py").read_text(
        encoding="utf-8"
    )
    undeclared = [
        profile for profile in profiles if f'"{profile}"' not in harness_text
    ]
    if undeclared:
        raise ValueError(
            f"Harness profiles not declared: {', '.join(undeclared)}"
        )

    schema_version = context.get("schema_version")
    if not isinstance(schema_version, int):
        raise TypeError("schema_version must be an integer")
    return {
        "schema_version": schema_version,
        "repository": str(context["repository"]),
        "context_files": len(required_context),
        "manifests": len(required_manifests),
        "tracks": len(track_indexes.active),
        "archived_tracks": len(track_indexes.archived),
        "registered_tracks": len(track_indexes.all),
        "autonomous_tracks": autonomous_track_count,
        "requirements": len(requirement_ids),
        "harness_profiles": len(profiles),
        "human_gates": len(human_gates),
        "releases": release_count,
        "status": "pass",
    }


def main() -> None:
    """Validate context and write a machine-readable CI receipt."""
    receipt = validate_context()
    output = PROJECT_ROOT / "build" / "context-validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
