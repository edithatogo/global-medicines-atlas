"""Pydantic v2 settings contract tests."""

from __future__ import annotations

from global_medicines_atlas.settings import AtlasSettings


def test_settings_use_namespaced_environment(monkeypatch) -> None:
    monkeypatch.setenv("GMA_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("GMA_ENABLE_LANCE_INDEX", "true")

    settings = AtlasSettings(_env_file=None)

    assert settings.log_level == "DEBUG"
    assert settings.enable_lance_index is True
