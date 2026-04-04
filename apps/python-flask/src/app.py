"""Main Flask application entrypoint."""

from __future__ import annotations

import platform
from importlib import import_module

from src.config import configure_logging, get_correlation_id, get_logger, get_settings
from src.middleware import register_correlation_middleware
from src.routes import register_blueprints


flask = import_module("flask")
Flask = flask.Flask
jsonify = flask.jsonify
request = flask.request


HOMEPAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Azure App Service Python Guide</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #f5f5f5;
            color: #333;
        }
        .container {
            background: white;
            border-radius: 8px;
            padding: 40px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 { color: #0078d4; margin-top: 0; }
        h2 {
            color: #333;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 8px;
            margin-top: 32px;
        }
        .endpoint {
            background: #f8f9fa;
            border-left: 4px solid #0078d4;
            padding: 16px;
            margin: 12px 0;
            border-radius: 4px;
        }
        .endpoint-method {
            display: inline-block;
            background: #0078d4;
            color: white;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 12px;
        }
        .endpoint-path { font-family: monospace; color: #333; font-weight: 500; }
        .endpoint-desc { color: #666; margin-top: 8px; font-size: 14px; }
        .badge {
            display: inline-block;
            background: #107c10;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Azure App Service Python Guide <span class="badge">Running</span></h1>
        <p>Sample Flask application for the Azure App Service Python Guide.</p>

        <h2>Endpoints</h2>

        <div class="endpoint">
            <span class="endpoint-method">GET</span>
            <span class="endpoint-path">/health</span>
            <div class="endpoint-desc">Health check</div>
        </div>

        <div class="endpoint">
            <span class="endpoint-method">GET</span>
            <span class="endpoint-path">/info</span>
            <div class="endpoint-desc">Application info</div>
        </div>

        <div class="endpoint">
            <span class="endpoint-method">GET</span>
            <span class="endpoint-path">/api/requests/log-levels</span>
            <div class="endpoint-desc">Generate logs at all severity levels</div>
        </div>

        <div class="endpoint">
            <span class="endpoint-method">GET</span>
            <span class="endpoint-path">/api/dependencies/external</span>
            <div class="endpoint-desc">External API call demo</div>
        </div>

        <div class="endpoint">
            <span class="endpoint-method">POST</span>
            <span class="endpoint-path">/api/exceptions/test-error</span>
            <div class="endpoint-desc">Error handling demo</div>
        </div>
    </div>
</body>
</html>
"""


def create_app() -> Flask:
    settings = get_settings()
    app = Flask(__name__)
    app.config["APP_SETTINGS"] = settings

    logger = configure_logging(settings)
    register_correlation_middleware(app)
    register_blueprints(app)

    @app.get("/")
    def home():
        logger.info("Root endpoint accessed")
        return HOMEPAGE_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.errorhandler(404)
    def not_found(_error):
        logger.warning(
            "Route not found",
            extra={
                "custom_dimensions": {
                    "method": request.method,
                    "url": request.path,
                }
            },
        )
        return (
            jsonify(
                {
                    "error": "Not Found",
                    "message": f"Cannot {request.method} {request.path}",
                    "correlationId": get_correlation_id(),
                }
            ),
            404,
        )

    @app.errorhandler(Exception)
    def handle_exception(error: Exception):
        status = getattr(error, "status", 500)

        logger.error(
            "Unhandled error",
            exc_info=True,
            extra={
                "custom_dimensions": {
                    "error": str(error),
                    "url": request.path,
                    "method": request.method,
                }
            },
        )

        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An error occurred" if settings.environment == "production" else str(error),
                    "correlationId": get_correlation_id(),
                }
            ),
            status,
        )

    logger.info(
        "Server configured",
        extra={
                "custom_dimensions": {
                    "port": settings.port,
                    "environment": settings.environment,
                    "pythonVersion": platform.python_version(),
                    "telemetryMode": settings.telemetry_mode,
                }
            },
        )
    return app


app = create_app()


if __name__ == "__main__":
    runtime_settings = get_settings()
    runtime_logger = get_logger(__name__)
    runtime_logger.info(
        "Starting Flask development server",
        extra={
            "custom_dimensions": {
                "port": runtime_settings.port,
                "environment": runtime_settings.environment,
                "telemetryMode": runtime_settings.telemetry_mode,
            }
        },
    )
    app.run(host="0.0.0.0", port=runtime_settings.port)
