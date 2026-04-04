import importlib
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify
request = flask_module.request

app = Flask(__name__)
PROCESS_START_TIME = time.time()
REQUEST_COUNT = 0
ENDPOINT_COUNTERS = {}
OUTBOUND_CALL_COUNTERS = {
    "without-pooling": {"successes": 0, "failures": 0},
    "with-pooling": {"successes": 0, "failures": 0},
}
_OUTBOUND_COUNTER_LOCK = threading.Lock()
SAFE_ENV_KEYS = [
    "PORT",
    "WEBSITES_PORT",
    "WEBSITE_SLOT_NAME",
    "WEBSITE_INSTANCE_ID",
    "WEBSITE_HOSTNAME",
    "SCM_DO_BUILD_DURING_DEPLOYMENT",
    "OUTBOUND_TIMEOUT_SECONDS",
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


def _parse_sockstat():
    data = _read_proc_file("/proc/net/sockstat")
    if "error" in data:
        return data
    parsed = {}
    for line in data["content"].splitlines():
        if ":" not in line:
            continue
        section, payload = line.split(":", 1)
        parts = payload.strip().split()
        section_values = {}
        idx = 0
        while idx + 1 < len(parts):
            section_values[parts[idx]] = parts[idx + 1]
            idx += 2
        parsed[section.strip()] = section_values
    return {
        "sockets": parsed.get("sockets", {}),
        "tcp": parsed.get("TCP", {}),
        "udp": parsed.get("UDP", {}),
    }


def _tcp_connection_count():
    data = _read_proc_file("/proc/net/tcp")
    if "error" in data:
        return data
    return len(data["content"].splitlines())


def _local_port_range():
    data = _read_proc_file("/proc/sys/net/ipv4/ip_local_port_range")
    if "error" in data:
        return data
    parts = data["content"].split()
    if len(parts) >= 2:
        return {"start": parts[0], "end": parts[1]}
    return {"error": "unexpected format"}


@app.before_request
def _count_request():
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    endpoint_key = request.endpoint or "<unknown>"
    ENDPOINT_COUNTERS[endpoint_key] = ENDPOINT_COUNTERS.get(endpoint_key, 0) + 1


@app.get("/")
def index():
    return "OK", 200


@app.get("/health")
def health():
    return jsonify({"status": "healthy", "lab": "snat-exhaustion"}), 200


def _int_arg(name: str, default: int) -> int:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return max(parsed, 1)


@app.get("/outbound")
def outbound_without_pooling():
    target_url = request.args.get("target", "https://httpbin.org/get")
    calls = _int_arg("calls", 40)
    timeout_seconds = float(os.getenv("OUTBOUND_TIMEOUT_SECONDS", "3"))

    successes = 0
    failures = 0
    errors = []
    started = time.time()

    for _ in range(calls):
        req = urllib.request.Request(
            target_url,
            method="GET",
            headers={"Connection": "close", "User-Agent": "snat-lab-no-pool"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                if 200 <= resp.status < 500:
                    successes += 1
                else:
                    failures += 1
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failures += 1
            if len(errors) < 5:
                errors.append(str(exc))

    elapsed_ms = int((time.time() - started) * 1000)
    with _OUTBOUND_COUNTER_LOCK:
        OUTBOUND_CALL_COUNTERS["without-pooling"]["successes"] += successes
        OUTBOUND_CALL_COUNTERS["without-pooling"]["failures"] += failures
    return (
        jsonify(
            {
                "mode": "without-pooling",
                "target": target_url,
                "calls": calls,
                "successes": successes,
                "failures": failures,
                "elapsedMs": elapsed_ms,
                "sampleErrors": errors,
            }
        ),
        200,
    )


@app.get("/outbound-fixed")
def outbound_with_pooling():
    import requests as requests_lib
    from requests.adapters import HTTPAdapter

    target_url = request.args.get("target", "https://httpbin.org/get")
    calls = _int_arg("calls", 40)
    timeout_seconds = float(os.getenv("OUTBOUND_TIMEOUT_SECONDS", "3"))

    successes = 0
    failures = 0
    errors = []
    started = time.time()

    with requests_lib.Session() as session:
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        for _ in range(calls):
            try:
                response = session.get(
                    target_url,
                    timeout=timeout_seconds,
                    headers={
                        "Connection": "keep-alive",
                        "User-Agent": "snat-lab-pooled",
                    },
                )
                if 200 <= response.status_code < 500:
                    successes += 1
                else:
                    failures += 1
            except requests_lib.RequestException as exc:
                failures += 1
                if len(errors) < 5:
                    errors.append(str(exc))

    elapsed_ms = int((time.time() - started) * 1000)
    with _OUTBOUND_COUNTER_LOCK:
        OUTBOUND_CALL_COUNTERS["with-pooling"]["successes"] += successes
        OUTBOUND_CALL_COUNTERS["with-pooling"]["failures"] += failures
    return (
        jsonify(
            {
                "mode": "with-pooling",
                "target": target_url,
                "calls": calls,
                "successes": successes,
                "failures": failures,
                "elapsedMs": elapsed_ms,
                "sampleErrors": errors,
            }
        ),
        200,
    )


@app.get("/diag/stats")
def diag_stats():
    return (
        jsonify(
            {
                "pid": os.getpid(),
                "process_start_time": _iso_utc(PROCESS_START_TIME),
                "uptime_seconds": round(time.time() - PROCESS_START_TIME, 3),
                "request_count": REQUEST_COUNT,
                "outbound_call_counters": OUTBOUND_CALL_COUNTERS,
                "endpoint_counters": ENDPOINT_COUNTERS,
            }
        ),
        200,
    )


@app.get("/diag/env")
def diag_env():
    return jsonify(_safe_env()), 200


@app.get("/diag/net")
def diag_net():
    return (
        jsonify(
            {
                "sockstat": _parse_sockstat(),
                "connection_count": _tcp_connection_count(),
                "ip_local_port_range": _local_port_range(),
            }
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
