#!/usr/bin/env bash
set -euo pipefail

# Pre-E1: Baseline re-verification (Blocker 9).
#
# Confirms the Lab 2 environment still produces the Lab 1 signature
# (500/121/0 @ ~230 s) before any load runs. Fires 3 serialized
# /slow/240 probes with backend-completion + 10 s pacing.
#
# This script does NOT query KQL - verification is deferred to
# verify.sh --experiment pre-e1. Separation of concerns: run-*.sh
# collects raw data; verify.sh interprets.
#
# Per design-proposal.md lines 98-133 (Oracle-approved).

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_METADATA="$SCRIPT_DIR/results/deploy-metadata.json"
readonly EXPERIMENT="pre-e1"
readonly PROBE_ENDPOINT="/slow/240"
readonly PROBE_COUNT=3
readonly PROBE_DURATION=240
readonly BACKEND_BUFFER_SEC=10
readonly LOG_ANALYTICS_BUFFER_SEC=30

# --- Load deploy metadata ---
if [[ ! -f "$DEPLOY_METADATA" ]]; then
    echo >&2 "ERROR: deploy-metadata.json not found at $DEPLOY_METADATA"
    echo >&2 "Run deploy.sh first to provision the Lab 2 environment."
    exit 1
fi

readonly HOSTNAME="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppHostname'])")"
readonly WEB_APP_RESOURCE_ID="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppResourceId'])")"

if [[ -z "$HOSTNAME" || -z "$WEB_APP_RESOURCE_ID" ]]; then
    echo >&2 "ERROR: Could not parse webAppHostname or webAppResourceId from deploy-metadata.json"
    exit 1
fi

readonly RESULTS_DIR="$SCRIPT_DIR/results/$EXPERIMENT"
mkdir -p "$RESULTS_DIR"

readonly BASE_URL="https://${HOSTNAME}"
readonly STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- Trap for graceful abort ---
PARTIAL=false
cleanup() {
    if [[ "$PARTIAL" == "true" ]]; then
        echo >&2 "WARN: Aborted mid-run. Partial artifacts in $RESULTS_DIR"
        write_manifest
    fi
}
trap cleanup SIGINT SIGTERM

# --- curl timing format (inline heredoc) ---
readonly CURL_FORMAT_FILE="$RESULTS_DIR/curl-format.txt"
cat > "$CURL_FORMAT_FILE" <<'EOF'
time_namelookup:  %{time_namelookup}s\n
time_connect:     %{time_connect}s\n
time_appconnect:  %{time_appconnect}s\n
time_pretransfer: %{time_pretransfer}s\n
time_starttransfer: %{time_starttransfer}s\n
time_total:       %{time_total}s\n
http_code:        %{http_code}\n
EOF

# --- Utility: write manifest.json ---
write_manifest() {
    local ended_at
    ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    local artifact_files="[]"
    artifact_files="$(python3 -c "
import os, json
files = [f for f in os.listdir('$RESULTS_DIR') if f != 'manifest.json']
print(json.dumps(sorted(files)))
")"
    python3 -c "
import json
manifest = {
    'experiment': '$EXPERIMENT',
    'runId': None,
    'startedAt': '$STARTED_AT',
    'endedAt': '$ended_at',
    'params': {
        'probeCount': $PROBE_COUNT,
        'probeDuration': $PROBE_DURATION,
        'endpoint': '$PROBE_ENDPOINT'
    },
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': $artifact_files
}
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"
}

# --- Main execution ---
echo >&2 "=== Pre-E1: Baseline re-verification ==="
echo >&2 "  Hostname:    $HOSTNAME"
echo >&2 "  Endpoint:    $PROBE_ENDPOINT"
echo >&2 "  Probes:      $PROBE_COUNT"
echo >&2 "  Pacing:      ~260s per probe (240s backend + ${BACKEND_BUFFER_SEC}s buffer + 10s)"
echo >&2 "  Started at:  $STARTED_AT"
echo >&2 ""

PARTIAL=true
ALL_OK=true

for i in $(seq 1 "$PROBE_COUNT"); do
    PROBE_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    PROBE_START_EPOCH="$(date +%s)"

    echo >&2 "  Probe $i/$PROBE_COUNT: sending GET ${BASE_URL}${PROBE_ENDPOINT} ..."

    # Fire the probe; capture timing and response
    set +e
    CURL_OUTPUT="$(curl --silent --show-error \
        --max-time 400 \
        --write-out '@'"$CURL_FORMAT_FILE" \
        --output "$RESULTS_DIR/probe-${i}-response.log" \
        "${BASE_URL}${PROBE_ENDPOINT}" 2>&1)"
    CURL_EXIT=$?
    set -e

    PROBE_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    PROBE_END_EPOCH="$(date +%s)"
    ELAPSED=$((PROBE_END_EPOCH - PROBE_START_EPOCH))

    # Save timestamp log
    {
        echo "probe_index: $i"
        echo "request_url: ${BASE_URL}${PROBE_ENDPOINT}"
        echo "started_utc: $PROBE_START"
        echo "ended_utc: $PROBE_END"
        echo "elapsed_seconds: $ELAPSED"
        echo "curl_exit_code: $CURL_EXIT"
        echo "---curl-timing---"
        echo "$CURL_OUTPUT"
    } > "$RESULTS_DIR/probe-${i}-timestamp.log"

    # Extract http_code from curl output
    HTTP_CODE="$(echo "$CURL_OUTPUT" | grep '^http_code:' | awk '{print $2}' || echo "000")"
    TIME_TOTAL="$(echo "$CURL_OUTPUT" | grep '^time_total:' | awk '{print $2}' | tr -d 's' || echo "$ELAPSED")"

    echo >&2 "  Probe $i/$PROBE_COUNT: HTTP=$HTTP_CODE time_total=${TIME_TOTAL} curl_exit=$CURL_EXIT elapsed=${ELAPSED}s"

    # Basic sanity: if http_code is not 500, baseline may have drifted
    if [[ "$HTTP_CODE" != "500" ]]; then
        ALL_OK=false
        echo >&2 "  WARN: Probe $i returned HTTP $HTTP_CODE (expected 500)"
    fi

    # Backend-completion pacing: wait until backend hold completes + buffer
    # Formula: remaining = PROBE_DURATION - client_elapsed + BACKEND_BUFFER_SEC + 10s idle
    if [[ $i -lt $PROBE_COUNT ]]; then
        REMAINING=$((PROBE_DURATION - ELAPSED + BACKEND_BUFFER_SEC + 10))
        if [[ $REMAINING -lt 10 ]]; then
            REMAINING=10
        fi
        echo >&2 "  Pacing: sleeping ${REMAINING}s (backend completion + buffer) ..."
        sleep "$REMAINING"
    fi
done

# Wait for Log Analytics ingest buffer
echo >&2 ""
echo >&2 "  All probes complete. Sleeping ${LOG_ANALYTICS_BUFFER_SEC}s for Log Analytics ingest buffer ..."
sleep "$LOG_ANALYTICS_BUFFER_SEC"

PARTIAL=false

# Write manifest
write_manifest

# Final verdict (client-side only; server-side check is verify.sh's job)
echo >&2 ""
if [[ "$ALL_OK" == "true" ]]; then
    echo >&2 "OK - All $PROBE_COUNT probes returned HTTP 500 (expected baseline signature)."
    echo >&2 "Probes complete. Run verify.sh --experiment pre-e1 to check baseline signature."
    # Print artifact paths to stdout
    echo "$RESULTS_DIR/manifest.json"
    exit 0
else
    echo >&2 "FAIL - baseline drifted: one or more probes returned unexpected HTTP code."
    echo >&2 "Investigate deployment drift before running any load experiment."
    echo "$RESULTS_DIR/manifest.json"
    exit 1
fi
