#!/usr/bin/env bash
set -euo pipefail

: "${RG:?RG must be set}"

echo "==> Deleting resource group $RG (async)"
echo "    This removes the App Service Plan, Web App (with its system-assigned identity),"
echo "    Container Registry, all role assignments scoped to those resources, and the"
echo "    Log Analytics workspace."
az group delete --name "$RG" --yes --no-wait
echo "Cleanup initiated."
