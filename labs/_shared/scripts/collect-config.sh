#!/usr/bin/env bash

set -euo pipefail

RG="${1:-}"
APP_NAME="${2:-}"
OUTPUT_DIR="${3:-artifacts/raw/config}"

if [[ -z "${RG}" || -z "${APP_NAME}" ]]; then
  echo "Usage: $0 <RG> <APP_NAME> [OUTPUT_DIR]"
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

az webapp show \
  --resource-group "${RG}" \
  --name "${APP_NAME}" \
  --output json > "${OUTPUT_DIR}/webapp-show.json"

az webapp config show \
  --resource-group "${RG}" \
  --name "${APP_NAME}" \
  --output json > "${OUTPUT_DIR}/config-show.json"

az webapp config appsettings list \
  --resource-group "${RG}" \
  --name "${APP_NAME}" \
  --output json > "${OUTPUT_DIR}/appsettings.json"

az webapp log deployment list \
  --resource-group "${RG}" \
  --name "${APP_NAME}" \
  --output json > "${OUTPUT_DIR}/deployment-list.json"

slots="$(az webapp deployment slot list --resource-group "${RG}" --name "${APP_NAME}" --query "[].name" --output tsv 2>/dev/null || true)"
if [[ -n "${slots}" ]]; then
  while IFS= read -r slot; do
    [[ -z "${slot}" ]] && continue
    slot_safe="$(python3 - <<'PY' "${slot}"
import re
import sys
print(re.sub(r'[^a-zA-Z0-9._-]+', '_', sys.argv[1]))
PY
)"

    az webapp show \
      --resource-group "${RG}" \
      --name "${APP_NAME}" \
      --slot "${slot}" \
      --output json > "${OUTPUT_DIR}/slot-${slot_safe}-webapp-show.json"

    az webapp config show \
      --resource-group "${RG}" \
      --name "${APP_NAME}" \
      --slot "${slot}" \
      --output json > "${OUTPUT_DIR}/slot-${slot_safe}-config-show.json"

    az webapp config appsettings list \
      --resource-group "${RG}" \
      --name "${APP_NAME}" \
      --slot "${slot}" \
      --output json > "${OUTPUT_DIR}/slot-${slot_safe}-appsettings.json"
  done <<< "${slots}"
fi

echo "[collect-config] output dir: ${OUTPUT_DIR}"
