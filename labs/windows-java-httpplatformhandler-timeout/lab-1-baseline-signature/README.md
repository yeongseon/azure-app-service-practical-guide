# Lab 1: Baseline `500.121.0` signature stability

Baseline-signature lab that runs **after Stage 0** and **before Lab 2**. Its purpose is to characterize the `500.121.0` timeout signature at high statistical confidence, resolve the remaining Stage 0 unknown (absolute vs idle 230 s), and inventory what `httpPlatformHandler` configuration is Kudu-visible on Windows App Service Java SE.

Lab 1 does **not** attempt to reproduce the production `500.121.64` sub-status - that is a concurrency-induced symptom whose reproduction requires load and is deferred to Lab 2. Lab 1 uses **serialized, no-overlap** probes so the queue depth stays at 1 and any `.64` observed would be an anomaly worth extending the iteration count over.

## Hypotheses

All five hypotheses are derived from Stage 0 findings. See [`design-proposal.md`](design-proposal.md) for the full Oracle review and per-hypothesis rationale.

| ID | Hypothesis | Falsification | Priority |
|---|---|---|---|
| L1-H1R | Under repeated serialized `/slow/240` probes, IIS `TimeTaken` clusters around 230000 ms (stddev < 200 ms) and `ScStatus/ScSubStatus` is `500/121` in 100% of iterations. | Any iteration outside `[229800, 230500]` ms server-side, OR `ScStatus/ScSubStatus` differs from `500/121` at least once. | Stability check |
| L1-H2R | Under serialized no-overlap baseline probes, `ScWin32Status` remains `0` on every iteration; any `.64` is exceptional and triggers adaptive extension. | Any single `.64` in the serialized baseline -> extend to 20 iterations and treat as anomaly, not pre-authorized noise. | Anomaly gate |
| L1-H3R | A Kudu-accessible IIS/site artifact **outside `wwwroot`** reveals the effective `httpPlatformHandler` configuration; if it exposes `requestTimeout`, that value is >= 230 s. | All 7 planned Kudu VFS/command paths return no `httpPlatform` element, OR a revealed timeout is < 230 s. Both outcomes are useful findings. | Best-effort discovery |
| L1-H4 | The 230 s front-end limit is an **ABSOLUTE** request-duration limit, not an idle timeout. `/stream/300` with `SPRING_MVC_ASYNC_REQUEST_TIMEOUT=600000` cuts at ~230 s after ~8 chunks. | `/stream/300` completes with all 11 chunks - the 230 s limit is IDLE (server-sent bytes reset the counter). | Primary unknown from Stage 0 |
| L1-H5R (optional) | On direct App Service requests, client-visible HTTP status matches IIS `ScStatus=500`; any client-visible `502` requires an added upstream hop or a different request path. | Baseline shows `502` at client on direct requests -> revise Stage 0 F2 attribution. | Passive observation only |

Priority ranking if wall time is constrained (per Oracle): **E3 > E2 > E1 > E4**. Recommended execution order: **E1 -> E2 -> E3** (serial, no cross-experiment interference).

## Prerequisites

Lab 1 is **gated on Stage 0**. Do not run Lab 1 until Stage 0 has:

1. Been executed end-to-end at least once against the same Azure subscription and region.
2. Confirmed the observations documented in [`../stage-0-config-discovery/results/stage-0-interpretation.md`](../stage-0-config-discovery/results/stage-0-interpretation.md): Q1 confirmed (~230 s front-end), Q2 answered (no `web.config` in `wwwroot`), Q3 blocked by Spring MVC async 30 s (which Lab 1's `SPRING_MVC_ASYNC_REQUEST_TIMEOUT` app setting resolves), Q4 confirmed (Auto-Heal fully disabled).

If any Stage 0 answer differs from the above, revisit the Stage 0 decision matrix before starting Lab 1 - the hypothesis IDs above may not apply.

| Requirement | Purpose |
|---|---|
| Azure CLI (`az`) 2.60+ signed in with rights to create resources in the target subscription | Deploy Bicep, query Log Analytics, delete RG |
| Maven (`mvn`) 3.8+ and JDK 17 on the local machine | Build the Spring Boot JAR (reused from Stage 0) |
| `curl` and `python3` on the local machine | Probes and KQL result parsing |
| Basic auth allowed on the target subscription's App Service | Kudu `/api/vfs` and `/api/command` fetches for E2. `main.bicep` sets the `scm` policy `allow: true` explicitly. |
| Stage 0 JAR available at `../stage-0-config-discovery/app/target/` | `deploy.sh` reuses the Stage 0 JAR unchanged (design-proposal.md rationale: same binary keeps the Stage 0 vs Lab 1 comparison clean). |

The lab deploys **one** B1 Windows plan and **one** Windows Java SE web app plus a Log Analytics workspace. Structurally identical to Stage 0 - the only difference is the `SPRING_MVC_ASYNC_REQUEST_TIMEOUT=600000` app setting.

## Steps

Run the scripts in order. Each writes to the same output directory when passed one.

```bash
cd labs/windows-java-httpplatformhandler-timeout/lab-1-baseline-signature

# 1. Deploy (creates RG, deploys Bicep with SPRING_MVC_ASYNC_REQUEST_TIMEOUT=600000, builds and uploads Stage 0 JAR)
bash deploy.sh <BASE_NAME> koreacentral rg-lab-<BASE_NAME>

# 2. Warm up (polls /actuator/health, JIT warm, 30 s idle settle)
bash warm-up.sh https://app-<BASE_NAME>-<suffix>.azurewebsites.net

# 3. Preflight isolation check (verifies Auto-Heal + Proactive Auto-Heal are still disabled after deploy)
bash collect-effective-config.sh --preflight app-<BASE_NAME>-<suffix> rg-lab-<BASE_NAME> ./results

# 4. E1: baseline signature stability (~43 min for 10 iterations; extend to ~87 min for 20 if triggered)
bash run-e1-signature-probe.sh https://app-<BASE_NAME>-<suffix>.azurewebsites.net ./results

# 5. E2: Kudu config visibility (7 fetches, ~5 min)
bash run-e2-config-visibility.sh app-<BASE_NAME>-<suffix> rg-lab-<BASE_NAME> ./results

# 6. E3: /stream/300 absolute-vs-idle probe (~6 min including buffer)
bash run-e3-stream-test.sh https://app-<BASE_NAME>-<suffix>.azurewebsites.net ./results

# 7. Post-flight full config collection (Kudu + ARM + manifest CSV)
bash collect-effective-config.sh app-<BASE_NAME>-<suffix> rg-lab-<BASE_NAME> ./results

# 8. Verify: KQL queries + statistics + H1R/H2R/H3R/H4/H5R verdicts + verify-report.md
bash verify.sh app-<BASE_NAME>-<suffix> rg-lab-<BASE_NAME> law-<BASE_NAME>-<suffix> ./results

# 9. Tear down
bash cleanup.sh rg-lab-<BASE_NAME>
```

The app name, hostname, and Log Analytics workspace name are printed by `deploy.sh` at the end of step 1. Copy them into the subsequent commands.

If step 3 (preflight) exits non-zero, **DO NOT proceed to step 4**. The environment is contaminated (Auto-Heal or Proactive Auto-Heal is active) and any signature collected from a contaminated environment cannot distinguish Auto-Heal recycles from front-end request-timeout cuts. Fix `main.bicep`, re-deploy, and re-run from step 1.

**Adaptive iteration count**: If `run-e1-signature-probe.sh` (step 4) observes any `ScWin32Status = 64` or any `TimeTaken` outside `[229800, 230500]` ms during the first 10 iterations, re-run with `ITERATIONS=20` and re-run `verify.sh` (step 8). The verify report will explicitly flag this recommendation in its "Next" section.

## Decision matrix

Read the E1 statistics, the E2 grep output, and the E3 stream-cut behavior together. `verify.sh` computes the verdicts automatically and writes them to `results/verify-report.md`.

| E1 statistics | E2 grep hit | E3 stream behavior | Interpretation | Routes to |
|---|---|---|---|---|
| 100% `500/121`, mean `TimeTaken` in `[229800, 230500]`, stdev < 200, all `ScWin32Status = 0` | Any Kudu-accessible artifact contains `requestTimeout` >= `230000` | Cuts at ~230 s, ~8 chunks, `ScStatus/ScSubStatus = 500/121` | Full signature confirmed: front-end 230 s dominates, Kudu-visible handler config >= front-end limit, timer is ABSOLUTE. **Cleanest possible result.** | Lab 2 (add loopback saturation to reproduce `.64`) |
| 100% `500/121`, stable timing, all `ScWin32Status = 0` | All 7 Kudu paths return no `requestTimeout` marker | Cuts at ~230 s, ~8 chunks, `500/121` | Signature confirmed and timer is ABSOLUTE, but effective handler config is not Kudu-visible on Windows Java SE. Documented as a **platform observability limitation**. | Lab 2 (loopback saturation) + final lab guide notes the observability gap |
| 100% `500/121`, stable timing, all `ScWin32Status = 0` | Any Kudu-accessible artifact contains `requestTimeout` < `230000` (e.g. 120 s default) | Cuts at ~230 s, ~8 chunks, `500/121` | Front-end 230 s wins over the handler's shorter timeout - handler default is present but non-operative. Documented as "handler config exists but overridden by front-end". | Lab 2 (loopback saturation) + final lab guide notes the redundancy |
| Any iteration outside `[229800, 230500]` OR any `ScStatus/ScSubStatus != 500/121` | Any | Any | H1R falsified. Baseline signature is not the tightly clustered `500/121` Stage 0 suggested; extend iterations, correlate with Log Analytics platform logs, and re-consult Oracle before proceeding. | Consult Oracle (session `ses_0e3010e14ffePDjr4dEej6mr7y`) before running Lab 2 |
| Any single `ScWin32Status = 64` in the first 10 | Any | Any | H2R triggered. Re-run E1 with `ITERATIONS=20`, correlate `.64` timestamps with `AppServiceConsoleLogs` for overlap. If `.64` persists at low rate without load, that itself is a novel finding for the final lab guide. | Extend E1, then Lab 2 with reduced surprise about `.64` behavior |
| Any | Any | `/stream/300` completes with all 11 chunks, `ScStatus = 200` | H4 IDLE confirmed. 230 s is an idle timeout; streaming production responses are safe up to their own duration. **Reverses part of the Stage 0 hypothesis basis for Lab 2.** | Revise final lab guide, revise Lab 2 mitigation direction (streaming becomes a valid mitigation) |
| Any | Any | `/stream/300` cuts anywhere other than ~230 s with ~8 chunks or ~300 s with 11 chunks | H4 ambiguous. Document the anomaly, re-run once, and if reproducible, consult Oracle before proceeding. | Consult Oracle before Lab 2 |
| Any client HTTP code other than `500` on the direct-App-Service request path | N/A | N/A | H5R falsified. Production `502` may not be from an upstream rewrite; revisit Stage 0 F2 attribution before writing the final lab guide. | Amend final lab guide's F2 discussion |

## Evidence to collect

After a successful run the `./results` directory should contain:

| File | Origin | Purpose |
|---|---|---|
| `e1-signature-probes.csv` | `run-e1-signature-probe.sh` | Per-iteration: `iteration_index, requested_seconds, http_code, time_total_sec, curl_exit_code, started_utc, ended_utc, paced_sleep_sec` |
| `e2-kudu-fetch-manifest.csv` | `run-e2-config-visibility.sh` | Per-probe: `probe_id, path_or_command, method, http_code, bytes, outfile` for all 7 Kudu attempts |
| `e2-kudu-p1-applicationhost-inetpub.xml` (or `.http-<code>`) etc. | `run-e2-config-visibility.sh` | The seven raw fetched artifacts, renamed with `.http-<code>` suffix on non-200 responses |
| `e2-httpplatform-grep.log` | `run-e2-config-visibility.sh` | `grep -iE 'httpPlatform\|requestTimeout'` over the HTTP-200 artifacts only |
| `e3-stream-probe.csv` | `run-e3-stream-test.sh` | Single-probe: `requested_seconds, http_code, time_total_sec, curl_exit_code, bytes_received, chunk_count, started_utc, ended_utc` |
| `e3-stream-body.ndjson` | `run-e3-stream-test.sh` | Actual chunks received - `chunkIndex` and `elapsedMs` per line |
| `verify-e1-http-rows.json` | `verify.sh` | Per-request `AppServiceHTTPLogs` rows for `/slow/*` (raw KQL output) |
| `verify-e1-stats.json` | `verify.sh` | Aggregated E1 statistics: mean/stdev `TimeTaken`, `ScWin32Status` distribution, `500/121` count |
| `verify-e3-http-rows.json` | `verify.sh` | `AppServiceHTTPLogs` row for the `/stream/300` request |
| `verify-e3-console-rows.json` | `verify.sh` | `AppServiceConsoleLogs` rows for `stream.start` / `stream.end` / `stream.interrupted` |
| `verify-report.md` | `verify.sh` | Rendered H1R/H2R/H3R/H4/H5R verdicts + summary tables + adaptive-extension recommendation |
| `kudu-fetch-manifest.csv` and companion files | `collect-effective-config.sh` | Same set as Stage 0 (see [`../stage-0-config-discovery/README.md`](../stage-0-config-discovery/README.md)) - baseline capture for cross-Stage 0/Lab 1 diff |
| `az-webapp-config-show.json`, `az-webapp-appsettings.json` | `collect-effective-config.sh` | Full siteConfig + all app settings including the added `SPRING_MVC_ASYNC_REQUEST_TIMEOUT` |

Commit sanitized copies (subscription ID, tenant ID, and any secrets scrubbed) to `artifacts-sanitized/lab-1/` under the parent lab directory before deleting the local copy.

## Cost

At B1 Basic in Korea Central, this Lab runs at approximately $0.075 per hour for the plan.

- **10-iteration path**: 65 min * ($0.075 / 60) = **~$0.08**
- **20-iteration path** (if H2R triggers adaptive extension): 108 min * ($0.075 / 60) = **~$0.14**
- **Budget cap**: $0.20 (Stage 0 confirmed actual costs run below theoretical)
- Log Analytics ingestion: negligible (< 100 MB total for the full run)

## What Lab 1 deliberately does NOT do

- **No load test.** E1 probes are strictly sequential with **backend-completion + 10 s** pacing (Stage 0 showed orphan work ends ~10 s after client cutoff). Queue depth stays at 1 for the entire run. This is why `.64` observed in E1 would be an anomaly - not pre-normalized as noise.
- **No downstream service.** Any observed timeout is attributable to IIS <-> httpPlatformHandler <-> Java SE only.
- **No mitigation attempt.** Auto-Heal and Proactive Auto-Heal are both disabled specifically so the platform's raw behavior is measured, same as Stage 0.
- **No custom `web.config`.** The Stage 0 JAR is reused byte-identical, without adding any customer-authored `web.config`. E3's async-timeout fix is done via the `SPRING_MVC_ASYNC_REQUEST_TIMEOUT` app setting to avoid JAR drift.
- **No `.64` reproduction.** `500.121.64` is concurrency-induced; reproducing it requires load and is deferred to Lab 2.
- **No production tuning.** `JAVA_OPTS`, `SERVER_TOMCAT_MAX_THREADS`, and similar knobs are left at their platform defaults so the lab reflects the out-of-the-box configuration production most likely started from.

Each of these is a Lab 2 concern once Lab 1 has confirmed the baseline signature and resolved the absolute-vs-idle question.

## See also

- Top-level lab overview: [`../README.md`](../README.md)
- Stage 0 (prerequisite): [`../stage-0-config-discovery/README.md`](../stage-0-config-discovery/README.md)
- Stage 0 interpretation: [`../stage-0-config-discovery/results/stage-0-interpretation.md`](../stage-0-config-discovery/results/stage-0-interpretation.md)
- Lab 2 (pending, gated on Lab 1 results): `../lab-2-loopback-saturation/README.md`
- Lab 1 design proposal (Oracle-reviewed): [`design-proposal.md`](design-proposal.md)
- Oracle Lab 1 design review session: `ses_0e3010e14ffePDjr4dEej6mr7y` (resumable for post-run sanity check if E1/E2/E3 verdicts diverge from the decision matrix)

## Sources

- `httpPlatformHandler` configuration reference (`requestTimeout` default 120 s):
  <https://learn.microsoft.com/en-us/iis/extensions/httpplatformhandler/httpplatformhandler-configuration-reference>
- App Service front-end 230-second request timeout:
  <https://learn.microsoft.com/en-us/troubleshoot/azure/app-service/web-request-times-out-app-service>
- App Service environment variables (`WEBSITE_PROACTIVE_AUTOHEAL_ENABLED`, relaxed binding for `SPRING_*` app settings):
  <https://learn.microsoft.com/en-us/azure/app-service/reference-app-settings>
- Windows App Service Java runtime (Java SE JAR execution model):
  <https://learn.microsoft.com/en-us/azure/app-service/configure-language-java-deploy-run>
- Kudu REST API reference (`/api/vfs`, `/api/command`):
  <https://github.com/projectkudu/kudu/wiki/REST-API>
- Log Analytics `AppServiceHTTPLogs` / `AppServiceConsoleLogs` schema reference:
  <https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/appservicehttplogs>
