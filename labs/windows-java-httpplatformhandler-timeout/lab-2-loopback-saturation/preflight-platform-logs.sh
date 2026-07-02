#!/usr/bin/env bash
set -euo pipefail

# E4 Preflight: Verify AppServicePlatformLogs surfaces Auto-Heal events.
#
# Two modes:
#   Default: Redeploy Bicep with actionType=LogEvent, print operator instructions.
#   --kql-only: Query Log Analytics for AutoHealing events, emit PROCEED/UNVERIFIABLE.
#
# Per design-proposal.md lines 343-366, Residual C (Oracle-approved).

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_METADATA="$SCRIPT_DIR/results/deploy-metadata.json"
readonly EXPERIMENT="preflight"

# --- Argument parsing ---
KQL_ONLY=false
if [[ "${1:-}" == "--kql-only" ]]; then
    KQL_ONLY=true
fi

# --- Load deploy metadata ---
if [[ ! -f "$DEPLOY_METADATA" ]]; then
    echo >&2 "ERROR: deploy-metadata.json not found at $DEPLOY_METADATA"
    echo >&2 "Run deploy.sh first to provision the Lab 2 environment."
    exit 1
fi

readonly APP="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppName'])")"
readonly HOSTNAME="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppHostname'])")"
readonly WEB_APP_RESOURCE_ID="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['webAppResourceId'])")"
readonly RG="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['resourceGroup'])")"
readonly WORKSPACE_ID="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['logAnalyticsWorkspaceId'])")"
readonly BASE_NAME="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['baseName'])")"

if [[ -z "$APP" || -z "$HOSTNAME" || -z "$RG" || -z "$WORKSPACE_ID" ]]; then
    echo >&2 "ERROR: Could not parse deploy-metadata.json fields"
    exit 1
fi

# --- Output directory ---
readonly RESULTS_DIR="$SCRIPT_DIR/results/$EXPERIMENT"
mkdir -p "$RESULTS_DIR"

readonly STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
readonly BICEP_FILE="${SCRIPT_DIR}/main.bicep"

# --- Write manifest helper ---
write_manifest() {
    local status="$1"
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
    'experiment': 'preflight',
    'startedAt': '$STARTED_AT',
    'endedAt': '$ended_at',
    'params': {
        'mode': '$( [[ "$KQL_ONLY" == "true" ]] && echo "kql-only" || echo "deploy" )',
        'autoHealActionType': 'LogEvent'
    },
    'preflight-status': '$status',
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': $artifact_files
}
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"
}

if [[ "$KQL_ONLY" == "true" ]]; then
    # --- KQL-only mode: query for AutoHealing events ---
    echo >&2 "=== E4 Preflight: KQL-only mode ==="
    echo >&2 "  Waiting 3 min + 60s for Log Analytics ingest ..."
    sleep 240

    echo >&2 "  Querying AppServicePlatformLogs for AutoHealing events ..."

    KQL_QUERY="AppServicePlatformLogs | where _ResourceId =~ \"${WEB_APP_RESOURCE_ID}\" | where TimeGenerated between (ago(30m) .. now()) | where OperationName startswith \"AutoHealing\" | project TimeGenerated, OperationName, Level, Message | order by TimeGenerated asc | limit 20"

    set +e
    KQL_RESULT="$(az monitor log-analytics query \
        --workspace "$WORKSPACE_ID" \
        --analytics-query "$KQL_QUERY" \
        --output json 2>&1)"
    KQL_EXIT=$?
    set -e

    echo "$KQL_RESULT" > "$RESULTS_DIR/kql-result.json"

    if [[ $KQL_EXIT -ne 0 ]]; then
        echo >&2 "  WARN: KQL query failed (exit $KQL_EXIT)"
        echo >&2 "  Output saved to: $RESULTS_DIR/kql-result.json"
        write_manifest "UNVERIFIABLE"
        echo >&2 ""
        echo >&2 "UNVERIFIABLE: KQL query failed. E4 will be marked unverifiable per Residual C."
        exit 0
    fi

    ROW_COUNT="$(python3 -c "
import json, sys
try:
    data = json.loads('''$KQL_RESULT''')
    if isinstance(data, list):
        print(len(data))
    else:
        print(0)
except:
    print(0)
")"

    echo >&2 "  Rows returned: $ROW_COUNT"
    echo >&2 ""

    if [[ "$ROW_COUNT" -gt 0 ]]; then
        echo >&2 "PROCEED: $ROW_COUNT AutoHealing events found. E4 verifiable."
        write_manifest "PROCEED"
    else
        echo >&2 "UNVERIFIABLE: 0 rows. E4 will be marked unverifiable per design Residual C."
        echo >&2 "Both H4 branches will be [Unknown]. M2 verdict: unverifiable via CLI-only tooling."
        write_manifest "UNVERIFIABLE"
    fi

    echo >&2 ""
    echo >&2 "Next step:"
    echo >&2 "  ./enable-autoheal-m2.sh"
    exit 0
fi

# --- Default mode: Bicep redeploy with LogEvent ---
echo >&2 "=== E4 Preflight: Deploy Auto-Heal with actionType=LogEvent ==="
echo >&2 "  App:     $APP"
echo >&2 "  RG:      $RG"
echo >&2 "  Started: $STARTED_AT"
echo >&2 ""

echo >&2 "  Deploying Bicep with enableCustomAutoHeal=true, autoHealActionType=LogEvent ..."

DEPLOYMENT_NAME="lab2-preflight-$(date -u +%Y%m%dT%H%M%SZ)"

set +e
DEPLOY_OUTPUT="$(az deployment group create \
    --resource-group "$RG" \
    --name "$DEPLOYMENT_NAME" \
    --template-file "$BICEP_FILE" \
    --parameters \
        baseName="$BASE_NAME" \
        enableCustomAutoHeal=true \
        autoHealActionType=LogEvent \
        planInstanceCount=1 \
    --query 'properties.provisioningState' \
    --output tsv 2>&1)"
DEPLOY_EXIT=$?
set -e

echo "$DEPLOY_OUTPUT" > "$RESULTS_DIR/deploy-output.txt"

if [[ $DEPLOY_EXIT -ne 0 ]]; then
    echo >&2 "  ERROR: Bicep deployment failed (exit $DEPLOY_EXIT)"
    echo >&2 "  Output: $DEPLOY_OUTPUT"
    write_manifest "NOT_YET_QUERIED"
    exit 1
fi

echo >&2 "  Deployment: $DEPLOY_OUTPUT"

# --- Post-deploy warmup ---
echo >&2 "  Warming up: polling /actuator/health (up to 300s) ..."

WARMUP_OK=false
for attempt in $(seq 1 60); do
    set +e
    HEALTH_CODE="$(curl --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 10 "https://${HOSTNAME}/actuator/health")"
    set -e
    if [[ "$HEALTH_CODE" == "200" ]]; then
        WARMUP_OK=true
        echo >&2 "  Health check passed on attempt $attempt"
        break
    fi
    sleep 5
done

if [[ "$WARMUP_OK" != "true" ]]; then
    echo >&2 "  WARN: /actuator/health did not return 200 within 300s"
fi

write_manifest "NOT_YET_QUERIED"

echo >&2 ""
echo >&2 "=== E4 Preflight: LogEvent Auto-Heal deployed ==="
echo >&2 ""
echo >&2 "To complete preflight verification:"
echo >&2 ""
echo >&2 "  1. Generate .64 events by running the sustained load at the E1-positive rate:"
echo >&2 "     ./run-e2-sustained.sh --rate <E1-first-positive-rate> --duration 8m"
echo >&2 ""
echo >&2 "  2. After ~8 min of load completes, query for Auto-Heal events:"
echo >&2 "     ./preflight-platform-logs.sh --kql-only"
echo >&2 ""
echo >&2 "  The --kql-only mode waits 3+1 min for ingest, then prints PROCEED or UNVERIFIABLE."
