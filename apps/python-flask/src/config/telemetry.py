"""Telemetry and structured logging configuration."""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import datetime, timezone
from importlib import import_module
import json
import logging
import sys
import traceback

from .settings import Settings

try:
    configure_azure_monitor = import_module("azure.monitor.opentelemetry").configure_azure_monitor
except Exception:  # pragma: no cover - optional dependency behavior
    configure_azure_monitor = None


_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_configured = False


def set_correlation_id(correlation_id: str) -> Token:
    return _correlation_id_ctx.set(correlation_id)


def reset_correlation_id(token: Token) -> None:
    _correlation_id_ctx.reset(token)


def get_correlation_id() -> str | None:
    return _correlation_id_ctx.get()


class CorrelationIdFilter(logging.Filter):
    """Inject correlation ID into each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


class JsonFormatter(logging.Formatter):
    """Emit newline-delimited JSON logs for Azure ingestion."""

    def __init__(self, service_name: str, environment: str) -> None:
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "service": self.service_name,
            "environment": self.environment,
        }

        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            payload["correlationId"] = correlation_id

        custom_dimensions = getattr(record, "custom_dimensions", None)
        if isinstance(custom_dimensions, dict):
            payload.update(custom_dimensions)

        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Exception",
                "message": str(record.exc_info[1]),
                "stack": "".join(traceback.format_exception(*record.exc_info)),
            }

        return json.dumps(payload, default=str)


def get_logger(name: str = "azure-appservice-reference") -> logging.Logger:
    return logging.getLogger(name)


def configure_logging(settings: Settings) -> logging.Logger:
    """Configure console JSON logging and optional Azure Monitor telemetry."""
    global _configured
    if _configured:
        return get_logger()

    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JsonFormatter(service_name=settings.app_name, environment=settings.environment))
    stream_handler.addFilter(CorrelationIdFilter())
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(settings.log_level)

    logging.getLogger("werkzeug").setLevel(settings.log_level)

    logger = get_logger()

    if settings.telemetry_mode == "advanced":
        if settings.applicationinsights_connection_string and configure_azure_monitor:
            configure_azure_monitor(connection_string=settings.applicationinsights_connection_string)
            logger.info(
                "Advanced telemetry initialized",
                extra={
                    "custom_dimensions": {
                        "telemetryMode": settings.telemetry_mode,
                        "appInsightsEnabled": True,
                        "logLevel": settings.log_level,
                    }
                },
            )
        else:
            logger.warning(
                "Advanced telemetry mode requested but Application Insights is not configured",
                extra={
                    "custom_dimensions": {
                        "telemetryMode": settings.telemetry_mode,
                        "appInsightsEnabled": False,
                    }
                },
            )
    else:
        logger.info(
            "Basic telemetry initialized",
            extra={
                "custom_dimensions": {
                    "telemetryMode": settings.telemetry_mode,
                    "logLevel": settings.log_level,
                }
            },
        )

    _configured = True
    return logger
