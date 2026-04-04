"""Health endpoint."""

from datetime import datetime, timezone
from importlib import import_module

flask = import_module("flask")
Blueprint = flask.Blueprint
jsonify = flask.jsonify


health_bp = Blueprint("health", __name__, url_prefix="/health")


@health_bp.get("")
@health_bp.get("/")
def health_check():
    return (
        jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
        200,
    )
