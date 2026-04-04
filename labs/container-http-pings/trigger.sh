#!/bin/bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    printf 'Usage: %s <resource-group> <app-name>\n' "$0"
    exit 1
fi

RESOURCE_GROUP="$1"
APP_NAME="$2"

printf 'Waiting 60 seconds for deployment to settle...\n'
sleep 60

printf 'Retrieving app status...\n'
az webapp show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query '{name:name,state:state,defaultHostName:defaultHostName}' \
    --output table

HOST_NAME=$(az webapp show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query 'defaultHostName' \
    --output tsv)

APP_URL="https://${HOST_NAME}"

printf 'Curling application URL: %s\n' "$APP_URL"
if curl --silent --show-error --max-time 20 "$APP_URL"; then
    printf '\nApp responded. If this is unexpected, check platform logs for startup probe history.\n'
else
    printf '\nRequest failed as expected for this lab scenario.\n'
fi

printf 'The lab is configured to fail startup pings: WEBSITES_PORT=8080 while app listens on 8000.\n'
