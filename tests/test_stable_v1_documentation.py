"""Task-oriented stable-v1 documentation contract."""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import pytest
from scripts import render_project_overview as overview

ROOT = Path(__file__).resolve().parents[1]
LOCAL_LINK = re.compile(r"\[[^\]]+\]\((?!https?://|#)([^)]+)\)")

TASK_DOCUMENTS = (
    Path("README.md"),
    Path("SUPPORT.md"),
    Path("docs/user-guide.md"),
    Path("docs/operations/README.md"),
)


def _prose(relative: str) -> str:
    """Return case-folded prose with Markdown wrapping removed."""
    return " ".join(
        (ROOT / relative).read_text(encoding="utf-8").casefold().split()
    )


@pytest.mark.parametrize("relative", TASK_DOCUMENTS)
def test_task_navigation_has_no_broken_local_file_links(relative: Path) -> None:
    document = ROOT / relative
    text = document.read_text(encoding="utf-8")
    for target in LOCAL_LINK.findall(text):
        path_fragment = target.split("#", 1)[0]
        assert path_fragment, f"{relative}: empty local link target {target}"
        assert (document.parent / path_fragment).resolve().is_file(), (
            f"{relative}: broken local link {target}"
        )


def test_readme_routes_all_stable_v1_user_tasks() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "[task-oriented user guide](docs/user-guide.md)" in readme
    for task in (
        "install",
        "CLI",
        "API",
        "Atlas",
        "interpret",
        "reproduce",
        "recovery",
        "security",
    ):
        assert task.casefold() in readme.casefold(), task


def test_user_guide_separates_installation_profiles_and_surfaces() -> None:
    guide = (ROOT / "docs/user-guide.md").read_text(encoding="utf-8")
    prose = _prose("docs/user-guide.md")
    required_commands = (
        "uv sync --python 3.15.1 --locked --no-dev",
        "--extra semantic",
        "uv run global-medicines-atlas --help",
        "uv run global-medicines-atlas comparison --help",
        "uv run pytest tests/test_product_api.py tests/test_concept_api.py",
        "uv run pytest tests/test_atlas_e2e.py tests/test_atlas_discovery_e2e.py",
        "uv run --python 3.15.1 python scripts/test_goblin.py quick",
        "uv run --python 3.15.1 ruff check .",
    )
    for command in required_commands:
        assert command in guide, command

    assert "core operation must remain usable without lancedb" in prose
    assert "does not yet provide a supported production launcher" in prose
    assert "no production database is bundled" in prose


def test_user_guide_preserves_interpretation_and_authority_boundaries() -> None:
    guide = _prose("docs/user-guide.md")
    required_boundaries = (
        "regulatory approval and public funding are separate",
        "unknown coverage is not a negative finding",
        "missing or unknown evidence produces an abstention",
        "not that the medicines are equal or unequal",
        "public repository access is not a software licence",
        "external identifiers, credentials, rights review, release execution",
        "not establish an rpo",
    )
    for boundary in required_boundaries:
        assert boundary in guide, boundary


def test_support_routes_public_data_and_private_security_reports() -> None:
    support = _prose("SUPPORT.md")
    assert "data incidents" in support
    assert "security.md" in support
    assert "do not put credentials" in support
    assert "no service sla" in support


@pytest.fixture
def overview_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for relative in (
        "conductor/tracks.md",
        "quality/qualifications/stable-v1-contract.json",
        "docs/project-status.json",
        "README.md",
        "conductor/roadmap.md",
        "docs/publication/huggingface-catalogue-card.md",
        "docs/project-overview.md",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    monkeypatch.setattr(overview, "ROOT", tmp_path)
    return tmp_path


def test_overview_derives_all_progress_sections_and_preserves_prose(
    overview_root: Path,
) -> None:
    (overview_root / "conductor/tracks.md").write_text(
        "- [x] **Track: First**\n- [~] **Track: Second**\n"
    )
    generated = overview.outputs(date(2026, 12, 4))
    snapshot = json.loads(generated[overview_root / "docs/project-status.json"])
    assert snapshot["tracks"] == {"closed": 1, "total": 2}
    assert snapshot["as_of"] == "2026-12-04"
    for relative in (
        "README.md",
        "conductor/roadmap.md",
        "docs/publication/huggingface-catalogue-card.md",
    ):
        path = overview_root / relative
        before = path.read_text()
        after = generated[path]
        assert after.split(overview.START)[0] == before.split(overview.START)[0]
        assert after.split(overview.END)[1] == before.split(overview.END)[1]
        assert "1/2 delivery tracks closed (50%)" in after
        assert "4 December 2026" in after
    assert "50.0%" in generated[overview_root / "docs/assets/roadmap.svg"]
    assert (
        json.loads(
            overview.outputs()[overview_root / "docs/project-status.json"]
        )["as_of"]
        == json.loads(
            (overview_root / "docs/project-status.json").read_bytes()
        )["as_of"]
    )


def test_overview_check_detects_drift_without_writing(
    overview_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for path, content in overview.outputs().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    readme = overview_root / "README.md"
    readme.write_text(readme.read_text().replace("14/20", "13/20"))
    before = {
        path: path.read_bytes()
        for path in overview_root.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(sys, "argv", ["render_project_overview.py", "--check"])
    with pytest.raises(ValueError, match=r"stale: README\.md"):
        overview.main()
    assert before == {path: path.read_bytes() for path in before}


@pytest.mark.parametrize(
    "document",
    [
        "missing",
        overview.START + overview.START + overview.END,
        overview.END + overview.START,
    ],
)
def test_overview_rejects_ambiguous_progress_sections(document: str) -> None:
    with pytest.raises(ValueError, match="marker"):
        overview.replace_progress(document, "new")


def test_overview_cli_refreshes_an_explicit_date(
    overview_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["render_project_overview.py", "--as-of", "2026-12-04"]
    )
    overview.main()
    assert (
        json.loads((overview_root / "docs/project-status.json").read_bytes())[
            "as_of"
        ]
        == "2026-12-04"
    )
    monkeypatch.setattr(sys, "argv", ["render_project_overview.py", "--check"])
    overview.main()
