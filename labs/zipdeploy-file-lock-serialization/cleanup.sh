#!/bin/bash
# Delete the lab resource group and retain contemporaneous proof that it is gone.
set -euo pipefail

RG="${1:-}"
OUT_DIR="${2:-artifacts/raw/evidence}"

if [ -z "$RG" ]; then
    echo "Usage: $0 <RESOURCE_GROUP> [OUTPUT_DIR]"
    exit 1
fi

mkdir -p "$OUT_DIR"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
az group delete --resource-group "$RG" --yes --output none
# tr strips the carriage return that a Windows-hosted Azure CLI appends to tsv output
EXISTS=$(az group exists --name "$RG" | tr -d '\r')
FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - "$OUT_DIR/cleanup.json" "$RG" "$STARTED_AT" "$FINISHED_AT" "$EXISTS" <<'PY'
import json
import sys

keys = ['resourceGroup', 'deleteStartedAt', 'checkedAt', 'groupExistsAfterDelete']
with open(sys.argv[1], 'w', encoding='utf-8') as handle:
    json.dump(dict(zip(keys, sys.argv[2:])), handle, indent=2)
PY
echo "groupExistsAfterDelete=$EXISTS"
