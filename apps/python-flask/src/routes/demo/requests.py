"""Request/logging demonstration routes."""

from datetime import datetime, timezone
from importlib import import_module

from src.config.telemetry import get_logger


flask = import_module("flask")
Blueprint = flask.Blueprint
jsonify = flask.jsonify
request = flask.request


logger = get_logger(__name__)
requests_bp = Blueprint("requests_demo", __name__, url_prefix="/api/requests")


@requests_bp.get("/log-levels")
def log_levels_demo():
    user_id = request.args.get("userId", "demo-user-123")

    logger.debug(
        "Debug level log - detailed diagnostic info",
        extra={
            "custom_dimensions": {
                "userId": user_id,
                "endpoint": "/api/requests/log-levels",
                "cacheStatus": "miss",
                "queryParams": request.args.to_dict(flat=True),
            }
        },
    )

    logger.info(
        "Info level log - normal operational message",
        extra={
            "custom_dimensions": {
                "userId": user_id,
                "action": "log-levels-demo",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    logger.warning(
        "Warn level log - potential issue detected",
        extra={
            "custom_dimensions": {
                "userId": user_id,
                "warning": "Demo warning: userId parameter not provided",
                "recommendation": "Include userId query parameter for tracking",
            }
        },
    )

    logger.error(
        "Error level log - application error",
        extra={
            "custom_dimensions": {
                "userId": user_id,
                "error": "Demo error: simulating error condition",
                "errorCode": "DEMO_ERROR",
                "severity": "high",
            }
        },
    )

    return jsonify(
        {
            "message": "Log level examples generated",
            "note": "Check Application Logs (az webapp log tail) and Application Insights (AppTraces table)",
            "logLevels": {
                "debug": "Verbose (0) - Detailed diagnostic info",
                "info": "Information (1) - Normal operational messages",
                "warn": "Warning (2) - Potential issues",
                "error": "Error (3) - Application errors",
            },
            "query": {
                "applicationLogs": "az webapp log tail --name <app-name> --resource-group <rg-name>",
                "appInsights": "AppTraces | where timestamp > ago(5m) | project timestamp, severityLevel, message, customDimensions",
            },
        }
    )
