#!/usr/bin/env bash
# shellcheck disable=SC2155
set -euo pipefail

# Revert: Redeploy Stage 0 JAR with --clean true to remove web.config.
#
# Called between E3 and E4 to restore the baseline (Lab 1) state.
# --clean true is critical: it removes files not in the JAR (i.e. web.config).
#
# Per design-proposal.md line 274 (Oracle-approved).

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_METADATA="$SCRIPT_DIR/results/deploy-metadata.json"
readonly EXPERIMENT="revert"

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

if [[ -z "$APP" || -z "$HOSTNAME" || -z "$RG" ]]; then
    echo >&2 "ERROR: Could not parse deploy-metadata.json fields"
    exit 1
fi

# --- Locate Stage 0 JAR ---
readonly JAR_DIR="${SCRIPT_DIR}/../stage-0-config-discovery/app/target"
STAGE0_JAR=""
if compgen -G "${JAR_DIR}/*.jar" >/dev/null 2>&1; then
    STAGE0_JAR="$(find "${JAR_DIR}" -maxdepth 1 -type f -name '*.jar' -print | head -n 1)"
fi

if [[ -z "$STAGE0_JAR" || ! -f "$STAGE0_JAR" ]]; then
    echo >&2 "ERROR: Stage 0 JAR not found in: $JAR_DIR"
    echo >&2 "Build it first: cd ../stage-0-config-discovery/app && mvn clean package -DskipTests"
    exit 1
fi

# --- Output directory ---
readonly RESULTS_DIR="$SCRIPT_DIR/results/$EXPERIMENT"
mkdir -p "$RESULTS_DIR"

readonly STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
readonly REVERT_LOG="$RESULTS_DIR/revert-$(date -u +%Y%m%dT%H%M%SZ).log"

echo >&2 "=== Revert: Redeploy baseline JAR (remove web.config) ==="
echo >&2 "  App:     $APP"
echo >&2 "  RG:      $RG"
echo >&2 "  JAR:     $STAGE0_JAR"
echo >&2 "  Started: $STARTED_AT"
echo >&2 ""

# --- Redeploy JAR with --clean true ---
echo >&2 "  Deploying JAR with --clean true (removes web.config) ..."
{
    echo "=== Revert: JAR deploy with --clean true ==="
    echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Command: az webapp deploy --resource-group $RG --name $APP --type jar --src-path $STAGE0_JAR --async false --clean true"
    echo ""
} > "$REVERT_LOG"

set +e
DEPLOY_OUTPUT="$(az webapp deploy \
    --resource-group "$RG" \
    --name "$APP" \
    --type jar \
    --src-path "$STAGE0_JAR" \
    --async false \
    --clean true \
    --output json 2>&1)"
DEPLOY_EXIT=$?
set -e

echo "$DEPLOY_OUTPUT" >> "$REVERT_LOG"

if [[ $DEPLOY_EXIT -ne 0 ]]; then
    echo >&2 "ERROR: JAR redeploy failed (exit $DEPLOY_EXIT). See: $REVERT_LOG"
    exit 1
fi

echo >&2 "  JAR deployed successfully."

# --- Warm-up: poll /actuator/health ---
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
    'experiment': 'revert',
    'startedAt': '$STARTED_AT',
    'endedAt': '$ENDED_AT',
    'status': 'aborted_readiness',
    'error': {'reason': 'post-deploy readiness check failed: https://${HOSTNAME}/actuator/health did not return 200 within 300s (last HTTP code: ${HEALTH_CODE:-000})'},
    'params': {
        'jarPath': '$(basename "$STAGE0_JAR")',
        'cleanDeploy': True,
        'warmupPassed': False,
        'sanityHttpCode': None, 'sanityTimeTotal': None
    },
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': $ARTIFACT_FILES
}
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"
    exit 5
fi

# --- Quick sanity: /slow/2 should return ~2s (baseline restored) ---
echo >&2 "  Sanity check: /slow/2 (expect ~2s 200 response) ..."
set +e
SANITY_OUTPUT="$(curl --silent --output /dev/null \
    --max-time 30 \
    --write-out 'http_code: %{http_code}\ntime_total: %{time_total}\n' \
    "https://${HOSTNAME}/slow/2" 2>&1)"
set -e
echo "$SANITY_OUTPUT" >> "$REVERT_LOG"
SANITY_CODE="$(echo "$SANITY_OUTPUT" | grep '^http_code:' | awk '{print $2}' || echo "000")"
SANITY_TIME="$(echo "$SANITY_OUTPUT" | grep '^time_total:' | awk '{print $2}' || echo "?")"
echo >&2 "  Sanity: HTTP=$SANITY_CODE time_total=$SANITY_TIME"

{
    echo ""
    echo "=== Sanity check: /slow/2 ==="
    echo "http_code: $SANITY_CODE"
    echo "time_total: $SANITY_TIME"
} >> "$REVERT_LOG"

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
    'experiment': 'revert',
    'startedAt': '$STARTED_AT',
    'endedAt': '$ENDED_AT',
    'params': {
        'jarPath': '$(basename "$STAGE0_JAR")',
        'cleanDeploy': True,
        'warmupPassed': $( [[ "$WARMUP_OK" == "true" ]] && echo "True" || echo "False" ),
        'sanityHttpCode': '$SANITY_CODE',
        'sanityTimeTotal': '$SANITY_TIME'
    },
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': $ARTIFACT_FILES
}
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"

echo >&2 ""
echo >&2 "=== Revert complete ==="
echo >&2 "  Ended:   $ENDED_AT"
echo >&2 "  Warmup:  $( [[ "$WARMUP_OK" == "true" ]] && echo "passed" || echo "FAILED" )"
echo >&2 "  Sanity:  HTTP=$SANITY_CODE time=$SANITY_TIME"
echo >&2 ""
echo >&2 "Baseline restored. E4 can proceed without E3's web.config."
echo >&2 ""
echo >&2 "Next step:"
echo >&2 "  ./preflight-platform-logs.sh"
