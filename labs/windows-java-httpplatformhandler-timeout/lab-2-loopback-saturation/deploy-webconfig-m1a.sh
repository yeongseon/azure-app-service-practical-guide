#!/usr/bin/env bash
set -euo pipefail

# E3: Deploy a customer web.config with requestTimeout to the web app.
#
# Uses OneDeploy (--type static) as primary path. Falls back through:
#   A) --type zip (JAR + web.config together)
#   B) az webapp deployment source config-zip (DEPRECATED)
#   C) Skip E3 entirely (exit 2)
#
# Per design-proposal.md lines 220-228 (Oracle-approved).

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_METADATA="$SCRIPT_DIR/results/deploy-metadata.json"
readonly EXPERIMENT="e3"

# --- Argument parsing ---
CANARY="${1:-primary}"
if [[ "$CANARY" != "primary" && "$CANARY" != "secondary" ]]; then
    echo >&2 "Usage: $0 [primary|secondary]"
    echo >&2 "  primary   → deploys webconfig/web.config (full httpPlatform element)"
    echo >&2 "  secondary → deploys webconfig/web.config.partial (requestTimeout-only override)"
    exit 1
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

if [[ -z "$APP" || -z "$HOSTNAME" || -z "$RG" ]]; then
    echo >&2 "ERROR: Could not parse deploy-metadata.json fields"
    exit 1
fi

# --- Resolve source file ---
if [[ "$CANARY" == "primary" ]]; then
    SRC="$SCRIPT_DIR/webconfig/web.config"
else
    SRC="$SCRIPT_DIR/webconfig/web.config.partial"
fi

if [[ ! -f "$SRC" ]]; then
    echo >&2 "ERROR: Canary source file not found: $SRC"
    echo >&2 "Agent 1 must create webconfig/web.config and webconfig/web.config.partial first."
    exit 1
fi

# --- Resolve Stage 0 JAR (needed for Fallback A) ---
readonly JAR_DIR="${SCRIPT_DIR}/../stage-0-config-discovery/app/target"
STAGE0_JAR=""
if compgen -G "${JAR_DIR}/*.jar" >/dev/null 2>&1; then
    STAGE0_JAR="$(ls -1 "${JAR_DIR}"/*.jar | head -1)"
fi

# --- Output directory ---
readonly RESULTS_DIR="$SCRIPT_DIR/results/$EXPERIMENT"
mkdir -p "$RESULTS_DIR"

readonly STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
readonly DEPLOY_LOG="$RESULTS_DIR/deploy-log-${CANARY}-$(date -u +%Y%m%dT%H%M%SZ).txt"

echo >&2 "=== E3: Deploy web.config (M1a) ==="
echo >&2 "  Canary:  $CANARY"
echo >&2 "  Source:  $SRC"
echo >&2 "  App:     $APP"
echo >&2 "  RG:      $RG"
echo >&2 "  Started: $STARTED_AT"
echo >&2 ""

DEPLOY_SUCCESS=false
DEPLOY_METHOD="none"

# --- Primary path: OneDeploy --type static ---
echo >&2 "  [Primary] az webapp deploy --type static --target-path web.config ..."
{
    echo "=== Primary: OneDeploy --type static ==="
    echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Command: az webapp deploy --resource-group $RG --name $APP --type static --target-path web.config --src-path $SRC --async false"
    echo ""
} >> "$DEPLOY_LOG"

set +e
PRIMARY_OUTPUT="$(az webapp deploy \
    --resource-group "$RG" \
    --name "$APP" \
    --type static \
    --target-path "web.config" \
    --src-path "$SRC" \
    --async false \
    --output json 2>&1)"
PRIMARY_EXIT=$?
set -e

echo "$PRIMARY_OUTPUT" >> "$DEPLOY_LOG"

if [[ $PRIMARY_EXIT -eq 0 ]]; then
    DEPLOY_SUCCESS=true
    DEPLOY_METHOD="static"
    echo >&2 "  [Primary] SUCCESS"
else
    echo >&2 "  [Primary] FAILED (exit $PRIMARY_EXIT)"
    echo "" >> "$DEPLOY_LOG"

    # --- Fallback A: zip deploy (JAR + web.config) ---
    if [[ -z "$STAGE0_JAR" || ! -f "$STAGE0_JAR" ]]; then
        echo >&2 "  [Fallback A] SKIPPED: Stage 0 JAR not found at $JAR_DIR"
        echo "=== Fallback A: SKIPPED (no JAR) ===" >> "$DEPLOY_LOG"
    else
        echo >&2 "  [Fallback A] Creating zip with app.jar + web.config ..."
        TMPDIR_ZIP="$(mktemp -d)"
        trap 'rm -rf "$TMPDIR_ZIP"' EXIT
        cp "$STAGE0_JAR" "$TMPDIR_ZIP/app.jar"
        # Always deploy as web.config regardless of canary source filename
        cp "$SRC" "$TMPDIR_ZIP/web.config"
        ZIP_PATH="$TMPDIR_ZIP/deploy-fallback-a.zip"
        (cd "$TMPDIR_ZIP" && zip -q "$ZIP_PATH" app.jar web.config)

        {
            echo ""
            echo "=== Fallback A: zip deploy ==="
            echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
            echo "Command: az webapp deploy --resource-group $RG --name $APP --type zip --src-path $ZIP_PATH --async false"
            echo ""
        } >> "$DEPLOY_LOG"

        set +e
        FALLBACK_A_OUTPUT="$(az webapp deploy \
            --resource-group "$RG" \
            --name "$APP" \
            --type zip \
            --src-path "$ZIP_PATH" \
            --async false \
            --output json 2>&1)"
        FALLBACK_A_EXIT=$?
        set -e

        echo "$FALLBACK_A_OUTPUT" >> "$DEPLOY_LOG"

        if [[ $FALLBACK_A_EXIT -eq 0 ]]; then
            DEPLOY_SUCCESS=true
            DEPLOY_METHOD="zip"
            echo >&2 "  [Fallback A] SUCCESS (WARNING: Fallback A used - zip deploy)"
        else
            echo >&2 "  [Fallback A] FAILED (exit $FALLBACK_A_EXIT)"
            echo "" >> "$DEPLOY_LOG"

            # --- Fallback B: DEPRECATED config-zip ---
            echo >&2 "  [Fallback B] DEPRECATED: az webapp deployment source config-zip ..."
            echo >&2 "  WARNING: This path is deprecated per Microsoft Learn."

            {
                echo ""
                echo "=== Fallback B: config-zip (DEPRECATED) ==="
                echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
                echo "Command: az webapp deployment source config-zip --resource-group $RG --name $APP --src $ZIP_PATH"
                echo ""
            } >> "$DEPLOY_LOG"

            set +e
            FALLBACK_B_OUTPUT="$(az webapp deployment source config-zip \
                --resource-group "$RG" \
                --name "$APP" \
                --src "$ZIP_PATH" \
                --output json 2>&1)"
            FALLBACK_B_EXIT=$?
            set -e

            echo "$FALLBACK_B_OUTPUT" >> "$DEPLOY_LOG"

            if [[ $FALLBACK_B_EXIT -eq 0 ]]; then
                DEPLOY_SUCCESS=true
                DEPLOY_METHOD="config-zip-deprecated"
                echo >&2 "  [Fallback B] SUCCESS (WARNING: Used deprecated config-zip path)"
            else
                echo >&2 "  [Fallback B] FAILED (exit $FALLBACK_B_EXIT)"
            fi
        fi

        rm -rf "$TMPDIR_ZIP"
        trap - EXIT
    fi
fi

# --- Fallback C: all paths exhausted ---
if [[ "$DEPLOY_SUCCESS" != "true" ]]; then
    echo >&2 ""
    echo >&2 "E3 SKIPPED: All deployment paths failed. Documented as platform limitation."
    echo >&2 "  See deploy log: $DEPLOY_LOG"

    {
        echo ""
        echo "=== Fallback C: ALL PATHS FAILED ==="
        echo "E3 is skipped. Documented as platform limitation."
    } >> "$DEPLOY_LOG"

    # Write manifest with failure state
    python3 -c "
import json, os
manifest = {
    'experiment': 'm1a-deploy',
    'startedAt': '$STARTED_AT',
    'endedAt': '$(date -u +%Y-%m-%dT%H:%M:%SZ)',
    'params': {
        'canary': '$CANARY',
        'sourceFile': '$SRC',
        'deployMethod': 'none',
        'deploySuccess': False
    },
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': [os.path.basename('$DEPLOY_LOG')]
}
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"
    exit 2
fi

# --- Post-deploy: warm-up health check ---
echo >&2 ""
echo >&2 "  Deploy succeeded via: $DEPLOY_METHOD"
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
    echo >&2 "  WARN: /actuator/health did not return 200 within 300s after web.config deploy"
    echo >&2 "  The Java process may not have restarted correctly. Probes may fail."
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
    'experiment': 'm1a-deploy',
    'startedAt': '$STARTED_AT',
    'endedAt': '$ENDED_AT',
    'params': {
        'canary': '$CANARY',
        'sourceFile': '$(basename "$SRC")',
        'deployMethod': '$DEPLOY_METHOD',
        'deploySuccess': True,
        'warmupPassed': $( [[ "$WARMUP_OK" == "true" ]] && echo "True" || echo "False" )
    },
    'webAppResourceId': '$WEB_APP_RESOURCE_ID',
    'artifactFiles': $ARTIFACT_FILES
}
with open('$RESULTS_DIR/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"

echo >&2 ""
echo >&2 "=== M1a web.config deployed successfully ==="
echo >&2 "  Method:  $DEPLOY_METHOD"
echo >&2 "  Canary:  $CANARY"
echo >&2 "  Ended:   $ENDED_AT"
echo >&2 ""
echo >&2 "Next step:"
echo >&2 "  ./run-e3-m1a-probes.sh --canary $CANARY"
