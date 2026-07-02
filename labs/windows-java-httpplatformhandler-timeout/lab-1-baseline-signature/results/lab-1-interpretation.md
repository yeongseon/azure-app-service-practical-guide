# Lab 1 interpretation

Baseline signature verification for the `500.121.0` timeout on Windows App Service Java SE + httpPlatformHandler. All timestamps UTC. All measurements reproducible from artifacts in this directory.

## Environment

| Field | Value |
|---|---|
| Subscription | MCAPS `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| Resource group | `rg-lab-winjavatol1` |
| App name | `app-winjavatol1-cevxrss3aa7mk` |
| App URL | `https://app-winjavatol1-cevxrss3aa7mk.<azurewebsites-domain-redacted>` |
| Log Analytics workspace | `law-winjavatol1-cevxrss3aa7mk` (customer id `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`) |
| Region | `koreacentral` |
| Plan SKU | `B1` (1 vCPU, 1.75 GB RAM) |
| Runtime | Java SE 17 (Windows) |
| Deployed JAR | Stage 0 `app.jar` (22 MB, Spring Boot 3.3.4), byte-identical to Stage 0 |
| Delta vs Stage 0 | `SPRING_MVC_ASYNC_REQUEST_TIMEOUT=600000` app setting (resolves Stage 0 Q3 blocker) |
| Auto-Heal | Disabled (custom + Proactive), preflight PASSED |
| E1 window | 2026-07-01T09:54:55Z .. 2026-07-01T10:36:14Z (~41 minutes, 10 iterations) |
| E2 window | 2026-07-01T10:36:44Z .. 2026-07-01T10:37:23Z (~40 seconds, 7 Kudu probes) |
| E3 window | 2026-07-01T10:38:19Z .. 2026-07-01T10:43:20Z (~5 minutes, 1 stream probe + backend completion) |

## Executive summary

Lab 1 confirms the baseline `500.121.0` signature at high statistical confidence and definitively resolves the Stage 0 Q3 unknown (ABSOLUTE vs IDLE 230 s ceiling) as **ABSOLUTE**. Two additional findings emerged that materially affect Lab 2 design and the final lab guide's production recommendations:

1. **The 230 s cut is deterministic to within 5 ms (stddev)** across 10 serialized probes. Front-end request-timeout enforcement is not jittery; it is a precise clock.
2. **httpPlatformHandler / IIS on Windows Java SE does not stream backend chunks to the client**. Spring produced all 11 stream chunks over 300 s (proven by `AppServiceConsoleLogs`), but the client received 0 chunks and got the platform's canonical 500 error page instead. Streaming is not a viable workaround for the 230 s front-end limit on this stack.

Full verdict table:

| Hypothesis | Verdict | Confidence | Evidence source |
|---|---|---|---|
| L1-H1R (500/121 signature stability) | CONFIRMED | High | 10/10 probes, mean 230001.3 ms, stdev 5.44 ms |
| L1-H2R (no `.64` on serialized baseline) | CONFIRMED | High | 10/10 `ScWin32Status = 0`, zero `.64` |
| L1-H3R (Kudu-visible handler config) | FALSIFIED | High | 7/7 Kudu probes HTTP 401 (subscription policy) |
| L1-H4 (ABSOLUTE 230 s timer) | CONFIRMED (with critical nuance - see below) | High | E3 `AppServiceHTTPLogs.TimeTaken=230005 ms` + Spring `stream.end chunkCount=11 elapsedMs=300008` |
| L1-H5R (client 500 == IIS `ScStatus`) | CONFIRMED | High | 10/10 E1 client HTTP 500, 1/1 E3 client HTTP 500, zero client 502 |

## Per-hypothesis analysis

### L1-H1R: `500/121` signature stability - **CONFIRMED with 5 ms stdev**

Evidence from `verify-e1-http-rows.json` (server-side `AppServiceHTTPLogs`, filtered to `CsUriStem == "/slow/240"`):

| iteration | ScStatus | ScSubStatus | ScWin32Status | TimeTaken (ms) |
|---|---|---|---|---|
| 1 | 500 | 121 | 0 | 230000 |
| 2 | 500 | 121 | 0 | 229993 |
| 3 | 500 | 121 | 0 | 230005 |
| 4 | 500 | 121 | 0 | 230003 |
| 5 | 500 | 121 | 0 | 230004 |
| 6 | 500 | 121 | 0 | 230007 |
| 7 | 500 | 121 | 0 | 229995 |
| 8 | 500 | 121 | 0 | 229994 |
| 9 | 500 | 121 | 0 | 230005 |
| 10 | 500 | 121 | 0 | 230007 |

Aggregated (server-side):

| metric | value |
|---|---|
| row_count | 10 |
| mean TimeTaken | 230001.3 ms |
| stdev TimeTaken | 5.44 ms |
| min TimeTaken | 229993 ms |
| max TimeTaken | 230007 ms |
| range | 14 ms |

Client-side (`results/e1-signature-probes.csv`) mean was ~230.71 s, giving a client-vs-server delta of ~0.71 s. That delta is consumed by TCP RST propagation, curl teardown, and client-to-Korea-Central RTT - consistent with Stage 0's observation of ~0.70 s client-side overhead.

**All three success criteria met**:
- 100% (10/10) `ScStatus/ScSubStatus == 500/121`
- Mean 230001.3 ms lies well inside `[229800, 230500]`
- Stddev 5.44 ms is 37x below the 200 ms ceiling

The 5.44 ms stddev is the most striking result. Front-end request-timeout enforcement is not a coarse jittery watchdog - it is a precise clock. This directly informs Lab 2: any timing variance observed under load will attribute cleanly to the load model, not to baseline timer jitter.

### L1-H2R: no `.64` on serialized baseline - **CONFIRMED (0/10)**

Evidence: 10/10 iterations have `ScWin32Status = 0`. Zero `.64` observed.

Adaptive extension trigger did not fire; no need to re-run at 20 iterations.

The design rationale for this hypothesis was: `.64` (transport-level connection reset) is expected to correlate with concurrency-induced backpressure, not with the front-end 230 s clock. Lab 1's serialized-with-pacing model keeps queue depth at 1 for the entire run, so `.64` should not appear. It did not. This falsifies any hypothesis that `.64` arises from the request-timeout mechanism itself; it must arise from something Lab 1 deliberately excluded (concurrent load, loopback saturation, or downstream failures).

### L1-H3R: Kudu-visible handler config - **FALSIFIED (0/7 accessible)**

Evidence from `results/e2-kudu-fetch-manifest.csv`:

| probe | path/command | HTTP status | bytes |
|---|---|---|---|
| P1 | `GET /api/vfs/systemdrive/inetpub/config/applicationHost.config` | 401 | 0 |
| P2 | `GET /api/vfs/systemdrive/Windows/System32/inetsrv/config/applicationHost.config` | 401 | 0 |
| P3 | `POST /api/command dir C:\home\site` | 401 | 0 |
| P4 | `POST /api/command type C:\home\site\config\applicationHost.xdt` | 401 | 0 |
| P5 | `POST /api/command dir C:\home\LogFiles\httpPlatform` | 401 | 0 |
| P6 | `GET /api/vfs/LogFiles/httpPlatform/` | 401 | 0 |
| P7 | `POST /api/command reg query HKLM\System\CurrentControlSet\Services\W3SVC\Parameters` | 401 | 0 |

All seven probes returned HTTP 401 despite `main.bicep` setting `basicPublishingCredentialsPolicies.scm.allow: true` and the deployment succeeding with the same policy. The identical 401 pattern was observed in Stage 0 preflight and post-flight. Interpretation: **the subscription (MCAPS) has an org-level policy that overrides site-level `scm allow: true`** and denies basic auth to Kudu.

Under design-proposal.md revision 2, this is a **valid falsification outcome** treated as documented "platform observability limitation" (decision-matrix row 2). It does not invalidate H1R, H2R, or H4; it only means the effective `httpPlatformHandler` config cannot be inspected on this environment. In an enterprise MCAPS subscription, engineers investigating this class of issue in production would typically fall back to:

1. **Diagnose and Solve Problems** blade in the Azure Portal (managed identity, bypasses basic auth policy).
2. **Kudu bearer-token auth** via `az account get-access-token --resource https://<app>.scm.<azurewebsites-domain-redacted>` if the policy permits AAD-based SCM access.
3. **Configure a customer-authored `web.config`** to install a permissive `httpPlatformHandler` element (which then becomes visible in `wwwroot`).

The final lab guide should document paths #1 and #2 as the enterprise-safe alternatives.

### L1-H4: ABSOLUTE 230 s timer - **CONFIRMED with critical nuance**

**Server-side timeline** (all three events from Log Analytics, single `/stream/300` request):

| # | Timestamp UTC | Source | Event | Details |
|---|---|---|---|---|
| 1 | 2026-07-01T10:38:20.775Z | `AppServiceConsoleLogs` | Spring `stream.start` | `seconds=300 bounded=300 intervalSec=30` |
| 2 | 2026-07-01T10:42:11.834Z | `AppServiceHTTPLogs` | IIS 500/121/0 | `TimeTaken=230005 ms` (front-end cut) |
| 3 | 2026-07-01T10:43:20.784Z | `AppServiceConsoleLogs` | Spring `stream.end` | `chunkCount=11 elapsedMs=300008` (natural completion) |

**Interpretation**:

- The IIS `TimeTaken=230005 ms` in event 2 is the front-end 230 s enforcement fire, identical to `/slow/240` in E1.
- The Spring `stream.end` in event 3 proves the backend produced all 11 chunks over the full 300 s duration, exactly as designed.
- The **client received 0 chunks** (evidence: `results/e3-stream-body.ndjson` contains the canonical IIS 500 error HTML page, 221 bytes, and no chunk NDJSON entries).
- The backend continued executing for **68.95 s after the client connection was severed** (event 3 minus event 2). This is "orphan work" - the app has no signal to abort when the front-end cuts the response.

**H4 verdict: ABSOLUTE, with critical nuance**: The 230 s limit is absolute at the client-facing HTTP layer, but it is enforced **on the buffered/aggregated response boundary**, not on the streaming boundary. On Windows Java SE via httpPlatformHandler, the observable client behavior is all-or-nothing:

- Response body is not delivered progressively; IIS/httpPlatformHandler buffers or discards it.
- When the 230 s timer fires, IIS replaces the entire response with its canonical error page.
- The backend continues to consume worker resources for the full request duration.

**Note on the automated verdict**: `verify.sh` recorded H4 as `AMBIGUOUS` because its client-side chunk-count heuristic (`~8 chunks` for ABSOLUTE, `11 chunks` for IDLE) implicitly assumed IIS would stream partial chunks to the client. That assumption is wrong on Windows Java SE. The AMBIGUOUS label in `verify-report.md` is a script-logic limitation, not a real ambiguity. The definitive verdict is ABSOLUTE, established by cross-correlating `AppServiceHTTPLogs.TimeTaken` (server-side cut) with `AppServiceConsoleLogs stream.start` / `stream.end` (backend completion). Future runs of `verify.sh` should enhance the H4 logic to consult the console log timeline instead of client chunk count.

### L1-H5R: client 500 == IIS `ScStatus` - **CONFIRMED (11/11 direct probes)**

- E1: 10/10 client HTTP 500, 10/10 IIS `ScStatus=500` (100% match)
- E3: 1/1 client HTTP 500, 1/1 IIS `ScStatus=500` (100% match)
- Zero client-visible 502 on direct App Service request paths

The Stage 0 F2 attribution (production `502` requires an upstream proxy hop or a different request path) stands. Any production report of `502` on this stack should trigger investigation of the upstream layer (Application Gateway, Front Door, custom reverse proxy), not the App Service backend itself.

## Additional findings not directly tied to a hypothesis

### F1: `SPRING_MVC_ASYNC_REQUEST_TIMEOUT` app setting works and is the correct fix for Stage 0 Q3 blocker

Evidence: E3's Spring `stream.start` at 10:38:20 and `stream.end` at 10:43:20 (elapsedMs=300008) demonstrate the Spring MVC async request timeout is now 600 s (or effectively unlimited), not the 30 s default that blocked Stage 0 Q3. The `SPRING_MVC_ASYNC_REQUEST_TIMEOUT=600000` app setting was correctly consumed by Spring Boot's relaxed binding, which maps `SPRING_MVC_ASYNC_REQUEST_TIMEOUT` (underscores) to `spring.mvc.async.request-timeout` (dots and dashes).

This confirms the Stage 0 interpretation.md recommendation and validates the approach of using an app setting instead of adding a `spring.mvc.async.request-timeout` property to `application.properties` (which would require a JAR rebuild and break byte-identical reuse of the Stage 0 binary).

### F2: Warm-up requests produced 5 additional `AppServiceHTTPLogs` rows and initially skewed E1 aggregate statistics in `verify.sh`

Before the fix, `verify.sh`'s KQL for E1 statistics used `where CsUriStem startswith "/slow/"`, which matched both the warm-up (`/slow/2`, 5 rows returning 200) and E1 (`/slow/240`, 10 rows returning 500/121). This inflated the row count to 15 and produced misleading mean (153755 ms) and stdev (111612 ms), causing H1R to be reported as FALSIFIED on the first verify pass.

The fix (recorded in the amended `verify.sh`): extract `E1_ENDPOINT="/slow/$(csv column 2)"` from the E1 CSV first row, then use `where CsUriStem == "$E1_ENDPOINT"` for both KQL queries. After the fix, the aggregate cleanly matched the client-side data: 10 rows, mean 230001.3 ms, stdev 5.44 ms.

**This is a soft observability lesson**: warm-up traffic must be excluded by URL match or by narrow time-window, not by `startswith`. The final lab guide's KQL cookbook should call this out explicitly.

### F3: `run-e3-stream-test.sh` had a bash bug that split the CSV row across two lines

`grep -c "..." file || echo 0` produces `"0\n0"` when `grep -c` finds zero matches (because `grep -c` outputs `"0"` **and** exits code 1). This inserted a stray newline inside the CSV data row, causing `verify.sh`'s E3 time-window extraction to fail silently. The E3 step was initially reported as skipped.

Fix: `grep -c ... | head -1` retains grep's stdout `"0"` and ignores the exit code. The amended `run-e3-stream-test.sh` includes this fix.

Both F2 and F3 are pre-existing script bugs, not observations about the platform under test. They are documented here so the Lab 2 author is aware of them and does not spend time re-diagnosing.

## Decision-matrix routing

Cross-referencing this Lab's outcome against the design-proposal.md decision matrix:

- **E1**: `100% 500/121, stable timing, all ScWin32Status = 0` → matches decision-matrix rows 1, 2, or 3 (depending on E2 outcome).
- **E2**: `All 7 Kudu paths return no requestTimeout marker` (specifically, 401 - inaccessible) → matches decision-matrix row 2.
- **E3**: `/stream/300 cuts at ~230 s, 500/121, chunks=0` → this maps to row 6 of the decision matrix but with a critical nuance: `chunks=0` is not "somewhere other than ~230 s with ~8 chunks" (row 7 = "ambiguous"). The 0 chunks are because IIS does not stream to the client, not because Spring did not produce chunks (proven by console log `stream.end chunkCount=11`).

**Routed action** (per design-proposal.md decision-matrix row 2 + H4 ABSOLUTE nuance):

- Proceed to **Lab 2 (loopback saturation)** to reproduce the production `500.121.64` sub-status under controlled concurrent load.
- **Final lab guide MUST document the observability gap** (Kudu VFS/command paths not accessible under enterprise subscription policy) as a first-class finding, and MUST document the enterprise alternative diagnostic paths (Diagnose and Solve, Kudu bearer-token, customer `web.config`).
- **Final lab guide MUST document the IIS/httpPlatformHandler streaming buffering behavior** and explicitly recommend against streaming as a mitigation for the 230 s front-end limit on Windows Java SE.

## Recommendations for Lab 2 design

Based on Lab 1's findings, the Lab 2 design should incorporate:

1. **Baseline is a solved problem**. Lab 2 does not need to re-establish that serialized probes produce clean 500/121 with 5 ms stddev. It can assume that as a control condition.
2. **The trigger for `.64` is not the timer itself**. Lab 1 falsified the hypothesis that `.64` arises from the 230 s clock alone. Lab 2 must find the concurrency threshold or the specific loopback traffic pattern that produces `.64`. Design open-model load (arrival-rate controlled) to isolate.
3. **Kudu is not accessible in this environment**. Lab 2 should not depend on Kudu VFS/command paths. Any diagnostics should use `az` CLI, Log Analytics KQL, or Diagnose-and-Solve endpoints.
4. **Backend orphan work is real**. Lab 2's load model must account for the fact that abandoned client connections leave server-side work running. Cost modeling should include the orphan CPU/memory consumption. If Lab 2 uses k6 or similar tools with request pacing, be aware that the backend queue continues to fill even after the load generator moves on.
5. **Enable stdout collection for httpPlatformHandler if possible**. Even though Kudu is not accessible, `AppServiceConsoleLogs` did surface Spring's `stream.start`/`stream.end`. Lab 2 should ensure equivalent server-side observability is in place BEFORE running the load.

## Observability limitations documented

For the final lab guide's "Observability" section:

1. **Kudu VFS and Kudu console are not accessible under MCAPS subscription policy**, even when the site-level `basicPublishingCredentialsPolicies.scm.allow = true` is set. This blocks all `/api/vfs`, `/api/command`, `/api/environment`, `/api/settings`, `/api/scm/info`, `/api/diagnostics/runtime`, and `/api/processes` endpoints. Enterprise engineers must use ARM-plane (`az webapp config show`), Diagnose-and-Solve, or bearer-token auth.
2. **IIS/httpPlatformHandler on Windows Java SE does not stream backend chunks to the client**. The observable client behavior of a streaming endpoint under the 230 s cut is: 0 bytes of streamed data + canonical IIS 500 error page + 500/121 status. Backend logs (`AppServiceConsoleLogs`) are the only place to confirm the backend was actually streaming.
3. **`ScWin32Status = 0` on the baseline cut proves the 230 s enforcement is not a transport-layer reset**. When `.64` appears in production, it is additional information about the connection state at cut time, not the primary cause of the cut.

## See also

- Lab 1 README: [`README.md`](../README.md)
- Lab 1 design proposal (Oracle-reviewed): [`../design-proposal.md`](../design-proposal.md)
- Lab 1 auto-generated verify report: [`verify-report.md`](verify-report.md)
- Stage 0 interpretation: [`../../stage-0-config-discovery/results/stage-0-interpretation.md`](../../stage-0-config-discovery/results/stage-0-interpretation.md)
- Lab 2 (pending, gated on this Lab): `../../lab-2-loopback-saturation/README.md`
- Oracle Lab 1 design review session: `ses_0e3010e14ffePDjr4dEej6mr7y` (resume for post-Lab-1 sanity check or Lab 2 design review)

## Sources

- App Service front-end 230-second request timeout:
  <https://learn.microsoft.com/en-us/troubleshoot/azure/app-service/web-request-times-out-app-service>
- `httpPlatformHandler` configuration reference (documented `requestTimeout` default 120 s):
  <https://learn.microsoft.com/en-us/iis/extensions/httpplatformhandler/httpplatformhandler-configuration-reference>
- App Service environment variables (`SPRING_*` relaxed binding, `WEBSITE_PROACTIVE_AUTOHEAL_ENABLED`):
  <https://learn.microsoft.com/en-us/azure/app-service/reference-app-settings>
- Windows App Service Java SE runtime (Java SE JAR execution model):
  <https://learn.microsoft.com/en-us/azure/app-service/configure-language-java-deploy-run>
- Log Analytics `AppServiceHTTPLogs` schema:
  <https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/appservicehttplogs>
- Log Analytics `AppServiceConsoleLogs` schema:
  <https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/appserviceconsolelogs>
- Kudu REST API reference:
  <https://github.com/projectkudu/kudu/wiki/REST-API>
- Spring Boot externalized configuration (relaxed binding for environment variables):
  <https://docs.spring.io/spring-boot/docs/current/reference/html/features.html#features.external-config.typesafe-configuration-properties.relaxed-binding.environment-variables>
