#!/usr/bin/env bash
set -euo pipefail

# Lab 2 config collection: Dumps the effective App Service configuration by
# querying web app settings, site config, plan details, auto-heal rules, and
# diagnostic settings, then writes a timestamped JSON snapshot with appsettings
# secrets masked.
#
# Inputs:
#   - results/deploy-metadata.json for resourceGroup, webAppName,
#     webAppResourceId, and appServicePlanName
#
# Outputs:
#   - results/effective-config-<UTC timestamp>.json
#   - temporary intermediate JSON files in a scratch directory
#
# Dependencies:
#   - az
#   - jq

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly METADATA_FILE="$SCRIPT_DIR/results/deploy-metadata.json"

TMP_DIR=""
cleanup_tmp() {
    if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
        rm -rf "$TMP_DIR"
    fi
}
trap 'cleanup_tmp; echo "Interrupted." >&2; exit 130' INT TERM
trap 'cleanup_tmp' EXIT

if [[ ! -f "$METADATA_FILE" ]]; then
    echo "ERROR: deploy-metadata.json not found at: $METADATA_FILE"
    echo "  Run deploy.sh first to provision the environment."
    exit 1
fi

RG="$(python3 -c "import json; print(json.load(open('$METADATA_FILE'))['resourceGroup'])")"
APP_NAME="$(python3 -c "import json; print(json.load(open('$METADATA_FILE'))['webAppName'])")"
RESOURCE_ID="$(python3 -c "import json; print(json.load(open('$METADATA_FILE'))['webAppResourceId'])")"
PLAN_NAME="$(python3 -c "import json; print(json.load(open('$METADATA_FILE'))['appServicePlanName'])")"

mkdir -p "$SCRIPT_DIR/results"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
readonly TIMESTAMP
readonly OUTPUT_FILE="$SCRIPT_DIR/results/effective-config-${TIMESTAMP}.json"
TMP_DIR="$(mktemp -d)"

echo "=== Collecting effective config ==="
echo "  App:    $APP_NAME"
echo "  RG:     $RG"
echo "  Plan:   $PLAN_NAME"
echo "  Output: $OUTPUT_FILE"
echo ""

echo "Step 1/5: webapp config show"
az webapp config show \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --output json > "$TMP_DIR/webapp_config.json"
echo "  [OK] webapp config"

echo "Step 2/5: webapp config appsettings list (with secret sanitization)"
az webapp config appsettings list \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --output json > "$TMP_DIR/raw_appsettings.json"

python3 -c "
import json, re
pattern = re.compile(r'(secret|password|key|token|connectionstring)', re.IGNORECASE)
with open('$TMP_DIR/raw_appsettings.json') as f:
    settings = json.load(f)
for s in settings:
    if pattern.search(s.get('name', '')):
        s['value'] = '<redacted>'
with open('$TMP_DIR/webapp_appsettings.json', 'w') as f:
    json.dump(settings, f)
"
echo "  [OK] appsettings (secrets masked)"

echo "Step 3/5: appservice plan show"
az appservice plan show \
    --resource-group "$RG" \
    --name "$PLAN_NAME" \
    --output json > "$TMP_DIR/plan_config.json"
echo "  [OK] plan config"

echo "Step 4/5: autoheal rules"
az webapp config show \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --query 'autoHealRules' \
    --output json > "$TMP_DIR/autoheal_rules.json"
# az CLI writes empty output when the queried value is null; normalize to JSON null.
if [[ ! -s "$TMP_DIR/autoheal_rules.json" ]]; then
    echo "null" > "$TMP_DIR/autoheal_rules.json"
fi
echo "  [OK] autoheal rules"

echo "Step 5/5: diagnostic settings"
az monitor diagnostic-settings list \
    --resource "$RESOURCE_ID" \
    --output json > "$TMP_DIR/diagnostic_settings.json"
echo "  [OK] diagnostic settings"

echo ""
echo "Assembling output..."
python3 -c "
import json, os

tmp = '$TMP_DIR'
output = {}
for key in ['webapp_config', 'webapp_appsettings', 'plan_config', 'autoheal_rules', 'diagnostic_settings']:
    fpath = os.path.join(tmp, key + '.json')
    with open(fpath) as f:
        output[key] = json.load(f)

with open('$OUTPUT_FILE', 'w') as f:
    json.dump(output, f, indent=2)
"

echo ""
echo "============================================="
echo "  Effective config collected"
echo "============================================="
echo "  Output: $OUTPUT_FILE"
echo "  Keys:   webapp_config, webapp_appsettings, plan_config, autoheal_rules, diagnostic_settings"
echo ""
echo "  NOTE: No Kudu (.scm.azurewebsites.net) attempts."
echo "        Lab 1 confirmed Kudu returns 401 under MCAPS policy."
