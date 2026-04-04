#!/bin/bash
set -euo pipefail

RESOURCE_GROUP_NAME="${1:-${RESOURCE_GROUP_NAME:-}}"
WEB_APP_NAME="${2:-${WEB_APP_NAME:-}}"

if [ -z "$RESOURCE_GROUP_NAME" ] || [ -z "$WEB_APP_NAME" ]; then
    echo "Usage: $0 <RESOURCE_GROUP_NAME> <WEB_APP_NAME>"
    echo "Example: $0 rg-lab-startup app-labstart-xxxxxxxx"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"
PACKAGE_PATH="$(mktemp --suffix=.zip)"

python3 - <<'PY' "$APP_DIR" "$PACKAGE_PATH"
import pathlib
import sys
import zipfile

app_dir = pathlib.Path(sys.argv[1]).resolve()
package_path = pathlib.Path(sys.argv[2]).resolve()

with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(app_dir.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(app_dir))
PY

echo "Deploying application package with Oryx build enabled..."
az webapp deploy \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$WEB_APP_NAME" \
    --src-path "$PACKAGE_PATH" \
    --type zip

rm --force "$PACKAGE_PATH"

APP_HOST_NAME=$(az webapp show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$WEB_APP_NAME" \
    --query "defaultHostName" \
    --output tsv)

APP_URL="https://$APP_HOST_NAME"

echo
echo "Deployment completed. Probing app endpoint (expected failure due to wrong startup command)..."
sleep 15

first_status_code=$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" --max-time 20 "$APP_URL/health" || true)
first_status_code=${first_status_code:-000}

echo "Initial /health status code: $first_status_code"
echo "Expected: non-200 (often 503 or timeout) even though deployment succeeded."

echo
echo "Applying startup command fix..."
az webapp config set \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$WEB_APP_NAME" \
    --startup-file "gunicorn --bind=0.0.0.0:8000 app:app"

echo "Waiting for app restart after startup command update..."
sleep 20

second_status_code=$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" --max-time 20 "$APP_URL/health" || true)
second_status_code=${second_status_code:-000}

echo "Post-fix /health status code: $second_status_code"
echo

if [ "$second_status_code" = "200" ]; then
    echo "✅ Reproduction complete: deployment succeeded but startup initially failed, then recovered after startup fix."
else
    echo "⚠️ App is not healthy yet. Wait 1-2 minutes and run: curl -i $APP_URL/health"
fi
