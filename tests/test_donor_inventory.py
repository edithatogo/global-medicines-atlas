"""Tests for exact, omission-sensitive donor repository inventories."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixture Git
from pathlib import Path

import pytest

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
    (repository / "data").mkdir()
    (repository / "data" / "raw.xml").write_bytes(b"<root><row /></root>\n")
    (repository / "empty.ipynb").write_bytes(b"")
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
    assert inventory["tracked_blob_count"] == 4
    files = {item["path"]: item for item in inventory["files"]}
    assert files["src/working.py"]["functions"] == ["acquire"]
    assert files["src/working.py"]["implementation_state"] == "implemented"
    assert files["src/invalid.py"]["implementation_state"] == "invalid_syntax"
    assert files["src/invalid.py"]["parse_error"]
    assert files["data/raw.xml"]["data_role"] == "raw_payload"
    assert files["empty.ipynb"]["implementation_state"] == "zero_byte"
    assert inventory["total_blob_bytes"] == sum(
        item["size_bytes"] for item in inventory["files"]
    )
    validate_donor_inventory(repository, inventory)


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
        validate_donor_inventory(repository, inventory)


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


def test_checked_in_two_repository_denominator_is_self_consistent() -> None:
    document = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
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
