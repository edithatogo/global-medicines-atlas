from __future__ import annotations

import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - temporary local Git fixtures only
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from global_medicines_atlas.australian_donor_inventory import (
    DonorRepository,
    InventoryCompletenessError,
    build_inventory,
    validate_inventory,
)

ROOT = Path(__file__).parents[1]
TRACK = (
    ROOT / "conductor/tracks/australian_health_source_consolidation_20260829"
)


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        ["git", *arguments],  # ruff: ignore[start-process-with-partial-path]
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _donor(tmp_path: Path, name: str) -> DonorRepository:
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.name", "Inventory Test")
    _git(root, "config", "user.email", "inventory@example.invalid")
    (root / ".github/workflows").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "src").mkdir()
    (root / ".github/workflows/ci.yml").write_text(
        "name: CI\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps: []\n"
    )
    (root / "data/source.csv").write_text("id,value\n1,a\n")
    (root / "src/parser.py").write_text(
        "def parse(value: str) -> str:\n    return value.strip()\n"
    )
    (root / "LICENSE").write_text("Apache License, Version 2.0\n")
    (root / "README.md").write_text("# Donor\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture donor")
    return DonorRepository(
        repository=f"example/{name}",
        revision=_git(root, "rev-parse", "HEAD"),
        git_dir=root,
    )


def test_inventory_covers_every_file_function_workflow_and_data_object(
    tmp_path: Path,
) -> None:
    donors = (_donor(tmp_path, "one"), _donor(tmp_path, "two"))

    inventory = build_inventory(donors)
    result = validate_inventory(inventory, donors)

    assert result.file_count == 10
    assert result.function_count == 2
    assert result.workflow_count == 2
    assert result.data_object_count == 2
    assert all(item.disposition != "unclassified" for item in inventory.files)


@pytest.mark.parametrize("section", ["files", "functions", "workflows"])
def test_inventory_rejects_an_omitted_tracked_item(
    tmp_path: Path, section: str
) -> None:
    donors = (_donor(tmp_path, "one"), _donor(tmp_path, "two"))
    inventory = build_inventory(donors).model_dump(mode="json")
    inventory[section].pop()

    with pytest.raises(InventoryCompletenessError, match=section):
        validate_inventory(inventory, donors)


def test_inventory_rejects_a_reclassified_tracked_item(tmp_path: Path) -> None:
    donors = (_donor(tmp_path, "one"), _donor(tmp_path, "two"))
    inventory = build_inventory(donors).model_dump(mode="json")
    inventory["files"][0]["disposition"] = "unclassified"

    with pytest.raises(InventoryCompletenessError, match="files"):
        validate_inventory(inventory, donors)


def test_inventory_is_deterministic_and_json_schema_valid(
    tmp_path: Path,
) -> None:
    donors = (_donor(tmp_path, "one"), _donor(tmp_path, "two"))

    first = build_inventory(donors)
    second = build_inventory(donors)

    assert json.dumps(
        first.model_dump(mode="json"), sort_keys=True
    ) == json.dumps(second.model_dump(mode="json"), sort_keys=True)
    assert first.schema_version == "1.0"
    assert first.denominator_sha256 == second.denominator_sha256


def test_inventory_retains_functions_from_known_trailing_fence_defect(
    tmp_path: Path,
) -> None:
    donor = _donor(tmp_path, "broken")
    parser = donor.git_dir / "src/parser.py"
    parser.write_text("def parse(value: str) -> str:\n    return value\n```\n")
    _git(donor.git_dir, "add", "src/parser.py")
    _git(donor.git_dir, "commit", "-m", "add known trailing fence defect")
    donor.revision = _git(donor.git_dir, "rev-parse", "HEAD")

    inventory = build_inventory((donor,))

    assert [item.qualified_name for item in inventory.functions] == ["parse"]


def test_committed_donor_denominator_is_schema_valid_and_exact() -> None:
    inventory = json.loads((TRACK / "donor-inventory.json").read_text())
    schema = json.loads(
        (ROOT / "contracts/australian-donor-inventory.schema.json").read_text()
    )

    Draft202012Validator(schema).validate(inventory)

    assert inventory["repositories"] == [
        {
            "code_license": "Apache-2.0",
            "license_path": "LICENSE",
            "license_sha256": "1b08c34fd4904bf72b922f034101323e8819d4d75e72b6a8873dae05946b2bd0",
            "reachable_commit_count": 12,
            "repository": "edithatogo/aus-health-data-scraper",
            "revision": "931da0b9b6ae3e3cec0743568abb71a50d62b7cf",
            "root_commits": ["b1598a6c228bd4030ae43ea15774a63fbaa24fb8"],
        },
        {
            "code_license": "Apache-2.0",
            "license_path": "LICENSE",
            "license_sha256": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
            "reachable_commit_count": 6,
            "repository": "edithatogo/aus_mbs_pbs_graph",
            "revision": "64e764cebeb3826f98ce672cbb4affc65d06a92f",
            "root_commits": ["e958d7dd9cc13464da04fd821edd9e66744903bd"],
        },
    ]
    assert len(inventory["files"]) == 54
    assert len(inventory["functions"]) == 17
    assert len(inventory["workflows"]) == 3
    assert len(inventory["roadmap_capabilities"]) == 10
    assert inventory["denominator_sha256"] == (
        "45e18c877e168734eec4e937f574089d11b25c60283d7484b34d4f069a5a70ba"
    )
    by_path = {
        (item["repository"], item["path"]): item for item in inventory["files"]
    }
    assert (
        by_path[
            "edithatogo/aus_mbs_pbs_graph",
            "scripts/parsing/MBS-XML-20250701 Version 3.XML",
        ]["sha256"]
        == "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
    )
    assert (
        by_path[
            "edithatogo/aus-health-data-scraper",
            "data/source/MBS - 2024.07 - Group P7 (Genetics).xlsx",
        ]["sha256"]
        == "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
    )
