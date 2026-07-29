"""Package-scoped structured logging without root-logger side effects."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import IO, Final, TypedDict
from urllib.parse import urlsplit, urlunsplit

LOGGER_NAME: Final = "global_medicines_atlas"
_CONTEXT_FIELDS: Final = (
    "adapter",
    "attempt",
    "authorization",
    "component",
    "jurisdiction",
    "outcome",
    "receipt_digest",
    "request_url",
    "run_id",
    "source_id",
    "track_id",
)
_SECRET_FIELDS: Final = frozenset({
    "authorization",
    "cookie",
    "password",
    "token",
})
_URL_FIELDS: Final = frozenset({"request_url"})


class LogContext(TypedDict, total=False):
    """Stable contextual fields accepted by the medicines logging contract."""

    component: str
    adapter: str
    attempt: str
    authorization: str
    jurisdiction: str
    outcome: str
    receipt_digest: str
    request_url: str
    run_id: str
    source_id: str
    track_id: str


def _safe_context(field: str, value: str) -> str:
    if field in _SECRET_FIELDS:
        return "[REDACTED]"
    if field in _URL_FIELDS:
        parsed = urlsplit(value)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return value


class JsonFormatter(logging.Formatter):
    """Render stable machine-readable JSON log records."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if isinstance(value, str) and value:
                payload[field] = _safe_context(field, value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_logging(
    *,
    level: int | str = logging.INFO,
    stream: IO[str] | None = None,
    json_output: bool = True,
) -> logging.Logger:
    """Configure and return the package logger idempotently."""

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    handler = logging.StreamHandler(stream or sys.stderr)
    formatter: logging.Formatter = (
        JsonFormatter()
        if json_output
        else logging.Formatter("%(levelname)s %(name)s %(message)s")
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def get_logger(
    name: str, **context: str
) -> logging.LoggerAdapter[logging.Logger]:
    """Return a package-child logger carrying validated structured context."""

    unknown = set(context).difference(_CONTEXT_FIELDS)
    if unknown:
        fields = ", ".join(sorted(unknown))
        raise ValueError(f"Unsupported logging context fields: {fields}")
    logger = logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logging.LoggerAdapter(logger, context, merge_extra=True)
