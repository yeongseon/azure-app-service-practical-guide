#!/usr/bin/env bash
set -euo pipefail

# Lab 2 cleanup: Deletes the Lab 2 Azure resource group with az group delete,
# using the metadata file by default and prompting for confirmation unless
# --yes is supplied.
#
# Inputs:
#   - results/deploy-metadata.json for resourceGroup
#   - optional RESOURCE_GROUP positional argument
#   - optional --yes flag
#
# Outputs:
#   - confirmation prompts and status messages
#   - asynchronous resource group deletion via Azure CLI
#
# Dependencies:
#   - az
#   - jq

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly METADATA_FILE="$SCRIPT_DIR/results/deploy-metadata.json"

trap 'echo "Interrupted." >&2; exit 130' INT TERM

YES_FLAG=false
RG=""

for arg in "$@"; do
    case "$arg" in
        --yes) YES_FLAG=true ;;
        -*) echo "ERROR: Unknown flag: $arg"; exit 1 ;;
        *)
            if [[ -z "$RG" ]]; then
                RG="$arg"
            else
                echo "ERROR: Unexpected positional argument: $arg"
                echo "Usage: $0 [RESOURCE_GROUP] [--yes]"
                exit 1
            fi
            ;;
    esac
done

if [[ -z "$RG" ]]; then
    if [[ -f "$METADATA_FILE" ]]; then
        RG="$(python3 -c "import json; print(json.load(open('$METADATA_FILE'))['resourceGroup'])")"
        echo "Loaded resource group from deploy-metadata.json: $RG"
    else
        echo "Usage: $0 [RESOURCE_GROUP] [--yes]"
        echo ""
        echo "Resource group can be auto-detected from results/deploy-metadata.json"
        echo "or passed as a positional argument."
        exit 1
    fi
fi

if ! az group show --resource-group "$RG" --output none 2>/dev/null; then
    echo "Resource group not found (already deleted?): $RG"
    exit 0
fi

if [[ "$YES_FLAG" == "false" ]]; then
    echo "About to delete resource group: $RG"
    echo "This will destroy ALL resources in the group."
    read -r -p "Continue? [y/N] " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

echo "Deleting resource group: $RG"
echo "This runs asynchronously; the CLI returns immediately."
az group delete \
    --resource-group "$RG" \
    --yes \
    --no-wait

echo ""
echo "Deletion initiated. Verify completion with:"
echo "  az group show --resource-group $RG"
echo "  (expected: ResourceGroupNotFound after 3-10 minutes)"
