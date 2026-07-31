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


def test_structured_logging_uses_operational_fields_and_redacts_secrets() -> (
    None
):
    stream = StringIO()
    configure_logging(stream=stream)

    get_logger(
        "acquisition",
        run_id="run-1",
        source_id="nzulm",
        adapter="nzulm-fhir",
        attempt="1",
        receipt_digest="sha256:abc",
        outcome="passed",
        request_url="https://example.test/file?token=secret&query=ok",
        authorization="Bearer secret",
    ).info("downloaded")

    payload = cast("dict[str, object]", json.loads(stream.getvalue()))
    assert payload["run_id"] == "run-1"
    assert payload["adapter"] == "nzulm-fhir"
    assert payload["attempt"] == "1"
    assert payload["receipt_digest"] == "sha256:abc"
    assert payload["outcome"] == "passed"
    assert payload["request_url"] == "https://example.test/file"
    assert payload["authorization"] == "[REDACTED]"
    assert "secret" not in stream.getvalue()
