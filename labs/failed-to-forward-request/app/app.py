import importlib
import os
import re
import socket
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


def read_cmdline() -> dict:
    try:
        with open("/proc/self/cmdline", "rb") as handle:
            raw_parts = handle.read().split(b"\x00")
        argv = [part.decode("utf-8", errors="replace") for part in raw_parts if part]
        return {"argv": argv}
    except Exception as exc:
        return {"error": str(exc)}


def bind_from_cmdline(argv: list[str]) -> str:
    for index, token in enumerate(argv):
        if token in ("-b", "--bind") and index + 1 < len(argv):
            return argv[index + 1]
        if token.startswith("--bind="):
            return token.split("=", 1)[1]
    pattern = re.compile(r"\b(\d+\.\d+\.\d+\.\d+:\d+|\[.*\]:\d+)\b")
    for token in argv:
        match = pattern.search(token)
        if match:
            return match.group(1)
    return "<unknown>"


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
    return "App is running", 200


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.get("/data")
def data():
    payload = {
        "service": "failed-to-forward-request-lab",
        "message": "This endpoint returns valid JSON from Flask.",
        "items": ["alpha", "beta", "gamma"],
    }
    return jsonify(payload), 200


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
    cmdline_info = read_cmdline()
    argv = cmdline_info.get("argv", []) if isinstance(cmdline_info, dict) else []
    return (
        jsonify(
            {
                "PORT": os.environ.get("PORT", "<unset>"),
                "WEBSITES_PORT": os.environ.get("WEBSITES_PORT", "<unset>"),
                "WEBSITE_SLOT_NAME": os.environ.get("WEBSITE_SLOT_NAME", "<unset>"),
                "WEBSITE_INSTANCE_ID": os.environ.get("WEBSITE_INSTANCE_ID", "<unset>"),
                "WEBSITE_HOSTNAME": os.environ.get("WEBSITE_HOSTNAME", "<unset>"),
                "BIND_ADDRESS": os.environ.get("BIND_ADDRESS", "<unset>"),
                "GUNICORN_CMD_ARGS": os.environ.get("GUNICORN_CMD_ARGS", "<unset>"),
                "gunicorn_bind_from_cmdline": bind_from_cmdline(argv),
                "cmdline": cmdline_info,
            }
        ),
        200,
    )


@app.get("/diag/bind")
def diag_bind():
    cmdline_info = read_cmdline()
    argv = cmdline_info.get("argv", []) if isinstance(cmdline_info, dict) else []
    bind_hint = bind_from_cmdline(argv)

    socket_info = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            socket_info["new_socket_getsockname"] = sock.getsockname()
        finally:
            sock.close()
    except Exception as exc:
        socket_info["new_socket_getsockname"] = {"error": str(exc)}

    try:
        host_ip_hint = socket.gethostbyname(socket.gethostname())
    except Exception as exc:
        host_ip_hint = {"error": str(exc)}

    return (
        jsonify(
            {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "host_ip_hint": host_ip_hint,
                "port_env": os.environ.get("PORT", "<unset>"),
                "websites_port_env": os.environ.get("WEBSITES_PORT", "<unset>"),
                "gunicorn_cmd_args": os.environ.get("GUNICORN_CMD_ARGS", "<unset>"),
                "gunicorn_bind_from_cmdline": bind_hint,
                "cmdline": cmdline_info,
                "socket_probe": socket_info,
                "note": "Bind address is inferred from env/cmdline because Flask app code cannot directly read Gunicorn listener sockets.",
            }
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
