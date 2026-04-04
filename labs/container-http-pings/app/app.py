import importlib

flask = importlib.import_module("flask")
Flask = flask.Flask
jsonify = flask.jsonify

app = Flask(__name__)


@app.route("/")
def index() -> str:
    return "OK"


@app.route("/health")
def health() -> tuple:
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
