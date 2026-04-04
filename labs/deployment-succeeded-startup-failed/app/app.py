import importlib

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify

app = Flask(__name__)


@app.get("/")
def index():
    return jsonify({"message": "app code is healthy"}), 200


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
