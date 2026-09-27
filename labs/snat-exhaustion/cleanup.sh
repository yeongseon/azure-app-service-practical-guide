#!/usr/bin/env bash
# Remove every Azure resource this lab created.
#
# The lab deploys into its own resource group so cleanup is a single
# delete rather than a list of individual resources that drifts out of
# date as the Bicep template changes. Deleting the group is what makes
# this procedure complete by construction.
set -euo pipefail

RG="${RG:-}"
if [ -z "$RG" ]; then
  echo "error: set RG to the resource group this lab deployed into" >&2
  echo "usage: RG=rg-appservice-demo bash $0" >&2
  exit 2
fi

if ! az group exists --name "$RG" | grep -q true; then
  echo "resource group '$RG' does not exist; nothing to clean up"
  exit 0
fi

echo "deleting resource group '$RG' and everything in it"
az group delete --name "$RG" --yes --no-wait

echo "delete accepted. verify with:"
echo "  az group exists --name $RG"
