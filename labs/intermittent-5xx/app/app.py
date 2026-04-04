import os
import random
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request  # pyright: ignore[reportMissingImports]

app = Flask(__name__)
PROCESS_START_TIME = time.time()
REQUEST_COUNT = 0
ENDPOINT_COUNTERS = {}
ACTIVE_SLOW_REQUESTS = 0
_SLOW_LOCK = threading.Lock()
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


def _read_proc_file(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return {"content": handle.read()}
    except OSError as exc:
        return {"error": str(exc)}


def _safe_env():
    values = {key: os.environ.get(key, "<unset>") for key in SAFE_ENV_KEYS}
    custom_lab_keys = sorted(key for key in os.environ if key.startswith("LAB_"))
    for key in custom_lab_keys:
        values[key] = os.environ.get(key, "<unset>")
    return values


@app.before_request
def _count_request():
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    endpoint_key = request.endpoint or "<unknown>"
    ENDPOINT_COUNTERS[endpoint_key] = ENDPOINT_COUNTERS.get(endpoint_key, 0) + 1


@app.get("/")
def root():
    return "OK", 200


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.get("/slow")
def slow():
    global ACTIVE_SLOW_REQUESTS
    delay_seconds = random.randint(5, 15)
    with _SLOW_LOCK:
        ACTIVE_SLOW_REQUESTS += 1
    try:
        time.sleep(delay_seconds)
        return jsonify({"endpoint": "slow", "delaySeconds": delay_seconds}), 200
    finally:
        with _SLOW_LOCK:
            ACTIVE_SLOW_REQUESTS -= 1


@app.get("/fast")
def fast():
    return jsonify({"endpoint": "fast", "message": "quick response"}), 200


@app.get("/diag/stats")
def diag_stats():
    return (
        jsonify(
            {
                "pid": os.getpid(),
                "process_start_time": _iso_utc(PROCESS_START_TIME),
                "uptime_seconds": round(time.time() - PROCESS_START_TIME, 3),
                "request_count": REQUEST_COUNT,
                "active_slow_requests": ACTIVE_SLOW_REQUESTS,
                "endpoint_counters": ENDPOINT_COUNTERS,
            }
        ),
        200,
    )


@app.get("/diag/env")
def diag_env():
    return jsonify(_safe_env()), 200


@app.get("/diag/proc")
def diag_proc():
    cpu_pressure = _read_proc_file("/proc/pressure/cpu")
    cpu_pressure_payload = (
        cpu_pressure.get("content", "").strip()
        if "content" in cpu_pressure
        else cpu_pressure
    )
    return jsonify({"cpu_pressure": cpu_pressure_payload}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
