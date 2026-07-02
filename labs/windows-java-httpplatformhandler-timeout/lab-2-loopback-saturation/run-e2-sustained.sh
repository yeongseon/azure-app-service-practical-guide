#!/usr/bin/env bash
set -euo pipefail

# E2: Sustained saturation characterization (L2-H2).
#
# Runs k6 at the above-threshold rate (from E1 result) for 20 min to
# compute stable pct_64 and TimeTaken percentiles. Detects
# dropped_iterations > 0 and suggests re-run with higher maxVUs.
#
# KQL verification deferred to verify.sh --experiment e2.
# Per design-proposal.md lines 295-337 (Oracle-approved).

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_METADATA="$SCRIPT_DIR/results/deploy-metadata.json"
readonly EXPERIMENT="e2"

# --- Parse arguments ---
RATE=""
DURATION="20m"
MAX_VUS=500
DRAIN=240

usage() {
    echo >&2 "Usage: $0 --rate <req/s> [--duration <k6-duration>] [--max-vus <int>] [--drain <seconds>]"
    echo >&2 ""
    echo >&2 "  --rate       Above-threshold arrival rate from E1 (required, e.g. 0.9)"
    echo >&2 "  --duration   k6 run duration (optional, default: 20m)"
    echo >&2 "  --max-vus    k6 maxVUs (optional, default: 500; use 800 if first run dropped)"
    echo >&2 "  --drain      Post-k6 drain wait in seconds (optional, default: 240)"
    echo >&2 ""
    echo >&2 "Example: $0 --rate 0.9"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rate) RATE="$2"; shift 2 ;;
        --duration) DURATION="$2"; shift 2 ;;
        --max-vus) MAX_VUS="$2"; shift 2 ;;
        --drain) DRAIN="$2"; shift 2 ;;
        *) echo >&2 "ERROR: Unknown argument: $1"; usage ;;
    esac
done

if [[ -z "$RATE" ]]; then
    echo >&2 "ERROR: --rate is required."
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
readonly RESULTS_DIR="$SCRIPT_DIR/results/e2/rate-${RATE}"
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
    'runId': None,
    'startedAt': '$STARTED_AT',
    'endedAt': '$ended_at',
    'params': {
        'rate': $RATE,
        'duration': '$DURATION',
        'maxVUs': $MAX_VUS,
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
echo >&2 "=== E2: Sustained saturation characterization ==="
echo >&2 "  Rate:        $RATE req/s"
echo >&2 "  Duration:    $DURATION"
echo >&2 "  Max VUs:     $MAX_VUS"
echo >&2 "  Drain:       ${DRAIN}s"
echo >&2 "  Hostname:    $HOSTNAME"
echo >&2 "  Results:     $RESULTS_DIR"
echo >&2 "  Started at:  $STARTED_AT"
echo >&2 ""

PARTIAL=true

# k6 env vars match Agent 2's contract: BASE_URL, RATE, DURATION, MAX_VUS, PREALLOCATED_VUS
echo >&2 "  Starting k6 (constant-arrival-rate at $RATE req/s for $DURATION, maxVUs=$MAX_VUS) ..."
(
    cd "$RESULTS_DIR"
    k6 run \
        --env BASE_URL="$BASE_URL" \
        --env RATE="$RATE" \
        --env DURATION="$DURATION" \
        --env MAX_VUS="$MAX_VUS" \
        --env PREALLOCATED_VUS="300" \
        "$K6_SCRIPT" 2>&1 | tee "$RESULTS_DIR/k6-stdout.log"
)

# k6 handleSummary writes summary.json to the current working directory
if [[ -f "$RESULTS_DIR/summary.json" ]]; then
    mv "$RESULTS_DIR/summary.json" "$RESULTS_DIR/k6-summary.json"
elif [[ -f "summary.json" ]]; then
    mv "summary.json" "$RESULTS_DIR/k6-summary.json"
fi

# Print k6 fidelity signals and detect dropped_iterations
echo >&2 ""
echo >&2 "  === k6 fidelity signals ==="
DROPPED_ITERATIONS=0
if [[ -f "$RESULTS_DIR/k6-summary.json" ]]; then
    DROPPED_ITERATIONS="$(python3 -c "
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

# Output dropped count to stdout for bash capture
print(int(dropped))
")"
else
    echo >&2 "  WARNING: k6-summary.json not found. k6 may have failed."
fi

# Warn if dropped_iterations > 0 (design-proposal line 301)
if [[ "$DROPPED_ITERATIONS" -gt 0 ]]; then
    echo >&2 ""
    echo >&2 "  ╔══════════════════════════════════════════════════════════════╗"
    echo >&2 "  ║  WARNING: E2 dropped_iterations > 0 ($DROPPED_ITERATIONS dropped).            ║"
    echo >&2 "  ║  Re-run with --max-vus 800 for higher fidelity.            ║"
    echo >&2 "  ║                                                              ║"
    echo >&2 "  ║  Command:                                                    ║"
    echo >&2 "  ║    bash run-e2-sustained.sh --rate $RATE --max-vus 800    ║"
    echo >&2 "  ╚══════════════════════════════════════════════════════════════╝"
fi

# Drain wait
echo >&2 ""
echo >&2 "  k6 finished. Draining ${DRAIN}s for backend completion + Log Analytics ingest ..."
sleep "$DRAIN"

PARTIAL=false

# Write manifest
write_manifest

ENDED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo >&2 ""
echo >&2 "  E2 sustained run at $RATE req/s complete. Drain finished."
echo >&2 "  Run verify.sh --experiment e2 to check characterization."
echo >&2 "  Ended at: $ENDED_AT"

# Print artifact path to stdout
echo "$RESULTS_DIR/manifest.json"
