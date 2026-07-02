#!/usr/bin/env bash
set -euo pipefail

# Lab 2 warm-up: Polls /actuator/health until the Java app is ready, then sends
# repeated /slow/2 requests and an idle settle pause so the JVM and JIT are
# warmed before load tests.
#
# Inputs:
#   - results/deploy-metadata.json for webAppHostname
#
# Outputs:
#   - stdout progress messages
#   - exit code (0 when warmed, non-zero on failure)
#
# Dependencies:
#   - curl
#   - jq

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly METADATA_FILE="$SCRIPT_DIR/results/deploy-metadata.json"
readonly POLL_TIMEOUT_SEC=300
readonly POLL_INTERVAL_SEC=5
readonly WARM_REQUESTS=5
readonly IDLE_SETTLE_SEC=30

if [[ ! -f "$METADATA_FILE" ]]; then
    echo "ERROR: deploy-metadata.json not found at: $METADATA_FILE"
    echo "  Run deploy.sh first to provision the environment."
    exit 1
fi

APP_HOSTNAME="$(python3 -c "import json; print(json.load(open('$METADATA_FILE'))['webAppHostname'])")"
APP_URL="https://${APP_HOSTNAME}"
HEALTH_URL="${APP_URL}/actuator/health"
WARM_URL="${APP_URL}/slow/2"

echo "=== Warm-up target: $APP_URL ==="
echo ""

echo "Step 1/3: Wait for /actuator/health to return 200 (timeout ${POLL_TIMEOUT_SEC}s)"
DEADLINE=$(( $(date +%s) + POLL_TIMEOUT_SEC ))
ATTEMPTS=0
FIRST_HEALTHY=""
while true; do
    ATTEMPTS=$((ATTEMPTS + 1))
    HTTP_CODE="$(curl --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 30 "$HEALTH_URL" || true)"
    if [[ "$HTTP_CODE" == "200" ]]; then
        FIRST_HEALTHY="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
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

echo ""
echo "Step 2/3: JIT warm-up (${WARM_REQUESTS} requests to /slow/2)"
for i in $(seq 1 "$WARM_REQUESTS"); do
    STATUS_TIME="$(curl --silent --output /dev/null --write-out '%{http_code} %{time_total}\n' \
        --max-time 30 "$WARM_URL" || echo 'ERR 0')"
    echo "  warm ${i}: ${STATUS_TIME}"
    if [[ $i -lt $WARM_REQUESTS ]]; then
        sleep 1
    fi
done

echo ""
echo "Step 3/3: Idle settle (${IDLE_SETTLE_SEC}s) so subsequent probes measure a cold-idle worker"
sleep "$IDLE_SETTLE_SEC"

WARMUP_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""
echo "============================================="
echo "  Warm-up complete"
echo "============================================="
echo "  First healthy:  $FIRST_HEALTHY"
echo "  Completed at:   $WARMUP_END"
echo "  Total attempts: $ATTEMPTS"
echo ""
echo "Next step:"
echo "  ./run-baseline-recheck.sh"
