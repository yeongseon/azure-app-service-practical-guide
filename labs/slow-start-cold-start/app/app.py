import importlib
import os
import time
from datetime import datetime, timezone

INITIALIZATION_STARTED_AT = time.time()

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify
request = flask_module.request

time.sleep(30)

INITIALIZATION_COMPLETED_AT = time.time()
STARTUP_DURATION_SECONDS = INITIALIZATION_COMPLETED_AT - INITIALIZATION_STARTED_AT
REQUEST_COUNT = 0

app = Flask(__name__)
ENDPOINT_COUNTERS = {}


def iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def increment_request_count() -> int:
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    return REQUEST_COUNT


@app.after_request
def track_endpoint_counter(response):
    endpoint = request.endpoint or "<unknown>"
    ENDPOINT_COUNTERS[endpoint] = ENDPOINT_COUNTERS.get(endpoint, 0) + 1
    return response


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


@app.get("/diag/stats")
def diag_stats():
    request_count = increment_request_count()
    current_time = time.time()
    uptime_seconds = current_time - INITIALIZATION_COMPLETED_AT
    return (
        jsonify(
            {
                "pid": os.getpid(),
                "process_start_time": iso_utc(INITIALIZATION_COMPLETED_AT),
                "initialization_started_at": iso_utc(INITIALIZATION_STARTED_AT),
                "initialization_completed_at": iso_utc(INITIALIZATION_COMPLETED_AT),
                "startup_duration_seconds": round(STARTUP_DURATION_SECONDS, 3),
                "uptime_seconds": round(uptime_seconds, 3),
                "request_count": request_count,
                "endpoint_counters": ENDPOINT_COUNTERS,
            }
        ),
        200,
    )


@app.get("/diag/env")
def diag_env():
    increment_request_count()
    safe_keys = ["PORT", "WEBSITES_PORT", "WEBSITE_SLOT_NAME", "WEBSITE_INSTANCE_ID"]
    return jsonify({key: os.environ.get(key, "<unset>") for key in safe_keys}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
