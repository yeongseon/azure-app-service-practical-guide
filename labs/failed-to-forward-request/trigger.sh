#!/bin/bash
set -euo pipefail

RESOURCE_GROUP_NAME="${1:-rg-lab-forward}"
APP_NAME_INPUT="${2:-}"

if [ -n "$APP_NAME_INPUT" ]; then
    APP_NAME="$APP_NAME_INPUT"
else
    APP_NAME=$(az webapp list \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --query "[0].name" \
        --output tsv)
fi

if [ -z "$APP_NAME" ]; then
    echo "No App Service app found in resource group: $RESOURCE_GROUP_NAME"
    echo "Deploy infrastructure first using labs/failed-to-forward-request/main.bicep"
    exit 1
fi

APP_URL=$(az webapp show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --query "defaultHostName" \
    --output tsv)

if [ -z "$APP_URL" ]; then
    echo "Unable to determine app URL for app: $APP_NAME"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"
PACKAGE_PATH="$(mktemp --suffix=.zip)"

echo "Packaging Flask sample app"
(
    cd "$APP_DIR"
    zip --quiet --recurse-paths "$PACKAGE_PATH" .
)

echo "Deploying app code to: $APP_NAME"
az webapp deploy \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --src-path "$PACKAGE_PATH" \
    --type zip \
    --restart true

rm --force "$PACKAGE_PATH"

echo
echo "Testing while startup command is intentionally wrong (127.0.0.1 bind)..."

status_before=$(curl --silent --show-error --max-time 15 --output /dev/null --write-out "%{http_code}" "https://$APP_URL/" || true)
if [ -z "$status_before" ]; then
    status_before="000"
fi

echo "Initial HTTP status: $status_before"
echo "Expected: 503 or 000 due to failed forwarding from platform proxy"

echo
echo "Applying fix: bind Gunicorn to 0.0.0.0:8000"
az webapp config set \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout=120 --workers=2 app:app" >/dev/null

echo "Waiting for restart and warm-up"
sleep 20

status_after="000"
for attempt in $(seq 1 12); do
    status_after=$(curl --silent --show-error --max-time 15 --output /dev/null --write-out "%{http_code}" "https://$APP_URL/health" || true)
    if [ "$status_after" = "200" ]; then
        break
    fi
    sleep 5
done

echo "Post-fix HTTP status on /health: $status_after"
echo

if [ "$status_after" = "200" ]; then
    echo "✅ Reproduction and mitigation successful."
else
    echo "⚠️  App did not return 200 yet. Wait 1-2 minutes and retry curl."
fi

echo "App URL: https://$APP_URL"
