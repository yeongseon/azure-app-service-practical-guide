"""Request correlation middleware for Flask."""

from __future__ import annotations

from importlib import import_module
from time import perf_counter
from uuid import uuid4

from src.config.telemetry import get_logger, reset_correlation_id, set_correlation_id


flask = import_module("flask")
Flask = flask.Flask
g = flask.g
request = flask.request


def register_correlation_middleware(app: Flask) -> None:
    """Attach correlation ID and request logging hooks to app."""
    logger = get_logger(__name__)

    @app.before_request
    def add_correlation_id() -> None:
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid4())
        )
        g.correlation_id = correlation_id
        g._correlation_token = set_correlation_id(correlation_id)
        g.request_start = perf_counter()

    @app.after_request
    def append_correlation_header(response):
        correlation_id = getattr(g, "correlation_id", None)
        if correlation_id:
            response.headers["X-Correlation-ID"] = correlation_id

        start = getattr(g, "request_start", None)
        if start is not None:
            duration_ms = round((perf_counter() - start) * 1000, 2)
            logger.info(
                "HTTP Request",
                extra={
                    "custom_dimensions": {
                        "method": request.method,
                        "url": request.path,
                        "statusCode": response.status_code,
                        "duration": duration_ms,
                        "userAgent": request.headers.get("User-Agent"),
                    }
                },
            )
        return response

    @app.teardown_request
    def clear_correlation_context(_error):
        token = getattr(g, "_correlation_token", None)
        if token is not None:
            reset_correlation_id(token)
