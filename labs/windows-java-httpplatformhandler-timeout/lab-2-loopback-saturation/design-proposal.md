# Lab 2 design proposal (post-Oracle-review revision 2)

Oracle verdict history (session `ses_0e29cc06fffeC21uAYAj7dym6h`):

- **Draft 1**: NEEDS-REWORK (9 blockers + 5 non-blocking recommendations)
- **Draft 2**: NEEDS-REWORK (8/9 blockers cleanly closed, all 5 recommendations addressed, 3 residual issues + 1 wording bug identified)

Draft 3 closes the 4 residual issues Oracle flagged in the Draft 2 re-review:

- **Residual A (Blocker 4 completion)**: E1 threshold KQL was aggregating a ~9-minute span (`E1_RUN_END_MINUS_5MIN .. E1_RUN_END_PLUS_DRAIN`) while the prose claimed "final 5-minute window". Fixed to aggregate exactly the last 5 minutes of the observation window (`E1_RUN_END_PLUS_DRAIN - 5min .. E1_RUN_END_PLUS_DRAIN`), which captures the completions of requests that were still arriving in the final minute of the arrivals period under sustained saturation.
- **Residual B (E2 sample-size unachievable)**: `total >= 1500` at 20 min × 1.05-1.20 req/s produces only 1260-1440 requests, so the run would appear to fail even when valid. Fixed to `total >= 0.9 × (arrival_rate_req_per_s × 1200)`, which is a rate-relative floor accounting for k6 `dropped_iterations` and Log Analytics ingest gaps.
- **Residual C (E4 unverifiable branch overstated)**: Draft 2's preflight-fail branch implied a recycle-effect verdict could still be drawn from HTTP-log trend alone. Fixed to explicitly mark both H4 branches (recycle-timing AND recycle-effect) as `[Unknown]` if preflight returns 0 rows, with any HTTP-log trend labeled `[Observed]` (not `[Correlated]` or `[Inferred]`) and the M2 mitigation verdict marked `unverifiable via CLI-only tooling`.
- **Wording D (E5 line 432)**: "Above 30% and H5 is not confirmed" was ambiguous. Fixed to unambiguously say "If `E5_pct_64 > 0.7 × E2_pct_64` (i.e. reduction below 30%), H5 is not confirmed".

The Draft 2 preamble (9 blockers + 5 recommendations from Draft 1) is preserved unchanged below; those items are already Oracle-verified as cleanly addressed except for Blocker 4, which Residual A completes.

---

Draft 2 applied all 9 blocking changes and all 5 non-blocking recommendations from Oracle Draft 1:

**Blocking (all applied)**:

1. **H1 rewritten** from a causal ("Tomcat thread pool exhaustion → `.64`") claim into an operational claim ("at arrival rates near or above estimated per-instance service capacity, `.64` appears").
2. **E1 restructured** from a single continuous ramp (which lets backlog carry across rate steps) into **independent per-rate runs** with full drain between each.
3. **Little's Law framing fixed**: hold time is **240 s** (backend continues after front-end cut), estimated per-instance service capacity is **~0.83 req/s** (200 threads / 240 s), so 1.0+ req/s is the overloaded region, not steady-state.
4. **Threshold definition tightened** to "final 5-minute window has `sc_500_121_64` >= 5 **AND** `pct_64` >= 1.0" (single-event trips at low rates are now rejected).
5. **All KQL queries fixed**: `AppServiceHTTPLogs.ScSubStatus` and `.ScWin32Status` are STRING columns and require `toint()`. Every query now also filters `_ResourceId == "<site-resource-id>"` to prevent cross-app noise if Log Analytics is ever shared.
6. **E4 Auto-Heal rule fully specified** with `subStatus: 121`, `win32Status: 64`, `path: '/slow/240'` so the rule only fires on the target signature. Timing claim rewritten: recycle window starts from the first eligible `.64` completion (~230 s after k6 start), not from scenario start.
7. **`AppServiceAppLogs` replaced with `AppServicePlatformLogs`** for Auto-Heal events (Windows Java SE does not emit into `AppServiceAppLogs`; that table is ASP.NET / Linux). A **preflight validation step** verifies events land in `AppServicePlatformLogs` before E4 runs; if not, E4 is marked **unverifiable** and reported as a platform observability finding.
8. **E3 hardened**: 3-5 probes with warm-up per probe (not `n=1`); Fallback B (`az webapp deployment source config-zip`) downgraded as deprecated; revert-between-experiments uses **baseline artifact redeploy** (not "empty `web.config`", which is not a valid revert primitive).
9. **New Pre-E1 baseline re-verification step** (3 serialized `/slow/240` probes) confirms `500/121/0 @ ~230 s` on the Lab 2 environment before any load runs, so any Lab 2 anomaly can be attributed to load rather than to plan-SKU or deployment-path drift.

**Non-blocking (all applied)**:

1. **`web.config` schema**: full `<httpPlatform>` element is the **primary** M1a canary; partial-override (`<httpPlatform requestTimeout="00:01:00" />` only) is a **secondary** canary if the full element deploys cleanly and the front-end still wins.
2. **k6 fidelity signals** captured per run: `dropped_iterations`, achieved arrival rate (`http_reqs / duration`), peak VUs, error counts. Any run where `dropped_iterations > 0` is either extended or re-run with higher `maxVUs`.
3. **E3 moved ahead of E2** in the recommended execution order (baseline-recheck → E1 → **E3** → E2 → E4 → E5) so the cheap deployment-path probe de-risks OneDeploy before the expensive E2 sustained run.
4. **Lab 1 references** in this Draft (e.g. path `../lab-1-baseline-signature/...`) point to files that exist in the working tree but are **not yet committed at Draft 2 time**; this is expected during the draft phase and will resolve when Lab 1 files land in the same PR series.
5. **E5 wording softened**: "scale-out halves the `.64` rate" was a strict-theorem claim that ignores load-balancer distribution variance. E5 is now framed as an **operational comparison** ("does scale-out materially reduce the `.64` rate at the same aggregate arrival rate?") with a documented tolerance.

## Goal

Reproduce and characterize the production `500.121.64` sub-status pattern under controlled concurrent open-model load, then validate two customer-authored mitigations:

- **M1a**: customer `web.config` with `httpPlatformHandler.requestTimeout = 00:01:00` (60 s) - test whether the handler timer becomes operative, or whether the front-end 230 s continues to dominate.
- **M2**: custom Auto-Heal rule scoped to the exact `500/121/64` signature on `/slow/240` - test whether Auto-Heal recycles a saturated worker fast enough to shorten the `.64` burst.

Provide statistical evidence of the arrival rate at which `.64` first appears at a defensible threshold. Establish measurement rigor for the final lab guide's "when this hits production" section.

**Non-goal**: Prove the mechanism behind `.64` (Tomcat thread pool exhaustion vs loopback ephemeral-port exhaustion vs httpPlatformHandler process pool vs GC pause). Lab 2 answers **at what load** the signature appears and **whether the two mitigations work**; the mechanism is deferred to a future lab if the mitigation verdicts warrant it.

## Scope

**IN**:

- Single Windows Java SE web app, **B1 Basic** SKU (1 vCPU, 1.75 GB). B1 supports manual scale-out to 3 instances, which is sufficient for optional E5. S1 is only needed if E5 required autoscale (not proposed here).
- Open-model load via k6 `constant-arrival-rate` executor from the operator's local machine. All E1 rate-search runs use one arrival rate per run (independent runs, not a continuous ramp).
- Reuse of the Lab 1 / Stage 0 JAR byte-identical (same `/slow/{n}` endpoint, same Spring Boot 3.3.4).
- ARM CLI + Log Analytics KQL only for diagnostics (Lab 1 confirmed Kudu inaccessibility under MCAPS).
- Two mitigation experiments (M1a `web.config`, M2 Auto-Heal).
- Baseline re-verification against Lab 2's plan SKU and deployment path before any load experiment runs.

**OUT**:

- Downstream service dependency (still deferred; adding one destroys `.64` attribution).
- VNet integration.
- Kudu-based diagnostics (Lab 1 L1-H3R falsified accessibility under MCAPS policy).
- Streaming mitigation (Lab 1 L1-H4 confirmed IIS/httpPlatformHandler does not stream backend chunks to the client on Windows Java SE).
- WAR / Tomcat container / JBoss (Java SE JAR only per repo scope).
- Alternate front-end path tests (Application Gateway, Front Door) - production `502` upstream attribution stands from Lab 1 L1-H5R.
- Cross-region / cross-tenant tests.
- Mechanism proof for `.64` (Tomcat thread pool vs loopback vs process pool vs GC).

## Hypotheses (all derived from Lab 1 findings + Oracle Draft 2 constraints)

Each hypothesis has an explicit falsification criterion measured against server-side Log Analytics data. Client k6 output is used for load-generation fidelity signals only, not as the primary measurement (Lab 1 F1 observation: client overhead ~0.68-0.72 s per request).

| ID | Hypothesis | Falsification |
|---|---|---|
| L2-H1 | At arrival rates near or above the estimated per-instance service capacity (**~0.83 req/s** = Spring Boot default `server.tomcat.threads.max=200` divided by 240 s backend hold time), the `500.121.64` sub-status appears at a nonzero rate under sustained open-model load; the same signature is absent from Lab 1's serialized (queue-depth-1) baseline. | E1's coarse per-rate runs at `{0.5, 0.75, 0.9, 1.05}` req/s all produce a final-5-minute window with `sc_500_121_64 < 5` AND `pct_64 < 1.0`. If falsified, `.64` is not reproducible under this load model on B1 and the lab must revisit either the load model or the SKU before proposing mitigations. |
| L2-H2 | Above the L2-H1 first-positive arrival rate, the `pct_64` measured in the final 5-minute window is **non-decreasing** when arrival rate is increased in independent runs (no shared backlog between runs). | Two adjacent above-threshold rates show `pct_64` decrease > 20% relative (higher rate has lower `pct_64`). Would indicate `.64` is driven by something other than sustained queue pressure and the mitigation recommendations must be re-scoped. |
| L2-H3 (M1a) | Deploying customer `web.config` with `<httpPlatform requestTimeout="00:01:00" />` (60 s) makes the handler-level timer operative, so serialized `/slow/240` probes cut at ~60 s server-side instead of ~230 s. | All 3-5 M1a probes still cut at ~230 s server-side (front-end wins) OR cut at some third value not near 60 s or 230 s. Both are useful findings: "customer `requestTimeout` is not honored on Windows Java SE" or "a third timer is present". |
| L2-H4 (M2) | Enabling a custom Auto-Heal rule scoped to `path=/slow/240, status=500, subStatus=121, win32Status=64, count=5, timeInterval=2min → Recycle` triggers a worker recycle within the 2-minute rolling window after the fifth eligible `.64` completion, and after recycle the `pct_64` measured over the next 5 minutes drops below 50% of the pre-recycle rate. | No recycle event in `AppServicePlatformLogs.OperationName startswith "AutoHealing"` within 5 minutes of the fifth eligible `.64`, OR recycle occurs but post-recycle `pct_64` does not drop below 50% of the pre-recycle rate. Would indicate rule tuning is needed or Recycle alone is insufficient. **If the preflight step confirms Auto-Heal events do not land in `AppServicePlatformLogs` at all on Windows Java SE, E4 is marked unverifiable.** |
| L2-H5 (optional) | Scaling from 1 instance to 2 instances at the same aggregate arrival rate materially reduces `pct_64` (target: at least 30% relative reduction, measured over the same-length window as the 1-instance run). | With 2 instances, `pct_64` does not drop by at least 30% relative. Would indicate `.64` is not reduced by per-instance concurrency dilution (e.g. all instances share a common bottleneck) and scale-out is not a mitigation. |

**H1 rationale** (Oracle-revised): The mechanism ("Tomcat thread pool exhaustion → loopback state confusion") is a hypothesis, not a fact. H1 now only claims a load threshold, not a mechanism. The `0.83 req/s` capacity estimate is `server.tomcat.threads.max` default of 200 (Spring Boot 3.3.4 `ServerProperties.Tomcat.Threads.max`) divided by 240 s backend hold (Lab 1: backend Java thread completes ~10 s after client cutoff at 230 s). Above 0.83 req/s, the queue must build; whether that build produces `.64` is what E1 measures.

**H2 rationale** (Oracle-revised): Monotonicity claim restricted to the above-threshold region only. Below-threshold runs may produce zero `.64` and comparing them to above-threshold rates is not a monotonicity test. Independent per-rate runs (Blocker 2) ensure no shared backlog contaminates the comparison.

**H3 rationale** (Oracle-revised): 3-5 serialized probes replace the Draft-1 single probe. The full `<httpPlatform>` element is the primary canary (Oracle recommendation 1); a partial override is the secondary canary, tested only if the primary deploys cleanly and the front-end still wins.

**H4 rationale** (Oracle-revised): Rule now scoped to the exact `.64` signature on `/slow/240` (Blocker 6), so unrelated 500s cannot false-trigger. Timing claim rewritten (Blocker 6): status-code triggers count **completed** requests, and the first eligible `.64` completes at ~230 s after k6 start, so the earliest possible recycle is `230 s + (time to accumulate 5 in a 2-min window)`. `AppServicePlatformLogs` replaces `AppServiceAppLogs` (Blocker 7). Preflight-validation step (Blocker 7) determines whether E4 is verifiable on Windows Java SE at all.

**H5 rationale (optional, Oracle-revised)**: Old wording ("halves the `.64` rate") was a strict theoretical claim (equal LB distribution + equal per-instance response). Real distribution variance and asymmetric warm-up make "halve" too strong. H5 is now an operational comparison with a 30% tolerance.

## Experiment design

### Pre-E1: Baseline re-verification (new mandatory step, Blocker 9)

**Objective**: Confirm that the Lab 2 environment (B1 Windows Java SE + OneDeploy JAR path + Lab 2 `main.bicep`) still produces the Lab 1 signature (`500/121/0 @ ~230 s`) before any load runs.

**Rationale**: Lab 2 changes vs Lab 1: plan SKU may be revisited on the same B1 (no SKU change) but the deployment path is now scripted independently, and any drift in warm-up behavior, JAR upload, or app-setting propagation would silently move the baseline. Distinguishing drift from load-attributed behavior requires a fresh baseline measurement on the Lab 2 environment.

**Execution**:

1. Deploy Lab 2 `main.bicep` (Auto-Heal disabled, Proactive Auto-Heal disabled, same appSettings as Lab 1 except `SPRING_MVC_ASYNC_REQUEST_TIMEOUT=600000` retained for symmetry).
2. Warm-up: `/actuator/health` poll + JIT settle (verbatim from Lab 1 `warm-up.sh`).
3. Fire 3 serialized `/slow/240` probes with **backend-completion + 10 s** pacing (verbatim from Lab 1 E1 pacing).
4. Wait 30 s buffer for Log Analytics ingest.
5. Query `AppServiceHTTPLogs` for the 3 probe rows.

**KQL** (baseline recheck):

```kusto
AppServiceHTTPLogs
| where _ResourceId == "<site-resource-id>"
| where TimeGenerated between (PRE_E1_START .. PRE_E1_END)
| where CsUriStem == "/slow/240"
| project TimeGenerated, TimeTaken, ScStatus, ScSubStatus, ScWin32Status
| order by TimeGenerated asc
```

**Success criteria** (all three must pass to proceed to E1):

- All 3 rows have `ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 0`.
- All 3 `TimeTaken` values are in `[229800, 230500]` ms (same tolerance as Lab 1 H1R).
- No `.64` on any of the 3 probes (baseline is `.0` only).

If any check fails, **STOP** the lab. The Lab 2 environment does not match Lab 1's baseline; investigate deployment drift before running any load experiment. Do not attribute any subsequent `.64` observation to load until baseline matches.

**Wall time**: 3 × 260 s = 13 min + 30 s buffer + KQL query = ~15 min.

**Cost**: negligible (part of the same B1 hour already provisioned).

### E1: Arrival-rate first-positive search (L2-H1, restructured per Blocker 2)

**Objective**: Find the lowest arrival rate at which the final 5-minute window of a sustained run satisfies `sc_500_121_64 >= 5 AND pct_64 >= 1.0` (Blocker 4 threshold).

**Load model**: k6 `constant-arrival-rate` executor. **One arrival rate per run, four independent runs**, with a **full drain** between runs (no shared backlog).

| Run | Target arrival rate | Duration | Full-drain wait after k6 stops |
|---|---|---|---|
| E1-R1 | 0.5 req/s | 15 min | 4 min (240 s backend hold + 60 s Log Analytics ingest buffer) |
| E1-R2 | 0.75 req/s | 15 min | 4 min |
| E1-R3 | 0.9 req/s | 15 min | 4 min |
| E1-R4 | 1.05 req/s | 15 min | 4 min |

Rate rationale: estimated per-instance capacity is ~0.83 req/s. The four coarse rates bracket that capacity: 0.5 and 0.75 are below-capacity, 0.9 is just above, 1.05 is comfortably above. If the first-positive rate falls between two coarse rates, **one refinement run** is executed at the midpoint (e.g. 0.825 req/s if E1-R2 negative and E1-R3 positive). Total wall time cap: 5 runs × (15 + 4) min = 95 min.

k6 configuration per run:

```javascript
export const options = {
  scenarios: {
    slow: {
      executor: 'constant-arrival-rate',
      rate: RATE,           // e.g. 0.5, one per second
      timeUnit: '1s',
      duration: '15m',
      preAllocatedVUs: 300,
      maxVUs: 500,
    },
  },
};
```

`maxVUs=500` handles the peak in-flight count at 1.05 req/s × 240 s hold = 252 concurrent, plus 2x margin for k6's VU-recycling latency.

**k6 fidelity signals** (Oracle recommendation 2) captured per run and written to `results/e1-run-<n>-k6-summary.json`:

- `iterations` (total requests started)
- `dropped_iterations` (requests k6 could not start on time - MUST be 0; otherwise the achieved arrival rate is below target and the run is re-run with higher `maxVUs`)
- `http_reqs` and derived `achieved_rate = http_reqs / duration`
- `vus_max` observed
- `http_req_failed` count (should equal expected 500 count on above-threshold runs)

**KQL post-analysis** per run (Blocker 5: `toint()` on STRING columns + `_ResourceId` filter):

```kusto
AppServiceHTTPLogs
| where _ResourceId == "<site-resource-id>"
| where TimeGenerated between (E1_RUN_START .. E1_RUN_END_PLUS_DRAIN)
| where CsUriStem == "/slow/240"
| summarize
    total = count(),
    sc_500_121_0 = countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 0),
    sc_500_121_64 = countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64),
    sc_other = countif(not(ScStatus == 500 and toint(ScSubStatus) == 121)),
    pct_64 = round(100.0 * countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64) / count(), 2)
    by bin(TimeGenerated, 1m)
| order by TimeGenerated asc
```

**Threshold evaluation** (Blocker 4, Residual A): the aggregation window is the **final 5 minutes of the observation window** (i.e. the last minute of arrivals plus the first 4 minutes of drain, `E1_RUN_END_PLUS_DRAIN - 5min .. E1_RUN_END_PLUS_DRAIN`). Given the 240 s backend hold and the ~230 s front-end cut, this window captures completions from requests that were still arriving in the final minute of the 15-minute arrivals period under sustained saturation. Total span is exactly 5 minutes, not ~9 minutes (Draft 2's `E1_RUN_END_MINUS_5MIN .. E1_RUN_END_PLUS_DRAIN` window mixed arrivals-period bins with drain-period bins and was ~9 min wide, which Oracle flagged in Draft 2 re-review).

```kusto
AppServiceHTTPLogs
| where _ResourceId == "<site-resource-id>"
| where TimeGenerated between (E1_RUN_END_PLUS_DRAIN - 5min .. E1_RUN_END_PLUS_DRAIN)
| where CsUriStem == "/slow/240"
| summarize
    total = count(),
    sc_500_121_64 = countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64),
    pct_64 = round(100.0 * countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64) / count(), 2)
```

A run is a **positive** if `sc_500_121_64 >= 5 AND pct_64 >= 1.0`.

**Success criteria**:

- L2-H1: at least one of the four coarse E1 runs is positive.
- L2-H2: for the above-threshold runs, `pct_64` is non-decreasing when ordered by arrival rate (allowing 20% relative tolerance per Draft 1).

### E3: M1a customer `web.config` requestTimeout (L2-H3, moved before E2 per Oracle recommendation 3)

**Objective**: Deploy a customer `web.config` with `<httpPlatform requestTimeout="00:01:00" />` (60 s) and observe whether serialized `/slow/240` probes cut at ~60 s (handler wins) or ~230 s (front-end wins).

**Why before E2**: E3 is cheap (~20 min including deploy + warm-up + probes) and tests a deployment path (OneDeploy for a static `web.config`) that also affects later scripting. Discovering an OneDeploy failure at E3 is much cheaper than discovering it after E2's 20-minute sustained run.

**Deployment method** (primary): `az webapp deploy --type static --target-path web.config --src-path ./webconfig/web.config`. OneDeploy authenticates with the ARM Entra token (`az account get-access-token`), bypassing the MCAPS policy that blocks Kudu basic auth. Confirmed by Microsoft Learn "Deploy authentication types" documentation.

**Fallback A** (if OneDeploy `--type static` fails): `az webapp deploy --type zip` with a ZIP containing both `app.jar` and `web.config` at wwwroot level. Also ARM-authenticated.

**Fallback B** (deprecated, last resort): `az webapp deployment source config-zip`. This path is deprecated per Microsoft Learn; use only if Fallbacks OneDeploy and ZIP both fail. Document the deprecation warning if used.

**Fallback C** (final): Skip E3, document the deployment inaccessibility as an additional platform limitation finding.

**`web.config` canaries** (Oracle recommendation 1: full element primary, partial override secondary):

*Primary canary* (`webconfig/web.config`, full element):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="httpPlatformHandler" path="*" verb="*" modules="httpPlatformHandler" resourceType="Unspecified" />
    </handlers>
    <httpPlatform processPath="%JAVA_HOME%\bin\java.exe"
                  arguments="-jar &quot;%HOME%\site\wwwroot\app.jar&quot; --server.port=%HTTP_PLATFORM_PORT%"
                  stdoutLogEnabled="true"
                  stdoutLogFile="%HOME%\LogFiles\httpPlatform\stdout"
                  startupTimeLimit="60"
                  requestTimeout="00:01:00">
      <environmentVariables>
        <environmentVariable name="PORT" value="%HTTP_PLATFORM_PORT%" />
      </environmentVariables>
    </httpPlatform>
  </system.webServer>
</configuration>
```

*Secondary canary* (`webconfig/web.config.partial`, only used if primary deploys cleanly and the front-end still wins - to differentiate "handler config overridden entirely" from "requestTimeout attribute alone not honored"):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <httpPlatform requestTimeout="00:01:00" />
  </system.webServer>
</configuration>
```

Note on `requestTimeout` default: httpPlatformHandler's documented default is `00:02:00` (2 minutes = 120 s) per the IIS reference. Lab 1 saw 230 s cuts, indicating the front-end wins over the 120 s default. M1a lowers `requestTimeout` to 60 s; if honored, cuts should shift from 230 s to 60 s (dramatic, unambiguous).

**Execution** (3-5 probes per canary, Blocker 8):

1. Deploy `webconfig/web.config` (primary canary) via OneDeploy.
2. Warm-up: `/actuator/health` poll (5-10 attempts, one per second) to confirm the Java process is up after the web.config-induced restart.
3. Fire 3 serialized `/slow/240` probes with **backend-completion + 10 s** pacing (identical to Lab 1 E1 pacing).
4. If all 3 probes cut at ~60 s → H3 confirmed with n=3, stop.
5. If all 3 probes cut at ~230 s → H3 falsified for the primary canary. Deploy secondary canary (`webconfig/web.config.partial`) and re-run 3 probes to distinguish "config not honored" from "full element replaces platform-injected handler entirely with a bad definition".
6. If probes cut at any other value (e.g. 120 s), extend to 5 probes on the current canary and flag as H3 ambiguous.
7. After E3 completes, **revert to baseline** (Blocker 8) by redeploying the known-good baseline artifact (either the deployment ZIP used in Pre-E1, or `az webapp deploy --type jar --src-path app.jar` targeting `%HOME%\site\wwwroot\app.jar` without the `web.config`). "Empty `web.config`" is not a valid revert because it may still register an empty handler element and shadow the platform's default; a full baseline redeploy is the only reliable revert.

**KQL** (per probe):

```kusto
AppServiceHTTPLogs
| where _ResourceId == "<site-resource-id>"
| where TimeGenerated between (E3_PROBE_START .. E3_PROBE_END_PLUS_BUFFER)
| where CsUriStem == "/slow/240"
| project TimeGenerated, TimeTaken, ScStatus, ScSubStatus, ScWin32Status
| order by TimeGenerated asc
```

**Success criteria** (H3 confirmed if any single outcome holds for all 3 primary-canary probes):

| Primary-canary outcome (3 probes) | Interpretation |
|---|---|
| All 3 have `TimeTaken ≈ 60000 ms` (tolerance ±2 s) and `500/121/*` | H3 confirmed: customer `requestTimeout` is operative on Windows Java SE. **M1a is a valid mitigation.** |
| All 3 have `TimeTaken ≈ 230000 ms` and `500/121/0` (Lab 1 baseline) | H3 falsified for primary canary. **Deploy secondary canary and re-test.** If secondary also cuts at 230 s: M1a not viable via customer `web.config` on this stack. |
| Any other value (e.g. 120 s, or non-`500/121` status) | H3 ambiguous. Extend to 5 probes; document; revisit before writing lab guide. |

### E2: Sustained saturation characterization (L2-H2 continued)

**Objective**: At an above-threshold arrival rate (`E1_first_positive_rate + 0.15 req/s`, or the next coarse tick above), run a longer sustained load to compute stable `pct_64` and `TimeTaken` percentiles.

**Load model**: k6 `constant-arrival-rate` at chosen rate, 20 min duration + 4 min drain.

**k6 fidelity signals**: same as E1 (Oracle recommendation 2). If `dropped_iterations > 0`, re-run with `maxVUs=800`.

**KQL post-analysis**:

```kusto
AppServiceHTTPLogs
| where _ResourceId == "<site-resource-id>"
| where TimeGenerated between (E2_START .. E2_END_PLUS_DRAIN)
| where CsUriStem == "/slow/240"
| summarize
    total = count(),
    sc_500_121_0 = countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 0),
    sc_500_121_64 = countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64),
    other = countif(not(ScStatus == 500 and toint(ScSubStatus) == 121)),
    pct_64 = round(100.0 * countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64) / count(), 2),
    time_taken_p50 = percentile(TimeTaken, 50),
    time_taken_p95 = percentile(TimeTaken, 95),
    time_taken_p99 = percentile(TimeTaken, 99)
```

**Success criteria** (Residual B):

- **Sample-size floor (rate-relative)**: `total >= 0.9 × (arrival_rate_req_per_s × 1200)` requests, i.e. at least 90% of expected arrivals over the 20-minute duration. This accounts for k6 `dropped_iterations` and Log Analytics ingest gaps. Draft 2's fixed `total >= 1500` was unachievable at the proposed above-threshold rates (`1.05-1.20 req/s × 1200 s = 1260-1440 total`), which would have caused valid runs to fail the criterion.
- **`pct_64` characterization value**: aggregated over the **final 5-minute window** of the observation using the same tail-window pattern as E1's threshold evaluation (Residual A), for direct comparability with E1:

    ```kusto
    AppServiceHTTPLogs
    | where _ResourceId == "<site-resource-id>"
    | where TimeGenerated between (E2_END_PLUS_DRAIN - 5min .. E2_END_PLUS_DRAIN)
    | where CsUriStem == "/slow/240"
    | summarize
        total_final_5min = count(),
        sc_500_121_64_final_5min = countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64),
        pct_64_final_5min = round(100.0 * countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64) / count(), 2)
    ```

    The full-window KQL above remains the source for `total` (sample-size check), `TimeTaken` percentiles, and the non-`121` status breakdown; the final-5-min block above supplies the E2 `pct_64` characterization value that is compared against E1 positives and against E4/E5.

### E4: M2 custom Auto-Heal recycle rule (L2-H4)

**Objective**: With M1a NOT applied (baseline reverted after E3), enable a custom Auto-Heal rule scoped to the exact `.64` signature and re-run E2's sustained load. Observe whether Auto-Heal recycles the worker within a useful timeframe and whether recycling breaks the `.64` burst.

**Preflight validation step** (Blocker 7, MANDATORY before E4):

Windows Java SE may not emit Auto-Heal events into `AppServicePlatformLogs`. This must be verified before E4, because if events do not land, the recycle-effect measurement has no server-side source of truth and E4 becomes unverifiable.

Preflight procedure:

1. Redeploy `main.bicep` with a **harmless** Auto-Heal rule: same status-code trigger BUT `actionType: 'LogEvent'` (not `Recycle`). LogEvent writes a platform log entry without disrupting the running process.
2. Fire 5 serialized `/slow/240` probes to accumulate 5 eligible `.64` completions **IF E1 confirmed 5 or more `.64` in a 5-minute window**. If E1 did not produce `.64` at a rate that would trip the rule during preflight, temporarily lower the trigger `count` to `1` and fire a single request that produces a `500/121/*` completion (any sub-status), just to verify the platform emits the event.
3. Wait 3 min + 60 s Log Analytics buffer.
4. Query `AppServicePlatformLogs`:

    ```kusto
    AppServicePlatformLogs
    | where _ResourceId == "<site-resource-id>"
    | where TimeGenerated between (PREFLIGHT_START .. PREFLIGHT_END)
    | where OperationName startswith "AutoHealing"
    | project TimeGenerated, OperationName, Level, Message
    | order by TimeGenerated asc
    ```

5. Interpretation:

    - **≥1 row returned**: `AppServicePlatformLogs` surfaces Auto-Heal events on Windows Java SE. Proceed to E4 with confidence in the recycle-event measurement.
    - **0 rows returned** (Residual C): `AppServicePlatformLogs` does NOT surface Auto-Heal events for this SKU/stack. **E4 is marked unverifiable end-to-end**: both H4 branches (recycle-timing AND recycle-effect) require a server-side recycle event anchor to attribute HTTP-log changes to Auto-Heal. Without that anchor, any observed `pct_64` trend is descriptive of the run, not attributable to Auto-Heal. Still run E4 to record the HTTP-log `pct_64` trend as an observational data point (labeled `[Observed]` per AGENTS.md evidence labels, NOT `[Correlated]` or `[Inferred]`), and mark the M2 mitigation verdict as `unverifiable via CLI-only tooling` in the lab guide. External evidence (App Service Diagnostics blade, portal Auto-Heal history, process restart telemetry) is required to close the verdict but is out of Lab 2's CLI-only scope under MCAPS.

**E4 Auto-Heal rule** (Blocker 6, fully-specified rule scoped to `.64` on `/slow/240`):

```bicep
siteConfig: {
  autoHealEnabled: true
  autoHealRules: {
    triggers: {
      statusCodes: [
        {
          status: 500
          subStatus: 121
          win32Status: 64
          path: '/slow/240'
          count: 5
          timeInterval: '00:02:00'
        }
      ]
    }
    actions: {
      actionType: 'Recycle'
      minProcessExecutionTime: '00:01:00'
    }
  }
  appSettings: [
    // Keep Proactive Auto-Heal disabled so only the custom rule fires
    { name: 'WEBSITE_PROACTIVE_AUTOHEAL_ENABLED', value: 'false' }
    // ... rest unchanged from Pre-E1 baseline
  ]
}
```

Rule-timing note (Blocker 6): status-code triggers count **completed** requests. The first eligible `.64` cannot complete until ~230 s after k6 start. Once 5 eligible `.64` accumulate within any rolling 2-minute window, the rule fires and Recycle begins. Draft 1's "recycle within 3 min of E4 start" claim was unphysical (there are no completed requests to count in the first 230 s); the corrected earliest recycle time is `~230 s + (time for 5 .64 to accumulate within a 2-min sliding window)`.

**Execution** (assuming preflight passed):

1. Redeploy `main.bicep` with `enableCustomAutoHeal=true` (the real rule with `actionType: 'Recycle'`).
2. Verify: `az webapp config show --query siteConfig.autoHealEnabled` returns `true`; `az webapp config show --query siteConfig.autoHealRules` shows the fully-scoped rule.
3. Warm-up: `/actuator/health` poll after Bicep redeploy triggers a restart.
4. Fire k6 with the E2 arrival rate.
5. Duration: 20 min (matches E2 so pre-recycle rate is comparable).
6. Drain: 4 min after k6 stops.

**KQL post-analysis** (Blocker 7: `AppServicePlatformLogs`, not `AppServiceAppLogs`):

Recycle event timeline:

```kusto
AppServicePlatformLogs
| where _ResourceId == "<site-resource-id>"
| where TimeGenerated between (E4_START .. E4_END_PLUS_DRAIN)
| where OperationName startswith "AutoHealing"
| project TimeGenerated, OperationName, Level, Message
| order by TimeGenerated asc
```

`.64` rate before and after each recycle (30-second bins for higher resolution):

```kusto
AppServiceHTTPLogs
| where _ResourceId == "<site-resource-id>"
| where TimeGenerated between (E4_START .. E4_END_PLUS_DRAIN)
| where CsUriStem == "/slow/240"
| summarize
    total = count(),
    sc_500_121_64 = countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64),
    pct_64 = round(100.0 * countif(ScStatus == 500 and toint(ScSubStatus) == 121 and toint(ScWin32Status) == 64) / count(), 2)
    by bin(TimeGenerated, 30s)
| order by TimeGenerated asc
```

**Success criteria** (Residual C: **both criteria require preflight-confirmed platform log emission**):

- H4 recycle-timing: at least one `AutoHealing` event in `AppServicePlatformLogs` after the 5th eligible `.64` completes (i.e. after `~230 s + accumulation time`).
- H4 recycle-effect: `pct_64` measured over any 5-minute window after a recycle drops below 50% of the pre-recycle 5-minute-window `pct_64`.

**Preflight-fail branch (Residual C)**: If the E4 preflight returned 0 rows in `AppServicePlatformLogs`, **both criteria are marked `[Unknown]`** per AGENTS.md evidence labels (not `[Correlated]`, not `[Inferred]`), the M2 mitigation verdict is `unverifiable via CLI-only tooling`, and the HTTP-log `pct_64` trend from the E4 run is reported as `[Observed]` only — a descriptive data point about the run, not evidence of recycle effect. Attribution of any client-side trend to Auto-Heal requires the server-side recycle event anchor that preflight established as absent on this SKU/stack; without that anchor, the recycle-effect criterion has no verifiable causal link between recycle and `pct_64` change even if the trend is directionally favorable.

### E5: Scale-out mitigation (L2-H5) - OPTIONAL

**Skip unless E1-E4 leave time and budget headroom.** E5 scales the plan from 1 to 2 instances at the E2 arrival rate.

**B1 scale-out**: B1 Basic supports manual scale-out to up to 3 instances. No SKU change needed.

**Deployment**: `az appservice plan update --name <plan> --resource-group <rg> --number-of-workers 2` (or Bicep `capacity: 2` on the same plan resource).

**Execution**:

1. Scale plan to 2 instances.
2. Wait for both instances to warm (check `az webapp instance list` returns 2 healthy IDs).
3. Warm-up: `/actuator/health` × 20 to increase odds of hitting each instance (round-robin LB).
4. Fire k6 with the E2 arrival rate.
5. Duration: 20 min (matches E2).
6. Drain: 4 min.

**KQL** (same as E2 but summarized across both instances via `AppServiceHTTPLogs`; per-instance breakdown available via `Computer` or `_ResourceId` if surfaced).

**Success criteria** (Oracle recommendation 5, softened wording; Wording D clarified): E5 `pct_64` **materially** lower than E2 `pct_64`. Threshold: at least 30% relative reduction (`E5_pct_64 <= 0.7 × E2_pct_64`). **If `E5_pct_64 > 0.7 × E2_pct_64` (i.e. reduction below 30%), H5 is not confirmed** (scale-out did not materially reduce `.64` at this arrival rate).

**Cost impact**: adds 1 extra instance-hour × instance rate for the E5 window (~30 min including drain).

## Priority ranking (Oracle-approved new order)

If wall time or budget forces dropping experiments:

1. **Pre-E1 baseline re-verification** (mandatory, cheap, non-negotiable - Blocker 9).
2. **E1** (highest information value) - the `.64` first-positive arrival rate unlocks E2, E3, E4 rate/timing decisions.
3. **E3** (cheap; de-risks OneDeploy path before expensive E4 Bicep redeploy) - Oracle recommendation 3.
4. **E2** - stable characterization at chosen above-threshold rate.
5. **E4** - requires preflight + Bicep redeploy + longer k6 run. Higher wall-time cost; may be marked unverifiable by preflight.
6. **E5** - optional, drop first.

Recommended execution order: **Pre-E1 → E1 → E3 → E2 → E4 → (E5)**.

## Bicep changes vs Lab 1

- **Plan SKU**: **B1 Basic** (unchanged from Lab 1). B1 supports manual scale-out to 3 instances - sufficient for optional E5. S1 is only needed if E5 required autoscale (not proposed).
- **Web app**: unchanged except for E4 (parameter toggle `enableCustomAutoHeal: true` adds the fully-scoped Auto-Heal rule) and E4 preflight (harmless `actionType: 'LogEvent'` variant, temporary).
- **App settings**: retain `SPRING_MVC_ASYNC_REQUEST_TIMEOUT = 600000` from Lab 1 (E1/E2 use `/slow/240`, not `/stream/*`, so this setting is harmless but keeps Bicep symmetrical with Lab 1). Keep `WEBSITE_PROACTIVE_AUTOHEAL_ENABLED = false` for the entire lab.
- **Diagnostic settings**: unchanged (same 4 log categories to Log Analytics), **and add `AppServicePlatformLogs` to the diagnostic setting** if not already present in Lab 1's diagnostic configuration - required for E4 preflight and Auto-Heal event visibility.
- **SCM basic auth**: unchanged (`allow: true`). Lab 1 proved it does not grant access under MCAPS, but leaving it consistent avoids Bicep drift.
- **No** downstream service, no VNet, no custom domain, no App Service certificate.

Proposed Bicep parameter set:

```bicep
@description('Base name used to build uniquely named Lab 2 resources.')
param baseName string

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Spring MVC async request timeout in milliseconds. Preserved from Lab 1 for symmetry; not used by /slow endpoint.')
param springMvcAsyncRequestTimeoutMs int = 600000

@description('Enable custom Auto-Heal rule. Toggle to true for E4 redeploy. Default false for Pre-E1 baseline.')
param enableCustomAutoHeal bool = false

@description('Auto-Heal action type. Set to LogEvent for E4 preflight (harmless), Recycle for E4 main run.')
@allowed(['LogEvent', 'Recycle'])
param autoHealActionType string = 'Recycle'

@description('Number of App Service Plan instances. Set to 2 for optional E5.')
param planInstanceCount int = 1
```

## Application changes

**Reuse the Lab 1 / Stage 0 JAR byte-identical.** No `application.properties` change, no new endpoint, no logging change. All Lab 2 test behavior is driven by:

- k6 arrival-rate configuration (client-side, not in JAR).
- App-setting / Bicep-parameter toggles (`enableCustomAutoHeal`, `autoHealActionType`, `planInstanceCount`).
- Optional `web.config` file (E3 only, deployed separately as a static file via OneDeploy).

Rationale: same binary across Stage 0, Lab 1, Lab 2 preserves the Stage 0 → Lab 1 → Lab 2 comparison chain. Any behavioral difference is attributable to load, configuration, or platform mitigation - not to code drift.

## Script design

| Script | Purpose | Notes |
|---|---|---|
| `deploy.sh` | Fresh RG, deploy `main.bicep` (Auto-Heal disabled), build+upload Stage 0 JAR | Reuse Lab 1 `deploy.sh` structure. Preflight isolation check retained. |
| `warm-up.sh` | `/actuator/health` poll + JIT settle | Verbatim copy of Lab 1 `warm-up.sh`. |
| `run-baseline-recheck.sh` | 3 serialized `/slow/240` probes + KQL verification | **NEW** (Blocker 9). Same pacing as Lab 1 E1. Blocks the lab if baseline drifts. |
| `run-e1-per-rate.sh` | Independent per-rate constant-arrival-rate runs with full drain between runs | **NEW** (Blocker 2). Takes `--rate <r>` and `--run-id <n>`. Writes k6 fidelity signals to `results/e1-run-<n>-k6-summary.json`. |
| `deploy-webconfig-m1a.sh` | OneDeploy customer `web.config` as static file | Uses `az webapp deploy --type static`. Fallback A (ZIP) and B (deprecated config-zip) implemented but Fallback C (skip) documented. |
| `run-e3-m1a-probes.sh` | 3-5 serialized probes with primary canary; auto-escalates to secondary canary if primary fails | **REWRITTEN** (Blocker 8: n>=3, not n=1). Same `/slow/240` + backend-completion + 10 s pacing as Lab 1. |
| `revert-baseline-artifact.sh` | Redeploys known-good baseline JAR (without `web.config`) between E3 and E4 | **NEW** (Blocker 8). Not "empty web.config"; a full baseline redeploy. |
| `preflight-platform-logs.sh` | E4 preflight: deploy harmless `actionType: 'LogEvent'` variant, fire dummy trigger, verify events land in `AppServicePlatformLogs` | **NEW** (Blocker 7). Marks E4 unverifiable if events do not land. |
| `enable-autoheal-m2.sh` | Redeploy `main.bicep` with `enableCustomAutoHeal=true, autoHealActionType='Recycle'` | Fast redeploy, no JAR upload. |
| `run-e2-sustained.sh` | 20 min constant-arrival-rate at chosen above-threshold rate | k6 fidelity signals captured. |
| `run-e4-m2-autoheal.sh` | 20 min constant-arrival-rate with fully-scoped Auto-Heal enabled | Same duration as E2 for direct comparison. |
| `run-e5-scaleout.sh` (optional) | Scale plan to 2 instances via `az appservice plan update`, warm-up both, re-run E2 k6 | Conditional on E1-E4 completing under budget. |
| `collect-effective-config.sh` | Post-flight ARM CLI dump (webapp config, appSettings, plan, autoHealRules) | Reuse Lab 1 version; drop Kudu attempts entirely (Lab 1 proved they fail under MCAPS). |
| `verify.sh` | Run all KQL queries with `_ResourceId` filter, compute statistics, render `verify-report.md` | Per-experiment sections. Adaptive: skips E5 sections if E5 not run. Marks E4 recycle-timing as unverifiable if preflight failed. |
| `cleanup.sh` | `az group delete` | Same as Lab 1. |

Directory layout:

```
lab-2-loopback-saturation/
├── design-proposal.md                    # This file
├── README.md                             # (pending, gated on Oracle Draft 2 approval)
├── main.bicep                            # B1 with parameter toggles
├── deploy.sh
├── warm-up.sh
├── run-baseline-recheck.sh
├── run-e1-per-rate.sh
├── deploy-webconfig-m1a.sh
├── run-e3-m1a-probes.sh
├── revert-baseline-artifact.sh
├── preflight-platform-logs.sh
├── enable-autoheal-m2.sh
├── run-e2-sustained.sh
├── run-e4-m2-autoheal.sh
├── run-e5-scaleout.sh                    # optional
├── collect-effective-config.sh
├── verify.sh
├── cleanup.sh
├── k6/
│   ├── constant-arrival.js               # single rate per run (E1/E2/E4/E5)
│   └── lib.js                            # shared base URL, endpoint, thresholds
└── webconfig/
    ├── web.config                        # primary canary: full element, requestTimeout 00:01:00
    └── web.config.partial                # secondary canary: partial override only
```

**Prerequisite additions vs Lab 1**:

- k6 installed locally (`brew install k6` or equivalent). `deploy.sh` checks for `k6 version` and fails early if missing.

## Expected wall time

| Step | Time |
|---|---|
| Deploy + warm-up + preflight isolation | 6 min (same as Lab 1) |
| Pre-E1 baseline re-verification (3 probes × ~260 s + KQL) | 15 min |
| E1 coarse per-rate runs (4 runs × 19 min each) | 76 min |
| E1 refinement run (1 midpoint if needed) | 19 min |
| E3 M1a: OneDeploy + warm-up + 3 primary probes + (conditional) 3 secondary probes + revert | 25 min (worst case with secondary canary + revert) |
| E2 sustained saturation (20 min + 4 min drain) | 24 min |
| E4 preflight (LogEvent variant + dummy trigger + KQL verify) | 12 min |
| E4 M2 Auto-Heal (Bicep redeploy + warm-up + 20 min + 4 min drain) | 30 min |
| E5 (optional) scale-out + warm-up + 20 min + 4 min drain | 30 min |
| Post-flight collect + verify | 10 min |
| **Total (Pre-E1 through E4, no E5)** | **~217 min (~3 h 40 min)** |
| **Total (with E5)** | **~247 min (~4 h 10 min)** |

Wall time increased vs Draft 1 (Draft 1 estimated 158 min) because:

- Pre-E1 baseline re-verification added (15 min, Blocker 9).
- E1 now four independent runs with full drain (Blocker 2), each with 4 min drain instead of shared ramp.
- E3 now 3-5 probes with revert (Blocker 8), not single probe.
- E4 now includes preflight (Blocker 7).

## Cost estimate

**Formula-based**, not hardcoded (Oracle Blocker 8 non-negotiable: "Do NOT publish `$0.26` as-is. Publish a formula plus 'verify current regional price sheet before execution.'").

Given `B1_HOURLY = <verify from Azure regional price sheet at execution time for the target region>`:

- **Pre-E1 through E4** (~217 min): `217 / 60 × B1_HOURLY`
- **With E5** (~247 min, of which E5 adds a second instance for ~30 min): `247 / 60 × B1_HOURLY + 30 / 60 × B1_HOURLY = 277 / 60 × B1_HOURLY`

Reference indicative value (**subject to change; verify at execution**): Azure Pricing Calculator historical B1 Windows rate in most regions has been ~$0.075/hour, which would put E1-E4 at ~$0.27 and E1-E5 at ~$0.35. These are **indicative only**; the operator MUST verify the current rate for the target region before running the lab and update the cost table in `verify-report.md`.

- Log Analytics ingestion: ~50-150 MB (E1/E2/E4 generate more rows than Draft 1 due to longer E1 with 4-5 runs). Under free-tier daily cap (5 GB/day).
- **Budget cap**: `$2.00` (safety margin for one full re-run if any experiment needs redo).

## Risks and open questions (updated vs Draft 1)

Draft 1 open questions 1, 4, 6, and the schema/deployment questions have been resolved by Oracle. Remaining risks:

1. **Preflight step fails for E4** (Blocker 7 branch): if `AppServicePlatformLogs` does not surface Auto-Heal events for Windows Java SE on this subscription/tenant, E4's recycle-timing criterion is unverifiable. E4 still runs to measure client-side `pct_64` effect, but the "did Auto-Heal actually recycle" question requires either portal Auto-Heal history (out of Lab 2 CLI-only scope) or a follow-up lab with Kudu/RDP access (also out of scope under MCAPS).

2. **k6 client-side location** (from Draft 1): if the operator runs k6 from outside Korea Central (Lab 1 F1 observation ~0.71 s client overhead), the k6-side arrival-rate scheduler is still accurate (open model), but individual response times see network jitter. Server-side KQL remains source of truth. Consider running k6 from an Azure VM in Korea Central for high-fidelity E1 data if E1 first-positive rate is ambiguous.

3. **Auto-Heal recycle causing k6 to fail its VU pool** (from Draft 1): when a worker recycles mid-request, k6's in-flight VUs receive TCP RST. k6 `dropped_iterations` and `http_req_failed` should surface this. If `dropped_iterations > 0` in E4, extend `maxVUs=800` and re-run.

4. **httpPlatformHandler `processesPerApplication`** (from Draft 1, not proposed for Lab 2): default is 1 process per site instance. If M1a `web.config` also affects `processesPerApplication` (unintentional side effect of writing a full handler element), E3 outcomes may reflect a process-pool change rather than a `requestTimeout` change. The primary canary explicitly does not set `processesPerApplication`, leaving it at the platform default; the secondary canary (partial override) is safer if the primary produces anomalies.

5. **Baseline re-verification failure attribution**: if Pre-E1 fails (baseline drifts from Lab 1), the failure could be transient (Log Analytics ingest lag, JAR upload race) or genuine (SKU-specific behavior, deployment-path drift). Rerun once; if still fails, revisit deployment path before continuing.

## Deferred to future labs / final lab guide

- Downstream service dependency and its interaction with `.64` (Lab 3 scope, not yet planned).
- VNet integration and its interaction with front-end timers (Lab 3 scope).
- WAR / Tomcat container comparison to Java SE (out of scope per repo README).
- Production incident-response runbook (final lab guide section, not a separate lab).
- Mechanism proof for `.64` (Tomcat thread pool exhaustion vs loopback ephemeral-port exhaustion vs process pool vs GC pause) - Lab 2 measures the load threshold and mitigation efficacy only.

## Open questions carried forward to lab guide authoring

- Does `.64` rate correlate with GC pauses? Requires GC logging enabled and cross-correlation with `AppServiceConsoleLogs` GC output. Not a Lab 2 hypothesis but worth noting during E2/E4 result review.
- Does `AppServiceHTTPLogs.CsBytes` show that IIS received a partial request body when `.64` fires? Passive observation during `verify.sh`, not a hypothesis.
- Under M1a (E3), does the httpPlatformHandler stdout log capture the handler-side timer firing at 60 s (if H3 confirmed)? If yes, that stdout is a useful production diagnostic; document in the lab guide.

## Content structure decision

Lab 2 outputs feed into the same final lab guide at `docs/troubleshooting/lab-guides/windows-java-httpplatformhandler-timeout.md` established in Lab 1's design (16-section troubleshooting template, per-stage subsections in sections 5-9).

Lab 2-specific placement:

- **5. Experiment**: 5.3 Lab 2 loopback saturation and mitigation.
- **7. Observation**: Pre-E1 baseline re-verification, E1 first-positive rate, E3 M1a outcome (primary + secondary canary if applicable), E2 rate characterization, E4 M2 recycle timeline (or unverifiable note), optional E5 comparison.
- **8. Measurement**: statistical tables per experiment; k6 fidelity signals per run.
- **9. Analysis**: `.64` load-threshold synthesis (Lab 1's null result + Lab 2's positive result), M1a and M2 verdicts (with explicit note if E4 was marked unverifiable), scale-out verdict (if E5 run).
- **13. Solution**: production runbook combining M1a (if operative) and M2 (if effective and verifiable).
- **14. Prevention**: architecture-level guidance (scale-out with tolerance, request-timeout policy caveats for Windows Java SE, monitoring thresholds using the `pct_64 >= 1.0 AND count >= 5` definition).

Evidence labels per AGENTS.md `[Observed] / [Measured] / [Correlated] / [Inferred] / [Strongly Suggested] / [Not Proven] / [Unknown]` applied throughout.

## Sources

Primary references cited above (all `en-us` locale per AGENTS.md):

- Spring Boot default `server.tomcat.threads.max = 200` (`ServerProperties.Tomcat.Threads.max`):
  <https://github.com/spring-projects/spring-boot/blob/main/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/web/ServerProperties.java>
- `AppServiceHTTPLogs` schema (`ScSubStatus` and `ScWin32Status` are STRING, `ScStatus` is INT):
  <https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/appservicehttplogs>
- `Microsoft.Web/sites/config-web` Auto-Heal `statusCodes[]` schema (with `status`, `subStatus`, `win32Status`, `path`, `count`, `timeInterval`):
  <https://learn.microsoft.com/en-us/azure/templates/microsoft.web/sites/config-web>
- App Service monitoring reference (Auto-Heal platform events):
  <https://learn.microsoft.com/en-us/azure/app-service/monitor-app-service-reference>
- httpPlatformHandler configuration reference (`requestTimeout` default `00:02:00`):
  <https://learn.microsoft.com/en-us/iis/extensions/httpplatformhandler/httpplatformhandler-configuration-reference>
- Deploy authentication types (Entra fallback for `az webapp deploy` under Kudu basic-auth policy block):
  <https://learn.microsoft.com/en-us/azure/app-service/deploy-authentication-types>
- Java deploy documentation (OneDeploy `--type static` and `--type jar`):
  <https://learn.microsoft.com/en-us/azure/app-service/configure-language-java-deploy-run>
- App Service hosting plans (B1 Basic scale-out to 3 instances):
  <https://learn.microsoft.com/en-us/azure/app-service/overview-hosting-plans>
- App Service scale-up / scale-out:
  <https://learn.microsoft.com/en-us/azure/app-service/manage-scale-up>
- App Service automatic scaling (Standard SKU only - referenced only to justify B1 sufficiency):
  <https://learn.microsoft.com/en-us/azure/app-service/manage-automatic-scaling>
