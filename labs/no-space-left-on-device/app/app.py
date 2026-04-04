import importlib
import os
import shutil
import time
import uuid
from pathlib import Path

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify
request = flask_module.request

app = Flask(__name__)

HOME_TEMP_DIR = Path("/home/site/wwwroot/temp")
TMP_TEMP_DIR = Path("/tmp/no-space-lab")
CHUNK_SIZE = 1024 * 1024


def disk_snapshot(path: Path) -> dict:
    usage = shutil.disk_usage(path)
    used_percent = round((usage.used / usage.total) * 100, 2) if usage.total else 0.0
    return {
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": used_percent,
    }


def write_payload(target_dir: Path, size_mb: int) -> dict:
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"diskfill-{int(time.time())}-{uuid.uuid4().hex}.bin"
    file_path = target_dir / file_name
    chunk = b"0" * CHUNK_SIZE
    requested_bytes = size_mb * CHUNK_SIZE
    written_bytes = 0

    with file_path.open("wb") as handle:
        while written_bytes < requested_bytes:
            remaining = requested_bytes - written_bytes
            next_chunk_size = CHUNK_SIZE if remaining >= CHUNK_SIZE else remaining
            handle.write(chunk[:next_chunk_size])
            written_bytes += next_chunk_size
        handle.flush()
        os.fsync(handle.fileno())

    return {
        "file_path": str(file_path),
        "requested_mb": size_mb,
        "written_bytes": written_bytes,
    }


def cleanup_directory(target_dir: Path) -> int:
    if not target_dir.exists():
        return 0

    deleted_files = 0
    for candidate in target_dir.glob("diskfill-*.bin"):
        if candidate.is_file():
            candidate.unlink(missing_ok=True)
            deleted_files += 1
    return deleted_files


@app.get("/")
def index():
    return "OK", 200


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.get("/disk-status")
def disk_status():
    HOME_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    TMP_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    return (
        jsonify(
            {
                "status": "ok",
                "home": disk_snapshot(HOME_TEMP_DIR),
                "tmp": disk_snapshot(TMP_TEMP_DIR),
            }
        ),
        200,
    )


@app.get("/fill-home")
def fill_home():
    size_mb = request.args.get("size_mb", default=100, type=int)
    size_mb = 100 if size_mb is None or size_mb <= 0 else size_mb

    try:
        write_result = write_payload(HOME_TEMP_DIR, size_mb)
        return jsonify({"status": "written", "target": "home", **write_result}), 200
    except OSError as exc:
        app.logger.exception("fill-home failed with disk error: %s", exc)
        return (
            jsonify({"status": "error", "target": "home", "error": str(exc)}),
            507,
        )


@app.get("/fill-tmp")
def fill_tmp():
    size_mb = request.args.get("size_mb", default=100, type=int)
    size_mb = 100 if size_mb is None or size_mb <= 0 else size_mb

    try:
        write_result = write_payload(TMP_TEMP_DIR, size_mb)
        return jsonify({"status": "written", "target": "tmp", **write_result}), 200
    except OSError as exc:
        app.logger.exception("fill-tmp failed with disk error: %s", exc)
        return (
            jsonify({"status": "error", "target": "tmp", "error": str(exc)}),
            507,
        )


@app.get("/cleanup")
def cleanup():
    removed_home_files = cleanup_directory(HOME_TEMP_DIR)
    removed_tmp_files = cleanup_directory(TMP_TEMP_DIR)
    return (
        jsonify(
            {
                "status": "cleaned",
                "removed_home_files": removed_home_files,
                "removed_tmp_files": removed_tmp_files,
            }
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
