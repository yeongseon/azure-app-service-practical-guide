#!/usr/bin/env bash

set -euo pipefail

RG="${1:-}"
APP_NAME="${2:-}"
OUTPUT_DIR="${3:-artifacts/raw/logs}"
DURATION_SECONDS="${4:-60}"

if [[ -z "${RG}" || -z "${APP_NAME}" ]]; then
  echo "Usage: $0 <RG> <APP_NAME> [OUTPUT_DIR] [DURATION_SECONDS]"
  exit 1
fi

if ! [[ "${DURATION_SECONDS}" =~ ^[0-9]+$ ]] || [[ "${DURATION_SECONDS}" -lt 1 ]]; then
  echo "[collect-app-logs] DURATION_SECONDS must be a positive integer"
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

echo "[collect-app-logs] Enabling filesystem application logging"
az webapp log config \
  --resource-group "${RG}" \
  --name "${APP_NAME}" \
  --application-logging "filesystem" \
  --level "verbose" \
  --output json > "${OUTPUT_DIR}/log-config.json"

echo "[collect-app-logs] Tailing logs for ${DURATION_SECONDS}s"
set +e
timeout --signal=INT "${DURATION_SECONDS}" az webapp log tail \
  --resource-group "${RG}" \
  --name "${APP_NAME}" > "${OUTPUT_DIR}/log-tail.txt" 2>&1
TAIL_EXIT_CODE=$?
set -e

if [[ "${TAIL_EXIT_CODE}" -ne 0 && "${TAIL_EXIT_CODE}" -ne 124 && "${TAIL_EXIT_CODE}" -ne 130 ]]; then
  echo "[collect-app-logs] az webapp log tail failed with exit code ${TAIL_EXIT_CODE}"
  exit "${TAIL_EXIT_CODE}"
fi

echo "[collect-app-logs] Downloading web app logs"
az webapp log download \
  --resource-group "${RG}" \
  --name "${APP_NAME}" \
  --log-file "${OUTPUT_DIR}/logs.zip"

echo "[collect-app-logs] Capturing deployment logs"
az webapp log deployment list \
  --resource-group "${RG}" \
  --name "${APP_NAME}" \
  --output json > "${OUTPUT_DIR}/deployment-log.json"

echo "[collect-app-logs] output dir: ${OUTPUT_DIR}"
