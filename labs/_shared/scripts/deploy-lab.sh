#!/usr/bin/env bash

set -euo pipefail

LAB_NAME="${1:-}"
LOCATION="${2:-koreacentral}"
SKU="${3:-B1}"

if [[ -z "${LAB_NAME}" ]]; then
  echo "Usage: $0 <LAB_NAME> [LOCATION] [SKU]"
  exit 1
fi

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
REPO_ROOT="$(realpath "${SCRIPT_DIR}/../../..")"
TEMPLATE_FILE="${REPO_ROOT}/labs/${LAB_NAME}/main.bicep"

if [[ ! -f "${TEMPLATE_FILE}" ]]; then
  echo "[deploy-lab] Template not found: ${TEMPLATE_FILE}"
  exit 1
fi

RG="rg-lab-${LAB_NAME}"
PLAN="plan-lab-${LAB_NAME}"
SUFFIX="$(openssl rand -hex 4)"
APP_NAME="app-lab-${LAB_NAME}-${SUFFIX}"
BASE_NAME="lab-${LAB_NAME}-${SUFFIX}"

ARTIFACTS_DIR="${PWD}/artifacts"
RAW_DIR="${ARTIFACTS_DIR}/raw"
mkdir -p "${RAW_DIR}"

DEPLOY_OUTPUT_FILE="${RAW_DIR}/deploy-output.json"
DEPLOY_OPERATIONS_FILE="${RAW_DIR}/deploy-operations.json"
DEPLOY_VERBOSE_FILE="${RAW_DIR}/deploy-verbose.log"
ENV_FILE="${ARTIFACTS_DIR}/.env"

echo "[deploy-lab] Creating resource group: ${RG}"
az group create \
  --resource-group "${RG}" \
  --location "${LOCATION}" \
  --output json > "${RAW_DIR}/resource-group.json"

declare -a PARAMS
if grep -Eq '^param\s+baseName\s+' "${TEMPLATE_FILE}"; then
  PARAMS+=("baseName=${BASE_NAME}")
fi
if grep -Eq '^param\s+location\s+' "${TEMPLATE_FILE}"; then
  PARAMS+=("location=${LOCATION}")
fi
if grep -Eq '^param\s+appName\s+' "${TEMPLATE_FILE}"; then
  PARAMS+=("appName=${APP_NAME}")
fi
if grep -Eq '^param\s+planName\s+' "${TEMPLATE_FILE}"; then
  PARAMS+=("planName=${PLAN}")
fi
if grep -Eq '^param\s+sku\s+' "${TEMPLATE_FILE}"; then
  PARAMS+=("sku=${SKU}")
fi
if grep -Eq '^param\s+skuName\s+' "${TEMPLATE_FILE}"; then
  PARAMS+=("skuName=${SKU}")
fi

echo "[deploy-lab] Deploying Bicep: ${TEMPLATE_FILE}"
if [[ ${#PARAMS[@]} -gt 0 ]]; then
  az deployment group create \
    --resource-group "${RG}" \
    --template-file "${TEMPLATE_FILE}" \
    --parameters "${PARAMS[@]}" \
    --verbose \
    --output json > "${DEPLOY_OUTPUT_FILE}" 2> "${DEPLOY_VERBOSE_FILE}"
else
  az deployment group create \
    --resource-group "${RG}" \
    --template-file "${TEMPLATE_FILE}" \
    --verbose \
    --output json > "${DEPLOY_OUTPUT_FILE}" 2> "${DEPLOY_VERBOSE_FILE}"
fi

DEPLOYMENT_NAME="$(python3 - <<'PY' "${DEPLOY_OUTPUT_FILE}"
import json
import sys

with open(sys.argv[1], encoding='utf-8') as handle:
    data = json.load(handle)
print(data.get('name', ''))
PY
)"

if [[ -z "${DEPLOYMENT_NAME}" ]]; then
  echo "[deploy-lab] Could not resolve deployment name from output"
  exit 1
fi

az deployment operation group list \
  --resource-group "${RG}" \
  --name "${DEPLOYMENT_NAME}" \
  --output json > "${DEPLOY_OPERATIONS_FILE}"

APP_HOST="$(python3 - <<'PY' "${DEPLOY_OUTPUT_FILE}"
import json
import sys

with open(sys.argv[1], encoding='utf-8') as handle:
    data = json.load(handle)
outputs = (data.get('properties') or {}).get('outputs') or {}
for key in ('defaultHostName', 'webAppDefaultHostName'):
    value = outputs.get(key, {}).get('value')
    if value:
        print(value)
        raise SystemExit(0)
print('')
PY
)"

DEPLOYED_APP_NAME="$(python3 - <<'PY' "${DEPLOY_OUTPUT_FILE}"
import json
import sys

with open(sys.argv[1], encoding='utf-8') as handle:
    data = json.load(handle)
outputs = (data.get('properties') or {}).get('outputs') or {}
for key in ('appName', 'webAppName'):
    value = outputs.get(key, {}).get('value')
    if value:
        print(value)
        raise SystemExit(0)
print('')
PY
)"

if [[ -n "${DEPLOYED_APP_NAME}" ]]; then
  APP_NAME="${DEPLOYED_APP_NAME}"
fi

if [[ -z "${APP_HOST}" ]]; then
  APP_HOST="$(az webapp list --resource-group "${RG}" --query "[0].defaultHostName" --output tsv)"
fi

APP_URL=""
if [[ -n "${APP_HOST}" ]]; then
  APP_URL="https://${APP_HOST}"
fi

cat > "${ENV_FILE}" <<EOF
LAB_NAME=${LAB_NAME}
LOCATION=${LOCATION}
SKU=${SKU}
RG=${RG}
PLAN=${PLAN}
APP_NAME=${APP_NAME}
APP_URL=${APP_URL}
DEPLOYMENT_NAME=${DEPLOYMENT_NAME}
TEMPLATE_FILE=${TEMPLATE_FILE}
EOF

echo "[deploy-lab] Completed"
echo "  Resource Group : ${RG}"
echo "  Plan           : ${PLAN}"
echo "  App Name       : ${APP_NAME}"
echo "  App URL        : ${APP_URL}"
echo "  Deploy Output  : ${DEPLOY_OUTPUT_FILE}"
echo "  Operations     : ${DEPLOY_OPERATIONS_FILE}"
echo "  Env File       : ${ENV_FILE}"
