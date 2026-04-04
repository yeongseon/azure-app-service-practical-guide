import importlib
import os
import time
from datetime import datetime, timezone

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify
request = flask_module.request

app = Flask(__name__)
PROCESS_START_TIME = time.time()
PROCESS_START_UTC = datetime.now(timezone.utc).isoformat()
REQUEST_COUNT = 0
ENDPOINT_COUNTERS = {}


@app.before_request
def track_request_count():
    global REQUEST_COUNT
    REQUEST_COUNT += 1


@app.after_request
def track_endpoint_counter(response):
    endpoint = request.endpoint or "<unknown>"
    ENDPOINT_COUNTERS[endpoint] = ENDPOINT_COUNTERS.get(endpoint, 0) + 1
    return response


@app.get("/")
def index():
    return jsonify({"message": "app code is healthy"}), 200


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.get("/diag/stats")
def diag_stats():
    uptime_seconds = time.time() - PROCESS_START_TIME
    return (
        jsonify(
            {
                "pid": os.getpid(),
                "process_start_time": PROCESS_START_UTC,
                "uptime_seconds": round(uptime_seconds, 3),
                "request_count": REQUEST_COUNT,
                "endpoint_counters": ENDPOINT_COUNTERS,
            }
        ),
        200,
    )


@app.get("/diag/env")
def diag_env():
    safe_keys = [
        "PORT",
        "WEBSITES_PORT",
        "WEBSITE_SLOT_NAME",
        "WEBSITE_INSTANCE_ID",
        "WEBSITE_HOSTNAME",
        "SCM_DO_BUILD_DURING_DEPLOYMENT",
        "STARTUP_COMMAND",
        "APP_STARTUP_COMMAND",
    ]
    return jsonify({key: os.environ.get(key, "<unset>") for key in safe_keys}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
