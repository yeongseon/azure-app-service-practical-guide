# Stage 0 interpretation

Discovery gate results and routing decisions for the follow-on labs. All timestamps are UTC. All measurements reproducible from artifacts in this directory.

## Environment

| Field | Value |
|---|---|
| Subscription | MCAPS `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| Resource group | `rg-lab-winjavatimeout` |
| App name | `app-winjavatimeout-eliroyg74lvho` |
| App URL | `https://app-winjavatimeout-eliroyg74lvho.<azurewebsites-domain-redacted>` |
| Region | `koreacentral` |
| Plan SKU | `B1` (1 vCPU, 1.75 GB RAM) |
| Runtime | Java SE 17 (Windows) |
| OS | Windows Server 2022 (build 20348; `os_name` in `/api/diagnostics/runtime` misleadingly reads `Windows Server 2016`) |
| Auto-Heal | Disabled (custom + Proactive) |
| Deployed JAR | `app.jar` (22 MB, Spring Boot 3.3.4) |
| Probe window | 2026-07-01T08:43:49Z .. 2026-07-01T09:16:06Z (~32 minutes) |

## Discovery answers

### Q1: Effective front-end request timeout - **230 seconds, high precision**

Evidence from `results/slow-probes.csv` (client-side curl):

| requested_s | http_code | client_time_s | curl_exit | delta_from_230s |
|---|---|---|---|---|
| 60 | 200 | 61.425 | 0 | -168.575 |
| 180 | 200 | 180.647 | 0 | -49.353 |
| 210 | 200 | 210.803 | 0 | -19.197 |
| 220 | 200 | 220.840 | 0 | -9.160 |
| 225 | 200 | 225.751 | 0 | -4.249 |
| 240 | **500** | **230.688** | 0 | **+0.688** |
| 300 | **500** | **230.715** | 0 | **+0.715** |
| 360 | **500** | **230.683** | 0 | **+0.683** |

The three cut samples span only 32 ms (230.683 s .. 230.715 s). The 700 ms delta above 230.000 s is consumed by TCP handshake + TLS + curl overhead + client-to-Korea-Central RTT.

Cross-validated by IIS-level `AppServiceHTTPLogs.TimeTaken`:

| CsUriStem | ScStatus | ScSubStatus | ScWin32Status | TimeTaken (ms) |
|---|---|---|---|---|
| `/slow/240` | 500 | 121 | 0 | 230000 |
| `/slow/300` | 500 | 121 | 0 | 230036 |
| `/slow/360` | 500 | 121 | 0 | 230011 |

The IIS `TimeTaken=230000` on `/slow/240` is exactly the front-end 230 s ceiling, measured server-side without RTT overhead. **H1 confirmed with high precision.**

Reference: [Web app request times out](https://learn.microsoft.com/en-us/troubleshoot/azure/app-service/web-request-times-out-app-service) - App Service front end has a fixed 230 s request timeout.

### Q2: `web.config` presence in `wwwroot` - **ABSENT (HTTP 404)**

Evidence from `results/kudu-fetch-manifest.csv`:

| path | http_code |
|---|---|
| `/api/vfs/site/wwwroot/` | 200 |
| `/api/vfs/site/wwwroot/web.config` | **404** |
| `/api/vfs/site/wwwroot/App_Data/` | 404 |
| `/api/command dir C:\home\site\wwwroot` | 200 (independent enumeration) |

`wwwroot` contains exactly two files:

- `app.jar` (22,592,445 bytes, MIME `application/java-archive`, deployed 2026-07-01T08:40:27Z)
- `hostingstart.html` (3,269 bytes, MIME `text/html`, platform default landing page)

The `dir C:\home\site\wwwroot` output via `/api/command` matches (2 files, no hidden `web.config`). This is a definitive independent enumeration - the file is not present under any name in `wwwroot`.

**Consequence**: the effective `httpPlatformHandler` configuration - specifically its `requestTimeout` - is NOT authored by the customer via `wwwroot\web.config`. Since `/slow/{n}` cuts at 230 s (not the httpPlatformHandler documented 120 s default), the effective `requestTimeout` MUST be >= 230 s. It lives either in:

1. A platform-scoped `applicationHost.config` mounted into IIS above the customer wwwroot (candidate location: `C:\home\SiteExtensions\` or `C:\Program Files (x86)\SiteExtensions\`)
2. The IIS site-scoped `applicationHost.config` that Antares generates per site (candidate location: `C:\DWASFiles\Sites\<sitename>\Config\` or via Kudu console at `d:\home\sitextensions\`)
3. httpPlatformHandler defaults compiled into the module

**H4 (effective config drift) is UNRESOLVED at Stage 0 and MUST become a Lab 1 diagnostic.** Stage 0 cannot inspect these paths through `/api/vfs`.

Reference: [httpPlatformHandler configuration reference](https://learn.microsoft.com/en-us/iis/extensions/httpplatformhandler/httpplatformhandler-configuration-reference) - documented `requestTimeout` default is 00:02:00 (120 s).

### Q3: IDLE vs ABSOLUTE 230 s ceiling - **UNKNOWN, blocked by app-level defect**

`results/stream-probes.csv`:

| requested_s | http_code | client_time_s | curl_exit | bytes_received |
|---|---|---|---|---|
| 300 | 200 | 32.227 | 0 | 145 |

Expected for an IDLE-timeout front-end: 11 chunks over 300 s. Observed: 2 chunks over 32 s.

Server-side `AppServiceConsoleLogs` reveals the root cause is NOT the front-end:

```
09:15:35.028Z  INFO stream.start seconds=300 bounded=300 intervalSec=30
09:16:06.135Z  WARN stream.interrupted seconds=300 chunkIndex=2 elapsedMs=31106
```

`Stage0Application#stream()` uses Spring MVC `StreamingResponseBody`, which runs on an async request. **Spring Boot's default `spring.mvc.async.request-timeout` is 30 s** on Tomcat (Tomcat servlet container default). At ~31 s the async request timer fired, Spring interrupted the writer thread, `Thread.sleep(...)` threw `InterruptedException`, and the handler returned cleanly. Tomcat completed the response as HTTP 200 (2 chunks were successfully flushed before the interrupt).

This is a Java application defect masking the platform question, not a platform behavior. **Lab 1 MUST set `spring.mvc.async.request-timeout=-1` (or a value greater than 230 s) on the `/stream` endpoint before H7 can be answered.**

### Q4: Auto-Heal isolation - **CONFIRMED disabled**

Evidence from `results/az-webapp-config-show.json` and `results/az-webapp-appsettings.json` (verified by `--preflight`):

| Setting | Value | Interpretation |
|---|---|---|
| `siteConfig.autoHealEnabled` | `false` | Custom Auto-Heal off |
| `siteConfig.autoHealRules` | `null` | No triggers configured |
| `WEBSITE_PROACTIVE_AUTOHEAL_ENABLED` | `"false"` | Platform Proactive Auto-Heal off |
| `siteConfig.alwaysOn` | `true` | Worker not unloaded between probes |

**H4 (Oracle fatal flaw #4 - Proactive Auto-Heal preemption) resolved.** The 230 s cut cannot be attributed to any Auto-Heal recycle. Timing observations are attributable purely to the request-timeout path.

## Additional findings

### F1: "Orphan backend work" pattern confirmed

For every /slow/{n} with n > 230 s, the Java `Thread.sleep(n)` completed to full duration on the server, even though the client saw HTTP 500 at 230 s and IIS closed the request at TimeTaken=230000 ms.

| Endpoint | Java `slow.start` -> `slow.end` | Java elapsedMs | IIS TimeTaken | Client time |
|---|---|---|---|---|
| `/slow/240` | 09:00:05.379 -> 09:04:05.395 | 240016 | 230000 | 230.688 s |
| `/slow/300` | 09:04:15.234 -> 09:09:15.297 | 300063 | 230036 | 230.715 s |
| `/slow/360` | 09:09:25.081 -> 09:15:25.116 | 360034 | 230011 | 230.683 s |

The Spring handler receives no `InterruptedException`. `httpPlatformHandler` keeps the loopback IIS<->Java connection open for the full duration. Only the CLIENT-facing response is truncated at 230 s. The Java response bytes are discarded by IIS (the transaction is already closed).

**Operational implication**: on a Windows Java SE app under production load, timed-out requests continue to consume Java worker threads until the underlying business logic finishes. On B1 with 1 vCPU, a burst of long requests can drain Tomcat's thread pool even though clients see 500s. This is a Lab 2 concern (queue-depth-under-load) and directly motivates the loopback-saturation hypothesis.

### F2: Production symptom `500.121.64` vs baseline `500.121.0`

Production ticket: `HTTP 502 Bad Gateway` with sub-status `500.121.64`.
Stage 0 baseline: `HTTP 500` with sub-status `500.121.0` (ScStatus=500, ScSubStatus=121, ScWin32Status=0).

Two components of the discrepancy:

**Outer status (500 vs 502).** IIS records ScStatus=500. Production may see 502 because a fronting layer (ARR, Front Door, Application Gateway, or the App Service front-end itself) rewrites the IIS 500 to 502 Bad Gateway when the backend cannot be reached "correctly" from its perspective. The IIS sub-status (`121.win32`) is preserved through the rewrite.

**Win32 status (0 vs 64).** ScWin32Status is the OS-level socket error at the moment IIS finalizes the transaction:

- `0` = no OS error (this baseline). IIS cut the response cleanly on its own request-timeout counter.
- `64` = `ERROR_NETNAME_DELETED` (0x40). The socket to the peer (either the client or the loopback backend) was already torn down when IIS tried to write.

The `.64` win32 status implies race-condition connection drops, not a clean timer expiration. This pattern is expected to emerge under loopback saturation (many concurrent long requests exhausting the loopback connection pool between w3wp and java.exe), which is exactly Lab 2's hypothesis. **Baseline `.0` in Stage 0 validates the two-lab split**: Lab 1 confirms `500.121.121` signature without load; Lab 2 reproduces `500.121.64` under load.

### F3: SCM basic-auth default is disabled

`Microsoft.Web/sites/basicPublishingCredentialsPolicies@2023-12-01` name `scm` had `properties.allow = false` after initial Bicep deploy. All Kudu REST calls returned HTTP 401 until an out-of-band `az resource update ... --set properties.allow=true` was applied.

Azure changed the default early 2024 for security. **The `main.bicep` in this Stage has been updated to explicitly set `allow: true` on the SCM policy** so subsequent runs of `collect-effective-config.sh` succeed without manual intervention. FTP publishing remains disabled (`ftpsState: 'Disabled'`).

## Routing to Lab 1 (Decision matrix)

Observation matches Row 2 of the discovery matrix in `README.md`:

> Succeeds for all n up to ~230, cuts around 230 s for n > 230 + `wwwroot/web.config` absent -> Front-end 230 s dominates AND platform does not materialize `web.config` in wwwroot for Java SE. H1 confirmed, but H4 UNRESOLVED.

Lab 1 objectives derived from Stage 0:

| Ref | Lab 1 objective | Stage 0 basis |
|---|---|---|
| L1-O1 | Reproduce the 230.121.win32 signature under baseline (no load, no downstream). Measure win32 sub-status distribution over 10-20 iterations to confirm `.0` (vs occasional `.64` from network noise). | F2, Q1 |
| L1-O2 | Add H4 diagnostic: fetch site-scoped `applicationHost.config` and any platform-injected `web.config` outside wwwroot via Kudu console (`d:\home\sitextensions\` scan) and via `%WINDIR%\System32\inetsrv\config\applicationHost.config`. Correlate with the observed `requestTimeout >= 230 s`. | Q2 unresolved |
| L1-O3 | Answer Q3 (IDLE vs ABSOLUTE) after setting `spring.mvc.async.request-timeout=-1` on the `/stream` endpoint. Rerun `/stream/300`; if 11 chunks received: idle-reset; if cut around 230 s: absolute-duration. | F1 blocking, Q3 unresolved |
| L1-O4 | Investigate the client-facing outer status (500 vs 502). Compare direct-to-App-Service response with a request via a preview slot / traffic-manager / Front Door front-end if trivially available. | F2 |
| L1-O5 | Document the "orphan backend work" F1 pattern with dedicated console-log evidence. This becomes a callout in the final lab guide but does not require a separate experiment. | F1 |

Lab 1 does NOT introduce load. Lab 2 handles L1-O2 mitigation scenarios and the loopback-saturation reproduction that generates `500.121.64` win32=64.

## Cost accounting

Total wall time so far: deploy ~2 min + warm-up 1 min + preflight 1 min + probes 32 min + post-flight 2 min = ~38 min.

At B1 Basic Korea Central ($0.075/hour prorated for a single 1-hour billing unit) + Log Analytics ingestion (well under the 5 GB free tier for this single-day burst): **estimated $0.05-0.10 to date**, well within the sub-$0.50 Stage 0 budget.

## Follow-up (before Lab 1)

- [x] Update `main.bicep` to enable SCM basic-auth policy (`Microsoft.Web/sites/basicPublishingCredentialsPolicies` `scm` `allow: true`).
- [ ] Do NOT tear down the Stage 0 environment until Lab 1 is deployed. Lab 1 provisions a separate resource group and does not depend on Stage 0 infrastructure.
- [ ] Sanitized artifacts (subscription ID scrubbed to `<subscription-id>`) will be committed to `labs/windows-java-httpplatformhandler-timeout/artifacts-sanitized/stage-0/` at end of session.
