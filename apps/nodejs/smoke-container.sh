#!/usr/bin/env bash
# Build the Node.js reference image, run it, and prove it serves /health with
# sshd alive. Used verbatim by the "Node.js Container Smoke" CI job and by the
# Golden Status gate, so the two can never drift apart.
set -Eeuo pipefail

cd "$(dirname "$0")"

tag="appsvc-nodejs-smoke:$$"
name="appsvc-nodejs-smoke-$$"
timeout_seconds="${SMOKE_TIMEOUT_SECONDS:-60}"

cleanup() {
  docker rm --force "$name" >/dev/null 2>&1 || true
  docker image rm --force "$tag" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

docker build --quiet --tag "$tag" . >/dev/null
docker run --detach --name "$name" --publish 127.0.0.1::3000 "$tag" >/dev/null
port="$(docker port "$name" 3000/tcp | head -n 1 | sed 's/.*://')"

deadline=$((SECONDS + timeout_seconds))
# --fail would accept any status below 400 (redirects, 204), so require exactly
# 200 rather than report a /health result that never happened.
health_status() {
  curl --silent --output /dev/null --write-out '%{http_code}' --max-time 3 \
    "http://127.0.0.1:${port}/health" || true
}
until [ "$(health_status)" = "200" ]; do
  if [ "$(docker inspect --format '{{.State.Running}}' "$name")" != "true" ]; then
    echo "Container exited before /health answered." >&2
    docker logs "$name" >&2 || true
    exit 1
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "/health did not return 200 within ${timeout_seconds}s." >&2
    docker logs "$name" >&2 || true
    exit 1
  fi
  sleep 2
done

if ! docker exec "$name" sh -c 'pidof sshd >/dev/null'; then
  echo "sshd is not running inside the container." >&2
  docker logs "$name" >&2 || true
  exit 1
fi

echo "Container smoke passed: /health returned 200 and sshd is running."
