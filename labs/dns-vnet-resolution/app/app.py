import importlib
import os
import socket
import time
from datetime import datetime, timezone

import requests

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify
request = flask_module.request

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
    "STORAGE_ACCOUNT_NAME",
]


def _iso_utc(timestamp):
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _safe_env():
    values = {key: os.environ.get(key, "<unset>") for key in SAFE_ENV_KEYS}
    custom_lab_keys = sorted(key for key in os.environ if key.startswith("LAB_"))
    for key in custom_lab_keys:
        values[key] = os.environ.get(key, "<unset>")
    return values


def _read_text_file(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return {"content": handle.read()}
    except OSError as exc:
        return {"error": str(exc)}


def _resolve_for_diag(hostname):
    try:
        records = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
        addresses = sorted({item[4][0] for item in records})
        return {"hostname": hostname, "resolved_ips": addresses}
    except Exception as exc:
        return {"hostname": hostname, "error": str(exc)}


@app.before_request
def _count_request():
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    endpoint_key = request.endpoint or "<unknown>"
    ENDPOINT_COUNTERS[endpoint_key] = ENDPOINT_COUNTERS.get(endpoint_key, 0) + 1


def resolve_host(hostname):
    try:
        records = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
        addresses = sorted({item[4][0] for item in records})
        return {"hostname": hostname, "ok": True, "addresses": addresses}
    except Exception as exc:
        return {"hostname": hostname, "ok": False, "error": str(exc)}


def connect_host(url):
    try:
        response = requests.get(url, timeout=8)
        return {
            "url": url,
            "ok": True,
            "status_code": response.status_code,
            "content_length": len(response.text),
        }
    except Exception as exc:
        return {"url": url, "ok": False, "error": str(exc)}


@app.get("/")
def index():
    return "OK", 200


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.get("/resolve")
def resolve():
    storage_account_name = os.getenv("STORAGE_ACCOUNT_NAME", "")
    if not storage_account_name:
        return jsonify(
            {"status": "error", "error": "STORAGE_ACCOUNT_NAME is not set"}
        ), 500

    blob_hostname = f"{storage_account_name}.blob.core.windows.net"
    private_blob_hostname = f"{storage_account_name}.privatelink.blob.core.windows.net"

    return (
        jsonify(
            {
                "status": "ok",
                "storage_account_name": storage_account_name,
                "results": [
                    resolve_host(blob_hostname),
                    resolve_host(private_blob_hostname),
                ],
            }
        ),
        200,
    )


@app.get("/connect")
def connect():
    storage_account_name = os.getenv("STORAGE_ACCOUNT_NAME", "")
    if not storage_account_name:
        return jsonify(
            {"status": "error", "error": "STORAGE_ACCOUNT_NAME is not set"}
        ), 500

    blob_url = f"https://{storage_account_name}.blob.core.windows.net/?comp=list"
    private_blob_url = (
        f"https://{storage_account_name}.privatelink.blob.core.windows.net/?comp=list"
    )

    return (
        jsonify(
            {
                "status": "ok",
                "storage_account_name": storage_account_name,
                "resolve": [
                    resolve_host(f"{storage_account_name}.blob.core.windows.net"),
                    resolve_host(
                        f"{storage_account_name}.privatelink.blob.core.windows.net"
                    ),
                ],
                "connect": [connect_host(blob_url), connect_host(private_blob_url)],
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
                "endpoint_counters": ENDPOINT_COUNTERS,
            }
        ),
        200,
    )


@app.get("/diag/env")
def diag_env():
    return jsonify(_safe_env()), 200


@app.get("/diag/dns")
def diag_dns():
    resolv_conf = _read_text_file("/etc/resolv.conf")
    resolv_conf_payload = (
        resolv_conf.get("content", "") if "content" in resolv_conf else resolv_conf
    )

    storage_account_name = os.environ.get("STORAGE_ACCOUNT_NAME", "")
    storage_blob_hostname = (
        f"{storage_account_name}.blob.core.windows.net"
        if storage_account_name
        else None
    )

    hostnames = ["management.azure.com", "login.microsoftonline.com"]
    if storage_blob_hostname:
        hostnames.append(storage_blob_hostname)

    resolutions = [_resolve_for_diag(hostname) for hostname in hostnames]
    if not storage_blob_hostname:
        resolutions.append(
            {
                "hostname": "<storage-account>.blob.core.windows.net",
                "error": "STORAGE_ACCOUNT_NAME is not set",
            }
        )

    return (
        jsonify(
            {
                "resolv_conf": resolv_conf_payload,
                "resolutions": resolutions,
            }
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
