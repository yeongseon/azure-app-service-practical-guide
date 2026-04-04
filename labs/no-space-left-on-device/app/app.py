import importlib
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

flask_module = importlib.import_module("flask")
Flask = flask_module.Flask
jsonify = flask_module.jsonify
request = flask_module.request

app = Flask(__name__)

HOME_TEMP_DIR = Path("/home/site/wwwroot/temp")
TMP_TEMP_DIR = Path("/tmp/no-space-lab")
CHUNK_SIZE = 1024 * 1024
PROCESS_START_TIME = time.time()
PROCESS_START_UTC = datetime.now(timezone.utc).isoformat()
REQUEST_COUNT = 0
ENDPOINT_COUNTERS = {}
TOTAL_BYTES_WRITTEN = 0


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
    global TOTAL_BYTES_WRITTEN
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

    TOTAL_BYTES_WRITTEN += written_bytes

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


def safe_disk_usage(path: Path | str) -> dict:
    try:
        usage = shutil.disk_usage(path)
        used_percent = (
            round((usage.used / usage.total) * 100, 2) if usage.total else 0.0
        )
        return {
            "path": str(path),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_percent": used_percent,
        }
    except Exception as exc:
        return {"path": str(path), "error": str(exc)}


def safe_directory_totals(path: Path) -> dict:
    try:
        file_count = 0
        total_size_bytes = 0
        if path.exists():
            for candidate in path.rglob("*"):
                if candidate.is_file():
                    file_count += 1
                    try:
                        total_size_bytes += candidate.stat().st_size
                    except Exception:
                        continue
        return {
            "path": str(path),
            "exists": path.exists(),
            "file_count": file_count,
            "total_size_bytes": total_size_bytes,
        }
    except Exception as exc:
        return {"path": str(path), "error": str(exc)}


def read_proc_mounts() -> dict:
    try:
        mounts = []
        with open("/proc/mounts", "r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                parts = raw_line.strip().split()
                if len(parts) >= 4:
                    mounts.append(
                        {
                            "filesystem": parts[0],
                            "mount_point": parts[1],
                            "fs_type": parts[2],
                            "options": parts[3],
                        }
                    )
        return {"mounts": mounts}
    except Exception as exc:
        return {"error": str(exc)}


@app.before_request
def track_request_count():
    global REQUEST_COUNT
    REQUEST_COUNT += 1


@app.after_request
def track_endpoint_counter(response):
    endpoint = request.endpoint or "<unknown>"
    ENDPOINT_COUNTERS[endpoint] = ENDPOINT_COUNTERS.get(endpoint, 0) + 1
    return response


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
                "total_bytes_written": TOTAL_BYTES_WRITTEN,
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
    ]
    return jsonify({key: os.environ.get(key, "<unset>") for key in safe_keys}), 200


@app.get("/diag/disk")
def diag_disk():
    watched_paths = [
        "/",
        "/home",
        "/tmp",
        "/home/site/wwwroot",
        "/home/LogFiles",
    ]
    disk_usage = {path: safe_disk_usage(path) for path in watched_paths}

    temp_dir_stats = {
        "HOME_TEMP_DIR": safe_directory_totals(HOME_TEMP_DIR),
        "TMP_TEMP_DIR": safe_directory_totals(TMP_TEMP_DIR),
        "tmp_root": safe_directory_totals(Path("/tmp")),
    }

    return (
        jsonify(
            {
                "disk_usage": disk_usage,
                "temp_dir_stats": temp_dir_stats,
                "proc_mounts": read_proc_mounts(),
            }
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
