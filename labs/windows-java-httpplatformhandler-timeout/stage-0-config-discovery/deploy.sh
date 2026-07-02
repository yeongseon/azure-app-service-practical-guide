#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
    echo "Usage: $0 <BASE_NAME> [LOCATION] [RESOURCE_GROUP_NAME]"
    echo "Example: $0 winjavatimeout koreacentral rg-lab-winjavatimeout"
    echo ""
    echo "BASE_NAME must be 3-15 chars, lowercase alphanumeric only."
    exit 1
fi

BASE_NAME="$1"
LOCATION="${2:-koreacentral}"
RESOURCE_GROUP_NAME="${3:-rg-lab-${BASE_NAME}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BICEP_FILE="${SCRIPT_DIR}/main.bicep"
APP_DIR="${SCRIPT_DIR}/app"

if ! [[ "$BASE_NAME" =~ ^[a-z0-9]{3,15}$ ]]; then
    echo "ERROR: BASE_NAME must be 3-15 lowercase alphanumeric characters, got: $BASE_NAME"
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
DEPLOYMENT_NAME="stage0-$(date -u +%Y%m%dT%H%M%SZ)"
DEPLOYMENT_OUTPUTS="$(az deployment group create \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$DEPLOYMENT_NAME" \
    --template-file "$BICEP_FILE" \
    --parameters "baseName=$BASE_NAME" \
    --query properties.outputs \
    --output json)"

APP_NAME="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["appName"]["value"])')"
DEFAULT_HOSTNAME="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["defaultHostName"]["value"])')"
APP_URL="https://${DEFAULT_HOSTNAME}"

echo "  App name:  $APP_NAME"
echo "  App URL:   $APP_URL"

echo
echo "=== Step 3/4: Build Java app ==="
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
echo "  Resource group:   $RESOURCE_GROUP_NAME"
echo "  App name:         $APP_NAME"
echo "  App URL:          $APP_URL"
echo
echo "Next steps:"
echo "  1. Warm up:              bash $SCRIPT_DIR/warm-up.sh $APP_URL"
echo "  2. Run timeout probe:    bash $SCRIPT_DIR/run-timeout-probe.sh $APP_URL"
echo "  3. Collect config:       bash $SCRIPT_DIR/collect-effective-config.sh $APP_NAME $RESOURCE_GROUP_NAME"
echo "  4. Cleanup:              bash $SCRIPT_DIR/cleanup.sh $RESOURCE_GROUP_NAME"
