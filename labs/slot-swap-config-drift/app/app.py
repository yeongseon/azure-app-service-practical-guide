import importlib
import os
from datetime import datetime, timezone

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify

app = Flask(__name__)
PROCESS_START_UTC = datetime.now(timezone.utc).isoformat()


def current_config():
    return {
        "DB_CONNECTION_STRING": os.environ.get("DB_CONNECTION_STRING", "<unset>"),
        "FEATURE_FLAG": os.environ.get("FEATURE_FLAG", "<unset>"),
        "WEBSITE_SLOT_NAME": os.environ.get("WEBSITE_SLOT_NAME", "Production"),
        "PROCESS_START_UTC": PROCESS_START_UTC,
    }


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
    return jsonify(current_config()), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
