#!/usr/bin/env bash
set -euo pipefail

# E4: 20-min sustained load with Auto-Heal M2 (Recycle) enabled.
#
# Same k6 invocation as run-e2-sustained.sh but with Auto-Heal active.
# 20 min duration for direct E2 comparability. 4 min drain after k6 stops.
#
# Per design-proposal.md lines 401-436 (Oracle-approved).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly DEPLOY_METADATA="$SCRIPT_DIR/results/deploy-metadata.json"
readonly EXPERIMENT="e4"

# --- Argument parsing ---
RATE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rate)
            RATE="$2"
            shift 2
            ;;
        *)
            echo >&2 "Usage: $0 --rate <req/s>"
            echo >&2 "  --rate: Arrival rate in requests/second (same as E2 for comparability)"
            exit 1
            ;;
    esac
done

if [[ -z "$RATE" ]]; then
    echo >&2 "ERROR: --rate is required"
    echo >&2 "Usage: $0 --rate <req/s>"
    echo >&2 "Use the same rate as E2 for direct comparison."
    exit 1
fi

# --- Load deploy metadata ---
if [[ ! -f "$DEPLOY_METADATA" ]]; then
    echo >&2 "ERROR: deploy-metadata.json not found at $DEPLOY_METADATA"
    echo >&2 "Run deploy.sh first to provision the Lab 2 environment."
    exit 1
fi

APP="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppName'])")"
readonly APP
HOSTNAME="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppHostname'])")"
readonly HOSTNAME
WEB_APP_RESOURCE_ID="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppResourceId'])")"
readonly WEB_APP_RESOURCE_ID
RG="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['resourceGroup'])")"
readonly RG

if [[ -z "$APP" || -z "$HOSTNAME" || -z "$RG" ]]; then
    echo >&2 "ERROR: Could not parse deploy-metadata.json fields"
    exit 1
fi

readonly DURATION="20m"
readonly DRAIN_SEC=240
readonly K6_SCRIPT="$SCRIPT_DIR/k6/constant-arrival.js"
readonly BASE_URL="https://${HOSTNAME}"

# --- Output directory ---
readonly RESULTS_DIR="$SCRIPT_DIR/results/$EXPERIMENT/rate-${RATE}"
mkdir -p "$RESULTS_DIR"

STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
readonly STARTED_AT

# --- Preflight: verify Auto-Heal is enabled ---
echo >&2 "=== E4: M2 Auto-Heal load run ==="
echo >&2 "  Preflight: checking autoHealEnabled ..."

AUTOHEAL_ENABLED="$(az webapp config show \
    --resource-group "$RG" \
    --name "$APP" \
    --query 'siteConfig.autoHealEnabled' \
    --output tsv)"

if [[ "$AUTOHEAL_ENABLED" != "true" ]]; then
    echo >&2 "ERROR: autoHealEnabled=$AUTOHEAL_ENABLED (expected true)"
    echo >&2 "Run ./enable-autoheal-m2.sh first."
    exit 1
fi
echo >&2 "  autoHealEnabled: true ✓"

echo >&2 ""
echo >&2 "  App:      $APP"
echo >&2 "  Hostname: $HOSTNAME"
echo >&2 "  Rate:     $RATE req/s"
echo >&2 "  Duration: $DURATION"
echo >&2 "  Drain:    ${DRAIN_SEC}s"
echo >&2 "  Started:  $STARTED_AT"
echo >&2 ""

# --- Verify k6 script exists ---
if [[ ! -f "$K6_SCRIPT" ]]; then
    echo >&2 "ERROR: k6 script not found at: $K6_SCRIPT"
    echo >&2 "Agent 2 must create the k6 script first."
    exit 1
fi

# --- Run k6 ---
echo >&2 "  Starting k6: $DURATION at $RATE req/s ..."

K6_SUMMARY="$RESULTS_DIR/k6-summary.json"
K6_STDOUT="$RESULTS_DIR/k6-stdout.log"

set +e
k6 run \
    --env "BASE_URL=${BASE_URL}" \
    --env "RATE=${RATE}" \
    --env "DURATION=${DURATION}" \
    --env "MAX_VUS=500" \
    --env "PREALLOCATED_VUS=300" \
    --out "json=$RESULTS_DIR/k6-raw.json" \
    --summary-export "$K6_SUMMARY" \
    "$K6_SCRIPT" > "$K6_STDOUT" 2>&1
K6_EXIT=$?
set -e

K6_ENDED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo >&2 "  k6 finished (exit $K6_EXIT) at $K6_ENDED_AT"

if [[ $K6_EXIT -ne 0 ]]; then
    echo >&2 "  WARN: k6 exited non-zero ($K6_EXIT). Check $K6_STDOUT"
fi

# --- Drain period ---
echo >&2 "  Drain: sleeping ${DRAIN_SEC}s for in-flight requests to complete ..."
sleep "$DRAIN_SEC"

# --- Write manifest ---
ENDED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ARTIFACT_FILES="$(python3 -c "
import os, json
files = [f for f in os.listdir('$RESULTS_DIR') if f != 'manifest.json']
print(json.dumps(sorted(files)))
")"

python3 -c "
import json
manifest = {
    'experiment': 'e4',
    'startedAt': '$STARTED_AT',
    'endedAt': '$ENDED_AT',
    'params': {
        'rate': $RATE,
        'duration': '$DURATION',
        'drainSeconds': $DRAIN_SEC,
        'autoHealEnabled': True,
        'autoHealActionType': 'Recycle',
        'k6ExitCode': $K6_EXIT
    },
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': $ARTIFACT_FILES
}
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"

echo >&2 ""
echo >&2 "=== E4: M2 Auto-Heal load run complete ==="
echo >&2 "  Rate:    $RATE req/s"
echo >&2 "  k6 exit: $K6_EXIT"
echo >&2 "  Ended:   $ENDED_AT"
echo >&2 ""
echo >&2 "verify.sh --experiment e4 will query:"
echo >&2 "  • AppServicePlatformLogs for AutoHealing recycle events"
echo >&2 "  • AppServiceHTTPLogs pct_64 timeline at 30s bins"
echo >&2 ""
echo >&2 "Next step:"
echo >&2 "  ./verify.sh --experiment e4"
