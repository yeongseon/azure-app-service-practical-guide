#!/usr/bin/env bash
set -euo pipefail

# Lab 2 deploy script: Loopback saturation + mitigation
#
# Provisions a fresh RG, deploys main.bicep with the 6-parameter contract,
# uploads the Stage 0 JAR byte-identically. Idempotent-safe: refuses to
# re-deploy over an existing RG unless --force is given.
#
# Usage: ./deploy.sh <BASE_NAME> [--force]
#
# BASE_NAME must be 3-15 chars, lowercase alphanumeric only.
# Resources created: rg-lab-<BASE_NAME> in koreacentral.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly LOCATION="koreacentral"

# --- Argument parsing ---
FORCE=false
BASE_NAME=""

for arg in "$@"; do
    case "$arg" in
        --force) FORCE=true ;;
        -*) echo "ERROR: Unknown flag: $arg"; exit 1 ;;
        *)
            if [[ -z "$BASE_NAME" ]]; then
                BASE_NAME="$arg"
            else
                echo "ERROR: Unexpected positional argument: $arg"
                echo "Usage: $0 <BASE_NAME> [--force]"
                exit 1
            fi
            ;;
    esac
done

if [[ -z "$BASE_NAME" ]]; then
    echo "Usage: $0 <BASE_NAME> [--force]"
    echo "Example: $0 winjaval2sat"
    echo ""
    echo "BASE_NAME must be 3-15 chars, lowercase alphanumeric only."
    echo "Creates resource group rg-lab-<BASE_NAME> in $LOCATION."
    echo ""
    echo "Options:"
    echo "  --force    Overwrite existing resource group (skips isolation check)"
    exit 1
fi

if ! [[ "$BASE_NAME" =~ ^[a-z0-9]{3,15}$ ]]; then
    echo "ERROR: BASE_NAME must be 3-15 lowercase alphanumeric characters, got: $BASE_NAME"
    exit 1
fi

readonly RG="rg-lab-${BASE_NAME}"
readonly BICEP_FILE="${SCRIPT_DIR}/main.bicep"
readonly JAR_DIR="${SCRIPT_DIR}/../stage-0-config-discovery/app/target"

# --- Preflight checks ---
echo "=== Preflight checks ==="

# 1. Azure CLI logged in
if ! az account show --output none 2>/dev/null; then
    echo "ERROR: Azure CLI not logged in. Run 'az login' first."
    exit 1
fi
echo "  [OK] Azure CLI authenticated"

# 2. k6 installed (Lab 2 prerequisite per design-proposal line 575)
if ! command -v k6 >/dev/null 2>&1; then
    echo "ERROR: k6 is not installed."
    echo "  Install with: brew install k6  (macOS)"
    echo "  Or see: https://grafana.com/docs/k6/latest/set-up/install-k6/"
    exit 1
fi
echo "  [OK] k6 $(k6 version 2>&1 | head -1)"

# 3. Required CLI tools
for cmd in az curl python3; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd"
        exit 1
    fi
done
echo "  [OK] az, curl, python3 available"

# 4. Stage 0 JAR exists (reuse per design-proposal line 58)
JAR_PATH=""
for jar_candidate in "${JAR_DIR}"/*.jar; do
    if [[ -f "$jar_candidate" ]]; then
        JAR_PATH="$jar_candidate"
        break
    fi
done
if [[ -z "$JAR_PATH" || ! -f "$JAR_PATH" ]]; then
    echo "ERROR: Stage 0 JAR not found in: $JAR_DIR"
    echo ""
    echo "Lab 2 reuses the Stage 0 JAR byte-identically. Build it first:"
    echo "  cd ${SCRIPT_DIR}/../stage-0-config-discovery/app && mvn clean package -DskipTests"
    exit 1
fi
echo "  [OK] JAR found: $JAR_PATH ($(du -h "$JAR_PATH" | cut -f1))"

# 5. Bicep template exists
if [[ ! -f "$BICEP_FILE" ]]; then
    echo "ERROR: Bicep template not found at: $BICEP_FILE"
    exit 1
fi
echo "  [OK] Bicep template: $BICEP_FILE"

# 6. Isolation check: refuse to deploy over existing RG unless --force
if az group show --resource-group "$RG" --output none 2>/dev/null; then
    if [[ "$FORCE" == "false" ]]; then
        echo ""
        echo "ERROR: Resource group '$RG' already exists."
        echo "  To avoid accidental overwrites, either:"
        echo "    1. Run cleanup first:  ./cleanup.sh"
        echo "    2. Pass --force:       ./deploy.sh $BASE_NAME --force"
        exit 1
    fi
    echo "  [WARN] Resource group '$RG' exists; --force given, proceeding with overwrite"
fi

echo ""
echo "=== Step 1/4: Create resource group ==="
echo "  Resource group: $RG"
echo "  Location:       $LOCATION"
az group create \
    --resource-group "$RG" \
    --location "$LOCATION" \
    --output none

echo ""
echo "=== Step 2/4: Deploy Bicep template ==="
echo "  Template: $BICEP_FILE"
DEPLOYMENT_NAME="lab2-$(date -u +%Y%m%dT%H%M%SZ)"
readonly DEPLOYMENT_NAME

mkdir -p "$SCRIPT_DIR/results"

DEPLOYMENT_OUTPUTS="$(az deployment group create \
    --resource-group "$RG" \
    --name "$DEPLOYMENT_NAME" \
    --template-file "$BICEP_FILE" \
    --parameters \
        baseName="$BASE_NAME" \
        enableCustomAutoHeal=false \
        autoHealActionType=Recycle \
        planInstanceCount=1 \
    --query 'properties.outputs' \
    --output json)"

echo "$DEPLOYMENT_OUTPUTS" > "$SCRIPT_DIR/results/deploy-outputs.json"

# Parse outputs (Bicep output names per Agent 1 contract)
web_app_name="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c "import json,sys; print(json.load(sys.stdin)['webAppName']['value'])")"
web_app_hostname="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c "import json,sys; print(json.load(sys.stdin)['webAppHostname']['value'])")"
web_app_resource_id="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c "import json,sys; print(json.load(sys.stdin)['webAppResourceId']['value'])")"
log_analytics_workspace_id="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c "import json,sys; print(json.load(sys.stdin)['logAnalyticsWorkspaceId']['value'])")"
app_service_plan_name="$(echo "$DEPLOYMENT_OUTPUTS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('appServicePlanName',{}).get('value','plan-${BASE_NAME}'))" 2>/dev/null || echo "plan-${BASE_NAME}")"

echo "  Web app name:     $web_app_name"
echo "  Hostname:         $web_app_hostname"
echo "  Resource ID:      $web_app_resource_id"
echo "  Log Analytics ID: $log_analytics_workspace_id"
echo "  Plan name:        $app_service_plan_name"

echo ""
echo "=== Step 3/4: Upload JAR to App Service ==="
echo "  Source: $JAR_PATH"
az webapp deploy \
    --resource-group "$RG" \
    --name "$web_app_name" \
    --type jar \
    --src-path "$JAR_PATH" \
    --async false \
    --clean true \
    --output none

echo ""
echo "=== Step 4/4: Save deployment metadata ==="
DEPLOY_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
readonly DEPLOY_TIMESTAMP

python3 -c "
import json
metadata = {
    'baseName': '$BASE_NAME',
    'resourceGroup': '$RG',
    'webAppName': '$web_app_name',
    'webAppHostname': '$web_app_hostname',
    'webAppResourceId': '$web_app_resource_id',
    'logAnalyticsWorkspaceId': '$log_analytics_workspace_id',
    'appServicePlanName': '$app_service_plan_name',
    'location': '$LOCATION',
    'deployedAt': '$DEPLOY_TIMESTAMP'
}
with open('$SCRIPT_DIR/results/deploy-metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)
print('  Written: $SCRIPT_DIR/results/deploy-metadata.json')
"

echo ""
echo "============================================="
echo "  Deployment complete"
echo "============================================="
echo "  Resource group:  $RG"
echo "  Web app:         $web_app_name"
echo "  URL:             https://$web_app_hostname"
echo "  Plan:            $app_service_plan_name"
echo "  Location:        $LOCATION"
echo "  Deployed at:     $DEPLOY_TIMESTAMP"
echo ""
echo "Next step:"
echo "  ./warm-up.sh"
