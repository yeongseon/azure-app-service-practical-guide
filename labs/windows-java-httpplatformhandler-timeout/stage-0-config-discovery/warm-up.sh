#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <APP_URL>"
    echo "Example: $0 https://app-winjavatimeout-abcd.azurewebsites.net"
    exit 1
fi

APP_URL="$1"
HEALTH_URL="${APP_URL}/actuator/health"
WARM_URL="${APP_URL}/slow/2"
POLL_TIMEOUT_SEC=300
POLL_INTERVAL_SEC=5
WARM_REQUESTS=5
IDLE_SETTLE_SEC=30

echo "=== Warm-up target: $APP_URL ==="
echo

echo "Step 1/3: Wait for /actuator/health to return 200 (timeout ${POLL_TIMEOUT_SEC}s)"
DEADLINE=$(( $(date +%s) + POLL_TIMEOUT_SEC ))
ATTEMPTS=0
while true; do
    ATTEMPTS=$((ATTEMPTS + 1))
    HTTP_CODE="$(curl --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 30 "$HEALTH_URL" || true)"
    if [[ "$HTTP_CODE" == "200" ]]; then
        echo "  attempt=${ATTEMPTS} status=200 -> ready"
        break
    fi
    if [[ $(date +%s) -ge $DEADLINE ]]; then
        echo "ERROR: /actuator/health did not return 200 within ${POLL_TIMEOUT_SEC}s"
        echo "  last observed status: $HTTP_CODE"
        exit 1
    fi
    echo "  attempt=${ATTEMPTS} status=${HTTP_CODE} -> retry in ${POLL_INTERVAL_SEC}s"
    sleep "$POLL_INTERVAL_SEC"
done

echo
echo "Step 2/3: JIT warm-up (${WARM_REQUESTS} requests to /slow/2)"
for i in $(seq 1 "$WARM_REQUESTS"); do
    STATUS_TIME="$(curl --silent --output /dev/null --write-out '%{http_code} %{time_total}\n' \
        --max-time 30 "$WARM_URL" || echo 'ERR 0')"
    echo "  warm ${i}: ${STATUS_TIME}"
done

echo
echo "Step 3/3: Idle settle (${IDLE_SETTLE_SEC}s) so subsequent probes measure a cold-idle worker"
sleep "$IDLE_SETTLE_SEC"

echo
echo "Warm-up complete. Proceed with: run-timeout-probe.sh $APP_URL"
