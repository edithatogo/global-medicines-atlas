"""Tests for exact, omission-sensitive donor repository inventories."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixture Git
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from global_medicines_atlas import donor_inventory
from global_medicines_atlas.donor_inventory import (
    DonorInventoryError,
    build_donor_inventory,
    validate_donor_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION = (
    ROOT
    / "quality"
    / "qualifications"
    / "australian-health-donor-inventory.json"
)
SCHEMA = ROOT / "contracts" / "australian-donor-inventory.schema.json"


def _git(repository: Path, *arguments: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("Git executable is required for this test")
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixture arguments never use a shell
        [executable, *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _validate(repository: Path, inventory: dict[str, object]) -> None:
    validate_donor_inventory(
        repository,
        inventory,
        expected_repository_name="owner/donor",
        expected_source_url="https://example.invalid/owner/donor",
    )


@pytest.fixture
def donor_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "donor"
    repository.mkdir()
    _git(repository, "init", "--initial-branch=main")
    _git(repository, "config", "user.name", "Inventory Test")
    _git(repository, "config", "user.email", "inventory@example.invalid")

    (repository / "src").mkdir()
    (repository / "src" / "working.py").write_text(
        "def acquire(month: str) -> str:\n    return month\n",
        encoding="utf-8",
    )
    (repository / "src" / "invalid.py").write_text(
        "def broken(:\n    pass\n",
        encoding="utf-8",
    )
    (repository / "src" / "fenced.py").write_text(
        "def recoverable() -> bool:\n    return True\n```\n",
        encoding="utf-8",
    )
    (repository / "data").mkdir()
    (repository / "data" / "raw.xml").write_bytes(b"<root><row /></root>\n")
    (repository / "empty.ipynb").write_bytes(b"")
    (repository / ".github" / "workflows").mkdir(parents=True)
    (repository / ".github" / "workflows" / "ci.yml").write_text(
        "name: CI\n",
        encoding="utf-8",
    )
    (repository / "ROADMAP.md").write_text("# Future\n", encoding="utf-8")
    (repository / "LICENSE").write_text("fixture\n", encoding="utf-8")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "fixture")
    return repository, _git(repository, "rev-parse", "HEAD")


def test_inventory_covers_every_blob_and_characterizes_code(
    donor_repository: tuple[Path, str],
) -> None:
    repository, revision = donor_repository

    inventory = build_donor_inventory(
        repository,
        repository_name="owner/donor",
        expected_commit=revision,
        source_url="https://example.invalid/owner/donor",
    )

    assert inventory["commit"] == revision
    assert inventory["tracked_blob_count"] == 8
    files = {item["path"]: item for item in inventory["files"]}
    assert files["src/working.py"]["functions"] == ["acquire"]
    assert files["src/working.py"]["implementation_state"] == "implemented"
    assert files["src/invalid.py"]["implementation_state"] == "invalid_syntax"
    assert files["src/invalid.py"]["parse_error"]
    assert files["src/fenced.py"]["functions"] == ["recoverable"]
    assert files["src/fenced.py"]["implementation_state"] == "invalid_syntax"
    assert files["src/fenced.py"]["parse_error"]
    assert len(files["src/working.py"]["git_object_sha1"]) == 40
    assert files["data/raw.xml"]["data_role"] == "raw_payload"
    assert files["empty.ipynb"]["implementation_state"] == "zero_byte"
    assert (
        files[".github/workflows/ci.yml"]["implementation_state"] == "workflow"
    )
    assert files["ROADMAP.md"]["implementation_state"] == "design_intent"
    assert files["LICENSE"]["disposition"] == "preserve_provenance"
    assert inventory["history"] == {
        "reachable_commit_count": 1,
        "root_commits": [revision],
    }
    assert inventory["code_license"] == {
        "spdx_id": "Apache-2.0",
        "path": "LICENSE",
        "sha256": hashlib.sha256(b"fixture\n").hexdigest(),
    }
    assert inventory["total_blob_bytes"] == sum(
        item["size_bytes"] for item in inventory["files"]
    )
    _validate(repository, inventory)


@pytest.mark.parametrize("change", ["omit", "add", "digest", "mode", "size"])
def test_inventory_rejects_any_denominator_difference(
    donor_repository: tuple[Path, str],
    change: str,
) -> None:
    repository, revision = donor_repository
    inventory = build_donor_inventory(
        repository,
        repository_name="owner/donor",
        expected_commit=revision,
        source_url="https://example.invalid/owner/donor",
    )

    if change == "omit":
        inventory["files"] = inventory["files"][1:]
    elif change == "add":
        inventory["files"].append({**inventory["files"][0], "path": "extra"})
    elif change == "digest":
        inventory["files"][0]["sha256"] = "0" * 64
    elif change == "mode":
        inventory["files"][0]["mode"] = "100755"
    else:
        inventory["files"][0]["size_bytes"] += 1

    with pytest.raises(DonorInventoryError):
        _validate(repository, inventory)


@pytest.mark.parametrize("field", ["repository", "source_url"])
def test_inventory_rejects_untrusted_donor_labels(
    donor_repository: tuple[Path, str],
    field: str,
) -> None:
    repository, revision = donor_repository
    inventory = build_donor_inventory(
        repository,
        repository_name="owner/donor",
        expected_commit=revision,
        source_url="https://example.invalid/owner/donor",
    )
    inventory[field] = "untrusted-identity"

    with pytest.raises(DonorInventoryError, match="pinned donor identity"):
        _validate(repository, inventory)


def test_inventory_refuses_a_different_commit(
    donor_repository: tuple[Path, str],
) -> None:
    repository, _revision = donor_repository

    with pytest.raises(DonorInventoryError, match="expected commit"):
        build_donor_inventory(
            repository,
            repository_name="owner/donor",
            expected_commit="0" * 40,
            source_url="https://example.invalid/owner/donor",
        )


def test_inventory_refuses_head_different_from_pinned_commit(
    donor_repository: tuple[Path, str],
) -> None:
    repository, revision = donor_repository
    (repository / "later.txt").write_text("later\n", encoding="utf-8")
    _git(repository, "add", "later.txt")
    _git(repository, "commit", "-m", "later")

    with pytest.raises(DonorInventoryError, match="does not equal expected"):
        build_donor_inventory(
            repository,
            repository_name="owner/donor",
            expected_commit=revision,
            source_url="https://example.invalid/owner/donor",
        )


def test_inventory_reports_missing_git_and_blob_size_drift(
    donor_repository: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, revision = donor_repository
    monkeypatch.setattr(donor_inventory.shutil, "which", lambda _name: None)
    with pytest.raises(DonorInventoryError, match="unavailable"):
        build_donor_inventory(
            repository,
            repository_name="owner/donor",
            expected_commit=revision,
            source_url="https://example.invalid/owner/donor",
        )

    monkeypatch.undo()
    monkeypatch.setattr(donor_inventory, "_blob", lambda *_args: b"drift")
    with pytest.raises(DonorInventoryError, match="Git reported"):
        build_donor_inventory(
            repository,
            repository_name="owner/donor",
            expected_commit=revision,
            source_url="https://example.invalid/owner/donor",
        )


@pytest.mark.parametrize("files", [None, ["not-an-object"]])
def test_inventory_rejects_malformed_file_collections(
    donor_repository: tuple[Path, str],
    files: object,
) -> None:
    repository, revision = donor_repository
    inventory = build_donor_inventory(
        repository,
        repository_name="owner/donor",
        expected_commit=revision,
        source_url="https://example.invalid/owner/donor",
    )
    inventory["files"] = files

    with pytest.raises(DonorInventoryError, match="list of objects"):
        _validate(repository, inventory)


def test_inventory_rejects_non_string_commit(
    donor_repository: tuple[Path, str],
) -> None:
    repository, revision = donor_repository
    inventory = build_donor_inventory(
        repository,
        repository_name="owner/donor",
        expected_commit=revision,
        source_url="https://example.invalid/owner/donor",
    )
    inventory["commit"] = 123

    with pytest.raises(DonorInventoryError, match="commit must be a string"):
        _validate(repository, inventory)


def test_python_characterization_fails_closed_on_unrecoverable_sources() -> (
    None
):
    functions, error = donor_inventory._python_characterization(b"\xff")
    assert functions == []
    assert error is not None
    assert error.startswith("UnicodeDecodeError")

    functions, error = donor_inventory._python_characterization(
        b"def still_broken(:\n```\n"
    )
    assert functions == []
    assert error is not None
    assert error.startswith("SyntaxError")


def test_inventory_rejects_history_or_license_drift(
    donor_repository: tuple[Path, str],
) -> None:
    repository, revision = donor_repository
    inventory = build_donor_inventory(
        repository,
        repository_name="owner/donor",
        expected_commit=revision,
        source_url="https://example.invalid/owner/donor",
    )

    inventory["history"] = {"reachable_commit_count": 2, "root_commits": []}
    with pytest.raises(DonorInventoryError, match="history differs"):
        _validate(repository, inventory)

    inventory = build_donor_inventory(
        repository,
        repository_name="owner/donor",
        expected_commit=revision,
        source_url="https://example.invalid/owner/donor",
    )
    inventory["code_license"] = {"spdx_id": "unknown"}
    with pytest.raises(DonorInventoryError, match="code_license differs"):
        _validate(repository, inventory)


def test_checked_in_two_repository_denominator_is_self_consistent() -> None:
    document = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(document)
    denominator = document["denominator"]
    canonical = json.dumps(
        denominator,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    assert (
        document["denominator_sha256"] == hashlib.sha256(canonical).hexdigest()
    )
    assert denominator["tracked_blob_count"] == 54
    assert denominator["total_blob_bytes"] == 8_389_043
    repositories = denominator["repositories"]
    assert [item["repository"] for item in repositories] == [
        "edithatogo/aus_mbs_pbs_graph",
        "edithatogo/aus-health-data-scraper",
    ]
    for repository in repositories:
        files = repository["files"]
        assert repository["tracked_blob_count"] == len(files)
        assert repository["total_blob_bytes"] == sum(
            item["size_bytes"] for item in files
        )
        assert len({item["path"] for item in files}) == len(files)
        assert all(len(item["git_object_sha1"]) == 40 for item in files)
        assert repository["history"]["reachable_commit_count"] > 0
        assert repository["history"]["root_commits"]
        assert repository["code_license"]["spdx_id"] == "Apache-2.0"
        license_digest = next(
            item["sha256"] for item in files if item["path"] == "LICENSE"
        )
        assert repository["code_license"]["sha256"] == license_digest

    graph_files = {item["path"]: item for item in repositories[0]["files"]}
    fenced_parser = graph_files["scripts/parsing/parse_pbs_xml.py"]
    assert fenced_parser["implementation_state"] == "invalid_syntax"
    assert fenced_parser["functions"] == ["parse_pbs_xml_initial"]


def test_checked_in_findings_bind_to_inventoried_digests() -> None:
    document = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    repositories = document["denominator"]["repositories"]
    files = {
        (repository["repository"], item["path"]): item["sha256"]
        for repository in repositories
        for item in repository["files"]
    }

    for finding in document["findings"]:
        for evidence in finding.get("evidence", []):
            if "path" not in evidence:
                continue
            identity = (evidence["repository"], evidence["path"])
            assert files[identity] == evidence["sha256"]

    policy = document["coverage_policy"]
    assert policy == {
        "all_legacy_data_included": True,
        "raw_payload_destination": "public_hugging_face_dataset",
        "repository_is_durable_raw_storage": False,
        "zero_byte_artifacts_are_coverage": False,
    }
