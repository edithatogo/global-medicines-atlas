"""Validate repository context, track links, and harness declarations."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import TypedDict, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_FILE = PROJECT_ROOT / ".context" / "project.toml"
TRACK_PATTERN = re.compile(r"\((?P<path>\./tracks/[^)]+/index\.md)\)")
REQUIREMENT_PATTERN = re.compile(r"\*\*(?P<id>[MSCW]-\d{3}):\*\*")


class ContextReceipt(TypedDict):
    schema_version: int
    repository: str
    context_files: int
    manifests: int
    tracks: int
    requirements: int
    harness_profiles: int
    human_gates: int
    status: str


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

    tracks_text = (PROJECT_ROOT / "conductor" / "tracks.md").read_text(encoding="utf-8")
    track_indexes = tuple(
        PROJECT_ROOT / "conductor" / match.group("path").removeprefix("./")
        for match in TRACK_PATTERN.finditer(tracks_text)
    )
    if not track_indexes or any(not path.is_file() for path in track_indexes):
        raise ValueError("Every registered track must resolve to an index")
    for index in track_indexes:
        track_root = index.parent
        for filename in ("spec.md", "plan.md", "metadata.json", "evidence.jsonl"):
            if not (track_root / filename).is_file():
                raise FileNotFoundError(f"{index.parent.name} missing {filename}")

    requirement_ids = REQUIREMENT_PATTERN.findall(
        (PROJECT_ROOT / "conductor" / "requirements.md").read_text(encoding="utf-8")
    )
    if not requirement_ids or len(requirement_ids) != len(set(requirement_ids)):
        raise ValueError("Requirement identifiers must exist and be unique")

    harness_text = (PROJECT_ROOT / "scripts" / "test_goblin.py").read_text(
        encoding="utf-8"
    )
    undeclared = [profile for profile in profiles if f'"{profile}"' not in harness_text]
    if undeclared:
        raise ValueError(f"Harness profiles not declared: {', '.join(undeclared)}")

    schema_version = context.get("schema_version")
    if not isinstance(schema_version, int):
        raise TypeError("schema_version must be an integer")
    return {
        "schema_version": schema_version,
        "repository": str(context["repository"]),
        "context_files": len(required_context),
        "manifests": len(required_manifests),
        "tracks": len(track_indexes),
        "requirements": len(requirement_ids),
        "harness_profiles": len(profiles),
        "human_gates": len(human_gates),
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
