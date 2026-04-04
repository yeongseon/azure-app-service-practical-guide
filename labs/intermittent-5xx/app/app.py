import random
import time

from flask import Flask, jsonify  # pyright: ignore[reportMissingImports]

app = Flask(__name__)


@app.get("/")
def root():
    return "OK", 200


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.get("/slow")
def slow():
    delay_seconds = random.randint(5, 15)
    time.sleep(delay_seconds)
    return jsonify({"endpoint": "slow", "delaySeconds": delay_seconds}), 200


@app.get("/fast")
def fast():
    return jsonify({"endpoint": "fast", "message": "quick response"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
