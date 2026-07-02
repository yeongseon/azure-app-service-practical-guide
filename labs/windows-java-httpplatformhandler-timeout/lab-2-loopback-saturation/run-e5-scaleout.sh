#!/usr/bin/env bash
# shellcheck disable=SC2155
set -euo pipefail

# E5: Scale-out mitigation (L2-H5, optional).
#
# Scales the App Service plan from 1 to 2 instances, warms both,
# re-runs the E2 k6 load, then ALWAYS restores capacity to 1.
# The restore trap is non-negotiable - it runs even on abort.
#
# KQL verification deferred to verify.sh --experiment e5.
# Per design-proposal.md lines 445-466 (Oracle-approved).

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_METADATA="$SCRIPT_DIR/results/deploy-metadata.json"
readonly EXPERIMENT="e5"

# --- Parse arguments ---
RATE=""
DURATION="20m"
MAX_VUS=500
DRAIN=240

usage() {
    echo >&2 "Usage: $0 --rate <req/s> [--duration <k6-duration>] [--max-vus <int>] [--drain <seconds>]"
    echo >&2 ""
    echo >&2 "  --rate       Same rate used in E2 (required)"
    echo >&2 "  --duration   k6 run duration (optional, default: 20m)"
    echo >&2 "  --max-vus    k6 maxVUs (optional, default: 500)"
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
readonly RG="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['resourceGroup'])")"
readonly APP_NAME="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppName'])")"
readonly PLAN="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['appServicePlanName'])")"

if [[ -z "$HOSTNAME" || -z "$WEB_APP_RESOURCE_ID" || -z "$RG" || -z "$APP_NAME" || -z "$PLAN" ]]; then
    echo >&2 "ERROR: Could not parse required fields from deploy-metadata.json"
    exit 1
fi

readonly BASE_URL="https://${HOSTNAME}"
readonly RESULTS_DIR="$SCRIPT_DIR/results/e5/rate-${RATE}"
mkdir -p "$RESULTS_DIR"

readonly K6_SCRIPT="$SCRIPT_DIR/k6/constant-arrival.js"
if [[ ! -f "$K6_SCRIPT" ]]; then
    echo >&2 "ERROR: k6 script not found at $K6_SCRIPT"
    exit 1
fi

readonly STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Manifest enrichment variables (set before write_manifest call)
MANIFEST_STATUS=""
MANIFEST_ERROR_REASON=""
OBSERVED_INSTANCES=2
SCALED_INSTANCE_IDS="[]"

# --- CRITICAL: Always restore capacity to 1 instance on exit ---
restore_capacity() {
    echo >&2 ""
    echo >&2 "  Restoring App Service plan to 1 instance ..."
    az appservice plan update \
        --resource-group "$RG" \
        --name "$PLAN" \
        --number-of-workers 1 \
        --output none 2>/dev/null || echo >&2 "  WARNING: Failed to restore capacity. Manual fix required: az appservice plan update --resource-group $RG --name $PLAN --number-of-workers 1"
    echo >&2 "  Capacity restored to 1 instance."
}
trap restore_capacity EXIT

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
        'drain': $DRAIN,
        'scaledInstances': $OBSERVED_INSTANCES
    },
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': $artifact_files
}
status = '$MANIFEST_STATUS'
if status:
    manifest['status'] = status
    manifest['params']['planInstanceCount'] = 2
error_reason = '$MANIFEST_ERROR_REASON'
if error_reason:
    manifest['error'] = {'reason': error_reason}
instance_ids = json.loads('$SCALED_INSTANCE_IDS')
if instance_ids:
    manifest['scaledInstanceIds'] = instance_ids
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"
}

# --- Main execution ---
echo >&2 "=== E5: Scale-out mitigation ==="
echo >&2 "  Rate:        $RATE req/s"
echo >&2 "  Duration:    $DURATION"
echo >&2 "  Max VUs:     $MAX_VUS"
echo >&2 "  Drain:       ${DRAIN}s"
echo >&2 "  Hostname:    $HOSTNAME"
echo >&2 "  Plan:        $PLAN (rg=$RG)"
echo >&2 "  Results:     $RESULTS_DIR"
echo >&2 "  Started at:  $STARTED_AT"
echo >&2 ""

# Step 1: Scale plan to 2 instances
echo >&2 "  Step 1: Scaling plan to 2 instances ..."
az appservice plan update \
    --resource-group "$RG" \
    --name "$PLAN" \
    --number-of-workers 2 \
    --output none
echo >&2 "  Scale command issued."

# Step 2: Poll until 2 instances are healthy (max 5 min)
echo >&2 "  Step 2: Waiting for 2 healthy instances (polling every 15s, max 5 min) ..."
readonly POLL_INTERVAL=15
readonly POLL_MAX_WAIT=300
POLL_ELAPSED=0

while [[ $POLL_ELAPSED -lt $POLL_MAX_WAIT ]]; do
    INSTANCE_COUNT="$(az webapp instance list \
        --resource-group "$RG" \
        --name "$APP_NAME" \
        --output json 2>/dev/null | python3 -c "
import json, sys
instances = json.load(sys.stdin)
print(len(instances))
" 2>/dev/null || echo "0")"

    if [[ "$INSTANCE_COUNT" -ge 2 ]]; then
        echo >&2 "  Found $INSTANCE_COUNT instances. Scale-out complete."
        OBSERVED_INSTANCES="$INSTANCE_COUNT"
        SCALED_INSTANCE_IDS="$(az webapp instance list \
            --resource-group "$RG" \
            --name "$APP_NAME" \
            --query "[].name" \
            --output json 2>/dev/null || echo "[]")"
        break
    fi

    echo >&2 "    ... $INSTANCE_COUNT instance(s) found, waiting ${POLL_INTERVAL}s ..."
    sleep "$POLL_INTERVAL"
    POLL_ELAPSED=$((POLL_ELAPSED + POLL_INTERVAL))
done

if [[ $POLL_ELAPSED -ge $POLL_MAX_WAIT ]]; then
    echo >&2 ""
    echo >&2 "  ERROR: Scale-out readiness gate FAILED."
    echo >&2 "    Observed instances: ${INSTANCE_COUNT} (target: 2)"
    echo >&2 "    Poll timeout:      ${POLL_MAX_WAIT}s"
    echo >&2 "    Action: Re-run E5 after investigating App Service plan quota or region capacity."
    echo >&2 "            az appservice plan show --resource-group $RG --name $PLAN --query sku"
    echo >&2 ""
    OBSERVED_INSTANCES="$INSTANCE_COUNT"
    MANIFEST_STATUS="aborted_scaleout_readiness"
    MANIFEST_ERROR_REASON="2 instances not observed within ${POLL_MAX_WAIT}s"
    write_manifest
    exit 4
fi

# Step 3: Warm-up (20 requests to /actuator/health with 1s sleep, then 30s idle)
echo >&2 "  Step 3: Warming up both instances (20 × /actuator/health + 30s idle) ..."
for _w in $(seq 1 20); do
    curl --silent --output /dev/null --max-time 30 "${BASE_URL}/actuator/health" || true
    sleep 1
done
echo >&2 "    Warm-up requests done. Settling 30s ..."
sleep 30
echo >&2 "    Warm-up complete."

# Step 4: Run k6 with same rate as E2
echo >&2 ""
echo >&2 "  Step 4: Starting k6 (constant-arrival-rate at $RATE req/s for $DURATION) ..."
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

# Print k6 fidelity signals
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
" >&2
else
    echo >&2 "  WARNING: k6-summary.json not found. k6 may have failed."
fi

# Step 5: Drain wait
echo >&2 ""
echo >&2 "  Step 5: Draining ${DRAIN}s for backend completion + Log Analytics ingest ..."
sleep "$DRAIN"

# Write manifest (capacity restore happens via EXIT trap after this)
write_manifest

ENDED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo >&2 ""
echo >&2 "  E5 scale-out run at $RATE req/s complete. Drain finished."
echo >&2 "  Capacity will be restored to 1 instance on exit (trap)."
echo >&2 "  Run verify.sh --experiment e5 to check scale-out effect."
echo >&2 "  Ended at: $ENDED_AT"

# Print artifact path to stdout
echo "$RESULTS_DIR/manifest.json"
