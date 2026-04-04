import importlib
import os
import socket

import requests

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify

app = Flask(__name__)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
