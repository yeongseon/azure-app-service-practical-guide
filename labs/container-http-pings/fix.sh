#!/bin/bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    printf 'Usage: %s <resource-group> <app-name>\n' "$0"
    exit 1
fi

RESOURCE_GROUP="$1"
APP_NAME="$2"

printf 'Updating app setting WEBSITES_PORT=8000...\n'
az webapp config appsettings set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --settings WEBSITES_PORT=8000 \
    --output table

printf 'Restarting the app...\n'
az webapp restart \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME"

HOST_NAME=$(az webapp show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query 'defaultHostName' \
    --output tsv)

HEALTH_URL="https://${HOST_NAME}/health"
printf 'Checking health endpoint: %s\n' "$HEALTH_URL"

for attempt in {1..12}; do
    if curl --silent --show-error --fail --max-time 20 "$HEALTH_URL"; then
        printf '\nApp is healthy after the fix.\n'
        exit 0
    fi

    printf 'Health check attempt %s/12 failed, retrying in 10 seconds...\n' "$attempt"
    sleep 10
done

printf 'App did not become healthy in time. Inspect AppServicePlatformLogs and AppServiceConsoleLogs.\n'
exit 1
