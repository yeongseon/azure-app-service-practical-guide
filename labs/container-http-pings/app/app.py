import importlib
import os
import time
from datetime import datetime, timezone

flask = importlib.import_module("flask")
Flask = flask.Flask
jsonify = flask.jsonify
request = flask.request

app = Flask(__name__)
PROCESS_START_TIME = time.time()
REQUEST_COUNT = 0
ENDPOINT_COUNTERS = {}
SAFE_ENV_KEYS = [
    "PORT",
    "WEBSITES_PORT",
    "WEBSITE_SLOT_NAME",
    "WEBSITE_INSTANCE_ID",
    "WEBSITE_HOSTNAME",
    "SCM_DO_BUILD_DURING_DEPLOYMENT",
]


def _iso_utc(timestamp):
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _safe_env():
    values = {key: os.environ.get(key, "<unset>") for key in SAFE_ENV_KEYS}
    custom_lab_keys = sorted(key for key in os.environ if key.startswith("LAB_"))
    for key in custom_lab_keys:
        values[key] = os.environ.get(key, "<unset>")
    values["actual_bind_host"] = "0.0.0.0"
    values["actual_bind_port"] = "8000"
    values["effective_port_hint"] = os.environ.get(
        "WEBSITES_PORT", os.environ.get("PORT", "8000")
    )
    return values


@app.before_request
def _count_request() -> None:
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    endpoint_key = request.endpoint or "<unknown>"
    ENDPOINT_COUNTERS[endpoint_key] = ENDPOINT_COUNTERS.get(endpoint_key, 0) + 1


@app.route("/")
def index() -> str:
    return "OK"


@app.route("/health")
def health() -> tuple:
    return jsonify({"status": "healthy"}), 200


@app.get("/diag/stats")
def diag_stats() -> tuple:
    return (
        jsonify(
            {
                "pid": os.getpid(),
                "process_start_time": _iso_utc(PROCESS_START_TIME),
                "uptime_seconds": round(time.time() - PROCESS_START_TIME, 3),
                "request_count": REQUEST_COUNT,
                "endpoint_counters": ENDPOINT_COUNTERS,
            }
        ),
        200,
    )


@app.get("/diag/env")
def diag_env() -> tuple:
    return jsonify(_safe_env()), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
