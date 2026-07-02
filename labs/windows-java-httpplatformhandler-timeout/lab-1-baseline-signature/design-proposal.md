# Lab 1 design proposal (post-Oracle-review revision 2)

Oracle verdict on revision 1: **APPROVE-WITH-CHANGES** (session `ses_0e3010e14ffePDjr4dEej6mr7y`).

This revision applies all 5 required changes from Oracle:

1. Rewritten **L1-H3** to a cleanly falsifiable Kudu-accessibility hypothesis.
2. Demoted **L1-H5 / E4** to an optional observation.
3. **Retained** the preflight isolation check in `deploy.sh`.
4. **Kept E1 serialized with no overlap**; pacing shortened to "previous backend completion + 10 s" (not immediately after curl exits).
5. **App setting** `SPRING_MVC_ASYNC_REQUEST_TIMEOUT` (finite value > 230 s) instead of a new JAR redeploy for E3.

## Goal

Add the diagnostic instrumentation that Stage 0 could not provide:

- Characterize the **baseline distribution** of the `500.121.0` signature under repeated serialized probes (Stage 0 had only 3 cut samples; enough to guide design, not enough to characterize rate).
- Resolve the only remaining major platform unknown from Stage 0: whether the 230 s front-end limit is **ABSOLUTE** (total request duration) or **IDLE** (stops when server sends bytes).
- Provide **best-effort visibility** into where the effective `httpPlatformHandler` configuration lives on Windows App Service, given that `wwwroot/web.config` is empty on the Java SE image.

## Scope

- **IN**: single Windows Java SE web app, serialized probe iterations (no overlap), Kudu-only config discovery, Log Analytics correlation
- **OUT**: load testing (Lab 2), downstream service dependencies (Lab 2), Auto-Heal mitigation (Lab 2), custom `web.config` mitigation (Lab 2), concurrency-induced `.64` reproduction (Lab 2)

## Hypotheses (all derived from Stage 0 findings)

| ID | Hypothesis | Falsification |
|---|---|---|
| L1-H1R | Under repeated serialized `/slow/240` probes, IIS `TimeTaken` remains tightly clustered around 230000 ms (stddev < 200 ms on the server side) and `ScStatus/ScSubStatus` remains `500/121` in 100% of iterations. | Any iteration outside `[229800, 230500]` ms on the server side, OR `ScStatus/ScSubStatus` differs from `500/121` at least once. |
| L1-H2R | Under serialized no-overlap baseline probes, `ScWin32Status` remains `0` on every iteration; any `.64` is exceptional and triggers extension/inspection, not pre-normalized as noise. | Any single `.64` in the serialized baseline -> extend to 20 iterations, correlate with console timestamps for overlap, treat as an anomaly finding rather than pre-authorized noise. |
| L1-H3R | A Kudu-accessible IIS/site artifact **outside `wwwroot`** will reveal the app's effective `httpPlatformHandler` configuration; if it exposes `requestTimeout`, that value will be >= 230 s. | After exhausting planned Kudu VFS/command paths and stdout logs, **no accessible artifact shows the effective config**, OR a revealed timeout is < 230 s. Both outcomes are still useful findings. |
| L1-H4 | The 230 s front-end limit is an **ABSOLUTE** request-duration limit, not an idle timeout. `/stream/300` with `SPRING_MVC_ASYNC_REQUEST_TIMEOUT` set to a value > 300 s (removing the Spring MVC async 30 s defect) will cut at ~230 s server-side after ~8 chunks. | `/stream/300` completes with all 11 chunks (IDLE - server-sent bytes reset front-end counter). Revise final lab guide accordingly. |
| L1-H5R (optional) | On direct App Service requests, client-visible HTTP status matches IIS `ScStatus=500`; any client-visible `502` requires an added upstream hop or a different request path. | Baseline shows `502` at client on direct requests -> revise Stage 0 F2 attribution (production `.64` outer 502 came from App Service front-end itself, not an upstream rewrite). |

**H1R rationale (per Oracle)**: Q1 (front-end 230 s limit) is already confirmed at high precision by Stage 0 (`stage-0-interpretation.md:23-49`). Repeating this measurement is only worthwhile as a **stability check** while E1 measures H2R. Client `curl time_total` will not be used as the measurement; server-side `AppServiceHTTPLogs.TimeTaken` will (Stage 0 already showed client overhead adds ~0.68-0.72 s while IIS recorded `230000/230036/230011` ms).

**H2R rationale (per Oracle)**: The original "occasional `.64` is possible but rare" clause was too forgiving. In a no-load serialized baseline, `.64` should be treated as anomaly - Stage 0 saw only `.0` in 3/3 cuts.

**H3R rationale (per Oracle)**: The original H3 was a disjunction ("found in injected `applicationHost.config` OR compiled-in default overridden by front-end at 230 s"). The second branch is not directly measurable with the proposed tools (Kudu cannot prove a compiled default path if config is inaccessible). The rewrite converts it into a falsifiable **accessibility question**: does a Kudu-visible artifact reveal the effective config? If not, that itself is a useful finding for App Service Windows Java SE troubleshooting.

**H5R rationale (per Oracle)**: Demoted from core hypothesis to optional observation. Stage 0 already saw direct client `500` (`stage-0-interpretation.md:34-36,130-145`) and reasonably attributed production `502` to an upstream rewrite. Not worth a dedicated experiment - just a data point captured during E1.

## Experiment design

### E1: Adaptive baseline signature stability (L1-H1R, L1-H2R)

**Adaptive pacing**: Run **10 iterations first**; extend to **20** only if variance widens, `.64` appears, or any unexpected status.

Iteration:

1. Fire `/slow/240` via `curl`, capture `http_code`, `time_total`.
2. Wait until the **backend Java thread completes** (Stage 0 showed orphan work ends ~10 s after client cutoff, so `elapsed_backend = 240 + 10 = 250 s`), then wait an **additional 10 s** buffer.
3. Log iteration index, timestamps, curl output, elapsed.
4. Repeat.

Total wall time per iteration: ~260 s (client cut at 230 s + 20 s backend/settle + 10 s buffer). 10 iterations = ~43 min. 20 iterations = ~87 min.

After all iterations complete, query:

- `AppServiceHTTPLogs.TimeTaken, ScStatus, ScSubStatus, ScWin32Status` per request
- Compute: mean/stddev of `TimeTaken`, distribution of `ScWin32Status`, `ScStatus/ScSubStatus` frequency table

Success criteria:

- H1R: `ScStatus/ScSubStatus = 500/121` in **100%** of iterations. `TimeTaken` mean in `[229800, 230500]` ms, stddev < 200 ms.
- H2R: `ScWin32Status = 0` in **100%** of iterations.

If either fails on the first 10, extend to 20 and re-evaluate.

### E2: Kudu-only config visibility (L1-H3R)

**Best-effort discovery, not RDP-dependent.** Kudu is already the SCM site; Stage 0 explicitly enabled SCM basic auth for that purpose. No `config-zip` upload needed.

Fetch (each may return 200/401/403/404 - record whichever):

1. `GET /api/vfs/systemdrive/inetpub/config/applicationHost.config`
2. `GET /api/vfs/systemdrive/Windows/System32/inetsrv/config/applicationHost.config`
3. `POST /api/command` with `command: "dir C:\\home\\site"` (already known to work from Stage 0)
4. `POST /api/command` with `command: "type C:\\home\\site\\config\\applicationHost.xdt"` (site-scoped IIS transform)
5. `POST /api/command` with `command: "dir C:\\home\\LogFiles\\httpPlatform"` (stdout log directory - may exist even without customer web.config if platform logging is enabled)
6. `GET /api/vfs/LogFiles/httpPlatform/` (VFS view of the same directory)
7. `POST /api/command` with `command: "reg query HKLM\\System\\CurrentControlSet\\Services\\W3SVC\\Parameters"` (unlikely to work but low cost to try)

Parse fetched artifacts (if any) for `<httpPlatform` elements and `requestTimeout` attribute.

**Interpretation matrix**:

| Outcome | H3R verdict | Downstream implication |
|---|---|---|
| Any artifact reveals `requestTimeout >= 230000` (or unset, defaulting to 120 s) | H3R **confirmed** - config lives outside `wwwroot` and is Kudu-visible | Documented for the final lab guide |
| Any artifact reveals `requestTimeout < 230000` | H3R **partially falsified** - handler config exists but is not the operative timer (front-end 230 s wins) | Documented as "handler default overridden by front-end" |
| **All** artifacts return 401/403/404 with no visible `httpPlatform` element | H3R **falsified** - effective config is not Kudu-accessible on Windows App Service Java SE | Documented as a platform limitation finding |

All three outcomes are useful. E2 cannot "fail" in a wasted-time sense.

### E3: /stream absolute-vs-idle resolution (L1-H4)

**App setting override, not JAR redeploy.** Set `SPRING_MVC_ASYNC_REQUEST_TIMEOUT` = `600000` (10 minutes in ms) via `main.bicep` before deployment. This removes the Spring MVC async 30 s defect that cut Stage 0's `/stream/300` at 32 s.

Rationale for finite value vs `-1`:

- Same binary as Stage 0 (no drift).
- `-1` semantics on Spring Boot / Tomcat vary by version; `600000` is unambiguous.
- 600 s comfortably exceeds both the front-end 230 s and the stream target 300 s.

Execution (once, one probe):

1. Fire `curl -N https://$APP.azurewebsites.net/stream/300`, capture chunk-by-chunk timing with `curl -w '%{time_total}\n'`.
2. Stream endpoint emits one chunk every 30 s per Stage 0 (11 chunks total for 300 s).
3. Query `AppServiceConsoleLogs` for `stream.start`, `stream.chunk`, `stream.end`, `stream.interrupted`.
4. Query `AppServiceHTTPLogs` for the `/stream/300` request `TimeTaken` and `ScStatus`.

Interpretation:

| Outcome | H4 verdict |
|---|---|
| `TimeTaken ~= 230000 ms`, ~8 chunks delivered, `ScStatus = 500`, `ScSubStatus = 121` | **ABSOLUTE** confirmed |
| `TimeTaken ~= 300000 ms`, 11 chunks delivered, `ScStatus = 200`, no interrupt | **IDLE** confirmed (server-sent bytes reset front-end counter) |
| Any other pattern | Ambiguous - documented as an anomaly for follow-up |

### E4 (demoted to optional observation): Client vs IIS outer status (L1-H5R)

**Not a dedicated experiment.** During E1 iterations, record `curl_http_code` alongside `AppServiceHTTPLogs.ScStatus`. If they differ (i.e., client sees anything other than `500` while IIS logs `500`), that is worth noting; otherwise treat as null observation.

If time permits after E1/E2/E3, optionally add:

- One probe via a preview slot (if configurable trivially) to check whether a slot's front-end still reports `500` directly.

**Skip if any of E1/E2/E3 needs rerun**; do not risk lab clarity for this low-value observation.

## Priority ranking (per Oracle)

If time constraints force dropping experiments:

1. **E3** (highest information value) - resolves the only remaining major Stage 0 unknown.
2. **E2** - may end in "not Kudu-accessible", which is still useful but less decisive.
3. **E1** - stability check for already-confirmed Q1. Adaptive 10 iterations keeps it cheap.
4. **E4** (drop first) - mostly redundant; direct `500` already observed in Stage 0.

Recommended execution order: E1 -> E2 -> E3 (serial, no cross-experiment interference). E1 must run first because E2 and E3 need the app deployed and warm.

## Bicep changes vs Stage 0

- **Reuse** the Stage 0 `main.bicep` as the starting point (B1 Windows Java SE, Log Analytics, diagnostic settings, Auto-Heal + Proactive Auto-Heal disabled, SCM basic auth enabled).
- **Add**: `SPRING_MVC_ASYNC_REQUEST_TIMEOUT` = `600000` as an app setting in the `siteConfig.appSettings` array. Spring Boot honors `SPRING_*` env vars via relaxed binding, mapping to `spring.mvc.async.request-timeout`.
- **No** downstream service, VNet, scale-out, custom web.config injection, or Auto-Heal rule additions.
- **No** change to preflight checks (`autoHealEnabled=false`, `WEBSITE_PROACTIVE_AUTOHEAL_ENABLED=false`) - these are the Stage 0 guarantees that must persist.

## Application changes vs Stage 0

**Reuse the Stage 0 JAR unchanged.** No `application.properties` modification, no new endpoint, no logging change. The app setting override handles the async timeout; the JAR stays byte-identical.

Rationale: same binary across Stage 0 and Lab 1 keeps the comparison clean. Only the platform configuration differs.

## Script design

| Script | Purpose | Notes |
|---|---|---|
| `deploy.sh` | Fresh RG, `main.bicep` deploy, JAR upload, preflight verification | **Preflight retained** (per Oracle change #3). Same structure as Stage 0 `deploy.sh` including `--preflight` guard. |
| `warm-up.sh` | `/actuator/health` poll + JIT settle | Verbatim copy of Stage 0 `warm-up.sh`. |
| `run-e1-signature-probe.sh` | E1 adaptive iterations | Starts with 10, extends to 20 if trigger conditions met. Backend-completion + 10 s pacing. |
| `run-e2-config-visibility.sh` | E2 Kudu-only discovery | Records all 7 fetch attempts with HTTP status codes in a manifest CSV. Best-effort, no failure semantics. |
| `run-e3-stream-test.sh` | E3 single stream probe | One `/stream/300` invocation with chunk timing capture. |
| `collect-effective-config.sh` | Post-flight collection | Reuses Stage 0 collect script. |
| `verify.sh` | KQL queries + statistics | Computes E1 mean/stddev of `TimeTaken`, tabulates `ScWin32Status` distribution, extracts E3 chunk timing. |
| `cleanup.sh` | `az group delete` | Same as Stage 0. |

## Expected wall time (revised)

| Step | Time |
|---|---|
| Deploy + warm-up + preflight | 6 min |
| E1 (10 iterations at ~260 s each) | 43 min |
| E1 extension to 20 (only if triggered) | +43 min |
| E2 config visibility (7 Kudu calls) | 5 min |
| E3 stream test (single 300 s probe + buffer) | 6 min |
| Post-flight + verify | 5 min |
| **Total (10 iterations)** | **~65 min** |
| **Total (20 iterations)** | **~108 min** |

## Cost estimate (revised per Oracle)

- B1 Basic Windows plan: $0.075/hour
- 10-iteration path: 65 min * ($0.075/60) = **~$0.08**
- 20-iteration path: 108 min * ($0.075/60) = **~$0.14**
- Log Analytics ingestion: negligible (< 100 MB)
- **Budget cap: $0.20** (Stage 0 confirmed actual costs run below theoretical)

## Deferred to Lab 2

- `500.121.64` reproduction via loopback saturation
- Custom `web.config` mitigation (M1: `requestTimeout` extension)
- Custom Auto-Heal rule mitigation (M2)
- Open-model load (k6 arrivals-per-second) beyond queue depth 1
- Downstream service dependency

## Open questions carried forward to lab guide authoring

- Does `AppServiceHTTPLogs.CsBytes` differ between successful `/slow/60` and cut `/slow/240`? (Passive observation during verify.sh, not a hypothesis.)
- Do the E2 Kudu responses reveal any App Service internal paths worth documenting in the final lab guide? (Diagnostic value question, not a hypothesis.)

## Content structure decision (per Oracle Section E)

Final lab guide at `docs/troubleshooting/lab-guides/windows-java-httpplatformhandler-timeout.md` will be **one document** with the 16-section troubleshooting template, split by stage inside sections 5-9:

- **5. Experiment**: 5.1 Stage 0 discovery, 5.2 Lab 1 signature, 5.3 Lab 2 load
- **7. Observation**: per-stage subsections
- **8. Measurement**: per-stage tables
- **9. Analysis**: per-stage conclusions, then overall synthesis

Evidence labels per AGENTS.md `[Observed] / [Measured] / [Inferred] / [Unknown]` applied throughout.
