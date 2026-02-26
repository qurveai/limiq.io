import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

_LOGGING_CONFIGURED = False


class JsonLogFormatter(logging.Formatter):
    _extra_fields = (
        "event_name",
        "workspace_id",
        "agent_id",
        "jti",
        "decision",
        "reason_code",
        "audit_event_id",
        "status",
        "latency_ms",
        "checked_count",
        "broken_at_event_id",
        "action_type",
        "configured_level",
        "path",
        "method",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in self._extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    root_logger = logging.getLogger()
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        logging.getLogger("kya.logging").warning(
            "invalid_log_level_fallback",
            extra={
                "event_name": "invalid_log_level_fallback",
                "configured_level": settings.log_level,
            },
        )
        level = logging.INFO

    root_logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger.handlers = [handler]

    _LOGGING_CONFIGURED = True
