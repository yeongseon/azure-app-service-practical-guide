#!/usr/bin/env bash
set -euo pipefail

# E1: Arrival-rate first-positive search (L2-H1, Blocker 2).
#
# Runs k6 constant-arrival at a single rate for 15 min, waits 4 min drain,
# saves fidelity JSON. One invocation per rate; the operator calls this
# script 4 times with --rate {0.5, 0.75, 0.9, 1.05} and --run-id {1..4}.
#
# KQL verification deferred to verify.sh --experiment e1 --run-id <n>.
# Per design-proposal.md lines 135-212 (Oracle-approved).

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_METADATA="$SCRIPT_DIR/results/deploy-metadata.json"
readonly EXPERIMENT="e1"

# --- Parse arguments ---
RATE=""
RUN_ID=""
DURATION="15m"
DRAIN=240

usage() {
    echo >&2 "Usage: $0 --rate <req/s> --run-id <n> [--duration <k6-duration>] [--drain <seconds>]"
    echo >&2 ""
    echo >&2 "  --rate       Target arrival rate in req/s (required, e.g. 0.5)"
    echo >&2 "  --run-id     Integer run identifier (required, e.g. 1)"
    echo >&2 "  --duration   k6 run duration (optional, default: 15m)"
    echo >&2 "  --drain      Post-k6 drain wait in seconds (optional, default: 240)"
    echo >&2 ""
    echo >&2 "Example: $0 --rate 0.5 --run-id 1"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rate) RATE="$2"; shift 2 ;;
        --run-id) RUN_ID="$2"; shift 2 ;;
        --duration) DURATION="$2"; shift 2 ;;
        --drain) DRAIN="$2"; shift 2 ;;
        *) echo >&2 "ERROR: Unknown argument: $1"; usage ;;
    esac
done

if [[ -z "$RATE" || -z "$RUN_ID" ]]; then
    echo >&2 "ERROR: --rate and --run-id are required."
    usage
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
    echo >&2 "ERROR: Could not parse webAppHostname or webAppResourceId from deploy-metadata.json"
    exit 1
fi

readonly BASE_URL="https://${HOSTNAME}"
readonly RESULTS_DIR="$SCRIPT_DIR/results/e1/run-${RUN_ID}-rate-${RATE}"
mkdir -p "$RESULTS_DIR"

readonly K6_SCRIPT="$SCRIPT_DIR/k6/constant-arrival.js"
if [[ ! -f "$K6_SCRIPT" ]]; then
    echo >&2 "ERROR: k6 script not found at $K6_SCRIPT"
    exit 1
fi

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

# --- Utility: write manifest.json ---
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
    'runId': $RUN_ID,
    'startedAt': '$STARTED_AT',
    'endedAt': '$ended_at',
    'params': {
        'rate': $RATE,
        'duration': '$DURATION',
        'drain': $DRAIN
    },
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': $artifact_files
}
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"
}

# --- Main execution ---
echo >&2 "=== E1: Arrival-rate first-positive search ==="
echo >&2 "  Run ID:      $RUN_ID"
echo >&2 "  Rate:        $RATE req/s"
echo >&2 "  Duration:    $DURATION"
echo >&2 "  Drain:       ${DRAIN}s"
echo >&2 "  Hostname:    $HOSTNAME"
echo >&2 "  Results:     $RESULTS_DIR"
echo >&2 "  Started at:  $STARTED_AT"
echo >&2 ""

PARTIAL=true

# Run k6 with env vars matching Agent 2's contract:
#   BASE_URL, RATE, DURATION, MAX_VUS, PREALLOCATED_VUS
echo >&2 "  Starting k6 (constant-arrival-rate at $RATE req/s for $DURATION) ..."
(
    cd "$RESULTS_DIR"
    k6 run \
        --env BASE_URL="$BASE_URL" \
        --env RATE="$RATE" \
        --env DURATION="$DURATION" \
        --env MAX_VUS="500" \
        --env PREALLOCATED_VUS="300" \
        "$K6_SCRIPT" 2>&1 | tee "$RESULTS_DIR/k6-stdout.log"
)

# k6 handleSummary writes summary.json to the current working directory
if [[ -f "$RESULTS_DIR/summary.json" ]]; then
    mv "$RESULTS_DIR/summary.json" "$RESULTS_DIR/k6-summary.json"
elif [[ -f "summary.json" ]]; then
    mv "summary.json" "$RESULTS_DIR/k6-summary.json"
fi

# Print k6 fidelity signals (Oracle recommendation 2)
echo >&2 ""
echo >&2 "  === k6 fidelity signals ==="
if [[ -f "$RESULTS_DIR/k6-summary.json" ]]; then
    python3 -c "
import json, sys

with open('$RESULTS_DIR/k6-summary.json') as f:
    summary = json.load(f)

metrics = summary.get('metrics', {})

iterations = metrics.get('iterations', {}).get('values', {}).get('count', 'N/A')
dropped = metrics.get('dropped_iterations', {}).get('values', {}).get('count', 0)
http_reqs = metrics.get('http_reqs', {}).get('values', {}).get('count', 'N/A')
vus_max = metrics.get('vus_max', {}).get('values', {}).get('max', 'N/A')
http_failed = metrics.get('http_req_failed', {}).get('values', {}).get('passes', 'N/A')

print(f'  iterations:        {iterations}', file=sys.stderr)
print(f'  dropped_iterations: {dropped}', file=sys.stderr)
print(f'  http_reqs:         {http_reqs}', file=sys.stderr)
print(f'  vus_max:           {vus_max}', file=sys.stderr)
print(f'  http_req_failed:   {http_failed}', file=sys.stderr)

if int(dropped) > 0:
    print(f'', file=sys.stderr)
    print(f'  WARNING: dropped_iterations > 0. Achieved rate is below target.', file=sys.stderr)
    print(f'  Consider re-running with higher maxVUs.', file=sys.stderr)
"
else
    echo >&2 "  WARNING: k6-summary.json not found. k6 may have failed."
fi

# Drain wait (4 min = 240s default per design-proposal Blocker 2)
echo >&2 ""
echo >&2 "  k6 finished. Draining ${DRAIN}s for backend completion + Log Analytics ingest ..."
sleep "$DRAIN"

PARTIAL=false

# Write manifest
write_manifest

ENDED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo >&2 ""
echo >&2 "  E1 run $RUN_ID at $RATE req/s complete. Drain finished."
echo >&2 "  Run verify.sh --experiment e1 --run-id $RUN_ID to check threshold."
echo >&2 "  Ended at: $ENDED_AT"

# Print artifact path to stdout
echo "$RESULTS_DIR/manifest.json"
