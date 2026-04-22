# Lab: CD Reconnect RBAC Conflict

Reproduce the `RoleAssignmentExists` error that surfaces when App Service Deployment Center container CD is reconnected to a Web App that uses its system-assigned managed identity to pull from Azure Container Registry.

See the full lab guide: [docs/troubleshooting/lab-guides/cd-reconnect-rbac-conflict.md](../../docs/troubleshooting/lab-guides/cd-reconnect-rbac-conflict.md)

## Files

| File | Purpose |
|---|---|
| `infra/main.bicep` | App Service Plan B1 + Linux container Web App with system-assigned MI + Basic ACR + Log Analytics + diagnostic settings |
| `infra/role-assignment.bicep` | `Microsoft.Authorization/roleAssignments` for AcrPull on the registry, optional `roleAssignmentName` parameter to force a fresh GUID |
| `trigger.sh` | Resolves the Web App MI, deploys the role assignment twice (deterministic GUID then fresh GUID) to surface the conflict |
| `verify.sh` | Confirms the conflict still reproduces, deletes the existing assignment, retries the deployment, and verifies recovery |
| `cleanup.sh` | Deletes the resource group (which owns the Web App MI, so no separate Entra cleanup is needed) |

## Quick start

```bash
export RG="rg-asp-lab-cd-rbac"
export LOCATION="koreacentral"

az group create --name "$RG" --location "$LOCATION"

az deployment group create \
    --name "lab-cd-rbac-base" \
    --resource-group "$RG" \
    --template-file "./labs/cd-reconnect-rbac-conflict/infra/main.bicep" \
    --parameters baseName="aspcdrbac"

export APP_NAME="$(az deployment group show --resource-group "$RG" --name "lab-cd-rbac-base" --query "properties.outputs.webAppName.value" --output tsv)"
export ACR_NAME="$(az deployment group show --resource-group "$RG" --name "lab-cd-rbac-base" --query "properties.outputs.containerRegistryName.value" --output tsv)"

./labs/cd-reconnect-rbac-conflict/trigger.sh
./labs/cd-reconnect-rbac-conflict/verify.sh
./labs/cd-reconnect-rbac-conflict/cleanup.sh
```

## Validation

| Tool | Last tested | CLI version | Result |
|---|---|---|---|
| `az` (Azure CLI) | 2026-04-22 | 2.70.0 | pass |
| `bicep` | 2026-04-22 | (bundled with az) | pass |

Reproduced the exact `RoleAssignmentExists` error: existing role assignment ID `561ed7ad-a306-588a-8d5f-2746e0ae4fca` on the registry scope. Recovery (delete + redeploy) succeeded with `1 active AcrPull assignment` afterwards.
