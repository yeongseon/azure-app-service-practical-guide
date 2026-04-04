import importlib
import hashlib
import json
import os
import time
from datetime import datetime, timezone

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify

app = Flask(__name__)
PROCESS_START_UTC = datetime.now(timezone.utc).isoformat()
PROCESS_START_TIME = time.time()
REQUEST_COUNT = 0
ENDPOINT_COUNTERS = {}
LAST_CONFIG_SNAPSHOT = None


def current_config():
    return {
        "DB_CONNECTION_STRING": os.environ.get("DB_CONNECTION_STRING", "<unset>"),
        "FEATURE_FLAG": os.environ.get("FEATURE_FLAG", "<unset>"),
        "WEBSITE_SLOT_NAME": os.environ.get("WEBSITE_SLOT_NAME", "Production"),
        "PROCESS_START_UTC": PROCESS_START_UTC,
    }


def config_hash(config: dict) -> str:
    serialized = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@app.before_request
def track_request_count():
    global REQUEST_COUNT
    REQUEST_COUNT += 1


@app.after_request
def track_endpoint_counter(response):
    endpoint = flask_module.request.endpoint or "<unknown>"
    ENDPOINT_COUNTERS[endpoint] = ENDPOINT_COUNTERS.get(endpoint, 0) + 1
    return response


@app.get("/")
def index():
    config = current_config()
    return (
        f"slot={config['WEBSITE_SLOT_NAME']}; "
        f"DB_CONNECTION_STRING={config['DB_CONNECTION_STRING']}; "
        f"FEATURE_FLAG={config['FEATURE_FLAG']}",
        200,
    )


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.get("/config")
def config_dump():
    global LAST_CONFIG_SNAPSHOT
    LAST_CONFIG_SNAPSHOT = current_config()
    return jsonify(LAST_CONFIG_SNAPSHOT), 200


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
                "last_config_snapshot": LAST_CONFIG_SNAPSHOT,
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
        "DB_CONNECTION_STRING",
        "FEATURE_FLAG",
        "EXPECTED_DB_CONNECTION_STRING",
    ]
    return jsonify({key: os.environ.get(key, "<unset>") for key in safe_keys}), 200


@app.get("/diag/slots")
def diag_slots():
    config = current_config()
    expected_db = os.environ.get("EXPECTED_DB_CONNECTION_STRING", "<unset>")
    actual_db = config.get("DB_CONNECTION_STRING", "<unset>")

    expected_vs_actual = {
        "expected_db_connection_string": expected_db,
        "actual_db_connection_string": actual_db,
        "matches": expected_db == "<unset>" or expected_db == actual_db,
    }

    slot_env = {
        "WEBSITE_SLOT_NAME": os.environ.get("WEBSITE_SLOT_NAME", "<unset>"),
        "WEBSITE_INSTANCE_ID": os.environ.get("WEBSITE_INSTANCE_ID", "<unset>"),
        "WEBSITE_HOSTNAME": os.environ.get("WEBSITE_HOSTNAME", "<unset>"),
        "DB_CONNECTION_STRING": os.environ.get("DB_CONNECTION_STRING", "<unset>"),
        "FEATURE_FLAG": os.environ.get("FEATURE_FLAG", "<unset>"),
        "EXPECTED_DB_CONNECTION_STRING": expected_db,
    }

    return (
        jsonify(
            {
                "current_slot_name": config.get("WEBSITE_SLOT_NAME", "<unset>"),
                "slot_relevant_env": slot_env,
                "process_start_time": PROCESS_START_UTC,
                "config_hash": config_hash(config),
                "current_config": config,
                "expected_vs_actual": expected_vs_actual,
            }
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
