"""Logging contract tests."""

import json
import logging
from io import StringIO
from typing import cast

import pytest

from global_medicines_atlas.logging import configure_logging, get_logger


def test_structured_logging_emits_context_without_propagating() -> None:
    stream = StringIO()
    package_logger = configure_logging(stream=stream)

    get_logger("adapter", jurisdiction="NZL", source_id="nzulm").info("loaded")

    payload = cast("dict[str, object]", json.loads(stream.getvalue()))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "global_medicines_atlas.adapter"
    assert payload["message"] == "loaded"
    assert payload["jurisdiction"] == "NZL"
    assert payload["source_id"] == "nzulm"
    assert package_logger.propagate is False


def test_logging_configuration_is_idempotent() -> None:
    first = configure_logging(stream=StringIO())
    second = configure_logging(stream=StringIO(), level=logging.DEBUG)

    assert first is second
    assert len(second.handlers) == 1
    assert second.level == logging.DEBUG


def test_unknown_context_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported logging context"):
        get_logger("adapter", medicine="example")
