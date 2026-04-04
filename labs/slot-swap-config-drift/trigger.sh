#!/bin/bash
set -euo pipefail

RESOURCE_GROUP="${1:-rg-lab-slotsw}"
APP_NAME="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SCRIPT_DIR}/app"
APP_PACKAGE="${SCRIPT_DIR}/app.zip"

if [ -z "${APP_NAME}" ]; then
    APP_NAME=$(az webapp list \
        --resource-group "${RESOURCE_GROUP}" \
        --query "[0].name" \
        --output tsv)
fi

if [ -z "${APP_NAME}" ] || [ "${APP_NAME}" = "null" ]; then
    echo "Unable to determine app name in resource group: ${RESOURCE_GROUP}"
    echo "Usage: bash labs/slot-swap-config-drift/trigger.sh <resource-group> <app-name>"
    exit 1
fi

echo "Using resource group: ${RESOURCE_GROUP}"
echo "Using app name: ${APP_NAME}"

rm --force "${APP_PACKAGE}"
(
    cd "${APP_DIR}"
    python3 -m zipfile --create "${APP_PACKAGE}" app.py requirements.txt
)

echo
echo "Deploying package to production slot..."
az webapp deploy \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${APP_NAME}" \
    --src-path "${APP_PACKAGE}" \
    --type zip \
    --clean true \
    --restart true

echo
echo "Deploying package to staging slot..."
az webapp deploy \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${APP_NAME}" \
    --slot staging \
    --src-path "${APP_PACKAGE}" \
    --type zip \
    --clean true \
    --restart true

PRODUCTION_HOST=$(az webapp show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${APP_NAME}" \
    --query "defaultHostName" \
    --output tsv)

STAGING_HOST="${APP_NAME}-staging.azurewebsites.net"
PRODUCTION_URL="https://${PRODUCTION_HOST}"
STAGING_URL="https://${STAGING_HOST}"

tmp_dir=$(mktemp --directory)
cleanup() {
    rm --recursive --force "${tmp_dir}" "${APP_PACKAGE}"
}
trap cleanup EXIT

echo
echo "Capturing pre-swap runtime config"
curl --silent --show-error "${PRODUCTION_URL}/config" > "${tmp_dir}/prod-before.json"
curl --silent --show-error "${STAGING_URL}/config" > "${tmp_dir}/staging-before.json"

echo "Production (/config before swap):"
cat "${tmp_dir}/prod-before.json"
echo
echo "Staging (/config before swap):"
cat "${tmp_dir}/staging-before.json"
echo

echo "Executing slot swap (staging -> production)..."
az webapp deployment slot swap \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${APP_NAME}" \
    --slot staging \
    --target-slot production

sleep 20

echo
echo "Capturing post-swap runtime config"
curl --silent --show-error "${PRODUCTION_URL}/config" > "${tmp_dir}/prod-after.json"
curl --silent --show-error "${STAGING_URL}/config" > "${tmp_dir}/staging-after.json"

echo "Production (/config after swap):"
cat "${tmp_dir}/prod-after.json"
echo
echo "Staging (/config after swap):"
cat "${tmp_dir}/staging-after.json"
echo

python3 - <<'PY' "${tmp_dir}/prod-before.json" "${tmp_dir}/staging-before.json" "${tmp_dir}/prod-after.json" "${tmp_dir}/staging-after.json"
import json
import sys

prod_before = json.load(open(sys.argv[1], encoding="utf-8"))
staging_before = json.load(open(sys.argv[2], encoding="utf-8"))
prod_after = json.load(open(sys.argv[3], encoding="utf-8"))
staging_after = json.load(open(sys.argv[4], encoding="utf-8"))

print("Swap behavior summary:")
print(f"  Production FEATURE_FLAG: {prod_before['FEATURE_FLAG']} -> {prod_after['FEATURE_FLAG']}")
print(f"  Staging FEATURE_FLAG:    {staging_before['FEATURE_FLAG']} -> {staging_after['FEATURE_FLAG']}")
print(f"  Production DB_CONNECTION_STRING: {prod_before['DB_CONNECTION_STRING']} -> {prod_after['DB_CONNECTION_STRING']}")
print(f"  Staging DB_CONNECTION_STRING:    {staging_before['DB_CONNECTION_STRING']} -> {staging_after['DB_CONNECTION_STRING']}")

feature_swapped = prod_after["FEATURE_FLAG"] == staging_before["FEATURE_FLAG"] and staging_after["FEATURE_FLAG"] == prod_before["FEATURE_FLAG"]
db_sticky = prod_after["DB_CONNECTION_STRING"] == prod_before["DB_CONNECTION_STRING"] and staging_after["DB_CONNECTION_STRING"] == staging_before["DB_CONNECTION_STRING"]

print()
print(f"  Non-sticky FEATURE_FLAG swapped with code: {feature_swapped}")
print(f"  Sticky DB_CONNECTION_STRING remained with slot: {db_sticky}")

restart_observed = prod_before.get("PROCESS_START_UTC") != prod_after.get("PROCESS_START_UTC")
print(f"  Production process restart observed: {restart_observed}")
if not restart_observed:
    print("  Note: If false, wait 1-2 minutes and query AppServicePlatformLogs using verify.sh.")
PY

echo
echo "Done. Run verify.sh to query swap/restart events in AppServicePlatformLogs."
