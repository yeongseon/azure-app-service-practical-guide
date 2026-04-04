"""Exception demonstration routes."""

from importlib import import_module

from src.config.telemetry import get_logger


flask = import_module("flask")
Blueprint = flask.Blueprint
jsonify = flask.jsonify
request = flask.request


logger = get_logger(__name__)
exceptions_bp = Blueprint("exceptions_demo", __name__, url_prefix="/api/exceptions")


class DemoError(Exception):
    """Controlled error class to test error handling."""

    def __init__(self, message: str, status: int, code: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


@exceptions_bp.post("/test-error")
def test_error():
    payload = request.get_json(silent=True) or {}
    error_type = payload.get("errorType", "generic")

    logger.warning("Triggering test error", extra={"custom_dimensions": {"errorType": error_type}})

    errors = {
        "validation": {"message": "Validation failed: Invalid input data", "status": 400, "code": "VALIDATION_ERROR"},
        "notfound": {"message": "Resource not found", "status": 404, "code": "NOT_FOUND"},
        "database": {"message": "Database connection failed", "status": 500, "code": "DB_CONNECTION_ERROR"},
        "timeout": {"message": "Request timeout", "status": 504, "code": "TIMEOUT"},
        "generic": {"message": "Generic error occurred", "status": 500, "code": "GENERIC_ERROR"},
    }

    error = errors.get(error_type, errors["generic"])
    raise DemoError(message=error["message"], status=error["status"], code=error["code"])


@exceptions_bp.get("/throw-exception")
def throw_exception():
    logger.error("About to throw unhandled exception")
    raise RuntimeError("Unhandled exception - this will be caught by Flask error handler")


@exceptions_bp.get("/unhandled-rejection")
def unhandled_rejection_demo():
    logger.error("Simulating rejected async operation")
    return (
        jsonify({"message": "Python does not expose JS-style unhandled rejections in Flask routes"}),
        500,
    )
