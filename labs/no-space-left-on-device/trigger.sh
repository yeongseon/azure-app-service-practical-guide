#!/bin/bash
set -euo pipefail

APP_URL_INPUT="${1:-${APP_URL:-}}"

if [ -z "$APP_URL_INPUT" ]; then
    echo "Usage: $0 <APP_URL>"
    echo "Example: $0 https://app-labdisk-xxxxxxxx.azurewebsites.net"
    exit 1
fi

APP_URL="${APP_URL_INPUT%/}"

echo "Starting no-space-left trigger against: $APP_URL"

echo
echo "Phase 1/5: Capture initial disk status"
curl --silent --show-error "$APP_URL/disk-status"
printf "\n"

echo
echo "Phase 2/5: Fill /home with 8 x 100MB writes"
for request_number in $(seq 1 8); do
    echo "  /fill-home call $request_number/8"
    curl --silent --show-error "$APP_URL/fill-home?size_mb=100"
    printf "\n"
done

echo
echo "Phase 3/5: Fill /tmp with 5 x 100MB writes"
for request_number in $(seq 1 5); do
    echo "  /fill-tmp call $request_number/5"
    curl --silent --show-error "$APP_URL/fill-tmp?size_mb=100"
    printf "\n"
done

echo
echo "Phase 4/5: Capture post-fill disk status"
curl --silent --show-error "$APP_URL/disk-status"
printf "\n"

echo
echo "Phase 5/5: Probe /health after storage pressure"
health_status_code=$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" "$APP_URL/health" || true)
echo "  /health HTTP status: ${health_status_code:-request_failed}"

echo
echo "Trigger complete."
echo "If /fill-home or /fill-tmp responses contain ENOSPC or 'No space left on device',"
echo "the lab successfully reproduced disk pressure symptoms."
