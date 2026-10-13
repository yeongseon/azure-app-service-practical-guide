#!/bin/bash
# Synthetic ZIP deploy file-lock and serialization experiment (Windows App Service, Node.js/iisnode).
# The only lock is the one the app creates on request via the token-protected POST /lab/hold-lock.
#
# Usage: trigger.sh <RESOURCE_GROUP> <APP_NAME> <no-lock-control|lock-ordinary|serialize|lock-rfp|lock-rfp-diag>
#   no-lock-control  the same changed-ZIP deployment with NO lock held (isolates the effect of the lock)
#   lock-rfp-diag  with Run From Package still enabled, ask PowerShell whether it can open the file exclusively
#   lock-ordinary  hold an exclusive handle on data/lockme.txt, then deploy a changed ZIP the ordinary way
#   lock-rfp       the same lock and deploy with Run From Package enabled and settled
#   serialize      submit deployment A, then deployment B while A is running
set -euo pipefail

RG="${1:-}"
APP_NAME="${2:-}"
ARM="${3:-}"
OUT_DIR="${OUT_DIR:-artifacts/raw/experiment}"

if [ -z "$RG" ] || [ -z "$APP_NAME" ] || [ -z "$ARM" ]; then
    echo "Usage: $0 <RESOURCE_GROUP> <APP_NAME> <no-lock-control|lock-ordinary|serialize|lock-rfp|lock-rfp-diag>"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_ID="run-$(date -u +%Y%m%dT%H%M%SZ)"
# Per-run secret, passed to the app as an app setting and to curl as a header. It is never written
# to the timeline, to artifacts, or to the repository.
LAB_TOKEN="$(openssl rand -hex 16)"
# tr strips the carriage return that a Windows-hosted Azure CLI appends to tsv output
APP_URL="https://$(az webapp show --resource-group "$RG" --name "$APP_NAME" --query defaultHostName --output tsv | tr -d '\r')"
mkdir -p "$OUT_DIR"
LOG="$OUT_DIR/${ARM}-timeline.log"
: > "$LOG"

now() { echo "$(date -u '+%Y-%m-%dT%H:%M:%S.%N' | cut -c1-23)Z"; }
mark() { echo "$(now) $*" | tee -a "$LOG"; }
fail() { mark "FAILED $*"; exit 1; }
state() { curl --silent --max-time 30 "$APP_URL/lab/state" || echo '{"error":"unreachable"}'; }
state_field() { state | python3 -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1],"unknown"))' "$1" 2>/dev/null || echo "unknown"; }
state_brief() { state | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps({"startedAt":d.get("startedAt"),"build":d.get("build"),"lockFile":d.get("lockFile"),"lockHolder":d.get("lockHolder")}))' 2>/dev/null || echo '{"error":"unreachable"}'; }
lab_curl() { curl --silent --max-time 60 --header "x-lab-token: $LAB_TOKEN" "$@"; }

wait_field() {
    # wait_field <field> <wanted>: wait until the state field equals the wanted value
    for _ in $(seq 1 60); do
        [ "$(state_field "$1")" = "$2" ] && return 0
        sleep 5
    done
    return 1
}

wait_new_process() {
    local previous="$1" current
    for _ in $(seq 1 60); do
        current=$(state_field startedAt)
        if [ "$current" != "$previous" ] && [ "$current" != "unknown" ]; then
            echo "$current"
            return 0
        fi
        sleep 5
    done
    return 1
}

configure_token() {
    local before new
    before=$(state_field startedAt)
    az webapp config appsettings set --resource-group "$RG" --name "$APP_NAME" --settings "LAB_TOKEN=$LAB_TOKEN" --output none
    mark "lab-token-configured (value not recorded) run=$RUN_ID"
    new=$(wait_new_process "$before") || fail "no new process after configuring the lab token"
    mark "process-after-token startedAt=$new"
}

deploy_build() {
    # One synchronous deployment of the given build id; the CLI result is recorded, not hidden.
    local build="$1" tag="$2" rc
    "$SCRIPT_DIR/package.sh" "$OUT_DIR/deploy-$build.zip" "$build" > "$OUT_DIR/package-$build.txt"
    mark "deploy-start $tag build=$build"
    set +e
    az webapp deploy --resource-group "$RG" --name "$APP_NAME" --src-path "$OUT_DIR/deploy-$build.zip" --type zip --output none > "$OUT_DIR/deploy-$tag.out" 2>&1
    rc=$?
    set -e
    mark "deploy-end $tag build=$build cli_exit=$rc"
}

hold_lock() {
    # hold_lock <tag> <required|optional>. The holder is a child process of the app, so it is lost
    # if the app process is recycled. Try up to three times and record every attempt. When the
    # lock is optional and never becomes effective, record that and continue.
    local attempt
    for attempt in 1 2 3; do
        lab_curl --request POST "$APP_URL/lab/hold-lock?file=data/lockme.txt" > "$OUT_DIR/$1-hold-attempt$attempt.json"
        mark "hold-lock-requested attempt=$attempt response=$(cat "$OUT_DIR/$1-hold-attempt$attempt.json") state=$(state_brief)"
        for _ in $(seq 1 10); do
            if [ "$(state | python3 -c 'import json,sys; print(json.load(sys.stdin)["lockFile"]["writeOpen"])' 2>/dev/null)" = "EBUSY" ]; then
                mark "lock-effective attempt=$attempt state=$(state_brief)"
                return 0
            fi
            sleep 3
        done
        mark "lock-not-effective attempt=$attempt state=$(state_brief)"
    done
    if [ "$2" = "optional" ]; then
        mark "lock-never-effective (continuing: the absence of a lock is itself the observation)"
        return 0
    fi
    fail "lock never became effective (writeOpen did not report EBUSY)"
}

collect_deployment_log() {
    az webapp log deployment show --resource-group "$RG" --name "$APP_NAME" --output json > "$OUT_DIR/$1-latest-deployment-log.json" 2>/dev/null || true
}

write_manifest() {
    local sku location cli_version git_rev git_dirty package_sha
    sku=$(az appservice plan list --resource-group "$RG" --query "[0].sku.name" --output tsv | tr -d '\r')
    location=$(az webapp show --resource-group "$RG" --name "$APP_NAME" --query location --output tsv | tr -d '\r')
    cli_version=$(az version --query '"azure-cli"' --output tsv | tr -d '\r')
    git_rev=$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null || echo "unknown")
    if [ -n "$(git -C "$SCRIPT_DIR" status --porcelain -- . 2>/dev/null)" ]; then git_dirty=true; else git_dirty=false; fi
    package_sha=$(sha256sum "$OUT_DIR"/deploy-*.zip | sha256sum | cut -d' ' -f1)
    python3 - "$OUT_DIR/manifest-$ARM.json" "$RUN_ID" "$ARM" "$ARM_STARTED_AT" "$(now)" "$SKU_AT_START" "$sku" "$location" "$cli_version" "$git_rev" "$git_dirty" "$package_sha" <<'PY'
import json
import sys

keys = ['runId', 'arm', 'armStartedAt', 'armFinishedAt', 'skuAtStart', 'skuAtEnd', 'location', 'azureCliVersion',
        'sourceRevision', 'sourceDirtyAtRun', 'packageSetSha256']
values = sys.argv[2:]
manifest = dict(zip(keys, values))
manifest['sourceDirtyAtRun'] = manifest['sourceDirtyAtRun'] == 'true'
manifest['runtime'] = 'Node.js 20 on Windows (iisnode)'
with open(sys.argv[1], 'w', encoding='utf-8') as handle:
    json.dump(manifest, handle, indent=2)
PY
}

ARM_STARTED_AT="$(now)"
SKU_AT_START="$(az appservice plan list --resource-group "$RG" --query "[0].sku.name" --output tsv | tr -d '\r')"
mark "plan-sku-at-start=$SKU_AT_START"

case "$ARM" in
no-lock-control)
    az webapp config appsettings delete --resource-group "$RG" --name "$APP_NAME" --setting-names WEBSITE_RUN_FROM_PACKAGE --output none
    mark "run-from-package-removed"
    sleep 150
    deploy_build 1 control-baseline
    wait_field build 1 || fail "build 1 not observed"
    configure_token
    sleep 20
    mark "baseline-state $(state_brief)"
    deploy_build 2 control-no-lock
    collect_deployment_log no-lock-control
    sleep 15
    mark "after-deploy-state $(state_brief)"
    ;;
lock-ordinary)
    az webapp config appsettings delete --resource-group "$RG" --name "$APP_NAME" --setting-names WEBSITE_RUN_FROM_PACKAGE --output none
    mark "run-from-package-removed"
    sleep 150
    deploy_build 1 ordinary-baseline
    wait_field build 1 || fail "build 1 not observed"
    configure_token
    sleep 20
    mark "baseline-state $(state_brief)"
    hold_lock lock-ordinary required
    deploy_build 2 ordinary-with-lock
    collect_deployment_log lock-ordinary
    sleep 15
    mark "after-deploy-state $(state_brief)"
    lab_curl --request POST "$APP_URL/lab/release-lock" > "$OUT_DIR/lock-ordinary-release.json" || true
    sleep 5
    mark "after-release-state $(state_brief)"
    ;;
serialize)
    mark "serialize-start"
    PAYLOAD_MB=40 "$SCRIPT_DIR/package.sh" "$OUT_DIR/deploy-A.zip" 5 > "$OUT_DIR/package-A.txt"
    PAYLOAD_MB=40 "$SCRIPT_DIR/package.sh" "$OUT_DIR/deploy-B.zip" 6 > "$OUT_DIR/package-B.txt"
    mark "submit-A"
    (set +e; az webapp deploy --resource-group "$RG" --name "$APP_NAME" --src-path "$OUT_DIR/deploy-A.zip" --type zip --output none > "$OUT_DIR/serialize-A.out" 2>&1; echo "cli_exit=$?" >> "$OUT_DIR/serialize-A.out"; mark "A-cli-returned") &
    PID_A=$!
    sleep 4
    mark "submit-B"
    (set +e; az webapp deploy --resource-group "$RG" --name "$APP_NAME" --src-path "$OUT_DIR/deploy-B.zip" --type zip --output none > "$OUT_DIR/serialize-B.out" 2>&1; echo "cli_exit=$?" >> "$OUT_DIR/serialize-B.out"; mark "B-cli-returned") &
    PID_B=$!
    wait "$PID_A" "$PID_B" || true
    sleep 30
    mark "final-state $(state_brief)"
    ;;
lock-rfp)
    az webapp config appsettings set --resource-group "$RG" --name "$APP_NAME" --settings WEBSITE_RUN_FROM_PACKAGE=1 --output none
    mark "run-from-package-enabled"
    sleep 150
    mark "settle-wait-complete"
    deploy_build 3 rfp-baseline
    wait_field build 3 || fail "build 3 not observed"
    configure_token
    sleep 20
    mark "baseline-state $(state_brief)"
    hold_lock lock-rfp optional
    deploy_build 4 rfp-with-lock
    collect_deployment_log lock-rfp
    sleep 15
    mark "after-deploy-state $(state_brief)"
    lab_curl --request POST "$APP_URL/lab/release-lock" > "$OUT_DIR/lock-rfp-release.json" || true
    sleep 5
    mark "after-release-state $(state_brief)"
    ;;
lock-rfp-diag)
    configure_token
    sleep 20
    lab_curl --request POST "$APP_URL/lab/ps-test" > "$OUT_DIR/lock-rfp-diag-ps-test.json"
    mark "ps-test response=$(cat "$OUT_DIR/lock-rfp-diag-ps-test.json")"
    mark "state $(state_brief)"
    ;;
*)
    echo "Unknown arm: $ARM"
    exit 1
    ;;
esac

az webapp log deployment list --resource-group "$RG" --name "$APP_NAME" --output json > "$OUT_DIR/${ARM}-deployment-records.json" 2>/dev/null || true
write_manifest
mark "arm-complete $ARM run=$RUN_ID"
