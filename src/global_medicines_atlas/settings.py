"""Strict Pydantic v2 runtime configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AtlasSettings(BaseSettings):
    """Environment-backed settings with unknown keys rejected."""

    model_config = SettingsConfigDict(
        env_prefix="GMA_",
        env_file=".env",
        extra="forbid",
        frozen=True,
    )

    data_dir: Path = Path("data")
    log_level: str = Field(
        default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR)$"
    )
    enable_lance_index: bool = False
