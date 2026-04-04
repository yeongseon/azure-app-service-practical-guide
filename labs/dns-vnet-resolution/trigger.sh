#!/bin/bash
set -euo pipefail

APP_URL_INPUT="${1:-${APP_URL:-}}"

if [ -z "$APP_URL_INPUT" ]; then
    echo "Usage: $0 <APP_URL>"
    echo "Example: $0 https://app-labdns-xxxxxxxx.azurewebsites.net"
    exit 1
fi

APP_URL="${APP_URL_INPUT%/}"

echo "Starting DNS resolution lab trigger against: $APP_URL"
echo "Phase 1/2: Calling /resolve to capture DNS lookups"

resolve_status_code=$(curl --silent --show-error --output /tmp/dns-resolve-response.json --write-out "%{http_code}" "$APP_URL/resolve")

echo "  /resolve HTTP status: $resolve_status_code"
echo "  /resolve response:"
cat /tmp/dns-resolve-response.json
echo

echo "Phase 2/2: Calling /connect to capture endpoint connection failures"

connect_status_code=$(curl --silent --show-error --output /tmp/dns-connect-response.json --write-out "%{http_code}" "$APP_URL/connect")

echo "  /connect HTTP status: $connect_status_code"
echo "  /connect response:"
cat /tmp/dns-connect-response.json
echo

rm --force /tmp/dns-resolve-response.json /tmp/dns-connect-response.json

echo "Trigger complete."
echo "Expected observation: DNS lookup and/or connection failures for storage private endpoint names"
echo "because the Private DNS Zone is intentionally NOT linked to the VNet."
