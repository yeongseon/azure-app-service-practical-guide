#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <RESOURCE_GROUP_NAME>"
    echo "Example: $0 rg-lab-winjavatimeout"
    exit 1
fi

RESOURCE_GROUP_NAME="$1"

if ! az group show --name "$RESOURCE_GROUP_NAME" --output none 2>/dev/null; then
    echo "Resource group not found (already deleted?): $RESOURCE_GROUP_NAME"
    exit 0
fi

echo "Deleting resource group: $RESOURCE_GROUP_NAME"
echo "This runs asynchronously; the CLI returns immediately."
az group delete \
    --name "$RESOURCE_GROUP_NAME" \
    --yes \
    --no-wait

echo
echo "Deletion initiated. Verify completion with:"
echo "  az group show --name $RESOURCE_GROUP_NAME"
echo "  (expected: ResourceGroupNotFound after 3-10 minutes)"
