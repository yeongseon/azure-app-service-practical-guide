#!/usr/bin/env bash
# shellcheck disable=SC2317,SC2329
# SC2317: older CI ShellCheck (Ubuntu apt ~0.9/0.10) misflags helper functions
# in this shell library as unreachable; they are invoked indirectly from later
# case/if branches and dispatched at runtime. Local ShellCheck 0.11.0 correctly
# recognizes reachability. Scoped to this file to preserve SC2317 elsewhere.
# SC2329: functions invoked via trap or indirect dispatch below.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly RESULTS_DIR="${SCRIPT_DIR}/results"
readonly DEPLOY_METADATA_FILE="${RESULTS_DIR}/deploy-metadata.json"
readonly REPORT_FILE="${RESULTS_DIR}/verify-report.md"

# VERIFY CURRENT REGIONAL PRICE at https://azure.microsoft.com/en-us/pricing/details/app-service/windows/
readonly B1_HOURLY="TBD"
readonly LA_PER_GB="TBD"
readonly LAB_NAME="Windows Java httpPlatformHandler timeout - Lab 2 (loopback saturation)"

EXPERIMENT=""
RUN_ID=""
DRY_RUN=false
VERBOSE=false

WEB_APP_RESOURCE_ID=""
LOG_ANALYTICS_WORKSPACE_ID=""
WEB_APP_NAME=""
RESOURCE_GROUP=""

OVERALL_SIGNATURE_STATUS="INSUFFICIENT DATA"
MITIGATION_M1A_EFFECT="UNTESTED"
MITIGATION_M2_EFFECT="UNTESTED"
MITIGATION_M3_EFFECT="UNTESTED"

SIGNATURE_CONFIRMED=false
SIGNATURE_CHECKED=false
E4_PREFLIGHT_STATUS="NOT_YET_QUERIED"

usage() {
    cat >&2 <<'EOF'
Usage: ./verify.sh --experiment <name> [--run-id <n>] [--dry-run] [--verbose]

  --experiment   pre-e1 | e1 | e3 | preflight | e2 | e4 | e5 | all
  --run-id       Required only for --experiment e1
  --dry-run      Skip az queries and emit stub evidence
  --verbose      Print each az monitor log-analytics query command
EOF
}

emit_finding() {
    local section="$1"
    local label="$2"
    local text="$3"
    printf -- '- %s %s\n' "$label" "$text" >> "$REPORT_FILE"
}

write_section_header() {
    local title="$1"
    printf '## %s\n\n' "$title" >> "$REPORT_FILE"
}

write_section_status() {
    local status_text="$1"
    printf 'Status: %s\n\n' "$status_text" >> "$REPORT_FILE"
}

append_blank_line() {
    printf '\n' >> "$REPORT_FILE"
}

status_text_from_code() {
    local code="$1"
    case "$code" in
        0) printf 'COMPLETE' ;;
        1) printf 'PARTIAL' ;;
        2) printf 'MISSING' ;;
        *) printf 'UNKNOWN' ;;
    esac
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --experiment)
                [[ $# -ge 2 ]] || {
                    usage
                    exit 2
                }
                EXPERIMENT="$2"
                shift 2
                ;;
            --run-id)
                [[ $# -ge 2 ]] || {
                    usage
                    exit 2
                }
                RUN_ID="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            *)
                usage
                exit 2
                ;;
        esac
    done

    case "$EXPERIMENT" in
        pre-e1|e1|e3|preflight|e2|e4|e5|all) ;;
        *)
            usage
            exit 2
            ;;
    esac

    if [[ "$EXPERIMENT" == "e1" ]]; then
        if [[ -z "$RUN_ID" || ! "$RUN_ID" =~ ^[0-9]+$ ]]; then
            usage
            exit 2
        fi
    elif [[ -n "$RUN_ID" ]]; then
        printf 'INFO: ignoring --run-id for experiment %s\n' "$EXPERIMENT" >&2
    fi
}

ensure_results_dir() {
    mkdir -p "$RESULTS_DIR"
}

load_deploy_metadata() {
    if [[ ! -f "$DEPLOY_METADATA_FILE" ]]; then
        printf 'ERROR: Run ./deploy.sh first to generate deploy-metadata.json\n' >&2
        exit 3
    fi

    WEB_APP_RESOURCE_ID="$(jq --raw-output '.webAppResourceId // empty' "$DEPLOY_METADATA_FILE")"
    LOG_ANALYTICS_WORKSPACE_ID="$(jq --raw-output '.logAnalyticsWorkspaceId // empty' "$DEPLOY_METADATA_FILE")"
    WEB_APP_NAME="$(jq --raw-output '.webAppName // empty' "$DEPLOY_METADATA_FILE")"
    RESOURCE_GROUP="$(jq --raw-output '.resourceGroup // empty' "$DEPLOY_METADATA_FILE")"

    if [[ -z "$WEB_APP_RESOURCE_ID" || -z "$LOG_ANALYTICS_WORKSPACE_ID" ]]; then
        printf 'ERROR: deploy-metadata.json is missing webAppResourceId or logAnalyticsWorkspaceId\n' >&2
        exit 3
    fi

    # az monitor log-analytics query --workspace requires the customerId (GUID),
    # not the ARM resource ID. Resolve once and cache.
    LOG_ANALYTICS_CUSTOMER_ID="$(az monitor log-analytics workspace show \
        --ids "$LOG_ANALYTICS_WORKSPACE_ID" \
        --query customerId \
        --output tsv 2>/dev/null)"
    if [[ -z "$LOG_ANALYTICS_CUSTOMER_ID" ]]; then
        printf 'ERROR: Failed to resolve Log Analytics customerId from %s\n' "$LOG_ANALYTICS_WORKSPACE_ID" >&2
        exit 3
    fi
}

mask_subscription() {
    printf '<subscription-id>'
}

cost_cell() {
    local rate="$1"
    local units="$2"
    if [[ "$rate" == "TBD" ]]; then
        printf 'TBD - verify pricing'
    else
        python3 - <<PY
rate = float(${rate@Q})
units = float(${units@Q})
print(f"${rate} x {units:.2f} = ${rate * units:.2f}")
PY
    fi
}

render_report_preamble() {
    local generated_at
    local app_cost
    local log_cost
    generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    app_cost="$(cost_cell "$B1_HOURLY" "3.6")"
    log_cost="$(cost_cell "$LA_PER_GB" "0.3")"

    cat > "$REPORT_FILE" <<EOF
# Lab 2 Verification Report

## Metadata
- Lab: ${LAB_NAME}
- Generated: ${generated_at}
- Sub: $(mask_subscription)
- RG: ${RESOURCE_GROUP}
- Web App: ${WEB_APP_NAME}

## Cost Breakdown
| Item | Rate | Units | Cost |
|------|------|-------|------|
| App Service Plan B1 | ${B1_HOURLY}/hour | ~3.6h wall time | ${app_cost} |
| Log Analytics ingestion | ${LA_PER_GB}/GB | ~0.3GB estimated | ${log_cost} |
| **TOTAL** | | | **$~1-2** |

**NOTE**: Verify current regional price sheet before execution. This table uses placeholder rates.

Sources:
- App Service pricing: https://azure.microsoft.com/en-us/pricing/details/app-service/windows/
- Log Analytics pricing: https://azure.microsoft.com/en-us/pricing/details/monitor/

EOF
}

run_log_query() {
    local query="$1"
    if [[ "$DRY_RUN" == "true" ]]; then
        printf '[]'
        return 0
    fi

    if [[ "$VERBOSE" == "true" ]]; then
        printf 'az monitor log-analytics query --workspace %q --analytics-query %q --output json\n' \
            "$LOG_ANALYTICS_CUSTOMER_ID" "$query" >&2
    fi

    az monitor log-analytics query \
        --workspace "$LOG_ANALYTICS_CUSTOMER_ID" \
        --analytics-query "$query" \
        --output json
}

json_length() {
    local json_input="$1"
    jq 'length' <<< "$json_input"
}

manifest_value() {
    local file_path="$1"
    local jq_filter="$2"
    jq --raw-output "$jq_filter // empty" "$file_path"
}

resolve_single_manifest() {
    local experiment_name="$1"
    local direct_path="${RESULTS_DIR}/${experiment_name}/manifest.json"
    local matches=()

    if [[ -f "$direct_path" ]]; then
        printf '%s\n' "$direct_path"
        return 0
    fi

    case "$experiment_name" in
        e2|e4|e5)
            shopt -s nullglob
            matches=("${RESULTS_DIR}/${experiment_name}"/*/manifest.json)
            shopt -u nullglob
            ;;
        *)
            matches=()
            ;;
    esac

    if [[ ${#matches[@]} -gt 0 ]]; then
        printf '%s\n' "${matches[0]}"
        return 0
    fi

    return 1
}

resolve_e1_manifest() {
    local run_id="$1"
    local matches=()
    shopt -s nullglob
    matches=("${RESULTS_DIR}/e1/run-${run_id}-"*/manifest.json)
    shopt -u nullglob
    if [[ ${#matches[@]} -gt 0 ]]; then
        printf '%s\n' "${matches[0]}"
        return 0
    fi
    return 1
}

resolve_e3_manifests() {
    local matches=()
    local direct_path="${RESULTS_DIR}/e3/manifest.json"
    # Bug fix: top-level results/e3/manifest.json is deploy-webconfig-m1a.sh's deploy metadata,
    # not a probe manifest. Only accept it if its .experiment field is "e3" (probe run marker),
    # otherwise fall through to the per-canary glob which finds run-e3-m1a-probes.sh output.
    if [[ -f "$direct_path" ]]; then
        local top_experiment
        top_experiment="$(jq --raw-output '.experiment // ""' "$direct_path" 2>/dev/null || true)"
        if [[ "$top_experiment" == "e3" ]]; then
            printf '%s\n' "$direct_path"
            return 0
        fi
    fi

    shopt -s nullglob
    matches=("${RESULTS_DIR}/e3"/*/manifest.json)
    shopt -u nullglob
    if [[ ${#matches[@]} -gt 0 ]]; then
        printf '%s\n' "${matches[@]}"
        return 0
    fi
    return 1
}

iso_shift_seconds() {
    local iso_value="$1"
    local seconds="$2"
    python3 - <<PY
from datetime import datetime, timedelta, timezone
value = ${iso_value@Q}
delta = int(${seconds@Q})
parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
shifted = parsed + timedelta(seconds=delta)
print(shifted.strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
}

minutes_between() {
    local start_iso="$1"
    local end_iso="$2"
    python3 - <<PY
from datetime import datetime, timezone
start = datetime.strptime(${start_iso@Q}, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
end = datetime.strptime(${end_iso@Q}, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
print(round((end - start).total_seconds() / 60.0, 2))
PY
}

safe_pct() {
    local numerator="$1"
    local denominator="$2"
    python3 - <<PY
num = float(${numerator@Q})
den = float(${denominator@Q})
if den == 0:
    print("0.00")
else:
    print(f"{(100.0 * num / den):.2f}")
PY
}

record_signature_observed() {
    local count="$1"
    local checked="${2:-true}"
    if [[ "$checked" == "true" ]]; then
        SIGNATURE_CHECKED=true
    fi
    if [[ "$count" =~ ^[0-9]+$ ]] && [[ "$count" -gt 0 ]]; then
        SIGNATURE_CONFIRMED=true
        OVERALL_SIGNATURE_STATUS="CONFIRMED"
    fi
}

note_dry_run() {
    local section="$1"
    emit_finding "$section" "[Not Proven]" "--dry-run: KQL not executed, evidence label placeholder"
}

capture_return_code() {
    # Global-variable pattern + nested-call safety.
    # `return "$rc"` with non-zero rc triggers set -e in the caller. Store rc
    # in __CAPTURED_RC and always return 0 so callers read via the global.
    # Restore the caller's previous -e state (via $-) instead of blindly
    # calling `set -e`, so a nested call cannot re-enable -e while an outer
    # capture_return_code is still holding it off.
    local prev_e_state="off"
    [[ $- == *e* ]] && prev_e_state="on"
    __CAPTURED_RC=0
    set +e
    "$@"
    __CAPTURED_RC=$?
    if [[ "$prev_e_state" == "on" ]]; then
        set -e
    fi
    return 0
}

verify_pre_e1() {
    local section="Pre-E1"
    local manifest_path
    local start_time=""
    local end_time=""
    local results_path=""
    local query=""
    local query_json=""
    local raw_json_path=""
    local row_count="0"
    local rows_with_status="0"
    local rows_with_win32_0="0"
    local rows_with_time_window="0"
    local rows_with_win32_64="0"
    local verdict="fail"
    local status_code=1

    write_section_header "Experiment: Pre-E1 (Baseline Recheck)"

    if ! manifest_path="$(resolve_single_manifest "pre-e1")"; then
        write_section_status "SKIPPED"
        emit_finding "$section" "[Not Proven]" "SKIPPED - no manifest"
        append_blank_line
        return 1
    fi

    start_time="$(manifest_value "$manifest_path" '.startedAt')"
    end_time="$(manifest_value "$manifest_path" '.endedAt')"
    results_path="$(dirname "$manifest_path")"
    raw_json_path="${results_path}/kql-baseline-rows.json"

    write_section_status "EVALUATING"
    emit_finding "$section" "[Observed]" "Manifest loaded from $(basename "$(dirname "$manifest_path")")/$(basename "$manifest_path") with window ${start_time} .. ${end_time}"

    if [[ "$DRY_RUN" == "true" ]]; then
        note_dry_run "$section"
        emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code 0)"
        append_blank_line
        return 0
    fi

    query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${start_time}') .. datetime('${end_time}'))
| where CsUriStem == "/slow/240"
| project TimeGenerated, TimeTaken, ScStatus, ScSubStatus, ScWin32Status
| order by TimeGenerated asc
KQL
)
    query_json="$(run_log_query "$query")" || {
        emit_finding "$section" "[Unknown]" "KQL baseline-row query failed for Pre-E1"
        append_blank_line
        return 2
    }
    printf '%s\n' "$query_json" > "$raw_json_path"

    row_count="$(jq 'length' <<< "$query_json")"
    rows_with_status="$(jq '[.[] | select(((.ScStatus | tonumber?) // -1) == 500 and ((.ScSubStatus | tonumber?) // -1) == 121)] | length' <<< "$query_json")"
    rows_with_win32_0="$(jq '[.[] | select((((.ScWin32Status | tonumber?) // -1) == 0))] | length' <<< "$query_json")"
    rows_with_time_window="$(jq '[.[] | select((((.TimeTaken | tonumber?) // -1) >= 229800 and ((.TimeTaken | tonumber?) // -1) <= 230500))] | length' <<< "$query_json")"
    rows_with_win32_64="$(jq '[.[] | select((((.ScWin32Status | tonumber?) // -1) == 64))] | length' <<< "$query_json")"

    emit_finding "$section" "[Measured]" "Baseline rows for /slow/240: ${row_count} (raw KQL: $(basename "$raw_json_path"))"
    emit_finding "$section" "[Measured]" "Exact status rows (500/121/*): ${rows_with_status}/3; win32=0 rows: ${rows_with_win32_0}/3; TimeTaken in [229800,230500] ms: ${rows_with_time_window}/3; rows with win32=64: ${rows_with_win32_64}"

    if [[ "$row_count" -lt 3 ]]; then
        status_code=2
        verdict="degraded"
    elif [[ "$row_count" -eq 3 && "$rows_with_status" -eq 3 && "$rows_with_win32_0" -eq 3 && "$rows_with_time_window" -eq 3 && "$rows_with_win32_64" -eq 0 ]]; then
        status_code=0
        verdict="pass"
    else
        status_code=1
        verdict="fail"
    fi

    emit_finding "$section" "[Observed]" "Baseline verdict=${verdict}"
    emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code "$status_code")"
    append_blank_line
    return "$status_code"
}

verify_e1_run() {
    local run_id="$1"
    local section="E1"
    local manifest_path
    local rate=""
    local end_time=""
    local end_plus_drain=""
    local window_start=""
    local results_path=""
    local raw_json_path=""
    local final_window_query=""
    local final_window_json=""
    local total_requests="0"
    local signature_count="0"
    local pct_64="0"
    local verdict="negative"
    local status_code=1

    printf '### Run %s\n\n' "$run_id" >> "$REPORT_FILE"

    if ! manifest_path="$(resolve_e1_manifest "$run_id")"; then
        emit_finding "$section" "[Not Proven]" "Run ${run_id}: SKIPPED - no manifest"
        append_blank_line
        return 1
    fi

    rate="$(manifest_value "$manifest_path" '.params.rate')"
    end_time="$(manifest_value "$manifest_path" '.endedAt')"
    results_path="$(dirname "$manifest_path")"
    raw_json_path="${results_path}/kql-final-5min.json"

    end_plus_drain="$(manifest_value "$manifest_path" '.endedAtPlusDrain')"
    if [[ -z "$end_plus_drain" ]]; then
        end_plus_drain="$end_time"
    fi
    window_start="$(iso_shift_seconds "$end_plus_drain" -300)"

    emit_finding "$section" "[Observed]" "Run ${run_id} final-5-minute window ${window_start} .. ${end_plus_drain}; rate=${rate} req/s"

    if [[ "$DRY_RUN" == "true" ]]; then
        note_dry_run "$section"
        record_signature_observed 0 true
        emit_finding "$section" "[Observed]" "Run ${run_id} verdict: $(status_text_from_code 0)"
        append_blank_line
        return 0
    fi

    final_window_query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${window_start}') .. datetime('${end_plus_drain}'))
| where CsUriStem == "/slow/240"
| summarize total=count(), sc_500_121_64=countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64), pct_64=round(100.0 * countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64) / count(), 2)
KQL
)
    final_window_json="$(run_log_query "$final_window_query")" || {
        emit_finding "$section" "[Unknown]" "Run ${run_id}: final-5-minute KQL failed"
        append_blank_line
        return 2
    }
    printf '%s\n' "$final_window_json" > "$raw_json_path"
    total_requests="$(jq --raw-output '.[0].total // 0' <<< "$final_window_json")"
    signature_count="$(jq --raw-output '.[0].sc_500_121_64 // 0' <<< "$final_window_json")"
    pct_64="$(jq --raw-output '.[0].pct_64 // 0' <<< "$final_window_json")"

    emit_finding "$section" "[Measured]" "Run ${run_id} final-5-minute metrics: total=${total_requests}; sc_500_121_64=${signature_count}; pct_64=${pct_64}; raw KQL=$(basename "$raw_json_path")"

    if [[ "$total_requests" -eq 0 ]]; then
        verdict="degraded"
        status_code=2
    elif python3 - <<PY
sc = int(${signature_count@Q})
pct = float(${pct_64@Q})
import sys
sys.exit(0 if sc >= 5 and pct >= 1.0 else 1)
PY
    then
        verdict="positive"
        status_code=0
    else
        verdict="negative"
        status_code=1
    fi

    record_signature_observed "$signature_count" true

    emit_finding "$section" "[Observed]" "Run ${run_id} threshold verdict=${verdict}"
    emit_finding "$section" "[Observed]" "Run ${run_id} verdict: $(status_text_from_code "$status_code")"
    append_blank_line
    return "$status_code"
}

verify_e1() {
    local section="E1"
    local run_status=0
    local overall_status=2
    local run_manifest=""
    local run_id=""
    local rate=""
    local run_dir=""
    local run_json_path=""
    local metric_line=""
    local results_blob=""
    local synthesis_json=""
    local positive_count="0"
    local degraded_count="0"
    local total_runs="0"
    local first_positive_rate=""
    local first_positive_run=""
    local monotonicity_verdict=""
    local monotonicity_note=""
    local overall_verdict="insufficient"
    local matches=()

    write_section_header "Experiment: E1 (Per-Rate Probe)"

    if [[ "$EXPERIMENT" == "e1" ]]; then
        write_section_status "EVALUATING"
        capture_return_code verify_e1_run "$RUN_ID"
        return "$__CAPTURED_RC"
    fi

    shopt -s nullglob
    matches=("${RESULTS_DIR}/e1"/run-*/manifest.json)
    shopt -u nullglob
    if [[ ${#matches[@]} -eq 0 ]]; then
        write_section_status "SKIPPED"
        emit_finding "$section" "[Not Proven]" "SKIPPED - no E1 manifests"
        append_blank_line
        return 1
    fi

    write_section_status "EVALUATING"
    if [[ "$DRY_RUN" == "true" ]]; then
        note_dry_run "$section"
        emit_finding "$section" "[Observed]" "E1 synthesis verdict=insufficient"
        append_blank_line
        return 0
    fi

    overall_status=0
    results_blob="[]"
    for run_manifest in "${matches[@]}"; do
        run_id="$(manifest_value "$run_manifest" '.runId')"
        rate="$(manifest_value "$run_manifest" '.params.rate')"
        capture_return_code verify_e1_run "$run_id"
        run_status="$__CAPTURED_RC"
        run_dir="$(dirname "$run_manifest")"
        run_json_path="${run_dir}/kql-final-5min.json"
        if [[ -f "$run_json_path" ]]; then
            metric_line="$(jq --arg run_id "$run_id" --arg rate "$rate" --arg status "$run_status" '[.[0] // {}] | map({run_id: ($run_id | tonumber), rate: ($rate | tonumber), status_code: ($status | tonumber), total: (.total // 0), sc_500_121_64: (.sc_500_121_64 // 0), pct_64: (.pct_64 // 0)}) | .[0]' "$run_json_path")"
        else
            metric_line="$(jq -n --arg run_id "$run_id" --arg rate "$rate" --arg status "$run_status" '{run_id: ($run_id | tonumber), rate: ($rate | tonumber), status_code: ($status | tonumber), total: 0, sc_500_121_64: 0, pct_64: 0}')"
        fi
        results_blob="$(jq --argjson item "$metric_line" '. + [$item]' <<< "$results_blob")"
        if [[ "$run_status" -gt "$overall_status" ]]; then
            overall_status="$run_status"
        fi
    done

    total_runs="$(jq 'length' <<< "$results_blob")"
    positive_count="$(jq '[.[] | select(.status_code == 0)] | length' <<< "$results_blob")"
    degraded_count="$(jq '[.[] | select(.status_code == 2)] | length' <<< "$results_blob")"
    synthesis_json="$(python3 - <<PY
import json

runs = json.loads('''${results_blob}''')
runs = sorted(runs, key=lambda item: item["rate"])
positive_runs = [item for item in runs if item["status_code"] == 0]
above_threshold = []

first_positive_rate = ""
first_positive_run = ""
monotonicity_ok = True
monotonicity_note = "trivial"

if positive_runs:
    first_positive_rate = str(positive_runs[0]["rate"])
    first_positive_run = str(positive_runs[0]["run_id"])
    threshold_rate = float(first_positive_rate)
    above_threshold = [item for item in runs if float(item["rate"]) >= threshold_rate]
    previous = None
    notes = []
    for item in above_threshold:
        pct = float(item["pct_64"])
        if int(item["status_code"]) != 0:
            monotonicity_ok = False
            notes.append(
                f"run {item['run_id']} rate={item['rate']} status_code={item['status_code']} is not positive in the above-threshold region"
            )
        if previous is not None:
            floor = previous * 0.8
            if pct + 1e-9 < floor:
                monotonicity_ok = False
                notes.append(
                    f"run {item['run_id']} rate={item['rate']} pct_64={pct} dropped below 80% of prior pct_64={previous}"
                )
        previous = pct
    monotonicity_note = "; ".join(notes) if notes else "non-decreasing within 20% relative tolerance"

print(json.dumps({
    "first_positive_rate": first_positive_rate,
    "first_positive_run": first_positive_run,
    "monotonicity_ok": monotonicity_ok,
    "monotonicity_note": monotonicity_note,
}))
PY
)"
    first_positive_rate="$(jq --raw-output '.first_positive_rate // empty' <<< "$synthesis_json")"
    first_positive_run="$(jq --raw-output '.first_positive_run // empty' <<< "$synthesis_json")"
    monotonicity_verdict="$(jq --raw-output 'if .monotonicity_ok then "pass" else "fail" end' <<< "$synthesis_json")"
    monotonicity_note="$(jq --raw-output '.monotonicity_note // empty' <<< "$synthesis_json")"

    emit_finding "$section" "[Measured]" "E1 runs evaluated=${total_runs}; positive=${positive_count}; degraded=${degraded_count}"

    if [[ "$positive_count" -gt 0 ]]; then
        emit_finding "$section" "[Measured]" "First positive arrival rate=${first_positive_rate} req/s (run ${first_positive_run})"
        emit_finding "$section" "[Observed]" "Above-threshold monotonicity=${monotonicity_verdict} (${monotonicity_note})"
    else
        emit_finding "$section" "[Observed]" "First positive arrival rate not found"
    fi

    if [[ "$total_runs" -eq 0 || "$degraded_count" -eq "$total_runs" ]]; then
        overall_verdict="insufficient"
        overall_status=2
    elif [[ "$positive_count" -eq 0 ]]; then
        overall_verdict="falsified"
        overall_status=1
    elif [[ "$monotonicity_verdict" == "pass" ]]; then
        overall_verdict="confirmed"
        overall_status=0
    else
        overall_verdict="partial"
        overall_status=1
    fi

    emit_finding "$section" "[Observed]" "E1 synthesis verdict=${overall_verdict}"

    return "$overall_status"
}

verify_e3() {
    local section="E3"
    local manifests_text=""
    local manifest_path=""
    local manifest_list=()
    local canary=""
    local probe_count=""
    local canary_dir=""
    local probe_file=""
    local probe_index=""
    local probe_start=""
    local probe_end=""
    local mitigation_field=""
    local probe_query=""
    local probe_json=""
    local probe_json_path=""
    local probe_rows="0"
    local probe_classification=""
    local probe_summary=""
    local count_60s="0"
    local count_230s="0"
    local count_other="0"
    local overall_canary_verdict="insufficient"
    local status_code=2
    local run_status=0
    local probe_files=()

    write_section_header "Experiment: E3 (M1a Mitigation Probes)"

    if ! manifests_text="$(resolve_e3_manifests)"; then
        write_section_status "SKIPPED"
        emit_finding "$section" "[Not Proven]" "SKIPPED - no manifest"
        append_blank_line
        return 1
    fi

    write_section_status "EVALUATING"
    IFS=$'\n' read -r -d '' -a manifest_list < <(printf '%s\n' "$manifests_text" && printf '\0')
    status_code=0

    for manifest_path in "${manifest_list[@]}"; do
        canary="$(manifest_value "$manifest_path" '.params.canary')"
        probe_count="$(manifest_value "$manifest_path" '.params.probeCount')"
        mitigation_field="$(manifest_value "$manifest_path" '.params.mitigation')"
        canary_dir="$(dirname "$manifest_path")"
        shopt -s nullglob
        probe_files=("${canary_dir}"/probe-[0-9].log)
        shopt -u nullglob

        printf '### Canary: %s\n\n' "${canary:-unknown}" >> "$REPORT_FILE"
        emit_finding "$section" "[Observed]" "Manifest $(basename "$(dirname "$manifest_path")")/$(basename "$manifest_path") with probeCount=${probe_count}; detected probe files=${#probe_files[@]}"

        if [[ "$mitigation_field" == "M1a-web.config-timeout-extension" ]]; then
            emit_finding "$section" "[Observed]" "Manifest explicitly records mitigation=M1a-web.config-timeout-extension"
        else
            emit_finding "$section" "[Observed]" "Manifest does not include params.mitigation; treating canary=${canary:-unknown} as the M1a probe identifier"
        fi

        if [[ "$DRY_RUN" == "true" ]]; then
            note_dry_run "$section"
            emit_finding "$section" "[Observed]" "Canary ${canary:-unknown} verdict: $(status_text_from_code 0)"
            append_blank_line
            continue
        fi

        count_60s=0
        count_230s=0
        count_other=0

        for probe_file in "${probe_files[@]}"; do
            probe_index="$(basename "$probe_file" .log)"
            probe_index="${probe_index#probe-}"
            probe_start="$(awk -F': ' '/^started_utc:/ {print $2}' "$probe_file")"
            probe_end="$(awk -F': ' '/^ended_utc:/ {print $2}' "$probe_file")"
            probe_json_path="${canary_dir}/kql-probe-${probe_index}.json"

            if [[ -z "$probe_start" || -z "$probe_end" ]]; then
                emit_finding "$section" "[Unknown]" "Canary ${canary:-unknown} probe ${probe_index}: missing started_utc or ended_utc in $(basename "$probe_file")"
                count_other=$((count_other + 1))
                continue
            fi

            # Extend upper bound by 300s to cover AppServiceHTTPLogs ingest lag
            # (empirical: ~50-60s between request completion and TimeGenerated).
            local probe_query_end
            probe_query_end="$(iso_shift_seconds "$probe_end" 300)"

            probe_query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${probe_start}') .. datetime('${probe_query_end}'))
| where CsUriStem == "/slow/240"
| project TimeGenerated, TimeTaken, ScStatus, ScSubStatus, ScWin32Status
| order by TimeGenerated asc
KQL
)
            probe_json="$(run_log_query "$probe_query")" || {
                emit_finding "$section" "[Unknown]" "E3 KQL failed for canary ${canary:-unknown} probe ${probe_index}"
                append_blank_line
                return 2
            }
            printf '%s\n' "$probe_json" > "$probe_json_path"
            probe_rows="$(jq 'length' <<< "$probe_json")"
            probe_classification="$(jq --raw-output 'if length == 0 then "other" elif any(.[]; ((.TimeTaken | tonumber?) // -1) >= 58000 and ((.TimeTaken | tonumber?) // -1) <= 65000 and ( (((.ScStatus | tonumber?) // -1) == 500 and ((.ScSubStatus | tonumber?) // -1) == 121) or (((.ScStatus | tonumber?) // -1) == 502 and ((.ScSubStatus | tonumber?) // -1) == 3) )) then "60s" elif any(.[]; ((.TimeTaken | tonumber?) // -1) >= 229800 and ((.TimeTaken | tonumber?) // -1) <= 230500 and ((.ScStatus | tonumber?) // -1) == 500 and (((.ScSubStatus | tonumber?) // -1) == 121) and (((.ScWin32Status | tonumber?) // -1) == 0)) then "230s" else "other" end' <<< "$probe_json")"
            probe_summary="$(jq --raw-output 'if length == 0 then "(no rows)" else map("t=" + (((.TimeTaken | tonumber?) // -1) | tostring) + " status=" + (.ScStatus | tostring) + " sub=" + ((((.ScSubStatus | tonumber?) // -1)) | tostring) + " win32=" + ((((.ScWin32Status | tonumber?) // -1)) | tostring)) | join("; ") end' <<< "$probe_json")"

            case "$probe_classification" in
                60s) count_60s=$((count_60s + 1)) ;;
                230s) count_230s=$((count_230s + 1)) ;;
                *) count_other=$((count_other + 1)) ;;
            esac

            emit_finding "$section" "[Measured]" "Canary ${canary:-unknown} probe ${probe_index}: rows=${probe_rows}; classification=${probe_classification}; raw KQL=$(basename "$probe_json_path")"
            emit_finding "$section" "[Observed]" "Canary ${canary:-unknown} probe ${probe_index} samples: ${probe_summary}"
        done

        if [[ ${#probe_files[@]} -lt 3 ]]; then
            overall_canary_verdict="insufficient"
            run_status=2
        elif [[ "$count_60s" -eq ${#probe_files[@]} ]]; then
            overall_canary_verdict="confirmed"
            MITIGATION_M1A_EFFECT="EFFECTIVE"
            run_status=0
        elif [[ "$count_230s" -eq ${#probe_files[@]} ]]; then
            overall_canary_verdict="falsified_primary"
            MITIGATION_M1A_EFFECT="INSUFFICIENT"
            run_status=1
        else
            overall_canary_verdict="ambiguous"
            if [[ "$MITIGATION_M1A_EFFECT" == "UNTESTED" ]]; then
                MITIGATION_M1A_EFFECT="INSUFFICIENT"
            fi
            run_status=1
        fi

        emit_finding "$section" "[Measured]" "Canary ${canary:-unknown} classifications: 60s=${count_60s}; 230s=${count_230s}; other=${count_other}"
        emit_finding "$section" "[Observed]" "Canary ${canary:-unknown} M1a verdict=${overall_canary_verdict}"

        if [[ "$run_status" -gt "$status_code" ]]; then
            status_code="$run_status"
        fi
        emit_finding "$section" "[Observed]" "Canary ${canary:-unknown} verdict: $(status_text_from_code "$run_status")"
        append_blank_line
    done

    return "$status_code"
}

verify_preflight() {
    local section="Preflight"
    local manifest_path=""

    write_section_header "Preflight: M2 Platform Log Verification"

    if ! manifest_path="$(resolve_single_manifest "preflight")"; then
        write_section_status "SKIPPED"
        emit_finding "$section" "[Not Proven]" "SKIPPED - no manifest"
        append_blank_line
        E4_PREFLIGHT_STATUS="NOT_YET_QUERIED"
        return 1
    fi

    write_section_status "EVALUATING"
    E4_PREFLIGHT_STATUS="$(manifest_value "$manifest_path" '."preflight-status"')"
    emit_finding "$section" "[Observed]" "preflight-status=${E4_PREFLIGHT_STATUS}"

    case "$E4_PREFLIGHT_STATUS" in
        PROCEED)
            emit_finding "$section" "[Observed]" "Custom Auto-Heal AppServicePlatformLogs visible - E4 recycle detection VERIFIED"
            emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code 0)"
            append_blank_line
            return 0
            ;;
        UNVERIFIABLE)
            emit_finding "$section" "[Unknown]" "AppServicePlatformLogs not emitting Auto-Heal events - E4 recycle timing and recycle effect will be [Unknown]"
            MITIGATION_M2_EFFECT="UNVERIFIABLE"
            emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code 1)"
            append_blank_line
            return 1
            ;;
        NOT_YET_QUERIED|"")
            emit_finding "$section" "[Not Proven]" "Preflight KQL not yet run - re-invoke preflight-platform-logs.sh --kql-only after E2 load"
            emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code 1)"
            append_blank_line
            return 1
            ;;
        *)
            emit_finding "$section" "[Unknown]" "Unexpected preflight-status value: ${E4_PREFLIGHT_STATUS}"
            emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code 2)"
            append_blank_line
            return 2
            ;;
    esac
}

verify_e2() {
    local section="E2"
    local manifest_path=""
    local rate=""
    local start_time=""
    local end_time=""
    local duration_minutes=""
    local expected_floor=""
    local summary_query=""
    local summary_json=""
    local final_window_query=""
    local final_window_json=""
    local console_query=""
    local console_json=""
    local total_requests="0"
    local total_500="0"
    local total_signature="0"
    local time_p50="0"
    local time_p95="0"
    local time_p99="0"
    local final_total="0"
    local final_signature="0"
    local final_pct="0"
    local console_hits="0"
    local console_samples=""
    local status_code=1

    write_section_header "Experiment: E2 (Sustained Load)"

    if ! manifest_path="$(resolve_single_manifest "e2")"; then
        write_section_status "SKIPPED"
        emit_finding "$section" "[Not Proven]" "SKIPPED - no manifest"
        append_blank_line
        return 1
    fi

    rate="$(manifest_value "$manifest_path" '.params.rate')"
    start_time="$(manifest_value "$manifest_path" '.startedAt')"
    end_time="$(manifest_value "$manifest_path" '.endedAt')"
    duration_minutes="$(minutes_between "$start_time" "$end_time")"
    expected_floor="$(python3 - <<PY
rate = float(${rate@Q})
print(int(0.9 * (rate * 1200)))
PY
)"

    write_section_status "EVALUATING"
    emit_finding "$section" "[Observed]" "Manifest window ${start_time} .. ${end_time}; rate=${rate} req/s; expected sample-size floor=${expected_floor} requests"

    if [[ "$DRY_RUN" == "true" ]]; then
        note_dry_run "$section"
        record_signature_observed 0 true
        emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code 0)"
        append_blank_line
        return 0
    fi

    summary_query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${start_time}') .. datetime('${end_time}'))
| where CsUriStem == "/slow/240"
| summarize total=count(), total_500=countif(ScStatus == 500), sc_500_121_64=countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64), time_taken_p50=percentile(TimeTaken, 50), time_taken_p95=percentile(TimeTaken, 95), time_taken_p99=percentile(TimeTaken, 99), sc_502=countif(ScStatus == 502), sc_503=countif(ScStatus == 503)
KQL
)
    summary_json="$(run_log_query "$summary_query")" || {
        emit_finding "$section" "[Unknown]" "E2 HTTP summary KQL failed"
        append_blank_line
        return 2
    }
    total_requests="$(jq --raw-output '.[0].total // 0' <<< "$summary_json")"
    total_500="$(jq --raw-output '.[0].total_500 // 0' <<< "$summary_json")"
    total_signature="$(jq --raw-output '.[0].sc_500_121_64 // 0' <<< "$summary_json")"
    time_p50="$(jq --raw-output '.[0].time_taken_p50 // 0' <<< "$summary_json")"
    time_p95="$(jq --raw-output '.[0].time_taken_p95 // 0' <<< "$summary_json")"
    time_p99="$(jq --raw-output '.[0].time_taken_p99 // 0' <<< "$summary_json")"

    final_window_query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${end_time}') - 5m .. datetime('${end_time}'))
| where CsUriStem == "/slow/240"
| summarize total_final_5min=count(), signature_final_5min=countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64)
KQL
)
    final_window_json="$(run_log_query "$final_window_query")" || {
        emit_finding "$section" "[Unknown]" "E2 final-5-minute KQL failed"
        append_blank_line
        return 2
    }
    final_total="$(jq --raw-output '.[0].total_final_5min // 0' <<< "$final_window_json")"
    final_signature="$(jq --raw-output '.[0].signature_final_5min // 0' <<< "$final_window_json")"
    final_pct="$(safe_pct "$final_signature" "$final_total")"

    console_query=$(cat <<KQL
AppServiceConsoleLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${start_time}') .. datetime('${end_time}'))
| where ResultDescription has_any ("GC", "Full GC", "RejectedExecution", "thread", "executor", "OutOfMemory")
| project TimeGenerated, ResultDescription
| order by TimeGenerated asc
| limit 20
KQL
)
    console_json="$(run_log_query "$console_query")" || {
        emit_finding "$section" "[Unknown]" "E2 console-log KQL failed"
        append_blank_line
        return 2
    }
    console_hits="$(json_length "$console_json")"
    console_samples="$(jq --raw-output 'if length == 0 then "(none)" else map(.ResultDescription) | join(" || ") end' <<< "$console_json")"

    emit_finding "$section" "[Measured]" "Sustained-load totals: requests=${total_requests}; HTTP 500=${total_500}; signature 500.121.64=${total_signature}; final-5-minute signature rate=${final_pct}% (${final_signature}/${final_total})"
    emit_finding "$section" "[Measured]" "Duration per request: p50=${time_p50} ms; p95=${time_p95} ms; p99=${time_p99} ms over ${duration_minutes} minutes"
    emit_finding "$section" "[Strongly Suggested]" "Console-log saturation signals (${console_hits} hits): ${console_samples}"

    record_signature_observed "$total_signature" true

    if [[ "$total_requests" -eq 0 ]]; then
        status_code=2
    elif [[ "$total_requests" -lt "$expected_floor" ]]; then
        emit_finding "$section" "[Not Proven]" "Sample-size floor missed: total=${total_requests} < expected floor ${expected_floor}"
        status_code=1
    elif [[ "$total_signature" -gt 0 ]]; then
        emit_finding "$section" "[Strongly Suggested]" "Sustained load preserves the 500.121.64 degradation pattern under pressure"
        status_code=0
    else
        emit_finding "$section" "[Strongly Suggested]" "Sustained load did not reproduce 500.121.64 in this window"
        status_code=1
    fi

    emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code "$status_code")"
    append_blank_line
    return "$status_code"
}

verify_e4() {
    local section="E4"
    local manifest_path=""
    local preflight_manifest=""
    local start_time=""
    local end_time=""
    local platform_query=""
    local platform_json=""
    local http_timeline_query=""
    local http_timeline_json=""
    local pre_query=""
    local pre_json=""
    local post_query=""
    local post_json=""
    local first_recycle=""
    local fifth_signature_time=""
    local pre_start=""
    local post_end=""
    local pre_pct="0"
    local post_pct="0"
    local pre_total="0"
    local pre_signature="0"
    local post_total="0"
    local post_signature="0"
    local platform_rows="0"
    local timeline_summary=""
    local latency_minutes=""
    local status_code=1

    write_section_header "Experiment: E4 (M2 Auto-Heal)"

    if ! manifest_path="$(resolve_single_manifest "e4")"; then
        write_section_status "SKIPPED"
        emit_finding "$section" "[Not Proven]" "SKIPPED - no manifest"
        append_blank_line
        return 1
    fi

    if preflight_manifest="$(resolve_single_manifest "preflight" 2>/dev/null)"; then
        E4_PREFLIGHT_STATUS="$(manifest_value "$preflight_manifest" '."preflight-status"')"
    fi

    start_time="$(manifest_value "$manifest_path" '.startedAt')"
    end_time="$(manifest_value "$manifest_path" '.endedAt')"
    write_section_status "EVALUATING"
    emit_finding "$section" "[Observed]" "Manifest window ${start_time} .. ${end_time}; preflight-status=${E4_PREFLIGHT_STATUS}"

    if [[ "$DRY_RUN" == "true" ]]; then
        note_dry_run "$section"
        emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code 0)"
        append_blank_line
        return 0
    fi

    http_timeline_query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${start_time}') .. datetime('${end_time}'))
| where CsUriStem == "/slow/240"
| summarize total=count(), signature_500_121_64=countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64) by bin(TimeGenerated, 30s)
| extend pct_64 = round(100.0 * signature_500_121_64 / iif(total == 0, 1.0, todouble(total)), 2)
| order by TimeGenerated asc
KQL
)
    http_timeline_json="$(run_log_query "$http_timeline_query")" || {
        emit_finding "$section" "[Unknown]" "E4 HTTP timeline KQL failed"
        append_blank_line
        return 2
    }
    timeline_summary="$(jq --raw-output 'if length == 0 then "(none)" else map("\(.TimeGenerated): pct_64=\(.pct_64) total=\(.total)") | .[0:8] | join("; ") end' <<< "$http_timeline_json")"
    emit_finding "$section" "[Observed]" "30-second HTTP timeline sample: ${timeline_summary}"

    if [[ "$E4_PREFLIGHT_STATUS" != "PROCEED" ]]; then
        emit_finding "$section" "[Unknown]" "Preflight did not verify AppServicePlatformLogs emission; recycle timing and recycle-effect remain [Unknown]"
        emit_finding "$section" "[Observed]" "HTTP trend captured without a recycle-event anchor; descriptive only"
        MITIGATION_M2_EFFECT="UNVERIFIABLE"
        emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code 1)"
        append_blank_line
        return 1
    fi

    platform_query=$(cat <<KQL
AppServicePlatformLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${start_time}') .. datetime('${end_time}'))
| where OperationName startswith "AutoHealing"
| project TimeGenerated, OperationName, Level, Message
| order by TimeGenerated asc
KQL
)
    platform_json="$(run_log_query "$platform_query")" || {
        emit_finding "$section" "[Unknown]" "E4 platform-log KQL failed"
        append_blank_line
        return 2
    }
    platform_rows="$(json_length "$platform_json")"
    first_recycle="$(jq --raw-output '.[0].TimeGenerated // empty' <<< "$platform_json")"

    if [[ "$platform_rows" -eq 0 || -z "$first_recycle" ]]; then
        emit_finding "$section" "[Measured]" "No AutoHealing event surfaced in AppServicePlatformLogs during the E4 window"
        MITIGATION_M2_EFFECT="INSUFFICIENT"
        emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code 1)"
        append_blank_line
        return 1
    fi

    fifth_signature_time="$(jq --raw-output '[.[] | select(.signature_500_121_64 > 0) | .TimeGenerated][4] // empty' <<< "$http_timeline_json")"
    if [[ -n "$fifth_signature_time" ]]; then
        latency_minutes="$(minutes_between "$fifth_signature_time" "$first_recycle")"
        emit_finding "$section" "[Measured]" "First recycle event at ${first_recycle}; latency from 5th signature-completion bin=${latency_minutes} minutes"
    else
        emit_finding "$section" "[Measured]" "First recycle event at ${first_recycle}; insufficient signature bins to estimate 5th-completion latency"
    fi

    pre_start="$(iso_shift_seconds "$first_recycle" -300)"
    post_end="$(iso_shift_seconds "$first_recycle" 300)"

    pre_query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${pre_start}') .. datetime('${first_recycle}'))
| where CsUriStem == "/slow/240"
| summarize total=count(), signature=countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64)
KQL
)
    pre_json="$(run_log_query "$pre_query")" || {
        emit_finding "$section" "[Unknown]" "E4 pre-recycle comparison KQL failed"
        append_blank_line
        return 2
    }
    post_query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${first_recycle}') .. datetime('${post_end}'))
| where CsUriStem == "/slow/240"
| summarize total=count(), signature=countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64)
KQL
)
    post_json="$(run_log_query "$post_query")" || {
        emit_finding "$section" "[Unknown]" "E4 post-recycle comparison KQL failed"
        append_blank_line
        return 2
    }

    pre_total="$(jq --raw-output '.[0].total // 0' <<< "$pre_json")"
    pre_signature="$(jq --raw-output '.[0].signature // 0' <<< "$pre_json")"
    post_total="$(jq --raw-output '.[0].total // 0' <<< "$post_json")"
    post_signature="$(jq --raw-output '.[0].signature // 0' <<< "$post_json")"
    pre_pct="$(safe_pct "$pre_signature" "$pre_total")"
    post_pct="$(safe_pct "$post_signature" "$post_total")"

    emit_finding "$section" "[Measured]" "Pre-recycle 5-minute window: ${pre_signature}/${pre_total} signature requests (${pre_pct}%)"
    emit_finding "$section" "[Measured]" "Post-recycle 5-minute window: ${post_signature}/${post_total} signature requests (${post_pct}%)"

    if [[ "$pre_total" -eq 0 && "$post_total" -eq 0 ]]; then
        status_code=2
    elif python3 - <<PY
pre = float(${pre_pct@Q})
post = float(${post_pct@Q})
import sys
sys.exit(0 if pre > 0 and post < (pre / 2.0) else 1)
PY
    then
        emit_finding "$section" "[Measured]" "Auto-Heal recycle coincides with >50% reduction in signature rate after recycle"
        MITIGATION_M2_EFFECT="EFFECTIVE"
        status_code=0
    else
        emit_finding "$section" "[Measured]" "Auto-Heal recycle did not reduce signature rate below 50% of the pre-recycle rate"
        MITIGATION_M2_EFFECT="INSUFFICIENT"
        status_code=1
    fi

    emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code "$status_code")"
    append_blank_line
    return "$status_code"
}

verify_e5() {
    local section="E5"
    local manifest_path=""
    local e2_manifest_path=""
    local instance_count=""
    local start_time=""
    local end_time=""
    local e2_end_time=""
    local e2_query=""
    local e2_json=""
    local e5_query=""
    local e5_json=""
    local distribution_query=""
    local distribution_json=""
    local e2_total="0"
    local e2_signature="0"
    local e5_total="0"
    local e5_signature="0"
    local e2_pct="0"
    local e5_pct="0"
    local reduction_pct="0"
    local distribution_summary=""
    local status_code=1

    write_section_header "Experiment: E5 (Scale-Out)"

    if ! manifest_path="$(resolve_single_manifest "e5")"; then
        write_section_status "SKIPPED"
        emit_finding "$section" "[Not Proven]" "SKIPPED - no manifest"
        append_blank_line
        return 1
    fi
    if ! e2_manifest_path="$(resolve_single_manifest "e2")"; then
        write_section_status "PARTIAL"
        emit_finding "$section" "[Not Proven]" "E5 comparison requires an E2 baseline manifest"
        append_blank_line
        return 1
    fi

    instance_count="$(manifest_value "$manifest_path" '.params.planInstanceCount')"
    if [[ -z "$instance_count" ]]; then
        instance_count="$(manifest_value "$manifest_path" '.params.scaledInstances')"
    fi
    start_time="$(manifest_value "$manifest_path" '.startedAt')"
    end_time="$(manifest_value "$manifest_path" '.endedAt')"
    e2_end_time="$(manifest_value "$e2_manifest_path" '.endedAt')"

    write_section_status "EVALUATING"
    emit_finding "$section" "[Observed]" "Manifest window ${start_time} .. ${end_time}; planInstanceCount=${instance_count:-unknown}"

    if [[ "$DRY_RUN" == "true" ]]; then
        note_dry_run "$section"
        emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code 0)"
        append_blank_line
        return 0
    fi

    e2_query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${e2_end_time}') - 5m .. datetime('${e2_end_time}'))
| where CsUriStem == "/slow/240"
| summarize total=count(), signature=countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64)
KQL
)
    e2_json="$(run_log_query "$e2_query")" || {
        emit_finding "$section" "[Unknown]" "E5 baseline E2 comparison query failed"
        append_blank_line
        return 2
    }
    e5_query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${end_time}') - 5m .. datetime('${end_time}'))
| where CsUriStem == "/slow/240"
| summarize total=count(), signature=countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64)
KQL
)
    e5_json="$(run_log_query "$e5_query")" || {
        emit_finding "$section" "[Unknown]" "E5 final-5-minute query failed"
        append_blank_line
        return 2
    }

    e2_total="$(jq --raw-output '.[0].total // 0' <<< "$e2_json")"
    e2_signature="$(jq --raw-output '.[0].signature // 0' <<< "$e2_json")"
    e5_total="$(jq --raw-output '.[0].total // 0' <<< "$e5_json")"
    e5_signature="$(jq --raw-output '.[0].signature // 0' <<< "$e5_json")"
    e2_pct="$(safe_pct "$e2_signature" "$e2_total")"
    e5_pct="$(safe_pct "$e5_signature" "$e5_total")"
    reduction_pct="$(python3 - <<PY
e2 = float(${e2_pct@Q})
e5 = float(${e5_pct@Q})
if e2 == 0:
    print("0.00")
else:
    print(f"{((e2 - e5) / e2) * 100.0:.2f}")
PY
)"

    distribution_query=$(cat <<KQL
AppServiceHTTPLogs
| where _ResourceId =~ "${WEB_APP_RESOURCE_ID}"
| where TimeGenerated between (datetime('${start_time}') .. datetime('${end_time}'))
| where CsUriStem == "/slow/240"
| extend instance_hint = iff(isempty(Computer), Host, Computer)
| summarize requests=count() by instance_hint
| order by requests desc
KQL
)
    distribution_json="$(run_log_query "$distribution_query")" || {
        emit_finding "$section" "[Unknown]" "E5 instance-distribution query failed"
        append_blank_line
        return 2
    }
    distribution_summary="$(jq --raw-output 'if length == 0 then "(none)" else map("\(.instance_hint)=\(.requests)") | join(", ") end' <<< "$distribution_json")"

    emit_finding "$section" "[Measured]" "E2 baseline final-5-minute signature rate=${e2_pct}% (${e2_signature}/${e2_total}); E5 final-5-minute signature rate=${e5_pct}% (${e5_signature}/${e5_total})"
    emit_finding "$section" "[Measured]" "Relative reduction from E2 to E5: ${reduction_pct}%"
    emit_finding "$section" "[Measured]" "Request distribution across instances: ${distribution_summary}"

    if [[ "$e5_total" -eq 0 ]]; then
        status_code=2
    elif python3 - <<PY
e2 = float(${e2_pct@Q})
e5 = float(${e5_pct@Q})
import sys
sys.exit(0 if e2 > 0 and e5 <= (0.7 * e2) else 1)
PY
    then
        MITIGATION_M3_EFFECT="EFFECTIVE"
        status_code=0
    else
        MITIGATION_M3_EFFECT="INSUFFICIENT"
        status_code=1
    fi

    emit_finding "$section" "[Observed]" "Section verdict: $(status_text_from_code "$status_code")"
    append_blank_line
    return "$status_code"
}

render_overall_verdict() {
    if [[ "$SIGNATURE_CONFIRMED" == "true" ]]; then
        OVERALL_SIGNATURE_STATUS="CONFIRMED"
    elif [[ "$SIGNATURE_CHECKED" == "true" ]]; then
        OVERALL_SIGNATURE_STATUS="REFUTED"
    else
        OVERALL_SIGNATURE_STATUS="INSUFFICIENT DATA"
    fi

    if [[ "$MITIGATION_M1A_EFFECT" == "UNTESTED" ]]; then
        MITIGATION_M1A_EFFECT="UNTESTED"
    fi
    if [[ "$MITIGATION_M2_EFFECT" == "UNTESTED" && "$E4_PREFLIGHT_STATUS" == "UNVERIFIABLE" ]]; then
        MITIGATION_M2_EFFECT="UNVERIFIABLE"
    fi
    if [[ "$MITIGATION_M3_EFFECT" == "UNTESTED" ]]; then
        MITIGATION_M3_EFFECT="UNTESTED"
    fi

    cat >> "$REPORT_FILE" <<EOF
## Overall Verdict
Signature 500.121.64 status: [${OVERALL_SIGNATURE_STATUS}]
Mitigation M1a effect: [${MITIGATION_M1A_EFFECT}]
Mitigation M2 effect: [${MITIGATION_M2_EFFECT}]
Mitigation M3 (scale-out) effect: [${MITIGATION_M3_EFFECT}]

## Take-away
Loopback saturation evidence must be anchored to the App Service _ResourceId-scoped logs and compared across baseline, load, and mitigation windows. Treat M2 as unverifiable when platform Auto-Heal events do not surface in AppServicePlatformLogs, even if the HTTP trend looks directionally favorable.
EOF
}

run_requested_experiments() {
    local rc=0
    local overall_rc=0

    case "$EXPERIMENT" in
        pre-e1)
            capture_return_code verify_pre_e1
            return "$__CAPTURED_RC"
            ;;
        e1)
            capture_return_code verify_e1
            return "$__CAPTURED_RC"
            ;;
        e3)
            capture_return_code verify_e3
            return "$__CAPTURED_RC"
            ;;
        preflight)
            capture_return_code verify_preflight
            return "$__CAPTURED_RC"
            ;;
        e2)
            capture_return_code verify_e2
            return "$__CAPTURED_RC"
            ;;
        e4)
            capture_return_code verify_preflight
            rc="$__CAPTURED_RC"
            overall_rc=$rc
            capture_return_code verify_e4
            rc="$__CAPTURED_RC"
            if [[ "$rc" -gt "$overall_rc" ]]; then
                overall_rc=$rc
            fi
            return "$overall_rc"
            ;;
        e5)
            capture_return_code verify_e5
            return "$__CAPTURED_RC"
            ;;
        all)
            capture_return_code verify_pre_e1
            rc="$__CAPTURED_RC"
            overall_rc=$rc
            capture_return_code verify_e1
            rc="$__CAPTURED_RC"
            if [[ "$rc" -gt "$overall_rc" ]]; then
                overall_rc=$rc
            fi
            capture_return_code verify_e3
            rc="$__CAPTURED_RC"
            if [[ "$rc" -gt "$overall_rc" ]]; then
                overall_rc=$rc
            fi
            capture_return_code verify_preflight
            rc="$__CAPTURED_RC"
            if [[ "$rc" -gt "$overall_rc" ]]; then
                overall_rc=$rc
            fi
            capture_return_code verify_e2
            rc="$__CAPTURED_RC"
            if [[ "$rc" -gt "$overall_rc" ]]; then
                overall_rc=$rc
            fi
            capture_return_code verify_e4
            rc="$__CAPTURED_RC"
            if [[ "$rc" -gt "$overall_rc" ]]; then
                overall_rc=$rc
            fi
            capture_return_code verify_e5
            rc="$__CAPTURED_RC"
            if [[ "$rc" -gt "$overall_rc" ]]; then
                overall_rc=$rc
            fi
            return "$overall_rc"
            ;;
    esac
}

main() {
    local final_rc=0
    parse_args "$@"
    ensure_results_dir
    load_deploy_metadata
    render_report_preamble
    capture_return_code run_requested_experiments
    final_rc="$__CAPTURED_RC"
    render_overall_verdict
    printf 'Wrote %s\n' "$REPORT_FILE" >&2
    exit "$final_rc"
}

main "$@"
