"""External dependency demonstration routes."""

from importlib import import_module
from time import perf_counter

import requests

from src.config.telemetry import get_logger


flask = import_module("flask")
Blueprint = flask.Blueprint
current_app = flask.current_app
g = flask.g
jsonify = flask.jsonify


logger = get_logger(__name__)
dependencies_bp = Blueprint("dependencies_demo", __name__, url_prefix="/api/dependencies")


@dependencies_bp.get("/external")
def external_dependency_demo():
    api_url = "https://jsonplaceholder.typicode.com/posts/1"
    logger.debug("Calling external API", extra={"custom_dimensions": {"url": api_url}})

    start = perf_counter()
    timeout = current_app.config["APP_SETTINGS"].external_api_timeout_seconds

    try:
        response = requests.get(api_url, timeout=timeout)
        duration_ms = round((perf_counter() - start) * 1000, 2)
        response.raise_for_status()
        data = response.json()

        logger.info(
            "External API call successful",
            extra={
                "custom_dimensions": {
                    "url": api_url,
                    "statusCode": response.status_code,
                    "duration": duration_ms,
                }
            },
        )

        return jsonify(
            {
                "message": "External dependency call successful",
                "data": data,
                "metadata": {
                    "duration": duration_ms,
                    "statusCode": response.status_code,
                    "correlationId": getattr(g, "correlation_id", None),
                },
            }
        )
    except requests.RequestException as exc:
        duration_ms = round((perf_counter() - start) * 1000, 2)
        logger.error(
            "External API call failed",
            exc_info=True,
            extra={
                "custom_dimensions": {
                    "url": api_url,
                    "error": str(exc),
                    "duration": duration_ms,
                }
            },
        )

        return (
            jsonify(
                {
                    "error": "Service Unavailable",
                    "message": "Failed to call external API",
                    "correlationId": getattr(g, "correlation_id", None),
                }
            ),
            503,
        )
