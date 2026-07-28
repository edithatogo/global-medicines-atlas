"""Read-only Conductor/GitHub drift detection.

The synchronizer intentionally has no mutation mode.  It can inspect live GitHub
state through ``gh`` or consume a normalized fixture for deterministic offline
tests.
"""

# ruff: file-ignore[too-many-branches]
# ruff: file-ignore[too-many-locals]
# ruff: file-ignore[too-many-statements]
# ruff: file-ignore[subprocess-without-shell-equals-true]

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from pathlib import Path
from typing import TypedDict, cast

TRACK_PATTERN = re.compile(
    r"- \[(?P<marker>[ x~])\] \*\*Track: (?P<title>.+?)\*\*.*?"
    r"\((?P<link>\./tracks/[^)]+/index\.md)\)",
    re.DOTALL,
)
PHASE_SECTION_PATTERN = re.compile(
    r"^## Phase (?P<phase>\d+):(?P<heading>[^\n]*)"
    r"(?P<body>\n.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)
GITHUB_LINK_PATTERN = re.compile(r"\[GitHub #(?P<issue>\d+)\]")
CHECKBOX_PATTERN = re.compile(r"^\s*- \[(?P<marker>[ x~])\]", re.MULTILINE)
ISSUE_URL_PATTERN = re.compile(r"/issues/(?P<number>\d+)$")


class IssueState(TypedDict):
    number: int
    state: str
    labels: list[str]
    parent: int | None
    subissues: list[int]


class Drift(TypedDict):
    code: str
    track_id: str
    issue: int | None
    expected: object
    actual: object


def _drift(
    code: str,
    track_id: str,
    *,
    issue: int | None,
    expected: object,
    actual: object,
) -> Drift:
    return {
        "code": code,
        "track_id": track_id,
        "issue": issue,
        "expected": expected,
        "actual": actual,
    }


def _normalise_state(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("GitHub issue state must be a string")
    state = value.lower()
    if state not in {"open", "closed"}:
        raise ValueError(f"Unsupported GitHub issue state: {value}")
    return state


def _normalise_issue(
    raw: dict[str, object],
) -> IssueState:
    number = raw.get("number")
    if not isinstance(number, int):
        raise TypeError("GitHub issue number must be an integer")
    raw_labels = raw.get("labels", [])
    if not isinstance(raw_labels, list):
        raise TypeError("GitHub issue labels must be a list")
    labels: list[str] = []
    for raw_label in cast("list[object]", raw_labels):
        if isinstance(raw_label, str):
            labels.append(raw_label)
        elif isinstance(raw_label, dict):
            label = cast("dict[str, object]", raw_label)
            if not isinstance(label.get("name"), str):
                raise TypeError(
                    "GitHub issue label objects require string names"
                )
            labels.append(cast("str", label["name"]))
        else:
            raise TypeError(
                "GitHub issue labels must be strings or name objects"
            )

    raw_parent = raw.get("parent")
    if isinstance(raw_parent, dict):
        raw_parent = cast("dict[str, object]", raw_parent).get("number")
    if raw_parent is not None and not isinstance(raw_parent, int):
        raise TypeError("GitHub parent issue number must be an integer or null")

    raw_subissues: object = raw.get("subissues", raw.get("subIssues", []))
    if isinstance(raw_subissues, dict):
        raw_subissues = cast("dict[str, object]", raw_subissues).get(
            "nodes",
            [],
        )
    if not isinstance(raw_subissues, list):
        raise TypeError("GitHub subissues must be a list")
    subissues: list[int] = []
    for raw_subissue in cast("list[object]", raw_subissues):
        value: object = raw_subissue
        if isinstance(raw_subissue, dict):
            value = cast("dict[str, object]", raw_subissue).get("number")
        if not isinstance(value, int):
            raise TypeError("GitHub subissue number must be an integer")
        subissues.append(value)
    return {
        "number": number,
        "state": _normalise_state(raw.get("state")),
        "labels": sorted(set(labels)),
        "parent": raw_parent,
        "subissues": sorted(set(subissues)),
    }


def load_fixture(path: Path) -> dict[int, IssueState]:
    """Load normalized GitHub issue state without credentials."""
    document: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError("Fixture must be an object containing an issues list")
    fixture = cast("dict[str, object]", document)
    if not isinstance(fixture.get("issues"), list):
        raise TypeError("Fixture must be an object containing an issues list")
    raw_issues = cast("list[object]", fixture["issues"])
    issues = [
        _normalise_issue(cast("dict[str, object]", raw))
        for raw in raw_issues
        if isinstance(raw, dict)
    ]
    if len(issues) != len(raw_issues):
        raise TypeError("Every fixture issue must be an object")
    if len({issue["number"] for issue in issues}) != len(issues):
        raise ValueError("Fixture issue numbers must be unique")
    return {issue["number"]: issue for issue in issues}


def load_live_issues(
    repository: str,
    numbers: set[int],
) -> dict[int, IssueState]:
    """Read issue state with the authenticated GitHub CLI."""
    issues: dict[int, IssueState] = {}
    fields = "number,state,labels,parent,subIssues"
    executable = shutil.which("gh")
    if executable is None:
        raise FileNotFoundError("GitHub CLI executable 'gh' was not found")
    for number in sorted(numbers):
        completed = subprocess.run(
            [
                executable,
                "issue",
                "view",
                str(number),
                "--repo",
                repository,
                "--json",
                fields,
            ],
            check=True,
            capture_output=True,
            shell=False,
            text=True,
        )
        raw: object = json.loads(completed.stdout)
        if not isinstance(raw, dict):
            raise TypeError("GitHub CLI returned a non-object issue")
        issues[number] = _normalise_issue(cast("dict[str, object]", raw))
    return issues


def _phase_complete(section: str) -> bool:
    markers = CHECKBOX_PATTERN.findall(section)
    return bool(markers) and all(marker == "x" for marker in markers)


def _plan_phases(plan: str) -> dict[int, tuple[int | None, str]]:
    phases: dict[int, tuple[int | None, str]] = {}
    for match in PHASE_SECTION_PATTERN.finditer(plan):
        phase = int(match.group("phase"))
        if phase in phases:
            raise ValueError("Plan phase numbers must be unique")
        issue_match = GITHUB_LINK_PATTERN.search(match.group("heading"))
        issue = (
            int(issue_match.group("issue")) if issue_match is not None else None
        )
        phases[phase] = (issue, match.group(0))
    return phases


def _issue_number(reference: object) -> int | None:
    if isinstance(reference, int):
        return reference
    if isinstance(reference, str):
        match = ISSUE_URL_PATTERN.search(reference)
        return int(match.group("number")) if match else None
    if isinstance(reference, dict):
        issue = cast("dict[str, object]", reference)
        number = issue.get("number")
        if isinstance(number, int):
            return number
        return _issue_number(issue.get("url"))
    return None


def _metadata_issue_numbers(
    metadata: dict[str, object],
    plan: str,
) -> tuple[int, list[dict[str, object]]]:
    github_issues: object = metadata.get("github_issues")
    github_issue_map = (
        cast("dict[str, object]", github_issues)
        if isinstance(github_issues, dict)
        else {}
    )
    parent_reference = github_issue_map.get(
        "parent",
        metadata.get("github_issue"),
    )
    parent_number = _issue_number(parent_reference)
    if parent_number is None:
        raise TypeError("Track metadata requires a numbered parent issue")

    plan_phases = _plan_phases(plan)
    phases_reference = github_issue_map.get(
        "phases",
        metadata.get("github_subissues", []),
    )
    if not isinstance(phases_reference, list):
        raise TypeError("Track metadata phases must be a list")
    references = cast("list[object]", phases_reference)
    plan_phase_numbers = sorted(plan_phases)
    if references and len(references) != len(plan_phase_numbers):
        raise ValueError(
            "Track metadata phase count must match plan phase count"
        )

    phase_entries: list[dict[str, object]] = []
    for index, reference in enumerate(references):
        if isinstance(reference, dict):
            phase_entry = dict(cast("dict[str, object]", reference))
            phase = phase_entry.get("phase", plan_phase_numbers[index])
            number = _issue_number(phase_entry)
        else:
            phase = plan_phase_numbers[index]
            number = _issue_number(reference)
            phase_entry = {}
        if not isinstance(phase, int) or number is None:
            raise TypeError(
                "Every metadata phase requires phase and issue numbers"
            )
        phase_entry.update({"phase": phase, "number": number})
        phase_entries.append(phase_entry)

    if not phase_entries:
        phase_entries = [
            {"phase": phase, "number": number}
            for phase, number in sorted(plan_phases.items())
        ]
    metadata_phases = [cast("int", entry["phase"]) for entry in phase_entries]
    if len(set(metadata_phases)) != len(metadata_phases):
        raise ValueError("Track metadata phase numbers must be unique")
    if set(metadata_phases) != set(plan_phases):
        raise ValueError(
            "Track metadata phase numbers must match plan phase numbers"
        )

    issue_numbers = [cast("int", entry["number"]) for entry in phase_entries]
    if len(set(issue_numbers)) != len(issue_numbers):
        raise ValueError("Track metadata issue numbers must be unique")
    for entry in phase_entries:
        phase = cast("int", entry["phase"])
        issue = cast("int", entry["number"])
        plan_issue = plan_phases[phase][0]
        if plan_issue is not None and plan_issue != issue:
            raise ValueError(
                "Track metadata issue numbers must match optional plan links"
            )
    return parent_number, phase_entries


def _metadata_validation_drift(
    track_id: str,
    error: TypeError | ValueError,
) -> Drift:
    return _drift(
        "track_issue_metadata_invalid",
        track_id,
        issue=None,
        expected="valid parent and phase issue metadata",
        actual={
            "error": type(error).__name__,
            "message": str(error),
        },
    )


def _best_effort_issue_numbers(
    metadata: dict[str, object],
    plan: str,
) -> set[int]:
    numbers = {
        issue
        for issue, _section in _plan_phases(plan).values()
        if issue is not None
    }
    github_issues = metadata.get("github_issues")
    github_issue_map = (
        cast("dict[str, object]", github_issues)
        if isinstance(github_issues, dict)
        else {}
    )
    references: list[object] = [
        github_issue_map.get("parent"),
        metadata.get("github_issue"),
    ]
    for key in ("phases",):
        value = github_issue_map.get(key)
        if isinstance(value, list):
            references.extend(cast("list[object]", value))
    top_level_subissues = metadata.get("github_subissues")
    if isinstance(top_level_subissues, list):
        references.extend(cast("list[object]", top_level_subissues))
    numbers.update(
        number
        for number in map(_issue_number, references)
        if number is not None
    )
    return numbers


def synchronise(
    root: Path,
    issues: dict[int, IssueState],
) -> dict[str, object]:
    """Compare local Conductor declarations with supplied GitHub state."""
    registry_path = root / "conductor" / "tracks.md"
    registry = registry_path.read_text(encoding="utf-8")
    registry_entries = list(TRACK_PATTERN.finditer(registry))
    drifts: list[Drift] = []
    checked_tracks = 0
    checked_issues: set[int] = set()

    for entry in registry_entries:
        track_root = (
            registry_path.parent / entry.group("link").removeprefix("./")
        ).parent
        track_id = track_root.name
        metadata = cast(
            "dict[str, object]",
            json.loads(
                (track_root / "metadata.json").read_text(encoding="utf-8")
            ),
        )
        metadata_track_id = metadata.get("track_id")
        if metadata_track_id != track_id:
            drifts.append(
                _drift(
                    "track_id_mismatch",
                    track_id,
                    issue=None,
                    expected=track_id,
                    actual=metadata_track_id,
                )
            )
        status = metadata.get("status")
        expected_marker = {
            "active": "~",
            "new": " ",
            "planned": " ",
            "complete": "x",
            "archived": "x",
        }.get(status if isinstance(status, str) else "")
        if expected_marker != entry.group("marker"):
            drifts.append(
                _drift(
                    "registry_status_mismatch",
                    track_id,
                    issue=None,
                    expected=expected_marker,
                    actual=entry.group("marker"),
                )
            )

        plan = (track_root / "plan.md").read_text(encoding="utf-8")
        try:
            parent_number, phase_metadata = _metadata_issue_numbers(
                metadata,
                plan,
            )
        except (TypeError, ValueError) as error:
            drifts.append(_metadata_validation_drift(track_id, error))
            checked_issues.update(_best_effort_issue_numbers(metadata, plan))
            checked_tracks += 1
            continue
        expected_numbers = {parent_number}
        expected_numbers.update(
            cast("int", phase["number"])
            for phase in phase_metadata
            if isinstance(phase.get("number"), int)
        )
        checked_issues.update(expected_numbers)
        missing = sorted(expected_numbers.difference(issues))
        drifts.extend([
            _drift(
                "github_issue_missing",
                track_id,
                issue=number,
                expected="present",
                actual="missing",
            )
            for number in missing
        ])
        if missing:
            checked_tracks += 1
            continue

        parent_issue = issues[parent_number]
        required_parent_labels = {"conductor", "type:track"}
        if not required_parent_labels.issubset(parent_issue["labels"]):
            drifts.append(
                _drift(
                    "github_labels_missing",
                    track_id,
                    issue=parent_number,
                    expected=sorted(required_parent_labels),
                    actual=parent_issue["labels"],
                )
            )
        phase_numbers = sorted(expected_numbers - {parent_number})
        if parent_issue["subissues"] != phase_numbers:
            drifts.append(
                _drift(
                    "github_subissues_mismatch",
                    track_id,
                    issue=parent_number,
                    expected=phase_numbers,
                    actual=parent_issue["subissues"],
                )
            )

        plan_phases = _plan_phases(plan)
        for phase in phase_metadata:
            phase_number = phase.get("phase")
            issue_number = phase.get("number")
            if not isinstance(phase_number, int) or not isinstance(
                issue_number,
                int,
            ):
                raise TypeError(
                    "Every phase requires integer phase and issue numbers"
                )
            plan_issue, plan_section = plan_phases.get(
                phase_number,
                (None, ""),
            )
            plan_complete = _phase_complete(plan_section)
            if plan_issue is not None and plan_issue != issue_number:
                drifts.append(
                    _drift(
                        "plan_issue_link_mismatch",
                        track_id,
                        issue=issue_number,
                        expected=issue_number,
                        actual=plan_issue,
                    )
                )
            live_issue = issues[issue_number]
            raw_metadata_state = phase.get("state")
            metadata_state = (
                _normalise_state(raw_metadata_state)
                if raw_metadata_state is not None
                else None
            )
            if (
                metadata_state is not None
                and metadata_state != live_issue["state"]
            ):
                code = (
                    "issue_closed_while_phase_incomplete"
                    if live_issue["state"] == "closed" and not plan_complete
                    else "github_state_mismatch"
                )
                drifts.append(
                    _drift(
                        code,
                        track_id,
                        issue=issue_number,
                        expected={
                            "metadata_state": metadata_state,
                            "plan_complete": plan_complete,
                        },
                        actual={"github_state": live_issue["state"]},
                    )
                )
            elif live_issue["state"] == "closed" and not plan_complete:
                drifts.append(
                    _drift(
                        "issue_closed_while_phase_incomplete",
                        track_id,
                        issue=issue_number,
                        expected={"plan_complete": False},
                        actual={"github_state": "closed"},
                    )
                )
            required_phase_labels = {
                "conductor",
                "type:track",
                f"phase:{phase_number}",
            }
            if not required_phase_labels.issubset(live_issue["labels"]):
                drifts.append(
                    _drift(
                        "github_labels_missing",
                        track_id,
                        issue=issue_number,
                        expected=sorted(required_phase_labels),
                        actual=live_issue["labels"],
                    )
                )
            if live_issue["parent"] != parent_number:
                drifts.append(
                    _drift(
                        "github_parent_mismatch",
                        track_id,
                        issue=issue_number,
                        expected=parent_number,
                        actual=live_issue["parent"],
                    )
                )
        checked_tracks += 1

    drifts.sort(
        key=lambda item: (
            item["track_id"],
            -1 if item["issue"] is None else item["issue"],
            item["code"],
        )
    )
    return {
        "schema_version": 1,
        "mode": "dry-run",
        "status": "drift" if drifts else "in_sync",
        "tracks_checked": checked_tracks,
        "issues_checked": len(checked_issues),
        "drift_count": len(drifts),
        "drifts": drifts,
    }


def _repository_from_metadata(root: Path) -> str:
    conductor = root / "conductor"
    candidates = sorted((conductor / "tracks").glob("*/metadata.json"))
    candidates.extend(
        sorted((conductor / "archive").glob("*/metadata.json"))
    )
    for candidate in candidates:
        raw: object = json.loads(candidate.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            metadata = cast("dict[str, object]", raw)
            repository: object = metadata.get("canonical_repository")
            if isinstance(repository, dict) and isinstance(
                cast("dict[str, object]", repository).get("full_name"), str
            ):
                repository_map = cast("dict[str, object]", repository)
                return cast("str", repository_map["full_name"])
    raise ValueError("No canonical GitHub repository found in track metadata")


def main() -> int:
    """Run a deterministic read-only synchronization check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--repository")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Accepted for clarity; read-only dry-run is always enabled.",
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()

    if arguments.fixture is not None:
        issues = load_fixture(arguments.fixture)
    else:
        repository = arguments.repository or _repository_from_metadata(root)
        metadata_files = sorted(
            (root / "conductor" / "tracks").glob("*/metadata.json")
        )
        numbers: set[int] = set()
        for metadata_file in metadata_files:
            metadata = cast(
                "dict[str, object]",
                json.loads(metadata_file.read_text(encoding="utf-8")),
            )
            plan = metadata_file.with_name("plan.md").read_text(
                encoding="utf-8"
            )
            try:
                parent, phases = _metadata_issue_numbers(metadata, plan)
            except TypeError, ValueError:
                numbers.update(_best_effort_issue_numbers(metadata, plan))
            else:
                numbers.add(parent)
                numbers.update(
                    cast("int", phase["number"])
                    for phase in phases
                    if isinstance(phase.get("number"), int)
                )
        issues = load_live_issues(repository, numbers)

    receipt = synchronise(root, issues)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 1 if receipt["status"] == "drift" else 0


if __name__ == "__main__":
    raise SystemExit(main())
