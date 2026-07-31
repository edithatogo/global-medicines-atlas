"""Task-oriented stable-v1 documentation contract."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

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
        "uv sync --python 3.14.6 --locked --no-dev",
        "--extra semantic",
        "uv run global-medicines-atlas --help",
        "uv run global-medicines-atlas comparison --help",
        "uv run pytest tests/test_product_api.py tests/test_concept_api.py",
        "uv run pytest tests/test_atlas_e2e.py tests/test_atlas_discovery_e2e.py",
        "uv run python scripts/test_goblin.py quick",
        "uv run ruff check .",
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
        "publication, licence selection, external identifiers, credentials",
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
