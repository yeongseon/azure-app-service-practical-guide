#!/bin/bash
set -euo pipefail

# E2 Kudu-only config visibility probe (L1-H3R).
#
# Design (per design-proposal.md revision 2, Oracle-approved):
#
# - Best-effort discovery via Kudu SCM only (no RDP, no config-zip upload).
# - 7 targeted fetches: each records HTTP status (200/401/403/404) in a
#   manifest CSV. Any status is a valid data point; there is no "failure".
# - Non-200 responses are renamed with .http-<code> suffix so a Kudu error
#   page cannot masquerade as a valid applicationHost.config XML.
#
# Interpretation is performed by verify.sh (not this script) because it
# requires cross-referencing with the E1 signature CSV and querying
# AppServiceHTTPLogs. This script only collects.
#
# H3R verdict routing (from design-proposal.md interpretation matrix):
# - Any artifact reveals requestTimeout >= 230000     -> H3R confirmed
# - Any artifact reveals requestTimeout <  230000     -> H3R partially falsified
# - All 7 return 401/403/404 with no httpPlatform el  -> H3R falsified (platform limitation finding)

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: $0 <APP_NAME> <RESOURCE_GROUP_NAME> [OUTPUT_DIR]"
    echo "Example: $0 app-winjavatimeoutl1-abcd rg-lab-winjavatimeoutl1 ./results"
    exit 1
fi

APP_NAME="$1"
RESOURCE_GROUP_NAME="$2"
OUTPUT_DIR="${3:-./lab1-results-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUTPUT_DIR"

SCM_HOST="${APP_NAME}.scm.azurewebsites.net"
MANIFEST="${OUTPUT_DIR}/e2-kudu-fetch-manifest.csv"
if [[ ! -f "$MANIFEST" ]]; then
    echo "probe_id,method,path_or_command,http_code,bytes,outfile" > "$MANIFEST"
fi

E2_SUMMARY="${OUTPUT_DIR}/e2-summary.md"

echo "=== E2 Kudu config visibility probe for $APP_NAME (rg=$RESOURCE_GROUP_NAME) ==="
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

# fetch_vfs_get writes the response body to $outfile, records HTTP status in
# the manifest CSV, and renames non-200 responses with a .http-<code> suffix.
# The rename is critical: Kudu returns HTML error pages on 404/403 that would
# otherwise pattern-match as XML if the file were named .xml or .config.
fetch_vfs_get() {
    local probe_id="$1"
    local path="$2"
    local outfile="$3"
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
    echo "${probe_id},GET,${path},${http_code},${bytes},$(basename "$final")" >> "$MANIFEST"
    echo "  [${probe_id}] GET ${path}: HTTP ${http_code} -> $(basename "$final") (${bytes} bytes)"
}

# fetch_command_post executes an arbitrary cmd.exe command via Kudu's
# /api/command REST endpoint. Body is a JSON object {"command": "...", "dir": "..."}.
# Used when /api/vfs cannot enumerate the target (registry queries, cross-drive
# type commands, etc.). Same manifest + rename semantics as fetch_vfs_get.
fetch_command_post() {
    local probe_id="$1"
    local command_label="$2"
    local outfile="$3"
    local body="$4"
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
    echo "${probe_id},POST,${command_label},${http_code},${bytes},$(basename "$final")" >> "$MANIFEST"
    echo "  [${probe_id}] POST /api/command '${command_label}': HTTP ${http_code} -> $(basename "$final") (${bytes} bytes)"
}

echo
echo "Step 2: Fetch 7 Kudu-visible artifacts (design-proposal.md E2)"

# Probe 1: applicationHost.config in inetpub/config (site-scoped IIS config location).
fetch_vfs_get "P1" \
    "/api/vfs/systemdrive/inetpub/config/applicationHost.config" \
    "${OUTPUT_DIR}/e2-p1-inetpub-applicationhost.config"

# Probe 2: applicationHost.config in Windows/System32/inetsrv/config (IIS server-scoped).
fetch_vfs_get "P2" \
    "/api/vfs/systemdrive/Windows/System32/inetsrv/config/applicationHost.config" \
    "${OUTPUT_DIR}/e2-p2-inetsrv-applicationhost.config"

# Probe 3: dir listing of C:\home\site (already known to work from Stage 0).
fetch_command_post "P3" \
    "dir C:\\home\\site" \
    "${OUTPUT_DIR}/e2-p3-dir-home-site.json" \
    '{"command":"dir C:\\home\\site","dir":"site"}'

# Probe 4: read site-scoped applicationHost.xdt (IIS config transform).
fetch_command_post "P4" \
    "type C:\\home\\site\\config\\applicationHost.xdt" \
    "${OUTPUT_DIR}/e2-p4-applicationhost-xdt.json" \
    '{"command":"type C:\\home\\site\\config\\applicationHost.xdt","dir":"site"}'

# Probe 5: dir listing of C:\home\LogFiles\httpPlatform (stdout log directory
# may exist even without a customer web.config if platform logging is on).
fetch_command_post "P5" \
    "dir C:\\home\\LogFiles\\httpPlatform" \
    "${OUTPUT_DIR}/e2-p5-dir-httpplatform-logs.json" \
    '{"command":"dir C:\\home\\LogFiles\\httpPlatform","dir":"site"}'

# Probe 6: VFS view of the same directory as P5 (parallel path via a
# different Kudu API; either may succeed independently).
fetch_vfs_get "P6" \
    "/api/vfs/LogFiles/httpPlatform/" \
    "${OUTPUT_DIR}/e2-p6-vfs-httpplatform-listing.json"

# Probe 7: Registry query for W3SVC parameters. Unlikely to succeed given
# App Service sandboxing; low cost to try and yields a definitive
# accessibility answer for the final lab guide.
fetch_command_post "P7" \
    "reg query HKLM\\System\\CurrentControlSet\\Services\\W3SVC\\Parameters" \
    "${OUTPUT_DIR}/e2-p7-reg-w3svc.json" \
    '{"command":"reg query HKLM\\System\\CurrentControlSet\\Services\\W3SVC\\Parameters","dir":"site"}'

echo
echo "Step 3: Grep any 200-response artifacts for httpPlatform / requestTimeout"

MATCHES_FOUND=0
GREP_LOG="${OUTPUT_DIR}/e2-httpplatform-grep.log"
: > "$GREP_LOG"

# Only grep files that came back HTTP 200. Non-200 files were renamed with
# .http-<code> suffix and contain Kudu error HTML, not IIS config.
for artifact in "${OUTPUT_DIR}"/e2-p1-inetpub-applicationhost.config \
                "${OUTPUT_DIR}"/e2-p2-inetsrv-applicationhost.config \
                "${OUTPUT_DIR}"/e2-p3-dir-home-site.json \
                "${OUTPUT_DIR}"/e2-p4-applicationhost-xdt.json \
                "${OUTPUT_DIR}"/e2-p5-dir-httpplatform-logs.json \
                "${OUTPUT_DIR}"/e2-p6-vfs-httpplatform-listing.json \
                "${OUTPUT_DIR}"/e2-p7-reg-w3svc.json; do
    if [[ -s "$artifact" ]]; then
        {
            echo "=== $(basename "$artifact") ==="
            grep -iE 'httpPlatform|requestTimeout|processPath|stdoutLogEnabled' "$artifact" || echo "  (no matches)"
            echo
        } >> "$GREP_LOG"
        if grep -iqE 'httpPlatform|requestTimeout' "$artifact"; then
            MATCHES_FOUND=$((MATCHES_FOUND + 1))
        fi
    fi
done

echo "  Grep results written to: $GREP_LOG"
echo "  Artifacts with httpPlatform/requestTimeout matches: $MATCHES_FOUND"

echo
echo "Step 4: Write preliminary E2 summary"
{
    echo "# E2 Kudu config visibility results (preliminary)"
    echo
    echo "- Target: \`$APP_NAME\` (rg=\`$RESOURCE_GROUP_NAME\`)"
    echo "- Manifest: \`$(basename "$MANIFEST")\`"
    echo "- Grep log: \`$(basename "$GREP_LOG")\`"
    echo
    echo "## Fetch manifest"
    echo
    echo "| probe | method | path/command | http | bytes | outfile |"
    echo "|---|---|---|---|---|---|"
    tail -n +2 "$MANIFEST" | while IFS=, read -r pid method path code bytes outfile; do
        printf "| %s | %s | \`%s\` | %s | %s | \`%s\` |\n" "$pid" "$method" "$path" "$code" "$bytes" "$outfile"
    done
    echo
    echo "## Preliminary H3R verdict"
    echo
    if [[ $MATCHES_FOUND -gt 0 ]]; then
        echo "- \`httpPlatform\` or \`requestTimeout\` markers found in $MATCHES_FOUND artifact(s)."
        echo "- Route to \`verify.sh\` for authoritative interpretation: any \`requestTimeout\` value in the grep log"
        echo "  should be checked against the 230000 ms threshold."
    else
        echo "- **Zero** artifacts contain \`httpPlatform\` or \`requestTimeout\` markers."
        echo "- Preliminary H3R verdict: **FALSIFIED** (effective config not Kudu-accessible on Windows App Service Java SE)."
        echo "- This is still a useful platform-limitation finding for the final lab guide."
    fi
    echo
    echo "## Next"
    echo
    echo "\`\`\`bash"
    echo "bash run-e3-stream-test.sh <APP_URL> $OUTPUT_DIR"
    echo "\`\`\`"
} > "$E2_SUMMARY"

echo
echo "E2 complete."
echo "  Manifest: $MANIFEST"
echo "  Summary:  $E2_SUMMARY"
echo
echo "Next: bash run-e3-stream-test.sh https://${APP_NAME}.azurewebsites.net $OUTPUT_DIR"
