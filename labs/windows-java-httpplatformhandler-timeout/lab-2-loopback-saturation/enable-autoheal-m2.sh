#!/usr/bin/env bash
# shellcheck disable=SC2155
set -euo pipefail

# E4: Enable Auto-Heal with actionType=Recycle (M2 mitigation).
#
# Redeploys Bicep with the fully-scoped Auto-Heal rule targeting
# 500/121/64 on /slow/240. Verifies the rule is active before E4 load.
#
# Per design-proposal.md lines 401-405 (Oracle-approved).

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_METADATA="$SCRIPT_DIR/results/deploy-metadata.json"
readonly EXPERIMENT="e4"

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
readonly BASE_NAME="$(python3 -c "import json; d=json.load(open('$DEPLOY_METADATA')); print(d['baseName'])")"

if [[ -z "$APP" || -z "$HOSTNAME" || -z "$RG" || -z "$BASE_NAME" ]]; then
    echo >&2 "ERROR: Could not parse deploy-metadata.json fields"
    exit 1
fi

readonly BICEP_FILE="${SCRIPT_DIR}/main.bicep"
readonly RESULTS_DIR="$SCRIPT_DIR/results/$EXPERIMENT"
mkdir -p "$RESULTS_DIR"

readonly STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo >&2 "=== E4: Enable Auto-Heal M2 (actionType=Recycle) ==="
echo >&2 "  App:     $APP"
echo >&2 "  RG:      $RG"
echo >&2 "  Started: $STARTED_AT"
echo >&2 ""

# --- Bicep redeploy with Recycle ---
echo >&2 "  Deploying Bicep with enableCustomAutoHeal=true, autoHealActionType=Recycle ..."

DEPLOYMENT_NAME="lab2-autoheal-$(date -u +%Y%m%dT%H%M%SZ)"

az deployment group create \
    --resource-group "$RG" \
    --name "$DEPLOYMENT_NAME" \
    --template-file "$BICEP_FILE" \
    --parameters \
        baseName="$BASE_NAME" \
        enableCustomAutoHeal=true \
        autoHealActionType=Recycle \
        planInstanceCount=1 \
    --output none

echo >&2 "  Deployment complete."

# --- Verify autoHealEnabled ---
echo >&2 "  Verifying autoHealEnabled ..."

AUTOHEAL_ENABLED="$(az webapp config show \
    --resource-group "$RG" \
    --name "$APP" \
    --query 'siteConfig.autoHealEnabled' \
    --output tsv)"

if [[ "$AUTOHEAL_ENABLED" != "true" ]]; then
    echo >&2 "ERROR: autoHealEnabled=$AUTOHEAL_ENABLED (expected true)"
    echo >&2 "The Bicep deployment may have failed to set Auto-Heal."
    exit 1
fi
echo >&2 "  autoHealEnabled: $AUTOHEAL_ENABLED ✓"

# --- Verify autoHealRules contains the .64 trigger ---
echo >&2 "  Verifying autoHealRules ..."

AUTOHEAL_RULES="$(az webapp config show \
    --resource-group "$RG" \
    --name "$APP" \
    --query 'siteConfig.autoHealRules' \
    --output json)"

echo "$AUTOHEAL_RULES" > "$RESULTS_DIR/autoheal-verify.json"

WIN32_CHECK="$(echo "$AUTOHEAL_RULES" | python3 -c "
import json, sys
rules = json.load(sys.stdin)
if rules and 'triggers' in rules:
    codes = rules.get('triggers', {}).get('statusCodes', [])
    for c in codes:
        if c.get('win32Status') == 64:
            print('found')
            sys.exit(0)
print('not_found')
")"

if [[ "$WIN32_CHECK" != "found" ]]; then
    echo >&2 "ERROR: autoHealRules does not contain win32Status=64 trigger"
    echo >&2 "Rules: $AUTOHEAL_RULES"
    exit 1
fi
echo >&2 "  autoHealRules: win32Status=64 trigger present ✓"

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
    echo >&2 "  ERROR: Post-deploy readiness check FAILED."
    echo >&2 "    URL polled:     https://${HOSTNAME}/actuator/health"
    echo >&2 "    Poll timeout:   300s (60 attempts x 5s interval)"
    echo >&2 "    Last HTTP code: ${HEALTH_CODE:-000}"
    echo >&2 "    DO NOT proceed to the next experiment until the app returns to healthy state."
    ENDED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    ARTIFACT_FILES="$(python3 -c "import os,json;print(json.dumps(sorted(f for f in os.listdir('$RESULTS_DIR') if f!='manifest.json')))")"
    python3 -c "
import json
manifest = {
    'experiment': 'autoheal-enable',
    'startedAt': '$STARTED_AT',
    'endedAt': '$ENDED_AT',
    'status': 'aborted_readiness',
    'error': {'reason': 'post-deploy readiness check failed: https://${HOSTNAME}/actuator/health did not return 200 within 300s (last HTTP code: ${HEALTH_CODE:-000})'},
    'params': {
        'enableCustomAutoHeal': True,
        'autoHealActionType': 'Recycle',
        'autoHealEnabled': '$AUTOHEAL_ENABLED',
        'win32StatusTrigger': '$WIN32_CHECK',
        'warmupPassed': False
    },
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': $ARTIFACT_FILES
}
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"
    exit 5
fi

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
    'experiment': 'autoheal-enable',
    'startedAt': '$STARTED_AT',
    'endedAt': '$ENDED_AT',
    'params': {
        'enableCustomAutoHeal': True,
        'autoHealActionType': 'Recycle',
        'autoHealEnabled': '$AUTOHEAL_ENABLED',
        'win32StatusTrigger': '$WIN32_CHECK',
        'warmupPassed': $( [[ "$WARMUP_OK" == "true" ]] && echo "True" || echo "False" )
    },
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': $ARTIFACT_FILES
}
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"

echo >&2 ""
echo >&2 "=== Auto-Heal M2 enabled ==="
echo >&2 "  autoHealEnabled: true"
echo >&2 "  actionType:      Recycle"
echo >&2 "  Trigger:         500/121/64 on /slow/240 (5 in 2 min)"
echo >&2 "  Ended:           $ENDED_AT"
echo >&2 ""
echo >&2 "Next step:"
echo >&2 "  ./run-e4-m2-autoheal.sh --rate <same-rate-as-E2>"
