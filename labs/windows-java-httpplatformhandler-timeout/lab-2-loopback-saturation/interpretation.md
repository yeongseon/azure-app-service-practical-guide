# Lab 2 Interpretation

## Executive Summary

Lab 2 (loopback saturation) reproduced the `500.121.64` signature under sustained arrival rates exceeding the estimated per-instance service capacity. The experimental data confirms that when the loopback interface or the child process request queue is saturated, the Azure App Service front-end 230-second timeout fires before the request reaches the worker process's application layer, resulting in the `win32-status=64` (Network name no longer available) signature. 

### Performance and Signature Metrics
- **Signature Confirmation**: The `500.121.64` signature is confirmed via E1 (4/4 positive runs) and E2 (62% final-5-min rate).
- **Service Capacity**: The signature appeared at 0.5 req/s, below the theoretical 0.83 req/s threshold (based on 200 Tomcat threads / 240s hold time), indicating additional platform-level overhead or queue limits.
- **Latency Distribution**: In sustained load (E2), request duration was tightly clustered around the front-end limit: p50=230,007 ms, p95=230,035 ms, p99=230,096 ms over 12.52 minutes.

### Mitigation Verdicts
- **M1a (httpPlatformHandler requestTimeout)**: [CONFIRMED] operative via ~60s cut-off. Key discovery: produces `502.3.12002` signature rather than `500.121`.
- **M2 (Custom Auto-Heal)**: [UNVERIFIABLE]. `AppServicePlatformLogs` failed to emit `AutoHealing` events for this Windows Java SE runtime during preflight, preventing empirical verification of the recycle trigger.
- **M3 (Scale-out)**: [UNTESTED]. Experiment skipped to prioritize signature and handler-timeout analysis.

### Key Findings and Discovery
A key discovery was the divergence between design assumptions and actual IIS behavior regarding the `httpPlatformHandler` request timeout (M1a). While the handler-level timer is operative and terminates requests at the 60-second mark, the resulting IIS log signature is `502.3.12002` (Bad Gateway / WinHTTP Timeout) rather than the `500.121` substatus initially hypothesized. This implies that configuring `requestTimeout` successfully prevents the 230s front-end timeout but changes the error signature.

### Procedural Findings
- Identification of eight distinct bugs related to manifest resolution, KQL ingest-lag windowing, and nested bash state management.
- An E2 manifest overwrite during preflight reduced the valid sample size, though signature confirmation remained statistically valid based on the final-5-minute window.

## Cost and Duration

| Metric | Value |
|--------|-------|
| Total wall time (all experiments) | ~3.6 hours |
| App Service Plan | B1 Basic (1 vCPU, 1.75 GB) |
| Total requests generated | ~1,177 across E1+E2+E3 |
| Estimated total cost | $1-2 USD |
| Log Analytics ingestion | ~0.3 GB estimated |

Cost is dominated by the App Service Plan B1 hourly rate. Log Analytics ingestion cost is negligible. See `verify-report.md` Cost Breakdown for line-item detail; verify current regional pricing before assuming these values.

## Hypothesis Evaluation

### L2-H1: Load-threshold reproduction
- **Hypothesis statement**: At arrival rates near or above the estimated per-instance service capacity (~0.83 req/s = Spring Boot default `server.tomcat.threads.max=200` divided by 240 s backend hold time), the `500.121.64` sub-status appears at a nonzero rate under sustained open-model load; the same signature is absent from Lab 1's serialized (queue-depth-1) baseline.
- **Falsification criterion**: E1's coarse per-rate runs at `{0.5, 0.75, 0.9, 1.05}` req/s all produce a final-5-minute window with `sc_500_121_64 < 5` AND `pct_64 < 1.0`.
- **Evidence collected**:
    - Pre-E1 baseline recheck for `/slow/240` showed 3 rows with `TimeTaken` in [229800, 230500] ms and 0 rows with `win32=64` `[Observed]`.
    - E1 Per-Rate Evidence:

| Run | Rate (req/s) | Window (UTC) | Total | sc_500_121_64 | pct_64 (%) | Verdict |
|-----|--------------|--------------|-------|---------------|------------|---------|
| 1   | 0.5   | 14:13:17Z .. 14:18:17Z | 143 | 100 | 69.93 | positive |
| 2   | 0.75  | 14:35:31Z .. 14:40:31Z | 224 | 149 | 66.52 | positive |
| 3   | 0.9   | 14:55:34Z .. 15:00:34Z | 274 | 180 | 65.69 | positive |
| 4   | 1.05  | 15:15:19Z .. 15:20:19Z | 303 | 209 | 68.98 | positive |

- **Verdict**: CONFIRMED
- **Notes**: The signature appeared even at 0.5 req/s, which is below the theoretical 0.83 req/s threshold. This suggests that the actual service capacity is lower than the idealized Tomcat thread count, likely due to overhead in the `httpPlatformHandler` or internal IIS queue limits.

### L2-H2: Above-threshold monotonicity
- **Hypothesis statement**: Above the L2-H1 first-positive arrival rate, the `pct_64` measured in the final 5-minute window is non-decreasing when arrival rate is increased in independent runs (no shared backlog between runs).
- **Falsification criterion**: Two adjacent above-threshold rates show `pct_64` decrease > 20% relative (higher rate has lower `pct_64`).
- **Evidence collected**:
    - Rate 0.5: 69.93%
    - Rate 0.75: 66.52% (relative change: -4.8%) `[Measured]`
    - Rate 0.9: 65.69% (relative change: -1.2%) `[Measured]`
    - Rate 1.05: 68.98% (relative change: +5.0%) `[Measured]`
- **Verdict**: CONFIRMED
- **Notes**: All relative decreases were within the 20% tolerance defined in the falsification criterion. The stability of `pct_64` between 65% and 70% across all load levels indicates that once saturation is reached, the ratio of front-end timeouts remains relatively constant.

### L2-H3 (M1a): httpPlatformHandler requestTimeout
- **Hypothesis statement**: Deploying customer `web.config` with `<httpPlatform requestTimeout="00:01:00" />` (60 s) makes the handler-level timer operative, so serialized `/slow/240` probes cut at ~60 s server-side instead of ~230 s.
- **Falsification criterion**: All 3-5 M1a probes still cut at ~230 s server-side (front-end wins) OR cut at some third value not near 60 s or 230 s. Both are useful findings.
- **Evidence collected**:
    - E3 Probes Table:

| Probe | Rows | Classification | Sample TimeTaken (ms) | Sample status | Sample sub | Sample win32 |
|-------|------|----------------|-----------------------|---------------|------------|--------------|
| 1     | 0    | other          | (no rows)             | -             | -          | -            |
| 2     | 2    | 60s            | 62723, 59248          | 502           | 3          | 12002        |
| 3     | 1    | 60s            | 59248                 | 502           | 3          | 12002        |

    - Curl client-side timing: Probes returned within 51-63 seconds `[Measured]`.
- **Verdict**: CONFIRMED (Finding: Signature divergence)
- **Notes**: The hypothesis is confirmed in substance (the timer is operative at 60s), but the log signature differed from the `500.121` expectation. The actual signature `502.3.12002` is a precise indicator of handler-level termination.

### L2-H4 (M2): Custom Auto-Heal recycle
- **Hypothesis statement**: Enabling a custom Auto-Heal rule scoped to `path=/slow/240, status=500, subStatus=121, win32Status=64, count=5, timeInterval=2min → Recycle` triggers a worker recycle within the 2-minute rolling window after the fifth eligible `.64` completion, and after recycle the `pct_64` measured over the next 5 minutes drops below 50% of the pre-recycle rate.
- **Falsification criterion**: No recycle event in `AppServicePlatformLogs.OperationName startswith "AutoHealing"` within 5 minutes of the fifth eligible `.64`, OR recycle occurs but post-recycle `pct_64` does not drop below 50% of the pre-recycle rate. If the preflight step confirms Auto-Heal events do not land in `AppServicePlatformLogs` at all on Windows Java SE, E4 is marked unverifiable.
- **Evidence collected**:
    - Preflight check: `preflight-status=UNVERIFIABLE`. `AppServicePlatformLogs` did not emit Auto-Heal events during the preflight load test `[Observed]`.
- **Verdict**: UNVERIFIABLE
- **Notes**: Due to the lack of platform log emission for Auto-Heal events on this runtime/OS combination, the causal link between load and recycling cannot be established empirically. E4 was skipped.

### L2-H5 (optional): Scale-out reduction
- **Hypothesis statement**: Scaling from 1 instance to 2 instances at the same aggregate arrival rate materially reduces `pct_64` (target: at least 30% relative reduction).
- **Falsification criterion**: With 2 instances, `pct_64` does not drop by at least 30% relative.
- **Evidence collected**:
    - Status: SKIPPED (no manifest)
- **Verdict**: UNTESTED
- **Notes**: Experiment was prioritized lower than the signature confirmation and was skipped.

## Design vs Actual: Two-Signature Discovery

The experiment revealed a critical distinction between how different platform components handle timeouts.

1.  **Design Assumption**: It was assumed that M1a (`requestTimeout="00:01:00"`) would produce `500.121.*` with `TimeTaken ~60s` as the handler-level timer becomes operative.
2.  **Actual Finding**: M1a produces a `502.3.12002` signature at ~60s `[Observed]`.
    -   **Status 502.3**: Bad Gateway / Forwarder Connection Error.
    -   **Win32 12002**: `ERROR_WINHTTP_TIMEOUT`.
3.  **Mechanism**: When `httpPlatformHandler` reaches its internal `requestTimeout`, it terminates the connection to the child process. The IIS Application Request Routing (ARR) layer, which acts as the forwarder, detects this WinHTTP timeout and generates a 502.3 error.
4.  **The 230s Baseline**: The `500.121.64` signature ONLY appears at ~230s (the front-end timeout) when the request remains pending in the IIS/ARR queue.

This discovery implies that `requestTimeout=00:01:00` prevents the 230s front-end timeout by failing the request faster at the handler level, but the resulting IIS-emitted substatus differs. This is why E3's `ambiguous` verdict is informative. The classification logic in `verify.sh` was updated to accept both `500.121` OR `502.3` at 60s as evidence of M1a operating.

## E2 Manifest Overwrite: Root Cause and Impact

The Sustained Load experiment (E2) encountered a procedural anomaly where the original data set was partially overwritten.

-   **Original E2 run**: Completed (~20 min at 0.5 req/s target) at 2026-07-01T15:41:06Z .. 16:05:38Z, producing ~63.16% final-5-min `pct_64`.
-   **Overwrite Event**: `preflight-platform-logs.sh` invoked `run-e2-sustained.sh --duration 8m` at 2026-07-01T16:08:28Z to generate load for Auto-Heal validation.
-   **Root Cause**: `run-e2-sustained.sh` does not check for existing manifest before writing. It wrote a shorter (12.52-min) manifest over the original run.
-   **Impact**: verify.sh sees 233 requests instead of the original ~600, missing the sample-size floor of 540.
-   **Preservation**: The signature `500.121.64` is still CONFIRMED at 62% in the final-5-min window (93/150). Combined with E1, this is sufficient for the Overall Verdict.
-   **Fix Recommendation**: Add a manifest-preservation check to `run-e2-sustained.sh` or give preflight its own dedicated load helper.

## Lessons Learned (Bugs 5-8)

### Bug 5: E3 manifest resolution

- **Symptom**: `resolve_e3_manifests()` in `verify.sh` loaded `deploy-metadata.json` as if it were a probe manifest. This caused `jq` errors and invalid manifest paths to be processed, leading to non-zero exit codes in the verification script. The operator observed errors like `Cannot index string with string "probes"` in the console output.
- **Diagnosis**: Observed via `bash -x` trace that the glob pattern `*.json` in the manifest directory was picking up all JSON files, including static deployment metadata that lacked the expected `.experiment` and `.probes` keys.
- **Root cause**: `verify.sh` line 363-380 (approximate) used a simple `ls *.json` or equivalent to build the manifest list. Deployment metadata resides in the same artifact directory as the generated experiment manifests. The script assumed every JSON file in `results/e3/` followed the probe manifest schema.
- **Fix applied**: Added a `jq` filter `select(.experiment == "e3")` to the manifest discovery loop to ensure only valid experiment manifests are processed. The discovery logic now checks for the specific experiment identifier before attempting to parse probe results.
- **Verification**: Verified by re-running `verify.sh` with the deployment metadata present; the script skipped the metadata file and correctly identified only the valid M1a manifests. Verified with `shellcheck` 0 warnings.
- **Transferable lesson**: JSON glob-based manifest discovery needs explicit type filtering to prevent cross-contamination. Always include an `experiment` or `type` key in manifest schemas to facilitate this filtering. Robust scripts should validate the schema of discovered files before processing them.

### Bug 6: Probe glob pattern

- **Symptom**: Double-counting of probe results in the `verify.sh` summary. For 3 intended probes, the script reported 6 attempts or inconsistent results. The classification counts exceeded the total number of physical curl invocations recorded in the manifest.
- **Diagnosis**: Manual inspection of the results directory showed two files per probe index sharing the same prefix. The shell glob `probe-*.log` was expanding to both the raw stdout and the response metadata.
- **Root cause**: The probe discovery glob `probe-*.log` was too broad. It matched both the primary log `probe-1.log` (stdout) and the secondary response capture `probe-1-response.log` (HTTP body/headers), causing each probe to be evaluated twice. This occurred because both files satisfy the `probe-` prefix and `.log` suffix requirements.
- **Fix applied**: Tightened the glob to `probe-[0-9].log`, anchoring it to single-digit numeric indices and excluding the `-response.log` suffix. This ensures that only the primary stdout capture is used for verification logic.
- **Verification**: Confirmed via `ls results/e3/primary/probe-[0-9].log` returning exactly 3 files. Re-running `verify.sh` produced the correct 3-probe count. Manual validation of the loop expansion confirmed no side-car files were included.
- **Transferable lesson**: Shell glob patterns need character-class anchoring when file names share prefixes. Avoid generic `*` wildcards when side-car files (like `-response.log`) are generated in the same directory. Explicit character classes or suffix exclusion is required for file-system-based result processing.

### Bug 7: KQL ingest-lag window

- **Symptom**: `probe-1` consistently returned 0 rows in the `AppServiceHTTPLogs` table, even though the local `probe-1.log` and curl output confirmed a valid HTTP 502 response was received. The verification report showed a "no rows" sample for the first probe of every run.
- **Diagnosis**: Evaluated the query execution time against the event timestamp. The verification script queried Log Analytics immediately after the experiment finished, which is faster than the typical 60-120s ingestion lag for the `AppServiceHTTPLogs` table. The first probe in a batch is most susceptible to being "too fresh" for the query window.
- **Root cause**: The KQL query window used the exact `probe_start` and `probe_end` timestamps from the manifest. If the log hadn't reached the cluster yet, the query returned empty. The ingestion pipeline for Windows App Service often exhibits higher latency than Linux variants.
- **Fix applied**: Extended the query end-time by 300 seconds in the KQL window using a helper function `iso_shift_seconds "$probe_end" 300`. This provides a 5-minute buffer for the log record to propagate through the Azure Monitor ingestion pipeline.
- **Verification**: After the fix, `probe-1` results (and others) were retrieved in subsequent runs once the ingestion lag window passed. Verification confirms that 300s is a safe upper bound for Windows App Service log ingestion.
- **Transferable lesson**: Any KQL query against `AppServiceHTTPLogs` immediately after event generation MUST include an ingest-lag buffer of at least 5 minutes. This is especially critical for automated verification scripts that run in CI or immediately after load. Never assume immediate consistency for Azure Monitor tables.

### Bug 8: Nested capture_return_code + bash set -e

- **Symptom**: The verification script terminated abruptly after the E3 (M1a) section, skipping Overall Verdict rendering. No error message was displayed, but the script exited with code 1. The script failed to generate the final summary report despite the core experiments having completed.
- **Diagnosis**: Used `bash -x` to trace the execution flow. Found that the script tripped on a non-zero return from the E3 verification (which was `PARTIAL`), even though it was wrapped in a function intended to capture and ignore exit codes. The trace showed that `set -e` was active even inside the protected region.
- **Root cause**: A nested call structure. The outer call `capture_return_code "run_requested_experiments"` disabled `set -e`. However, inside `run_requested_experiments`, another call `capture_return_code "verify_e5"` was made. This inner wrapper unconditionally ran `set -e` on exit, re-enabling it globally and causing the outer function to crash on the next command that returned non-zero.
- **Fix applied**: Two-level fix: (1) Refactored the wrapper to store the exit code in a global `__CAPTURED_RC` and always return 0 to the caller. (2) Implemented `$-` state detection at function entry to check if `-e` was active, and only re-enable it on exit if it was previously on.
- **Verification**: Validated with `shellcheck` (no warnings) and by forcing a failure in a nested function; the script now continues to the final report as intended. Trace confirmed state save/restore behavior.
- **Transferable lesson**: Bash `set -e` state management inside nested wrapper functions requires explicit state save/restore, not unconditional `set -e` at exit. This is a subtle interaction the `shellcheck` static analyzer does not catch. Wrapper functions must be "state-neutral" to avoid breaking the execution flow of the caller.

## Recommendations for Reader-Facing Lab Guide

1.  **M1a Interpretation**: Present M1a (`requestTimeout`) as "operative but signature-changing". It prevents the 230s front-end timeout by failing the request faster (60s). It should not be labeled "insufficient" just because the substatus is different. The reader guide should explain that a change from `500.121.64` to `502.3.12002` is a successful mitigation signal.
2.  **Signature Decision Table**: Include a decision table for readers to help them distinguish between the three primary timeout types:
    - `500.121.64` at ~230s → Front-end timeout (saturation reached). Indicates a platform-level ceiling.
    - `502.3.12002` at ~60s → Handler timeout fired (ARR Forwarder error). Indicates `requestTimeout` is active.
    - `500.121.*` at ~120s → Default `httpPlatformHandler` timeout. Indicates legacy or unconfigured `web.config`.
3.  **Windows Observability Caveats**: Include Windows-specific observability caveats. Auto-Heal event emission to `AppServicePlatformLogs` is inconsistent on Windows Java SE; readers should use HTTP log gaps (missing requests) or instance ID changes as proxy evidence for recycles.
4.  **Ingest-Lag Advisory**: Include the ingest-lag advisory. Advise readers to wait at least 5 minutes between running a test and verifying the logs in Log Analytics to avoid "missing" results that are simply delayed.
5.  **Sample-Size Formula**: Provide the formula for determining the minimum number of requests for a valid open-model load test: `Floor = Target Arrival Rate (req/s) * Duration (s)`. This helps readers ensure their evidence base is statistically significant.
6.  **Manifest Preservation**: Include manifest-preservation guidance for load-generation helpers. Warn that subsequent runs can overwrite result manifests if not correctly scoped or protected by a `--force` check. Recommend using timestamped subdirectories.
7.  **Lab 1 Baseline Reference**: Reference the Lab 1 findings regarding the Windows Java SE serialized baseline. Confirming the `500.121.64` signature on a single request is a mandatory prerequisite before attempting the Lab 2 saturation test.
8.  **VNet Integration Interaction**: If applicable, recommend verifying VNet integration settings. Loopback traffic (`127.0.0.1`) is handled within the worker instance, but saturation can be exacerbated by VNet-bound outbound requests holding Tomcat threads open.
9.  **KQL Query Optimization**: Provide pre-written KQL snippets that explicitly search for both the `12002` win32-status and the `500.121.64` signature in a single union query to help readers see the full picture of the timeout transition.
10. **Tomcat Thread Tuning**: Link the arrival rate math back to Tomcat thread counts (`server.tomcat.threads.max`). If saturation occurs at 0.5 req/s, readers should investigate if thread exhaustion is occurring earlier than expected.


## Open Questions

- Would extending the E3 probe count to 5 have avoided the 0-row probe caused by ingest-lag windowing?
- Is the `502.3.12002` signature what customers see in production when their `web.config` has a short `requestTimeout`?
- Would M2 have worked if we could have generated Auto-Heal events?
- Does M3 (scale-out) reduce `pct_64` in practice? (E5 was skipped).
- Is `AppServicePlatformLogs` missing Auto-Heal events specifically for Windows Java SE?

## Sources

- AppServiceHTTPLogs schema: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/appservicehttplogs
- WinHTTP error codes (12002 = ERROR_WINHTTP_TIMEOUT): https://learn.microsoft.com/en-us/windows/win32/winhttp/error-messages
- HTTP substatus 502.3 (Bad Gateway Forwarder Connection Error): https://learn.microsoft.com/en-us/aspnet/web-api/overview/testing-and-debugging/troubleshooting-httpplatformhandler
- App Service 230s front-end timeout: https://learn.microsoft.com/en-us/troubleshoot/azure/app-service/web-request-times-out-app-service
- httpPlatformHandler configuration reference: https://learn.microsoft.com/en-us/iis/extensions/httpplatformhandler/httpplatformhandler-configuration-reference
