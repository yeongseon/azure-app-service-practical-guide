#!/usr/bin/env bash
set -euo pipefail

: "${RG:?RG must be set}"
: "${APP_NAME:?APP_NAME must be set}"
: "${ACR_NAME:?ACR_NAME must be set}"

SUBSCRIPTION_ID="${SUBSCRIPTION_ID:-$(az account show --query id --output tsv | tr -d '\r')}"
ACR_ID="${ACR_ID:-$(az acr show --name "$ACR_NAME" --resource-group "$RG" --query id --output tsv | tr -d '\r')}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/infra/role-assignment.bicep"

echo "==> 1) Resolve the Web App's system-assigned managed identity (the CD identity)"
# App Service Deployment Center grants this principal AcrPull when configured to use
# managed-identity image pulls. We use the same principal here to mirror that flow.
APP_PRINCIPAL_ID=$(az webapp identity show --name "$APP_NAME" --resource-group "$RG" \
    --query principalId --output tsv | tr -d '\r')
if [ -z "$APP_PRINCIPAL_ID" ] || [ "$APP_PRINCIPAL_ID" = "null" ]; then
    echo "    Web App has no system-assigned identity yet, enabling..."
    APP_PRINCIPAL_ID=$(az webapp identity assign --name "$APP_NAME" --resource-group "$RG" \
        --query principalId --output tsv | tr -d '\r')
fi
echo "    principalId=$APP_PRINCIPAL_ID"

echo "==> 2) Initial CD setup: ARM deployment that grants AcrPull on registry"
# This deployment mirrors what Deployment Center does when you enable container CD with
# managed identity: it creates a Microsoft.Authorization/roleAssignments resource via
# ARM. The default resource name is a GUID derived from (scope, principal, role).
az deployment group create \
    --resource-group "$RG" \
    --name "lab-ra-initial" \
    --template-file "$TEMPLATE" \
    --parameters principalObjectId="$APP_PRINCIPAL_ID" registryName="$ACR_NAME" \
    --query "properties.{state:provisioningState, name:outputs.roleAssignmentName.value}" \
    --output table

echo "    Waiting 15s for RBAC propagation..."
sleep 15
az role assignment list --assignee "$APP_PRINCIPAL_ID" --scope "$ACR_ID" --output table

echo "==> 3) Simulated 'Disconnect' from Deployment Center (only app-side config cleared)"
echo "    Deployment Center disconnect typically clears site config bindings but leaves"
echo "    the AcrPull role assignment on the registry intact."

echo "==> 4) Attempt 'Reconnect' - second ARM deployment with a fresh role assignment GUID"
# Real Deployment Center reconnect generates a new role assignment GUID on each invocation.
# Same scope + same principal + same role with a different assignment name triggers the
# RBAC unique key violation, surfaced as RoleAssignmentExists in the Portal/CLI error.
NEW_NAME=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen | tr '[:upper:]' '[:lower:]')
set +e
az deployment group create \
    --resource-group "$RG" \
    --name "lab-ra-reconnect" \
    --template-file "$TEMPLATE" \
    --parameters principalObjectId="$APP_PRINCIPAL_ID" registryName="$ACR_NAME" roleAssignmentName="$NEW_NAME" \
    --output json 2>&1 | tee /tmp/cd-rbac-conflict.log
RESULT=${PIPESTATUS[0]}
set -e

if grep -qE "RoleAssignmentExists|already exists" /tmp/cd-rbac-conflict.log; then
    EXISTING_ID=$(grep -oE 'existing role assignment is [a-f0-9]{32}' /tmp/cd-rbac-conflict.log | awk '{print $NF}' | head -1)
    echo ""
    echo "PASS: RoleAssignmentExists conflict reproduced."
    echo "    Existing assignment ID (no hyphens): $EXISTING_ID"
    echo "    GUID format: $(echo "$EXISTING_ID" | sed 's/\(........\)\(....\)\(....\)\(....\)\(............\)/\1-\2-\3-\4-\5/')"
    echo "    This is the same error returned by Deployment Center on container CD reconnect."
    exit 0
elif [ "$RESULT" -eq 0 ]; then
    echo "FAIL: Second deployment succeeded - conflict not reproduced."
    exit 1
else
    echo "FAIL: Unexpected error - check /tmp/cd-rbac-conflict.log"
    exit 1
fi
