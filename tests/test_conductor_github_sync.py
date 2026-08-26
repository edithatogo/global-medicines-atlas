"""Focused tests for read-only Conductor/GitHub synchronization."""

# ruff: file-ignore[subprocess-without-shell-equals-true]

from __future__ import annotations

import importlib.util
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "sync_conductor_github.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "conductor_github_sync",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load synchronization module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_track(
    root: Path,
    *,
    phase_complete: bool = False,
    metadata_shape: str = "nested",
) -> None:
    track = root / "conductor" / "tracks" / "migration"
    track.mkdir(parents=True)
    (root / "conductor" / "tracks.md").write_text(
        "# Tracks Registry\n\n"
        "- [~] **Track: Migration**\n"
        "  *Link: [tracks/migration/index.md](./tracks/migration/index.md)*\n",
        encoding="utf-8",
    )
    (track / "index.md").write_text("# Migration\n", encoding="utf-8")
    metadata: dict[str, object] = {
        "track_id": "migration",
        "status": "active",
        "canonical_repository": {"full_name": "owner/repository"},
    }
    if metadata_shape == "nested":
        metadata["github_issues"] = {
            "parent": {"number": 1, "state": "open"},
            "phases": [
                {"phase": 4, "number": 5, "state": "open"},
                {"phase": 5, "number": 6, "state": "open"},
            ],
        }
    elif metadata_shape == "top-level":
        metadata["github_issue"] = (
            "https://github.com/owner/repository/issues/1"
        )
        metadata["github_subissues"] = [
            "https://github.com/owner/repository/issues/5",
            "https://github.com/owner/repository/issues/6",
        ]
    else:
        raise ValueError(f"Unsupported metadata shape: {metadata_shape}")
    (track / "metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    marker = "x" if phase_complete else " "
    (track / "plan.md").write_text(
        "# Implementation Plan\n\n"
        "## Phase 4: Harness ([GitHub #5](https://example.test/issues/5))\n\n"
        f"- [{marker}] Task: Dry-run synchronization\n\n"
        "## Phase 5: Handoff ([GitHub #6](https://example.test/issues/6))\n\n"
        "- [ ] Task: Handoff\n",
        encoding="utf-8",
    )


def _fixture(*, issue_five_state: str = "open") -> dict[str, object]:
    return {
        "issues": [
            {
                "number": 1,
                "state": "open",
                "labels": ["type:track", "conductor"],
                "parent": None,
                "subissues": [6, 5],
            },
            {
                "number": 5,
                "state": issue_five_state,
                "labels": ["phase:4", "conductor", "type:track", "area:ci-cd"],
                "parent": 1,
                "subissues": [],
            },
            {
                "number": 6,
                "state": "open",
                "labels": ["phase:5", "conductor", "type:track"],
                "parent": 1,
                "subissues": [],
            },
        ]
    }


@pytest.mark.unit
def test_fixture_check_is_deterministic_and_in_sync(tmp_path: Path) -> None:
    _write_track(tmp_path)
    fixture = tmp_path / "github.json"
    fixture.write_text(json.dumps(_fixture()), encoding="utf-8")

    command = [
        sys.executable,
        str(SCRIPT),
        "--root",
        str(tmp_path),
        "--fixture",
        str(fixture),
    ]
    first = subprocess.run(
        command, capture_output=True, text=True, check=False, shell=False
    )
    second = subprocess.run(
        command, capture_output=True, text=True, check=False, shell=False
    )

    assert first.returncode == 0
    assert second.returncode == 0
    assert first.stdout == second.stdout
    assert json.loads(first.stdout) == {
        "drift_count": 0,
        "drifts": [],
        "issues_checked": 3,
        "mode": "dry-run",
        "schema_version": 1,
        "status": "in_sync",
        "tracks_checked": 1,
    }


@pytest.mark.unit
def test_top_level_subissues_map_to_plan_phases_without_false_drift(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _write_track(tmp_path, metadata_shape="top-level")
    fixture_path = tmp_path / "github.json"
    fixture_path.write_text(json.dumps(_fixture()), encoding="utf-8")

    receipt = module.synchronise(
        tmp_path,
        module.load_fixture(fixture_path),
    )

    assert receipt["status"] == "in_sync"
    assert receipt["drifts"] == []
    assert receipt["issues_checked"] == 3


@pytest.mark.unit
@pytest.mark.parametrize(
    ("layout", "review_heading"),
    [
        ("temporal", "## Phase 2 review fixes"),
        ("country-adapter", "## Review fixes"),
    ],
)
def test_existing_unlinked_plan_layouts_map_subissues_by_phase_order(
    tmp_path: Path,
    layout: str,
    review_heading: str,
) -> None:
    module = _load_module()
    _write_track(tmp_path, metadata_shape="top-level")
    track = tmp_path / "conductor" / "tracks" / "migration"
    phase_count = 3 if layout == "temporal" else 4
    metadata_path = track / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["github_subissues"] = [
        f"https://github.com/owner/repository/issues/{number}"
        for number in range(5, 5 + phase_count)
    ]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    sections = [
        "# Implementation Plan",
        "",
        "## Phase 1: Contracts and tests",
        "",
        "- [x] Contract tests",
        "",
        "## Phase 2: Reference implementation",
        "",
        "- [x] Reference implementation",
        "",
        review_heading,
        "",
        "- [ ] Review note that is not a numbered phase",
        "",
        "## Phase 3: Qualification",
        "",
        "- [ ] Qualification",
    ]
    if phase_count == 4:
        sections.extend([
            "",
            "## Phase 4: Global source census",
            "",
            "- [ ] Source census",
        ])
    (track / "plan.md").write_text(
        "\n".join(sections) + "\n",
        encoding="utf-8",
    )
    fixture = _fixture()
    raw_issues = cast("list[object]", fixture["issues"])
    parent = cast("dict[str, object]", raw_issues[0])
    parent["subissues"] = list(range(5, 5 + phase_count))
    raw_issues[1:] = [
        {
            "number": number,
            "state": "open" if number >= 7 else "closed",
            "labels": [
                "conductor",
                "type:track",
                f"phase:{phase}",
            ],
            "parent": 1,
            "subissues": [],
        }
        for phase, number in enumerate(
            range(5, 5 + phase_count),
            start=1,
        )
    ]
    fixture_path = _write_fixture(tmp_path, fixture)

    receipt = module.synchronise(
        tmp_path,
        module.load_fixture(fixture_path),
    )

    assert receipt["status"] == "in_sync"
    assert receipt["drifts"] == []
    assert receipt["issues_checked"] == phase_count + 1


@pytest.mark.unit
def test_optional_plan_link_is_validated_when_present(tmp_path: Path) -> None:
    module = _load_module()
    _write_track(tmp_path, metadata_shape="top-level")
    plan_path = tmp_path / "conductor" / "tracks" / "migration" / "plan.md"
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8").replace(
            "[GitHub #5]",
            "[GitHub #99]",
        ),
        encoding="utf-8",
    )
    metadata_path = plan_path.with_name("metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="optional plan links"):
        module._metadata_issue_numbers(
            metadata,
            plan_path.read_text(encoding="utf-8"),
        )


@pytest.mark.unit
def test_metadata_phase_count_must_match_plan(tmp_path: Path) -> None:
    module = _load_module()
    _write_track(tmp_path, metadata_shape="top-level")
    metadata_path = (
        tmp_path / "conductor" / "tracks" / "migration" / "metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["github_subissues"] = metadata["github_subissues"][:1]
    plan_path = metadata_path.with_name("plan.md")

    with pytest.raises(ValueError, match="phase count"):
        module._metadata_issue_numbers(
            metadata,
            plan_path.read_text(encoding="utf-8"),
        )


@pytest.mark.unit
def test_metadata_phase_numbers_must_match_plan(tmp_path: Path) -> None:
    module = _load_module()
    _write_track(tmp_path)
    metadata_path = (
        tmp_path / "conductor" / "tracks" / "migration" / "metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["github_issues"]["phases"][0]["phase"] = 3
    plan_path = metadata_path.with_name("plan.md")

    with pytest.raises(ValueError, match="phase numbers"):
        module._metadata_issue_numbers(
            metadata,
            plan_path.read_text(encoding="utf-8"),
        )


@pytest.mark.unit
def test_metadata_issue_numbers_must_be_unique(tmp_path: Path) -> None:
    module = _load_module()
    _write_track(tmp_path, metadata_shape="top-level")
    metadata_path = (
        tmp_path / "conductor" / "tracks" / "migration" / "metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["github_subissues"][1] = metadata["github_subissues"][0]
    plan_path = metadata_path.with_name("plan.md")

    with pytest.raises(ValueError, match="issue numbers"):
        module._metadata_issue_numbers(
            metadata,
            plan_path.read_text(encoding="utf-8"),
        )


@pytest.mark.unit
def test_invalid_metadata_is_drift_and_other_tracks_are_checked(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _write_track(tmp_path, metadata_shape="top-level")
    first_track = tmp_path / "conductor" / "tracks" / "migration"
    metadata_path = first_track / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["github_subissues"] = metadata["github_subissues"][:1]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    second_track = tmp_path / "conductor" / "tracks" / "valid"
    second_track.mkdir()
    (second_track / "index.md").write_text(
        "# Valid\n",
        encoding="utf-8",
    )
    (second_track / "metadata.json").write_text(
        json.dumps({
            "track_id": "valid",
            "status": "active",
            "github_issue": "https://example.test/issues/10",
            "github_subissues": [
                "https://example.test/issues/11",
            ],
        }),
        encoding="utf-8",
    )
    (second_track / "plan.md").write_text(
        "# Plan\n\n"
        "## Phase 1: Valid "
        "([GitHub #11](https://example.test/issues/11))\n\n"
        "- [ ] Task\n",
        encoding="utf-8",
    )
    registry_path = tmp_path / "conductor" / "tracks.md"
    registry_path.write_text(
        registry_path.read_text(encoding="utf-8") + "- [~] **Track: Valid**\n"
        "  *Link: [tracks/valid/index.md]"
        "(./tracks/valid/index.md)*\n",
        encoding="utf-8",
    )
    existing_issues = cast(
        "list[object]",
        _fixture()["issues"],
    )
    issues = module.load_fixture(
        _write_fixture(
            tmp_path,
            {
                "issues": [
                    *existing_issues,
                    {
                        "number": 10,
                        "state": "open",
                        "labels": ["conductor", "type:track"],
                        "parent": None,
                        "subissues": [11],
                    },
                    {
                        "number": 11,
                        "state": "open",
                        "labels": [
                            "conductor",
                            "type:track",
                            "phase:1",
                        ],
                        "parent": 10,
                        "subissues": [],
                    },
                ]
            },
        )
    )

    receipt = module.synchronise(tmp_path, issues)

    assert receipt["tracks_checked"] == 2
    assert receipt["issues_checked"] == 5
    assert receipt["drifts"] == [
        {
            "actual": {
                "error": "ValueError",
                "message": (
                    "Track metadata phase count must match plan phase count"
                ),
            },
            "code": "track_issue_metadata_invalid",
            "expected": "valid parent and phase issue metadata",
            "issue": None,
            "track_id": "migration",
        }
    ]


@pytest.mark.unit
def test_duplicate_plan_phases_are_reported_without_crashing(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _write_track(tmp_path, metadata_shape="top-level")
    track = tmp_path / "conductor" / "tracks" / "migration"
    plan_path = track / "plan.md"
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8")
        + "\n## Phase 4: Duplicate\n\n- [ ] Task: Duplicate\n",
        encoding="utf-8",
    )

    receipt = module.synchronise(tmp_path, {})

    assert receipt["status"] == "drift"
    assert receipt["drifts"] == [
        {
            "actual": {
                "error": "ValueError",
                "message": "Plan phase numbers must be unique",
            },
            "code": "track_issue_metadata_invalid",
            "expected": "valid parent and phase issue metadata",
            "issue": None,
            "track_id": "migration",
        }
    ]
    assert receipt["issues_checked"] == 3


@pytest.mark.unit
@pytest.mark.parametrize("status", ["active", "in_progress"])
def test_active_status_dialects_match_in_progress_registry(
    tmp_path: Path,
    status: str,
) -> None:
    module = _load_module()
    _write_track(tmp_path)
    metadata_path = (
        tmp_path / "conductor" / "tracks" / "migration" / "metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["status"] = status
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    fixture_path = _write_fixture(tmp_path, _fixture())

    receipt = module.synchronise(
        tmp_path,
        module.load_fixture(fixture_path),
    )

    assert receipt["status"] == "in_sync"


def _write_fixture(
    root: Path,
    fixture: dict[str, object],
) -> Path:
    path = root / "github.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    return path


@pytest.mark.unit
def test_issue_five_closed_while_phase_incomplete_is_explicit(
    tmp_path: Path,
) -> None:
    _write_track(tmp_path)
    fixture = tmp_path / "github.json"
    fixture.write_text(
        json.dumps(_fixture(issue_five_state="closed")),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path),
            "--fixture",
            str(fixture),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    receipt = json.loads(completed.stdout)

    assert completed.returncode == 1
    assert receipt["status"] == "drift"
    assert {(drift["code"], drift["issue"]) for drift in receipt["drifts"]} == {
        ("issue_closed_while_phase_incomplete", 5)
    }


@pytest.mark.unit
def test_closed_parent_while_track_in_progress_is_explicit(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _write_track(tmp_path)
    fixture = _fixture()
    issues = cast("list[object]", fixture["issues"])
    parent = cast("dict[str, object]", issues[0])
    parent["state"] = "closed"
    fixture_path = _write_fixture(tmp_path, fixture)

    receipt = module.synchronise(
        tmp_path,
        module.load_fixture(fixture_path),
    )

    assert receipt["status"] == "drift"
    assert receipt["drifts"] == [
        {
            "actual": {"github_state": "closed"},
            "code": "issue_closed_while_track_incomplete",
            "expected": {"github_state": "open", "registry_marker": "~"},
            "issue": 1,
            "track_id": "migration",
        }
    ]


@pytest.mark.unit
def test_labels_and_relationship_drift_are_reported_in_stable_order(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _write_track(tmp_path)
    fixture = _fixture()
    issues = fixture["issues"]
    assert isinstance(issues, list)
    typed_issues = cast("list[object]", issues)
    parent = cast("dict[str, object]", typed_issues[0])
    phase = cast("dict[str, object]", typed_issues[1])
    assert isinstance(parent, dict)
    assert isinstance(phase, dict)
    parent["subissues"] = [5]
    phase["labels"] = ["conductor"]
    phase["parent"] = 99
    fixture_path = tmp_path / "github.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    receipt = module.synchronise(tmp_path, module.load_fixture(fixture_path))

    assert receipt["status"] == "drift"
    assert [(drift["issue"], drift["code"]) for drift in receipt["drifts"]] == [
        (1, "github_subissues_mismatch"),
        (5, "github_labels_missing"),
        (5, "github_parent_mismatch"),
    ]


@pytest.mark.unit
def test_fixture_rejects_duplicate_issue_numbers(tmp_path: Path) -> None:
    module = _load_module()
    fixture = _fixture()
    issues = fixture["issues"]
    assert isinstance(issues, list)
    typed_issues = cast("list[object]", issues)
    typed_issues.append(typed_issues[0])
    fixture_path = tmp_path / "github.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(ValueError, match="unique"):
        module.load_fixture(fixture_path)


@pytest.mark.unit
def test_repository_identity_can_be_read_from_archived_track(
    tmp_path: Path,
) -> None:
    module = _load_module()
    metadata = (
        tmp_path / "conductor" / "archive" / "migration" / "metadata.json"
    )
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        json.dumps({
            "canonical_repository": {
                "full_name": "edithatogo/global-medicines-atlas"
            }
        }),
        encoding="utf-8",
    )

    assert (
        module._repository_from_metadata(tmp_path)
        == "edithatogo/global-medicines-atlas"
    )
