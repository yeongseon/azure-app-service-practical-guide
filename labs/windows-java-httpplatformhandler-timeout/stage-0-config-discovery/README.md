# Stage 0: Effective config discovery gate

Discovery gate that runs before Lab 1 (baseline signature) and Lab 2 (mitigation). Its purpose is to answer four falsifiable questions about a Windows App Service Java SE app whose observed answers dictate which hypotheses are still valid for the follow-on labs.

This is not a signal-reproduction lab. It measures what the platform actually does before we spend effort designing an experiment against what we assume it does.

## Discovery questions

| # | Question | Origin | Method |
|---|---|---|---|
| Q1 | What is the effective front-end request timeout for a Windows Java SE app on B1? | Oracle H1 refinement | Sequential `/slow/{n}` probes at 60, 180, 210, 220, 225, 240, 300, 360s |
| Q2 | Does the platform generate a `web.config` for a Java SE app, and if so, what is the effective `httpPlatformHandler.requestTimeout`? | Oracle H4 | Kudu `/api/vfs/site/wwwroot/web.config` fetch |
| Q3 | Is the ~230s ceiling an idle timeout (bytes reset the clock) or an absolute request-duration limit? | Oracle H7 | `/stream/300` with a chunk emitted every 30s |
| Q4 | Are Proactive Auto-Heal and any Auto-Heal rules disabled during the probe window? | Oracle fatal-flaw #4 | `az webapp config show` + app settings dump |

Without these four answers, Lab 1's hypotheses are unfalsifiable: the 120s vs 230s timer contradiction, the direction of any mitigation experiment, and the attribution of a mid-request connection close all depend on them.

## Prerequisites

| Requirement | Purpose |
|---|---|
| Azure CLI (`az`) 2.60+ signed in with rights to create resources in the target subscription | Deploy Bicep, query config, delete RG |
| Maven (`mvn`) 3.8+ and JDK 17 on the local machine | Build the Spring Boot JAR |
| `curl` and `python3` on the local machine | Probes and Kudu API parsing |
| Basic auth allowed on the target subscription's App Service | Kudu `/api/vfs` and `/api/environment` fetches. Azure changed the default in early 2024 so newly-provisioned sites have `Microsoft.Web/sites/basicPublishingCredentialsPolicies` `scm` `allow: false`. `main.bicep` sets `allow: true` explicitly. |

The lab deploys **one** B1 Windows plan and **one** Windows Java SE web app plus a Log Analytics workspace. No downstream service, no VNet, no scale-out.

## Steps

Run the scripts in order. Each writes to the same output directory when passed one.

```bash
cd labs/windows-java-httpplatformhandler-timeout/stage-0-config-discovery

# 1. Deploy (creates RG, deploys Bicep, builds and uploads JAR)
bash deploy.sh <BASE_NAME> koreacentral rg-lab-<BASE_NAME>

# 2. Warm up (polls /actuator/health, JIT warm, 30s idle settle)
bash warm-up.sh https://app-<BASE_NAME>-<suffix>.azurewebsites.net

# 3. Preflight config check (verifies Auto-Heal is disabled before spending 40 min on probes)
bash collect-effective-config.sh --preflight app-<BASE_NAME>-<suffix> rg-lab-<BASE_NAME> ./results

# 4. Timeout probes (~40 minutes total wall time; longer probes wait for backend completion)
bash run-timeout-probe.sh https://app-<BASE_NAME>-<suffix>.azurewebsites.net ./results

# 5. Post-flight full config collection (Kudu + ARM + manifest CSV)
bash collect-effective-config.sh app-<BASE_NAME>-<suffix> rg-lab-<BASE_NAME> ./results

# 6. Tear down
bash cleanup.sh rg-lab-<BASE_NAME>
```

The app name and hostname are printed by `deploy.sh` at the end of step 1. Copy them into the subsequent commands.

If step 3 (preflight) exits non-zero, DO NOT proceed to step 4. The environment is contaminated and any timing curve collected from a contaminated environment cannot distinguish Auto-Heal recycles from front-end request-timeout cuts. Fix `main.bicep`, re-deploy, and re-run from step 1.

## Decision matrix

Read the observed timing curve and the effective `web.config` together. The matrix below routes to the correct hypothesis for the follow-on labs; the labels in the "Routes to" column are the hypothesis IDs from the Oracle-reviewed design.

| Observed `/slow/{n}` behavior | Observed `web.config` (Kudu) | Interpretation | Routes to |
|---|---|---|---|
| Succeeds for all n up to ~230, cuts around 230s for n > 230 | `requestTimeout="00:04:00"` (240s) explicit in `wwwroot/web.config` | Front-end 230s dominates; httpPlatformHandler 120s default is NOT in effect and platform sets 240s so handler cannot cut before front-end. H1 confirmed, H4 fully resolved. | Lab 1 H1 (front-end limit) as primary; H4 answered |
| Succeeds for all n up to ~230, cuts around 230s for n > 230 | `wwwroot/web.config` absent (HTTP 404 in `kudu-fetch-manifest.csv`) | Front-end 230s dominates AND platform does not materialize `web.config` in `wwwroot` for Java SE. H1 confirmed, but **H4 UNRESOLVED**: the effective handler config lives elsewhere (site-scoped `applicationHost.config` or IIS defaults) and Stage 0 cannot see it. | Lab 1 H1 confirmed; Lab 1 MUST add an H4 diagnostic that Stage 0 does NOT collect: (a) fetch IIS site-scoped `applicationHost.config` from Kudu VFS at `/api/vfs/systemdrive/inetpub/config/` or via Kudu console, (b) enable httpPlatformHandler stdout logging (`stdoutLog.enabled="true"` in a customer-authored `web.config`) and read `%HOME%\LogFiles\httpPlatform\*.log` after a failed request, (c) query `AntaresIISLogWorkerTable` in Log Analytics for `sc-substatus=64` correlated with client cut-off times |
| Cuts around 120s regardless of n | `requestTimeout` absent or `"00:02:00"` | httpPlatformHandler 120s default is in force; the observed 230s in the production ticket must be a different code path. | Lab 1 H2 (handler default) becomes the primary suspect; re-check production `web.config` |
| Cuts around some other value X | Any | Effective config differs from both defaults; document X and the config value together. | Lab 1 H4 (effective config drift) becomes primary |
| /stream/300 completes with 11 chunks | N/A | 230s (or X) is an IDLE timeout - streaming responses in production are safe up to their own duration. | Add H7 verdict to Lab 1 conclusion; adjust production advice |
| /stream/300 cuts around 230s (or X) with ~8 chunks | N/A | 230s (or X) is an ABSOLUTE request-duration limit - streaming does not help. | Add H7 verdict to Lab 1 conclusion; production must chunk work below X |
| /stream/300 cuts around 30s with fewer than 3 chunks AND app console log shows `stream.interrupted` | N/A | Spring MVC async request timeout (Tomcat default 30s) fired before the front-end timer had a chance to demonstrate its behavior. **This is an application-level defect, not a platform behavior**, and Q3 is unresolved. Lab 1 MUST set `spring.mvc.async.request-timeout=-1` (or a value >= 240s) before re-running the stream test. This is what Stage 0 observed on 2026-07-01 - see `results/stage-0-interpretation.md`. | Route to Lab 1 with the async-timeout fix baked into the app; do NOT trust Q3 until re-tested |
| `autoHealEnabled: true` OR `WEBSITE_PROACTIVE_AUTOHEAL_ENABLED` absent/true in the dump | N/A | Stage 0 environment is contaminated - re-deploy before trusting the timing curve. | Re-run Stage 0 after fixing `main.bicep`; preflight step (`--preflight`) should catch this before probes run |

## Evidence to collect

After a successful run the `./results` directory should contain:

| File | Origin | Purpose |
|---|---|---|
| `slow-probes.csv` | `run-timeout-probe.sh` | HTTP code, `time_total`, `curl_exit_code` for each of the 8 durations |
| `stream-probes.csv` | `run-timeout-probe.sh` | Same for the H7 `/stream/300` probe |
| `stream-body.ndjson` | `run-timeout-probe.sh` | Actual chunks received - `chunkIndex` and `elapsedMs` per line |
| `summary.md` | `run-timeout-probe.sh` | Rendered tables + interpretation hints |
| `kudu-fetch-manifest.csv` | `collect-effective-config.sh` | Definitive record of `path,http_code,bytes,outfile` for every Kudu fetch. Distinguishes HTTP 404 (file absent) from HTTP 200 (file present but empty). |
| `kudu-web-config.xml` (or `.http-404`) | `collect-effective-config.sh` | The `web.config` the platform generated. Renamed with `.http-<code>` suffix on non-200 responses so the file's name reflects its HTTP status. |
| `kudu-wwwroot-listing.json` | `collect-effective-config.sh` | Directory listing of `wwwroot` - primary source for what files the platform materialized |
| `kudu-site-listing.json` | `collect-effective-config.sh` | Directory listing of `site` (one level above `wwwroot`) - fallback for App_Data or nested config directories |
| `kudu-command-dir-wwwroot.json` | `collect-effective-config.sh` | Output of `dir C:\home\site\wwwroot` via Kudu `/api/command`. Independent enumeration when `/api/vfs` returns 404 or is filtered. |
| `kudu-environment.json` | `collect-effective-config.sh` | All environment variables visible to the worker |
| `kudu-diagnostics-runtime.json` | `collect-effective-config.sh` | Java version, GC, HTTP stack version |
| `kudu-processes.json` | `collect-effective-config.sh` | Running processes with PIDs (java.exe, w3wp.exe) |
| `az-webapp-config-show.json` | `collect-effective-config.sh` | Full siteConfig including `autoHealRules` |
| `az-webapp-appsettings.json` | `collect-effective-config.sh` | All app settings including `WEBSITE_PROACTIVE_AUTOHEAL_ENABLED` |

Commit sanitized copies (subscription ID, tenant ID, and any secrets scrubbed) to `artifacts-sanitized/stage-0/` under the parent lab directory before deleting the local copy.

## Cost

At B1 Basic in Korea Central, this Stage runs at approximately $0.10 per hour for the plan. A full pass (deploy + warm-up + preflight + 40-minute probe + post-flight config collection + teardown) fits inside a single billed hour, so the expected end-to-end cost is under $0.50. Log Analytics ingestion of a single-day burst of platform + HTTP + console logs from one B1 plan is below the 5 GB per-workspace free tier when only Stage 0 runs.

## What Stage 0 deliberately does NOT do

- No load test. Probes are strictly sequential with **at least 15-second spacing**, extended to `backend_completion_time + 10s` for probes where the front-end cuts the client before the backend `Thread.sleep(n)` finishes. This keeps the queue-depth signal at 1 even after long /slow/300 or /slow/360 probes leave backend work running past the client's curl abort.
- No downstream service. Any observed timeout is attributable to IIS <-> httpPlatformHandler <-> Java SE only.
- No mitigation attempt. Auto-Heal and Proactive Auto-Heal are both disabled specifically so the platform's raw behavior is measured.
- No production tuning. `JAVA_OPTS`, `SERVER_TOMCAT_MAX_THREADS`, and similar knobs are left at their platform defaults so the discovery reflects the out-of-the-box configuration production most likely started from.

Each of these is a Lab 1 or Lab 2 concern once Stage 0 has fixed the timer-chain interpretation.

## See also

- Top-level lab overview: `../README.md`
- Oracle-reviewed design: `docs/troubleshooting/lab-guides/windows-java-httpplatformhandler-timeout.md` (pending, gated on Stage 0 results)

## Sources

- `httpPlatformHandler` configuration reference (`requestTimeout` default 120s):
  <https://learn.microsoft.com/en-us/iis/extensions/httpplatformhandler/httpplatformhandler-configuration-reference>
- App Service front-end 230-second request timeout:
  <https://learn.microsoft.com/en-us/troubleshoot/azure/app-service/web-request-times-out-app-service>
- App Service environment variables (`WEBSITE_PROACTIVE_AUTOHEAL_ENABLED`, `WEBSITE_JAVA_JAR_FILE_NAME`):
  <https://learn.microsoft.com/en-us/azure/app-service/reference-app-settings>
- Windows App Service Java runtime (Java SE JAR execution model):
  <https://learn.microsoft.com/en-us/azure/app-service/configure-language-java-deploy-run>
- Kudu REST API reference (`/api/vfs`, `/api/environment`, `/api/settings`):
  <https://github.com/projectkudu/kudu/wiki/REST-API>
