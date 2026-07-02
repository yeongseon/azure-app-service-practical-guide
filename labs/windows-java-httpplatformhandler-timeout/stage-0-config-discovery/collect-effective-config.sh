#!/bin/bash
set -euo pipefail

PREFLIGHT=false
if [[ "${1:-}" == "--preflight" ]]; then
    PREFLIGHT=true
    shift
fi

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: $0 [--preflight] <APP_NAME> <RESOURCE_GROUP_NAME> [OUTPUT_DIR]"
    echo "Example (full):      $0 app-winjavatimeout-abcd rg-lab-winjavatimeout ./results"
    echo "Example (preflight): $0 --preflight app-winjavatimeout-abcd rg-lab-winjavatimeout ./results"
    echo ""
    echo "Preflight mode runs ARM config check + Kudu reachability + Auto-Heal isolation guard."
    echo "It exits non-zero if the environment is contaminated (Auto-Heal enabled, wrong jar name)."
    echo "Full mode runs the complete Kudu + ARM dump (run this AFTER the timeout probe)."
    exit 1
fi

APP_NAME="$1"
RESOURCE_GROUP_NAME="$2"
OUTPUT_DIR="${3:-./stage0-config-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUTPUT_DIR"

SCM_HOST="${APP_NAME}.scm.azurewebsites.net"
MANIFEST="${OUTPUT_DIR}/kudu-fetch-manifest.csv"
if [[ ! -f "$MANIFEST" ]]; then
    echo "path,http_code,bytes,outfile" > "$MANIFEST"
fi

MODE_LABEL="full"
if [[ "$PREFLIGHT" == "true" ]]; then
    MODE_LABEL="preflight"
fi

echo "=== Collecting effective config for $APP_NAME (rg=$RESOURCE_GROUP_NAME) ==="
echo "  Mode:       $MODE_LABEL"
echo "  Output dir: $OUTPUT_DIR"
echo "  Manifest:   $MANIFEST"
echo

echo "Step 1: Retrieve Kudu publishing credentials"
CREDS_JSON="$(az webapp deployment list-publishing-credentials \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --output json)"
KUDU_USER="$(echo "$CREDS_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["publishingUserName"])')"
KUDU_PASS="$(echo "$CREDS_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["publishingPassword"])')"

# fetch_kudu writes to a manifest CSV AND renames non-200 responses so a stray
# 404 body (e.g. Kudu's HTML error page) is never mistaken for a valid
# web.config or environment dump. Oracle sanity check issue D.
fetch_kudu() {
    local path="$1"
    local outfile="$2"
    local http_code
    http_code="$(curl --silent --show-error --output "$outfile" \
        --write-out '%{http_code}' \
        --max-time 60 \
        -u "${KUDU_USER}:${KUDU_PASS}" \
        "https://${SCM_HOST}${path}" || echo '000')"
    local bytes
    bytes="$(wc -c < "$outfile" 2>/dev/null | tr -d ' ' || echo 0)"
    local final="$outfile"
    if [[ "$http_code" != "200" ]]; then
        mv "$outfile" "${outfile}.http-${http_code}" 2>/dev/null || true
        final="${outfile}.http-${http_code}"
    fi
    echo "${path},${http_code},${bytes},$(basename "$final")" >> "$MANIFEST"
    echo "  ${path}: HTTP ${http_code} -> $(basename "$final") (${bytes} bytes)"
}

# fetch_kudu_command executes an arbitrary cmd.exe command via Kudu's
# /api/command REST endpoint. Used as a fallback when /api/vfs cannot
# enumerate the target directory (permission denied or 404). Oracle
# sanity check issue D fallback #3.
fetch_kudu_command() {
    local outfile="$1"
    local body="$2"
    local http_code
    http_code="$(curl --silent --show-error --output "$outfile" \
        --write-out '%{http_code}' \
        --max-time 60 \
        -u "${KUDU_USER}:${KUDU_PASS}" \
        -H 'Content-Type: application/json' \
        -X POST \
        --data "$body" \
        "https://${SCM_HOST}/api/command" || echo '000')"
    local bytes
    bytes="$(wc -c < "$outfile" 2>/dev/null | tr -d ' ' || echo 0)"
    local final="$outfile"
    if [[ "$http_code" != "200" ]]; then
        mv "$outfile" "${outfile}.http-${http_code}" 2>/dev/null || true
        final="${outfile}.http-${http_code}"
    fi
    echo "/api/command,${http_code},${bytes},$(basename "$final")" >> "$MANIFEST"
    echo "  /api/command ${body}: HTTP ${http_code} -> $(basename "$final") (${bytes} bytes)"
}

echo
echo "Step 2: Fetch ARM-plane configuration (siteConfig + appSettings)"
az webapp config show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --output json > "${OUTPUT_DIR}/az-webapp-config-show.json"
echo "  az webapp config show -> ${OUTPUT_DIR}/az-webapp-config-show.json"

az webapp config appsettings list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --output json > "${OUTPUT_DIR}/az-webapp-appsettings.json"
echo "  az webapp config appsettings list -> ${OUTPUT_DIR}/az-webapp-appsettings.json"

if [[ "$PREFLIGHT" == "true" ]]; then
    echo
    echo "Step 3: Preflight - Kudu reachability"
    fetch_kudu "/api/scm/info" "${OUTPUT_DIR}/kudu-scm-info.json"

    echo
    echo "Step 4: Preflight - verify Auto-Heal is disabled and Java jar name is set"
    FAIL=0

    AUTOHEAL="$(python3 -c '
import json
cfg = json.load(open("'"${OUTPUT_DIR}"'/az-webapp-config-show.json"))
print(cfg.get("autoHealEnabled", "MISSING"))
')"
    if [[ "$AUTOHEAL" != "False" ]]; then
        echo "  FAIL: siteConfig.autoHealEnabled=$AUTOHEAL (expected False)"
        FAIL=1
    else
        echo "  PASS: siteConfig.autoHealEnabled=False"
    fi

    AUTOHEAL_RULES="$(python3 -c '
import json
cfg = json.load(open("'"${OUTPUT_DIR}"'/az-webapp-config-show.json"))
rules = cfg.get("autoHealRules") or {}
triggers = rules.get("triggers") or {}
has_any = bool(triggers.get("requests") or triggers.get("slowRequests") or triggers.get("statusCodes") or triggers.get("privateBytesInKB"))
print("HAS_TRIGGERS" if has_any else "NONE")
')"
    if [[ "$AUTOHEAL_RULES" != "NONE" ]]; then
        echo "  FAIL: siteConfig.autoHealRules has triggers ($AUTOHEAL_RULES)"
        FAIL=1
    else
        echo "  PASS: siteConfig.autoHealRules has no active triggers"
    fi

    PROACTIVE="$(python3 -c '
import json
settings = json.load(open("'"${OUTPUT_DIR}"'/az-webapp-appsettings.json"))
found = [s["value"] for s in settings if s["name"] == "WEBSITE_PROACTIVE_AUTOHEAL_ENABLED"]
print(found[0].lower() if found else "MISSING")
')"
    if [[ "$PROACTIVE" != "false" ]]; then
        echo "  FAIL: WEBSITE_PROACTIVE_AUTOHEAL_ENABLED=$PROACTIVE (expected 'false', case-insensitive)"
        FAIL=1
    else
        echo "  PASS: WEBSITE_PROACTIVE_AUTOHEAL_ENABLED=false (case-insensitive match)"
    fi

    JARNAME="$(python3 -c '
import json
settings = json.load(open("'"${OUTPUT_DIR}"'/az-webapp-appsettings.json"))
found = [s["value"] for s in settings if s["name"] == "WEBSITE_JAVA_JAR_FILE_NAME"]
print(found[0] if found else "MISSING")
')"
    if [[ "$JARNAME" != "app.jar" ]]; then
        echo "  FAIL: WEBSITE_JAVA_JAR_FILE_NAME=$JARNAME (expected 'app.jar')"
        FAIL=1
    else
        echo "  PASS: WEBSITE_JAVA_JAR_FILE_NAME=app.jar"
    fi

    if [[ $FAIL -ne 0 ]]; then
        echo
        echo "PREFLIGHT FAILED: environment is contaminated for a Stage 0 discovery run."
        echo "Fix main.bicep (autoHealEnabled, autoHealRules, WEBSITE_PROACTIVE_AUTOHEAL_ENABLED,"
        echo "WEBSITE_JAVA_JAR_FILE_NAME) then re-deploy before running the timeout probe."
        echo "Contaminated timing curves cannot distinguish Auto-Heal recycles from front-end cuts."
        exit 1
    fi

    echo
    echo "PREFLIGHT PASSED. Environment is clean. Next:"
    echo "  bash run-timeout-probe.sh https://<hostname> $OUTPUT_DIR"
    exit 0
fi

echo
echo "Step 3/4: Fetch Kudu diagnostic endpoints (primary)"
fetch_kudu "/api/vfs/site/wwwroot/"           "${OUTPUT_DIR}/kudu-wwwroot-listing.json"
fetch_kudu "/api/vfs/site/wwwroot/web.config" "${OUTPUT_DIR}/kudu-web-config.xml"
fetch_kudu "/api/environment"                 "${OUTPUT_DIR}/kudu-environment.json"
fetch_kudu "/api/settings"                    "${OUTPUT_DIR}/kudu-settings.json"
fetch_kudu "/api/scm/info"                    "${OUTPUT_DIR}/kudu-scm-info.json"
fetch_kudu "/api/diagnostics/runtime"         "${OUTPUT_DIR}/kudu-diagnostics-runtime.json"
fetch_kudu "/api/processes"                   "${OUTPUT_DIR}/kudu-processes.json"

echo
echo "Step 3b/4: Fetch Kudu fallback endpoints (source-of-truth for web.config absence)"
fetch_kudu "/api/vfs/site/"                   "${OUTPUT_DIR}/kudu-site-listing.json"
fetch_kudu "/api/vfs/site/wwwroot/App_Data/"  "${OUTPUT_DIR}/kudu-appdata-listing.json"
fetch_kudu_command "${OUTPUT_DIR}/kudu-command-dir-wwwroot.json" \
    '{"command":"dir C:\\home\\site\\wwwroot","dir":"site\\wwwroot"}'
fetch_kudu_command "${OUTPUT_DIR}/kudu-command-dir-config.json" \
    '{"command":"dir C:\\home\\site\\wwwroot\\App_Data\\Config","dir":"site\\wwwroot"}'

echo
echo "Step 4/4: Additional ARM-plane detail"
az webapp show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --output json > "${OUTPUT_DIR}/az-webapp-show.json"
echo "  az webapp show -> ${OUTPUT_DIR}/az-webapp-show.json"

echo
echo "=== Key findings extraction ==="

# The web.config file may legitimately be absent for Java SE apps because
# App Service generates it at runtime rather than materializing it in
# wwwroot. Only grep the file if the fetch returned HTTP 200 (file exists)
# rather than the renamed .http-404 artifact (Kudu's HTML error page).
if [[ -s "${OUTPUT_DIR}/kudu-web-config.xml" ]]; then
    echo
    echo "-- web.config (searching for httpPlatformHandler and requestTimeout) --"
    grep -iE 'httpPlatform|requestTimeout|processPath|arguments' \
        "${OUTPUT_DIR}/kudu-web-config.xml" || echo "  (no matching lines)"
else
    echo
    echo "-- web.config NOT present in wwwroot (see manifest for HTTP status) --"
    echo "  This is expected for Java SE - the platform may generate web.config outside wwwroot."
    echo "  Cross-reference with: kudu-command-dir-wwwroot.json (dir listing)"
    echo "  and Lab 1 additional diagnostic for site-scoped applicationHost.config."
fi

if [[ -s "${OUTPUT_DIR}/az-webapp-config-show.json" ]]; then
    echo
    echo "-- siteConfig Java + Auto-Heal + Always On --"
    python3 -c '
import json
with open("'"${OUTPUT_DIR}"'/az-webapp-config-show.json") as f:
    cfg = json.load(f)
keys = ["javaVersion", "javaContainer", "javaContainerVersion",
        "windowsFxVersion", "linuxFxVersion",
        "alwaysOn", "autoHealEnabled", "autoHealRules",
        "requestTracingEnabled", "detailedErrorLoggingEnabled", "httpLoggingEnabled",
        "minTlsVersion", "http20Enabled", "clientCertEnabled"]
for k in keys:
    if k in cfg:
        print(f"  {k}: {json.dumps(cfg[k])}")
'
fi

if [[ -s "${OUTPUT_DIR}/az-webapp-appsettings.json" ]]; then
    echo
    echo "-- app settings relevant to timing / Auto-Heal / Java --"
    python3 -c '
import json
with open("'"${OUTPUT_DIR}"'/az-webapp-appsettings.json") as f:
    settings = json.load(f)
watch = {"WEBSITE_JAVA_JAR_FILE_NAME", "WEBSITE_PROACTIVE_AUTOHEAL_ENABLED",
         "WEBSITE_TIME_ZONE", "JAVA_OPTS", "JAVA_TOOL_OPTIONS",
         "WEBSITES_CONTAINER_START_TIME_LIMIT", "WEBSITES_PORT"}
found = {s["name"]: s["value"] for s in settings if s["name"] in watch}
if not found:
    print("  (no watched settings present)")
else:
    for k, v in sorted(found.items()):
        print(f"  {k}={v}")
'
fi

echo
echo "Config collection complete. All artifacts in: $OUTPUT_DIR"
echo "Manifest of Kudu fetches (path,http_code,bytes,outfile): $MANIFEST"
