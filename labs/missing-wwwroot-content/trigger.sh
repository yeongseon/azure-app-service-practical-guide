#!/bin/bash
# Synthetic missing-content experiment. The ONLY file removal is the explicit, token-protected,
# instrumented POST /lab/remove-asset call made by this script, and it can remove only
# /assets/probe.txt. Every audit line carries a non-secret run ID.
#
# Usage: trigger.sh <RESOURCE_GROUP> <APP_NAME> <arm-a|arm-b-repeat|arm-b-diag|arm-b-settle>
#   arm-a         ordinary ZIP deploy: dated removal, probed discovery, and a restart-adjacency run
#   arm-b-repeat  Run From Package: the same removal attempt at first activation and again after a second deployment
#   arm-b-diag    file system view (mount, write test, package directory) with Run From Package on and off
#   arm-b-settle  enable the setting, wait for it to take effect, then deploy for the first time
set -euo pipefail

RG="${1:-}"
APP_NAME="${2:-}"
ARM="${3:-}"
OUT_DIR="${OUT_DIR:-artifacts/raw/experiment}"
ASSET="/assets/probe.txt"

if [ -z "$RG" ] || [ -z "$APP_NAME" ] || [ -z "$ARM" ]; then
    echo "Usage: $0 <RESOURCE_GROUP> <APP_NAME> <arm-a|arm-b-repeat|arm-b-diag|arm-b-settle>"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_ID="run-$(date -u +%Y%m%dT%H%M%SZ)"
# Per-run secret, configured after the first deployment of each arm. It is passed to the app as an app setting and to curl as a header; it is never
# written to the timeline, to artifacts, or to the repository.
LAB_TOKEN="$(openssl rand -hex 16)"
# tr strips the carriage return that a Windows-hosted Azure CLI appends to tsv output
APP_URL="https://$(az webapp show --resource-group "$RG" --name "$APP_NAME" --query defaultHostName --output tsv | tr -d '\r')"
mkdir -p "$OUT_DIR"
LOG="$OUT_DIR/${ARM}-timeline.log"
: > "$LOG"
ARM_STARTED_AT=""

now() { echo "$(date -u '+%Y-%m-%dT%H:%M:%S.%N' | cut -c1-23)Z"; }
mark() { echo "$(now) $*" | tee -a "$LOG"; }
fail() { mark "FAILED $*"; exit 1; }
probe() { curl --silent --output /dev/null --write-out "%{http_code}" --max-time 20 "$APP_URL$ASSET" || echo "000"; }
lab_curl() { curl --silent --max-time 30 --header "x-lab-token: $LAB_TOKEN" "$@"; }

started_at() {
    curl --silent --max-time 10 "$APP_URL/healthz" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("startedAt","unknown"))' 2>/dev/null || echo "unknown"
}

wait_new_process() {
    local previous="$1" current
    for _ in $(seq 1 60); do
        current=$(started_at)
        if [ "$current" != "$previous" ] && [ "$current" != "unknown" ]; then
            echo "$current"
            return 0
        fi
        sleep 5
    done
    return 1
}

wait_healthy() {
    local code
    for _ in $(seq 1 60); do
        code=$(curl --silent --output /dev/null --write-out "%{http_code}" --max-time 10 "$APP_URL/healthz" || echo "000")
        [ "$code" = "200" ] && return 0
        sleep 5
    done
    return 1
}

configure_token() {
    local before
    before=$(started_at)
    az webapp config appsettings set --resource-group "$RG" --name "$APP_NAME" --settings "LAB_TOKEN=$LAB_TOKEN" --output none
    mark "lab-token-configured (value not recorded) run=$RUN_ID"
    NEW=$(wait_new_process "$before") || fail "no new process after configuring the lab token"
    mark "process-after-token startedAt=$NEW"
    wait_healthy || fail "app not healthy after configuring the lab token"
}

deploy_zip() {
    "$SCRIPT_DIR/package.sh" "$OUT_DIR/deploy.zip" > "$OUT_DIR/package.txt"
    local before_started_at new_started_at
    before_started_at=$(started_at)
    mark "deploy-start mode=$1 startedAt-before=$before_started_at"
    az webapp deploy --resource-group "$RG" --name "$APP_NAME" --src-path "$OUT_DIR/deploy.zip" --type zip --output none
    mark "deploy-end mode=$1"
    # A 200 right after deploy can come from the previous process, so wait for a new process.
    new_started_at=$(wait_new_process "$before_started_at") || fail "no new process after deploy mode=$1"
    mark "new-process-after-deploy startedAt=$new_started_at"
    wait_healthy || fail "app not healthy after deploy mode=$1"
    mark "healthy-after-deploy"
}

remove_asset() {
    # Prints the HTTP status; the response body goes to the file given as $1.
    lab_curl --output "$1" --write-out "%{http_code}" --request POST "$APP_URL/lab/remove-asset?name=$ASSET&run=$RUN_ID"
}

write_manifest() {
    local sku runtime location cli_version git_rev git_dirty package_sha
    sku=$(az appservice plan list --resource-group "$RG" --query "[0].sku.name" --output tsv | tr -d '\r')
    runtime=$(az webapp config show --resource-group "$RG" --name "$APP_NAME" --query linuxFxVersion --output tsv | tr -d '\r')
    location=$(az webapp show --resource-group "$RG" --name "$APP_NAME" --query location --output tsv | tr -d '\r')
    cli_version=$(az version --query '"azure-cli"' --output tsv | tr -d '\r')
    git_rev=$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null || echo "unknown")
    if [ -n "$(git -C "$SCRIPT_DIR" status --porcelain -- . 2>/dev/null)" ]; then git_dirty=true; else git_dirty=false; fi
    package_sha=$(sha256sum "$OUT_DIR/deploy.zip" | cut -d' ' -f1)
    python3 - "$OUT_DIR/manifest-$ARM.json" "$RUN_ID" "$ARM" "$ARM_STARTED_AT" "$(now)" "$SKU_AT_START" "$sku" "$runtime" "$location" "$cli_version" "$git_rev" "$git_dirty" "$package_sha" <<'PY'
import json
import sys

keys = ['output', 'runId', 'arm', 'armStartedAt', 'armFinishedAt', 'skuAtStart', 'skuAtEnd', 'runtime', 'location',
        'azureCliVersion', 'sourceRevision', 'sourceDirtyAtRun', 'packageSha256']
values = sys.argv[1:]
manifest = dict(zip(keys[1:], values[1:]))
manifest['sourceDirtyAtRun'] = manifest['sourceDirtyAtRun'] == 'true'
with open(values[0], 'w', encoding='utf-8') as handle:
    json.dump(manifest, handle, indent=2)
PY
}

ARM_STARTED_AT="$(now)"
SKU_AT_START="$(az appservice plan list --resource-group "$RG" --query "[0].sku.name" --output tsv | tr -d '\r')"
mark "plan-sku-at-start=$SKU_AT_START"

case "$ARM" in
arm-a)
    deploy_zip ordinary-zip
    configure_token
    mark "baseline asset_status=$(probe)"

    # A1: removal observed by a 5-second probe loop
    mark "A1-probe-loop-start"
    (for _ in $(seq 1 18); do echo "$(now) $(probe)" >> "$OUT_DIR/arm-a1-probe.log"; sleep 5; done) &
    PROBE_PID=$!
    sleep 20
    mark "A1-remove-request"
    status=$(remove_asset "$OUT_DIR/arm-a1-remove-response.json")
    mark "A1-remove-response http_status=$status"
    wait "$PROBE_PID"
    mark "A1-probe-loop-end"

    # A2: removal with NO probing, then a restart, then the first probe after the restart
    deploy_zip ordinary-zip-restore
    mark "A2-baseline asset_status=$(probe)"
    mark "A2-probing-paused"
    mark "A2-remove-request"
    status=$(remove_asset "$OUT_DIR/arm-a2-remove-response.json")
    mark "A2-remove-response http_status=$status"
    sleep 90
    BEFORE_STARTED_AT=$(started_at)
    mark "A2-process-startedAt-before-restart=$BEFORE_STARTED_AT"
    mark "A2-restart-request"
    az webapp restart --resource-group "$RG" --name "$APP_NAME" --output none
    mark "A2-restart-returned"
    mark "A2-first-probe-after-restart-returned asset_status=$(probe) startedAt=$(started_at)"
    NEW_STARTED_AT=$(wait_new_process "$BEFORE_STARTED_AT") || fail "no new process after restart"
    mark "A2-new-process-observed startedAt=$NEW_STARTED_AT"
    wait_healthy || fail "app not healthy after restart"
    mark "A2-probe-after-new-process asset_status=$(probe)"
    curl --silent "$APP_URL/healthz" > "$OUT_DIR/arm-a2-state-after.json"
    ;;
arm-b-repeat)
    az webapp config appsettings delete --resource-group "$RG" --name "$APP_NAME" --setting-names WEBSITE_RUN_FROM_PACKAGE --output none
    mark "run-from-package-removed"
    sleep 120
    deploy_zip ordinary-zip
    configure_token
    mark "R-baseline-ordinary asset_status=$(probe)"
    az webapp config appsettings set --resource-group "$RG" --name "$APP_NAME" --settings WEBSITE_RUN_FROM_PACKAGE=1 --output none
    mark "run-from-package-enabled"
    deploy_zip run-from-package-first
    lab_curl "$APP_URL/lab/fs" > "$OUT_DIR/arm-b-repeat-first-fs.json"
    mark "R1-remove-request"
    status=$(remove_asset "$OUT_DIR/arm-b-repeat-first-remove.json")
    mark "R1-remove-response http_status=$status"
    deploy_zip run-from-package-second
    lab_curl "$APP_URL/lab/fs" > "$OUT_DIR/arm-b-repeat-second-fs.json"
    mark "R2-baseline asset_status=$(probe)"
    mark "R2-remove-request"
    status=$(remove_asset "$OUT_DIR/arm-b-repeat-second-remove.json")
    mark "R2-remove-response http_status=$status"
    mark "R2-asset-status-after-removal-attempt=$(probe)"
    ;;
arm-b-diag)
    az webapp config appsettings set --resource-group "$RG" --name "$APP_NAME" --settings WEBSITE_RUN_FROM_PACKAGE=1 --output none
    mark "run-from-package-enabled"
    deploy_zip run-from-package
    configure_token
    lab_curl "$APP_URL/lab/fs" > "$OUT_DIR/arm-b-diag-rfp-on.json"
    az webapp config appsettings delete --resource-group "$RG" --name "$APP_NAME" --setting-names WEBSITE_RUN_FROM_PACKAGE --output none
    mark "run-from-package-removed"
    deploy_zip ordinary-zip
    lab_curl "$APP_URL/lab/fs" > "$OUT_DIR/arm-b-diag-rfp-off.json"
    ;;
arm-b-settle)
    az webapp config appsettings delete --resource-group "$RG" --name "$APP_NAME" --setting-names WEBSITE_RUN_FROM_PACKAGE --output none
    mark "run-from-package-removed"
    sleep 120
    deploy_zip ordinary-zip
    configure_token
    mark "S-baseline-ordinary asset_status=$(probe)"
    BEFORE_STARTED_AT=$(started_at)
    az webapp config appsettings set --resource-group "$RG" --name "$APP_NAME" --settings WEBSITE_RUN_FROM_PACKAGE=1 --output none
    mark "run-from-package-enabled"
    SETTLED_STARTED_AT=$(wait_new_process "$BEFORE_STARTED_AT") || fail "no new process after enabling the setting"
    mark "setting-change-process-observed startedAt=$SETTLED_STARTED_AT"
    sleep 120
    mark "settle-wait-complete"
    deploy_zip run-from-package-after-settle
    lab_curl "$APP_URL/lab/fs" > "$OUT_DIR/arm-b-settle-fs.json"
    mark "S1-remove-request"
    status=$(remove_asset "$OUT_DIR/arm-b-settle-remove.json")
    mark "S1-remove-response http_status=$status"
    mark "S1-asset-status-after-removal-attempt=$(probe)"
    ;;
*)
    echo "Unknown arm: $ARM"
    exit 1
    ;;
esac

write_manifest
mark "arm-complete $ARM run=$RUN_ID"
