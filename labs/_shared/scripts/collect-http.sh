#!/usr/bin/env bash

set -euo pipefail

APP_URL="${1:-}"
ENDPOINTS="${2:-}"
OUTPUT_DIR="${3:-artifacts/raw/http}"
INTERVAL="${4:-0}"
ROUNDS="${5:-1}"

if [[ -z "${APP_URL}" || -z "${ENDPOINTS}" ]]; then
  echo "Usage: $0 <APP_URL> <ENDPOINTS_CSV> [OUTPUT_DIR] [INTERVAL_SECONDS] [ROUNDS]"
  exit 1
fi

if ! [[ "${ROUNDS}" =~ ^[0-9]+$ ]] || [[ "${ROUNDS}" -lt 1 ]]; then
  echo "[collect-http] ROUNDS must be a positive integer"
  exit 1
fi

if ! [[ "${INTERVAL}" =~ ^[0-9]+$ ]]; then
  echo "[collect-http] INTERVAL must be an integer >= 0"
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"
SUMMARY_CSV="${OUTPUT_DIR}/http-summary.csv"
printf 'timestamp,round,endpoint,status,time_total,time_starttransfer,size_download\n' > "${SUMMARY_CSV}"

IFS=',' read -r -a ENDPOINT_ARRAY <<< "${ENDPOINTS}"

for (( round = 1; round <= ROUNDS; round += 1 )); do
  for endpoint in "${ENDPOINT_ARRAY[@]}"; do
    endpoint_trimmed="$(python3 - <<'PY' "${endpoint}"
import sys
print(sys.argv[1].strip())
PY
)"
    [[ -z "${endpoint_trimmed}" ]] && continue

    if [[ "${endpoint_trimmed}" != /* ]]; then
      endpoint_trimmed="/${endpoint_trimmed}"
    fi

    endpoint_safe="$(python3 - <<'PY' "${endpoint_trimmed}"
import re
import sys

value = sys.argv[1]
safe = re.sub(r'[^a-zA-Z0-9._-]+', '_', value).strip('_')
print(safe or 'root')
PY
)"

    headers_file="${OUTPUT_DIR}/${endpoint_safe}-${round}-headers.txt"
    body_file="${OUTPUT_DIR}/${endpoint_safe}-${round}-body.txt"
    timing_file="${OUTPUT_DIR}/${endpoint_safe}-${round}-timing.json"
    verbose_file="${OUTPUT_DIR}/${endpoint_safe}-${round}-curl-verbose.txt"

    target_url="${APP_URL%/}${endpoint_trimmed}"
    timing_json="$(curl \
      --silent \
      --show-error \
      --verbose \
      --max-time 30 \
      --output "${body_file}" \
      --dump-header "${headers_file}" \
      --write-out '{"http_code":"%{http_code}","time_namelookup":%{time_namelookup},"time_connect":%{time_connect},"time_appconnect":%{time_appconnect},"time_pretransfer":%{time_pretransfer},"time_starttransfer":%{time_starttransfer},"time_total":%{time_total},"size_download":%{size_download},"url_effective":"%{url_effective}"}' \
      "${target_url}" 2> "${verbose_file}")"

    printf '%s\n' "${timing_json}" > "${timing_file}"

    summary_row="$(python3 - <<'PY' "${timing_file}" "${round}" "${endpoint_trimmed}"
import datetime
import json
import sys

with open(sys.argv[1], encoding='utf-8') as handle:
    data = json.load(handle)

timestamp = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
print(','.join([
    timestamp,
    sys.argv[2],
    sys.argv[3],
    str(data.get('http_code', '')),
    str(data.get('time_total', '')),
    str(data.get('time_starttransfer', '')),
    str(data.get('size_download', '')),
]))
PY
)"
    printf '%s\n' "${summary_row}" >> "${SUMMARY_CSV}"

    echo "[collect-http] round=${round} endpoint=${endpoint_trimmed} status=$(python3 - <<'PY' "${timing_file}"
import json
import sys
with open(sys.argv[1], encoding='utf-8') as handle:
    print(json.load(handle).get('http_code', ''))
PY
)"
  done

  if [[ "${INTERVAL}" -gt 0 && "${round}" -lt "${ROUNDS}" ]]; then
    sleep "${INTERVAL}"
  fi
done

echo "[collect-http] Summary CSV: ${SUMMARY_CSV}"
