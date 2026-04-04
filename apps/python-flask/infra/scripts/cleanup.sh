#!/bin/bash
set -euo pipefail

echo "============================================"
echo "Azure App Service Python Reference - Cleanup"
echo "============================================"
echo ""

if [ -f ../.env ]; then
  echo "📁 Loading configuration from infra/.env file..."
  set -a
  # shellcheck disable=SC1091
  source ../.env
  set +a
fi

RESOURCE_GROUP_NAME=${RESOURCE_GROUP_NAME:-"rg-python-reference"}

echo "Resource group scheduled for deletion: $RESOURCE_GROUP_NAME"
read -p "Delete this resource group? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Cleanup cancelled."
  exit 1
fi

if ! az account show > /dev/null 2>&1; then
  echo "❌ Not logged in to Azure. Please run 'az login' first."
  exit 1
fi

if az group show --name "$RESOURCE_GROUP_NAME" > /dev/null 2>&1; then
  az group delete --name "$RESOURCE_GROUP_NAME" --yes --no-wait
  echo "✅ Deletion started for resource group: $RESOURCE_GROUP_NAME"
else
  echo "ℹ️  Resource group '$RESOURCE_GROUP_NAME' does not exist."
fi
