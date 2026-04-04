"""Info endpoint."""

import platform
from importlib import import_module

flask = import_module("flask")
Blueprint = flask.Blueprint
current_app = flask.current_app
jsonify = flask.jsonify


info_bp = Blueprint("info", __name__, url_prefix="/info")


@info_bp.get("")
@info_bp.get("/")
def app_info():
    settings = current_app.config["APP_SETTINGS"]
    return jsonify(
        {
            "name": settings.app_name,
            "version": settings.app_version,
            "python": platform.python_version(),
            "environment": settings.environment,
            "telemetryMode": settings.telemetry_mode,
        }
    )
