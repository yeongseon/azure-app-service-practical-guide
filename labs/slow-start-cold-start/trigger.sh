#!/bin/bash
set -euo pipefail

RESOURCE_GROUP_NAME="${1:-${RESOURCE_GROUP_NAME:-rg-lab-coldstart}}"
BASE_NAME="${2:-${BASE_NAME:-labcold}}"
LOCATION="${3:-${LOCATION:-koreacentral}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SOURCE_DIR="$SCRIPT_DIR/app"

echo "Lab configuration"
echo "  RESOURCE_GROUP_NAME: $RESOURCE_GROUP_NAME"
echo "  BASE_NAME: $BASE_NAME"
echo "  LOCATION: $LOCATION"
echo

echo "Phase 1/6: Deploy app and wait for initial cold start"
az group create \
    --name "$RESOURCE_GROUP_NAME" \
    --location "$LOCATION" \
    --output none

APP_NAME=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --template-file "$SCRIPT_DIR/main.bicep" \
    --parameters "baseName=$BASE_NAME" \
    --query "properties.outputs.webAppName.value" \
    --output tsv)

APP_HOSTNAME=$(az webapp show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --query "defaultHostName" \
    --output tsv)

APP_URL="https://$APP_HOSTNAME"

DEPLOY_PACKAGE_PATH="$(mktemp /tmp/slow-start-cold-start-XXXXXX.zip)"
python3 - "$APP_SOURCE_DIR" "$DEPLOY_PACKAGE_PATH" <<'PY'
import pathlib
import sys
import zipfile

source_dir = pathlib.Path(sys.argv[1])
package_path = pathlib.Path(sys.argv[2])

with zipfile.ZipFile(package_path, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
    for file_path in sorted(source_dir.rglob("*")):
        if file_path.is_file():
            package.write(file_path, file_path.relative_to(source_dir))
PY

az webapp deploy \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --src-path "$DEPLOY_PACKAGE_PATH" \
    --type zip \
    --clean true \
    --restart true \
    --output none

rm --force "$DEPLOY_PACKAGE_PATH"

echo "Deployed app: $APP_NAME"
echo "App URL: $APP_URL"
echo

measure_seconds() {
    local target_url="$1"
    curl \
        --silent \
        --show-error \
        --output /dev/null \
        --max-time 240 \
        --write-out "%{time_total}" \
        "$target_url"
}

echo "Phase 2/6: First request latency measurement (expected cold start)"
cold_first_request_seconds=$(measure_seconds "$APP_URL/timing")
printf "  First request latency: %.3f seconds\n" "$cold_first_request_seconds"
echo

echo "Phase 3/6: Ten warm request latency measurements"
warm_times=()
for request_index in $(seq 1 10); do
    request_time=$(measure_seconds "$APP_URL/fast")
    warm_times+=("$request_time")
    printf "  Warm request %02d: %.3f seconds\n" "$request_index" "$request_time"
done

warm_average_seconds=$(printf "%s\n" "${warm_times[@]}" | awk '{sum+=$1} END {if (NR>0) printf "%.3f", sum/NR; else print "0.000"}')
warm_min_seconds=$(printf "%s\n" "${warm_times[@]}" | awk 'NR==1 {min=$1} $1<min {min=$1} END {if (NR>0) printf "%.3f", min; else print "0.000"}')
warm_max_seconds=$(printf "%s\n" "${warm_times[@]}" | awk 'NR==1 {max=$1} $1>max {max=$1} END {if (NR>0) printf "%.3f", max; else print "0.000"}')
echo

echo "Phase 4/6: Restart app to force another cold start"
az webapp restart \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --output none
echo "  Restart command completed"
echo

echo "Phase 5/6: First request latency after restart (expected cold start)"
cold_after_restart_seconds=$(measure_seconds "$APP_URL/timing")
printf "  First request after restart latency: %.3f seconds\n" "$cold_after_restart_seconds"
echo

echo "Phase 6/6: Compare cold vs warm latencies"
cold_to_warm_ratio=$(awk -v cold="$cold_first_request_seconds" -v warm="$warm_average_seconds" 'BEGIN {if (warm > 0) printf "%.1f", cold/warm; else print "N/A"}')
restart_to_warm_ratio=$(awk -v cold="$cold_after_restart_seconds" -v warm="$warm_average_seconds" 'BEGIN {if (warm > 0) printf "%.1f", cold/warm; else print "N/A"}')

echo
printf "%-38s | %-12s\n" "Measurement" "Latency (s)"
printf "%-38s-+-%-12s\n" "--------------------------------------" "------------"
printf "%-38s | %-12.3f\n" "Cold request (post-deploy)" "$cold_first_request_seconds"
printf "%-38s | %-12.3f\n" "Warm request average (10 calls)" "$warm_average_seconds"
printf "%-38s | %-12.3f\n" "Warm request minimum" "$warm_min_seconds"
printf "%-38s | %-12.3f\n" "Warm request maximum" "$warm_max_seconds"
printf "%-38s | %-12.3f\n" "Cold request (post-restart)" "$cold_after_restart_seconds"

echo
echo "Relative comparison"
echo "  Post-deploy cold to warm-average ratio: ${cold_to_warm_ratio}x"
echo "  Post-restart cold to warm-average ratio: ${restart_to_warm_ratio}x"
echo
echo "Expected lesson: cold start latency is a one-time startup cost and should not be mistaken for steady-state regression."
