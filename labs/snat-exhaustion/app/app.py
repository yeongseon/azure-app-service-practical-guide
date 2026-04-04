import importlib
import os
import time
import urllib.error
import urllib.request

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify
request = flask_module.request

app = Flask(__name__)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
