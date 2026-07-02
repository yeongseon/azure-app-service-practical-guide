#!/bin/bash
set -euo pipefail

# Lab 1 deploy script.
#
# Reuses the Stage 0 JAR byte-identically (per design-proposal.md revision 2
# and Oracle Section E3). The Stage 0 app/ directory must exist at the
# repository path shown below; the script errors out with a clear message if
# it does not.
#
# Preflight verification is RETAINED (per Oracle change #3): even though
# Stage 0 already validated the Bicep isolation guarantees, Lab 1 is a
# separate fresh deployment and could drift. `collect-effective-config.sh
# --preflight` verifies autoHealEnabled=false,
# WEBSITE_PROACTIVE_AUTOHEAL_ENABLED=false, and WEBSITE_JAVA_JAR_FILE_NAME
# before E1 spends up to 87 minutes on probes.

if [[ $# -lt 1 || $# -gt 3 ]]; then
    echo "Usage: $0 <BASE_NAME> [LOCATION] [RESOURCE_GROUP_NAME]"
    echo "Example: $0 winjavatimeoutl1 koreacentral rg-lab-winjavatimeoutl1"
    echo ""
    echo "BASE_NAME must be 3-15 chars, lowercase alphanumeric only."
    exit 1
fi

BASE_NAME="$1"
LOCATION="${2:-koreacentral}"
RESOURCE_GROUP_NAME="${3:-rg-lab-${BASE_NAME}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BICEP_FILE="${SCRIPT_DIR}/main.bicep"
# Byte-identical JAR reuse: Lab 1 does NOT maintain its own app/ directory.
# The comparison between Stage 0 and Lab 1 must isolate a single configuration
# delta (the async timeout app setting). Rebuilding a copy would introduce
# potential drift.
APP_DIR="${SCRIPT_DIR}/../stage-0-config-discovery/app"

if ! [[ "$BASE_NAME" =~ ^[a-z0-9]{3,15}$ ]]; then
    echo "ERROR: BASE_NAME must be 3-15 lowercase alphanumeric characters, got: $BASE_NAME"
    exit 1
fi

if [[ ! -d "$APP_DIR" ]]; then
    echo "ERROR: Stage 0 app directory not found at: $APP_DIR"
    echo ""
    echo "Lab 1 reuses the Stage 0 JAR byte-identically. Restore the Stage 0"
    echo "source tree before deploying Lab 1:"
    echo "  git checkout labs/windows-java-httpplatformhandler-timeout/stage-0-config-discovery/app"
    exit 1
fi

for cmd in az mvn curl python3; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd"
        exit 1
    fi
done

echo "=== Step 1/4: Create resource group ==="
echo "  Resource group: $RESOURCE_GROUP_NAME"
echo "  Location:       $LOCATION"
az group create \
    --name "$RESOURCE_GROUP_NAME" \
    --location "$LOCATION" \
    --output none

echo
echo "=== Step 2/4: Deploy Bicep template ==="
echo "  Template: $BICEP_FILE"
DEPLOYMENT_NAME="lab1-$(date -u +%Y%m%dT%H%M%SZ)"
DEPLOYMENT_OUTPUTS="$(az deployment group create \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$DEPLOYMENT_NAME" \
    --template-file "$BICEP_FILE" \
    --parameters "baseName=$BASE_NAME" \
    --query properties.outputs \
    --output json)"

APP_NAME="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["appName"]["value"])')"
DEFAULT_HOSTNAME="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["defaultHostName"]["value"])')"
LAW_NAME="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["logAnalyticsWorkspaceName"]["value"])')"
ASYNC_TIMEOUT_MS="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["springMvcAsyncRequestTimeoutMs"]["value"])')"
APP_URL="https://${DEFAULT_HOSTNAME}"

echo "  App name:                        $APP_NAME"
echo "  App URL:                         $APP_URL"
echo "  Log Analytics workspace:         $LAW_NAME"
echo "  SPRING_MVC_ASYNC_REQUEST_TIMEOUT: ${ASYNC_TIMEOUT_MS} ms"

echo
echo "=== Step 3/4: Build Java app (byte-identical to Stage 0 JAR) ==="
echo "  Building in: $APP_DIR"
(cd "$APP_DIR" && mvn --quiet clean package -DskipTests)
JAR_PATH="${APP_DIR}/target/app.jar"
if [[ ! -f "$JAR_PATH" ]]; then
    echo "ERROR: expected JAR not produced at $JAR_PATH"
    exit 1
fi
echo "  Built JAR: $JAR_PATH ($(du -h "$JAR_PATH" | cut -f1))"

echo
echo "=== Step 4/4: Deploy JAR to App Service ==="
az webapp deploy \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --src-path "$JAR_PATH" \
    --type jar \
    --async false \
    --output none

echo
echo "=== Deployment complete ==="
echo "  Resource group:                  $RESOURCE_GROUP_NAME"
echo "  App name:                        $APP_NAME"
echo "  App URL:                         $APP_URL"
echo "  Log Analytics workspace:         $LAW_NAME"
echo "  SPRING_MVC_ASYNC_REQUEST_TIMEOUT: ${ASYNC_TIMEOUT_MS} ms"
echo
echo "Next steps (must run in order):"
echo "  1. Warm up:            bash $SCRIPT_DIR/warm-up.sh $APP_URL"
echo "  2. Preflight check:    bash $SCRIPT_DIR/collect-effective-config.sh --preflight $APP_NAME $RESOURCE_GROUP_NAME ./results"
echo "  3. E1 signature probe: bash $SCRIPT_DIR/run-e1-signature-probe.sh $APP_URL ./results"
echo "  4. E2 config visibility: bash $SCRIPT_DIR/run-e2-config-visibility.sh $APP_NAME $RESOURCE_GROUP_NAME ./results"
echo "  5. E3 stream test:     bash $SCRIPT_DIR/run-e3-stream-test.sh $APP_URL ./results"
echo "  6. Post-flight config: bash $SCRIPT_DIR/collect-effective-config.sh $APP_NAME $RESOURCE_GROUP_NAME ./results"
echo "  7. Verify + summarize: bash $SCRIPT_DIR/verify.sh $APP_NAME $RESOURCE_GROUP_NAME $LAW_NAME ./results"
echo "  8. Cleanup:            bash $SCRIPT_DIR/cleanup.sh $RESOURCE_GROUP_NAME"
