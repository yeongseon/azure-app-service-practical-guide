#!/usr/bin/env bash
set -euo pipefail

# E3: Serialized /slow/240 probes after M1a web.config deploy.
#
# Fires N probes (default 3, max 5) and records timing. Does NOT
# auto-escalate to secondary canary — operator makes that decision.
#
# Per design-proposal.md lines 266-294 (Oracle-approved).

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_METADATA="$SCRIPT_DIR/results/deploy-metadata.json"
readonly EXPERIMENT="e3"
readonly PROBE_ENDPOINT="/slow/240"
readonly PROBE_DURATION=240
readonly BACKEND_BUFFER_SEC=10
readonly CURL_MAX_TIME=400

# --- Argument parsing ---
CANARY=""
PROBE_COUNT=3

while [[ $# -gt 0 ]]; do
    case "$1" in
        --canary)
            CANARY="$2"
            shift 2
            ;;
        --n)
            PROBE_COUNT="$2"
            shift 2
            ;;
        *)
            echo >&2 "Usage: $0 --canary <primary|secondary> [--n <1-5>]"
            exit 1
            ;;
    esac
done

if [[ -z "$CANARY" ]]; then
    echo >&2 "ERROR: --canary is required"
    echo >&2 "Usage: $0 --canary <primary|secondary> [--n <1-5>]"
    exit 1
fi

if [[ "$CANARY" != "primary" && "$CANARY" != "secondary" ]]; then
    echo >&2 "ERROR: --canary must be 'primary' or 'secondary', got: $CANARY"
    exit 1
fi

if [[ $PROBE_COUNT -lt 1 || $PROBE_COUNT -gt 5 ]]; then
    echo >&2 "ERROR: --n must be between 1 and 5, got: $PROBE_COUNT"
    exit 1
fi

# --- Load deploy metadata ---
if [[ ! -f "$DEPLOY_METADATA" ]]; then
    echo >&2 "ERROR: deploy-metadata.json not found at $DEPLOY_METADATA"
    echo >&2 "Run deploy.sh first to provision the Lab 2 environment."
    exit 1
fi

readonly HOSTNAME="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppHostname'])")"
readonly WEB_APP_RESOURCE_ID="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppResourceId'])")"

if [[ -z "$HOSTNAME" || -z "$WEB_APP_RESOURCE_ID" ]]; then
    echo >&2 "ERROR: Could not parse deploy-metadata.json fields"
    exit 1
fi

# --- Output directory ---
readonly RESULTS_DIR="$SCRIPT_DIR/results/$EXPERIMENT/$CANARY"
mkdir -p "$RESULTS_DIR"

readonly BASE_URL="https://${HOSTNAME}"
readonly STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- Manifest writer ---
write_manifest() {
    local ended_at
    ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    local artifact_files
    artifact_files="$(python3 -c "
import os, json
files = [f for f in os.listdir('$RESULTS_DIR') if f != 'manifest.json']
print(json.dumps(sorted(files)))
")"
    python3 -c "
import json
manifest = {
    'experiment': '$EXPERIMENT',
    'startedAt': '$STARTED_AT',
    'endedAt': '$ended_at',
    'params': {
        'canary': '$CANARY',
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

# --- Trap for graceful abort ---
PARTIAL=false
cleanup() {
    if [[ "$PARTIAL" == "true" ]]; then
        echo >&2 "WARN: Aborted mid-run. Partial artifacts in $RESULTS_DIR"
        write_manifest
    fi
}
trap cleanup SIGINT SIGTERM

# --- Main execution ---
echo >&2 "=== E3: M1a probes (canary=$CANARY, n=$PROBE_COUNT) ==="
echo >&2 "  Hostname:  $HOSTNAME"
echo >&2 "  Endpoint:  $PROBE_ENDPOINT"
echo >&2 "  Probes:    $PROBE_COUNT"
echo >&2 "  Pacing:    ~260s per probe (backend completion + ${BACKEND_BUFFER_SEC}s buffer)"
echo >&2 "  Started:   $STARTED_AT"
echo >&2 ""

PARTIAL=true

for i in $(seq 1 "$PROBE_COUNT"); do
    PROBE_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    PROBE_START_EPOCH="$(date +%s)"

    echo >&2 "  Probe $i/$PROBE_COUNT: GET ${BASE_URL}${PROBE_ENDPOINT} ..."

    set +e
    CURL_OUTPUT="$(curl --silent --show-error \
        --max-time "$CURL_MAX_TIME" \
        --write-out 'time_starttransfer: %{time_starttransfer}\ntime_total: %{time_total}\nhttp_code: %{http_code}\n' \
        --output "$RESULTS_DIR/probe-${i}-response.log" \
        "${BASE_URL}${PROBE_ENDPOINT}" 2>&1)"
    CURL_EXIT=$?
    set -e

    PROBE_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    PROBE_END_EPOCH="$(date +%s)"
    ELAPSED=$((PROBE_END_EPOCH - PROBE_START_EPOCH))

    HTTP_CODE="$(echo "$CURL_OUTPUT" | grep '^http_code:' | awk '{print $2}' || echo "000")"
    TIME_TOTAL="$(echo "$CURL_OUTPUT" | grep '^time_total:' | awk '{print $2}' || echo "$ELAPSED")"
    TIME_STARTTRANSFER="$(echo "$CURL_OUTPUT" | grep '^time_starttransfer:' | awk '{print $2}' || echo "0")"

    {
        echo "probe_index: $i"
        echo "canary: $CANARY"
        echo "request_url: ${BASE_URL}${PROBE_ENDPOINT}"
        echo "started_utc: $PROBE_START"
        echo "ended_utc: $PROBE_END"
        echo "elapsed_seconds: $ELAPSED"
        echo "curl_exit_code: $CURL_EXIT"
        echo "http_code: $HTTP_CODE"
        echo "time_starttransfer: $TIME_STARTTRANSFER"
        echo "time_total: $TIME_TOTAL"
    } > "$RESULTS_DIR/probe-${i}.log"

    echo >&2 "  Probe $i/$PROBE_COUNT: HTTP=$HTTP_CODE time_total=${TIME_TOTAL} starttransfer=${TIME_STARTTRANSFER} curl_exit=$CURL_EXIT elapsed=${ELAPSED}s"

    # Backend-completion pacing
    if [[ $i -lt $PROBE_COUNT ]]; then
        REMAINING=$((PROBE_DURATION - ELAPSED + BACKEND_BUFFER_SEC + 10))
        if [[ $REMAINING -lt 10 ]]; then
            REMAINING=10
        fi
        echo >&2 "  Pacing: sleeping ${REMAINING}s ..."
        sleep "$REMAINING"
    fi
done

PARTIAL=false
write_manifest

# --- Interpretation hints ---
echo >&2 ""
echo >&2 "=== E3 M1a probes complete (canary=$CANARY, n=$PROBE_COUNT) ==="
echo >&2 ""
echo >&2 "Interpretation:"
echo >&2 "  • If all $PROBE_COUNT probes have time_total ~60s → H3 confirmed (M1a operative)."
echo >&2 "  • If all $PROBE_COUNT probes have time_total ~230s → H3 falsified for canary=$CANARY."
if [[ "$CANARY" == "primary" ]]; then
    echo >&2 "    → Re-run with: ./run-e3-m1a-probes.sh --canary secondary"
fi
echo >&2 "  • If any other value (e.g. 120s), extend to 5 probes: --n 5"
echo >&2 ""
echo >&2 "verify.sh --experiment e3 will render this into the final report."
echo >&2 ""
echo >&2 "After E3 completes, revert to baseline:"
echo >&2 "  ./revert-baseline-artifact.sh"
