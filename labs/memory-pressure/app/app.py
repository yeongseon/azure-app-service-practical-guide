import importlib
import os
import time
from datetime import datetime, timezone

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify
request = flask_module.request

app = Flask(__name__)

LEAK_BUCKET = []
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


def _read_proc_file(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return {"content": handle.read()}
    except OSError as exc:
        return {"error": str(exc)}


def _parse_meminfo():
    data = _read_proc_file("/proc/meminfo")
    if "error" in data:
        return data
    wanted = {
        "MemTotal",
        "MemFree",
        "MemAvailable",
        "Cached",
        "SwapTotal",
        "SwapFree",
        "SwapCached",
    }
    parsed = {}
    for line in data["content"].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key in wanted:
            parsed[key] = value.strip()
    return parsed


def _parse_vmstat():
    data = _read_proc_file("/proc/vmstat")
    if "error" in data:
        return data
    wanted = {
        "pgscan_kswapd",
        "pgscan_direct",
        "pgsteal_kswapd",
        "pswpin",
        "pswpout",
        "allocstall_normal",
        "allocstall_movable",
    }
    parsed = {}
    for line in data["content"].splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in wanted:
            parsed[parts[0]] = parts[1]
    return parsed


def _parse_pressure_memory():
    data = _read_proc_file("/proc/pressure/memory")
    if "error" in data:
        return data
    parsed = {}
    for line in data["content"].splitlines():
        if line.startswith("some "):
            parsed["some"] = line
        elif line.startswith("full "):
            parsed["full"] = line
    return parsed


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
def index():
    return "OK", 200


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.get("/leak")
def leak():
    block = [f"leak-{i:08d}" for i in range(250_000)]
    LEAK_BUCKET.append(block)
    return jsonify({"status": "allocated", "blocks": len(LEAK_BUCKET)}), 200


@app.get("/heavy")
def heavy():
    numbers = [((i * 97) % 10_000_019) for i in range(500_000)]
    numbers.sort(reverse=True)
    sample = numbers[0:3]
    return jsonify(
        {"status": "computed", "max_values": sample, "count": len(numbers)}
    ), 200


@app.get("/diag/stats")
def diag_stats():
    return (
        jsonify(
            {
                "pid": os.getpid(),
                "process_start_time": _iso_utc(PROCESS_START_TIME),
                "uptime_seconds": round(time.time() - PROCESS_START_TIME, 3),
                "request_count": REQUEST_COUNT,
                "leak_block_count": len(LEAK_BUCKET),
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
    loadavg = _read_proc_file("/proc/loadavg")
    loadavg_payload = (
        loadavg.get("content", "").strip() if "content" in loadavg else loadavg
    )
    return (
        jsonify(
            {
                "meminfo": _parse_meminfo(),
                "vmstat": _parse_vmstat(),
                "pressure_memory": _parse_pressure_memory(),
                "loadavg": loadavg_payload,
            }
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
