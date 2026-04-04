import importlib
import time
from datetime import datetime, timezone

INITIALIZATION_STARTED_AT = time.time()

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify

time.sleep(30)

INITIALIZATION_COMPLETED_AT = time.time()
STARTUP_DURATION_SECONDS = INITIALIZATION_COMPLETED_AT - INITIALIZATION_STARTED_AT
REQUEST_COUNT = 0

app = Flask(__name__)


def iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def increment_request_count() -> int:
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    return REQUEST_COUNT


@app.get("/")
def index():
    request_count = increment_request_count()
    return (
        jsonify(
            {
                "status": "OK",
                "startup_time": iso_utc(INITIALIZATION_COMPLETED_AT),
                "startup_duration": round(STARTUP_DURATION_SECONDS, 3),
                "request_count": request_count,
            }
        ),
        200,
    )


@app.get("/health")
def health():
    increment_request_count()
    return jsonify({"status": "healthy"}), 200


@app.get("/fast")
def fast():
    request_count = increment_request_count()
    return jsonify({"status": "fast", "request_count": request_count}), 200


@app.get("/timing")
def timing():
    request_count = increment_request_count()
    current_time = time.time()
    uptime_seconds = current_time - INITIALIZATION_COMPLETED_AT

    return (
        jsonify(
            {
                "startup_duration": round(STARTUP_DURATION_SECONDS, 3),
                "current_time": iso_utc(current_time),
                "uptime_seconds": round(uptime_seconds, 3),
                "request_count": request_count,
            }
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
