"""Core package behavior when the optional semantic dependency is absent."""

from __future__ import annotations

import builtins
import tomllib
from pathlib import Path

from global_medicines_atlas.semantic_retrieval import (
    optional_semantic_retriever,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_lancedb_is_declared_only_as_an_optional_runtime_extra() -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    runtime = project["project"]["dependencies"]
    semantic = project["project"]["optional-dependencies"]["semantic"]

    assert not any(item.startswith("lancedb") for item in runtime)
    assert semantic == ["lancedb>=0.27"]


def test_core_import_and_fallback_do_not_import_lancedb(
    monkeypatch,
    tmp_path: Path,
) -> None:
    original_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "lancedb" or name.startswith("lancedb."):
            raise AssertionError("core path imported optional LanceDB")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    retriever = optional_semantic_retriever(tmp_path)

    assert not retriever.available
    assert retriever.search([0.1], mapping_level="ingredient") == ()
