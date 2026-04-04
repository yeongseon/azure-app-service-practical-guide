import importlib

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify

app = Flask(__name__)

LEAK_BUCKET = []


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
