---
title: SNAT Evidence Review (#389)
slug: snat-evidence-review
doc_type: reference
section: reference
summary: Pinned review of the unmerged Scenario B comparison, unavailable port-pressure evidence, causal limits and the smallest justified follow-up.
topics: [troubleshooting, evidence]
products: [azure-app-service]
content_sources:
  references:
    - type: self-generated
      justification: Offline inspection of main and PR 249 at the SHAs below, retained public package hashes and saved Microsoft Learn text; no Azure execution or new evaluation.
    - type: mslearn
      url: https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-intermittent-outbound-connection-errors
    - type: mslearn
      url: https://learn.microsoft.com/en-us/azure/nat-gateway/nat-metrics
    - type: mslearn
      url: https://learn.microsoft.com/en-us/azure/firewall/metrics
---

# SNAT Evidence Review (#389)

The retained comparison does not establish SNAT exhaustion or its absence. Its causal status remains **INCONCLUSIVE**. This describes the two PR #249 runs separately from the [main inventory](outbound-evidence-gap-matrix.md); it does not import them, rerun them, re-evaluate them or change their stored labels.

## 1. Basis and provenance

Review reads occurred on 2026-11-04 UTC. **Observed** below means a named retained artifact or source file shows the value, not independent proof of Azure execution. **Documented** means the cited Learn text; **Inferred** and **Not Proven** retain their Golden meanings. Missing data is **Unknown**.

| Source | Pinned basis |
|---|---|
| `origin/main` | `eb104e09901d9181ecd742dfbd50bc8129b449b6`, committed `2026-11-04T23:22:43+09:00`; all main file:line references below use this commit |
| [PR #249](https://github.com/yeongseon/azure-app-service-practical-guide/pull/249) | Open, `CONFLICTING` / `DIRTY` at read; head `c3b7c750319aafaedc204a1b32c26c5c5c68c6d8`, committed `2026-10-16T23:20:30+00:00`; **every PR observation here is pinned to this head** |
| Read method | `git fetch origin evidence/177-scenario-b-live`, then `git show <head>:<path>`; issue bodies and all comments for #177, #129, #387, #389; seven saved Learn pages retrieved `2026-11-04T14:04Z` (Sources) |
| Artifact layout | At that PR head only: `evidence/runs/<run-id>/{manifest,evidence,result,provenance,cleanup}.json`; declarations in `evidence/run-declarations.json`, anchors in `evidence/retained-digests.json` |

**Observed:** SHA-256 of each of the five public files in each run matches its retained-digest entry (ten matches), computed directly from `git show` bytes. The private raw captures are not available here; their phase hashes cannot be independently checked. Byte integrity does not certify collection or causality.
Both registry entries say `historical: false`, both manifests `trusted-current`; the first PR description nevertheless calls its design invalid. These stored metadata are reported, not endorsed or relabeled.

## 2. Retained comparison

Use **F** for `20261016T124329Z-70fb229a0bd1` and **R** for `20261016T154910Z-a034cccd79d6`. All values in this section are **Observed** at the pinned PR head, including capture-source files reached through its manifests.

| Field | F: invalid self-targeting design | R: replacement |
|---|---|---|
| `captured_at` / capture end | `2026-10-16T12:43:29.917770+00:00` / `2026-10-16T12:49:17.397658+00:00` | `2026-10-16T15:49:10.528138+00:00` / `2026-10-16T15:53:33.414422+00:00` |
| `evaluated_at`: manifest / result | `2026-10-16T13:05:20Z` / `2026-10-16T13:06:55Z` | `2026-10-16T15:58:00Z` / `2026-10-16T15:57:17Z` |
| Capture `source_commit` = `runner_source_commit`; commit time | `a6414fde20e746bf0ea275955b3b24d338c73b4e`; `2026-10-16T12:37:32+00:00` | `4d74f2a85bfbded24b82810b530f758f1e9344f5`; `2026-10-16T15:49:05+00:00` |
| Hosting / tier / runtime / region | Linux App Service, `B1 Linux` (template `Basic`, capacity `1`), `Python 3.11`, `koreacentral` | Same |
| Workload and destination | `/outbound` versus `/outbound-fixed`, `calls=5`; tested app's own public `/health` (PR description and PR lab §4.15); original hostname omitted | Same endpoints and calls; separate lab-controlled App Service endpoint; retained target `https://target.example/health` is sanitized, not a runnable destination |
| Probe concurrency per path per phase / workers | `12` / Gunicorn `4`; unpooled then pooled | `3` / Gunicorn `4`; unpooled then pooled |
| Pressure recipe / recovery wait | `LOAD_WORKERS=32`, `LOAD_SECONDS=45`, `RECOVERY_SETTLE_SECONDS=90` | Same |
| Stored execution / hypothesis | `COMPLETE` / `CONTRADICTED` | `COMPLETE` / `INCONCLUSIVE` |
| Cleanup record, not a fresh check | `VERIFIED`, `resource_group_exists=false`, output `false`, `2026-10-16T12:50:39Z` | Same values, `2026-10-16T15:58:00Z` |

Manifest evaluation times equal provenance `derivation.derived_at`; result times differ as shown. None is this review's date. F's derivation collector is `8523cf93f76c93546d2f156424964db55bfa14a7`; R's is its capture source above.
The head's `scripts/golden/scenario-b-recipe.json` instead pins collector `cd8134c9e3684983693d88f7dccf9b433a8c58f5`; recipe identity is not capture time. R records a separate sanitizer commit `4125ea820904d7fbe50c3bb4452a2eae014e90bc`.

### Every declared assertion and its input

Outcomes are **stored**, not newly evaluated. Inputs are in `evidence.json` `observations`; expected predicates are in `manifest.json`. No assertion has the `supporting` role. F does not declare the pooling assertion.

| Assertion id | Role | F outcome; raw input | R outcome; raw input |
|---|---|---|---|
| `baseline-outbound-succeeds` | control | `CONTRADICTED`; `baseline_success_count=0`, expected `12`; baseline rows have inner transport failures | `SUPPORTED`; `baseline_success_count=3`, expected `3`; each path's three baseline rows has status `200`, inner success `5`, failure/transport failure `0` |
| `symptom-transport-failures-appear` | symptom | `SUPPORTED`; `load_transport_failure_count=12`, allowed `1..12`; all load rows have null status and inner transport failure `1` | `SUPPORTED`; count `3`, allowed `1..3`; all three unpooled load rows have null status and inner transport failure `1` |
| `control-destination-bound-to-workload` | control | `SUPPORTED`; `destination_binding=true` | `SUPPORTED`; same; retained row targets equal `observations.destination` |
| `discriminating-snat-port-pressure` | discriminating | `INCONCLUSIVE`; `snat_port_pressure="unavailable"`, expected `"observed"` | `INCONCLUSIVE`; same |
| `discriminating-destination-stays-healthy` | discriminating | `CONTRADICTED`; `destination_health.status=null`, scalar absent and listed incomplete | `SUPPORTED`; health status `200` at `2026-10-16T15:51:03.217268+00:00` |
| `discriminating-http-errors-absent` | discriminating | `SUPPORTED`; `load_http_error_count=0`; inner failure `0` in load rows | `SUPPORTED`; same; null outer statuses do not prove successful outbound calls |
| `discriminating-pooling-reduces-transport-failures` | discriminating | Not declared; pooled rows not retained in `observations` | `CONTRADICTED`; `pooling_reduces_transport_failures=false`; three failed unpooled and three failed pooled load rows |
| `recovery-outbound-succeeds-again` | recovery | `CONTRADICTED`; `recovery_success_count=0`, expected `12`; null statuses, inner transport failure `1` | `CONTRADICTED`; count `0`, expected `3`; both paths' recovery rows have null status, inner transport failure `1` |

### What those inputs actually discriminate

The PR-head collector (`collect_scenario_b.py:149–165`) synthesizes inner outcome counts from **outer** probe errors when no app JSON body is returned. Therefore the retained `inner.transport_failure` is not necessarily an app-to-destination failure. R's baseline app bodies differ from its null-status load rows. The comparison cannot establish pooling's effect on actual outbound transport errors.

At each capture source, `run_scenario_b.py` calls `apply_pressure` to completion **before** capturing the phase named `load`, then probes destination health. R's load ends `15:51:03.215767+00:00`, before the health sample above. That single healthy sample is not continuous destination-health control during pressure.
Actual new-connection rate and SNAT inventory are **Unknown**, not the number of outer probes. R's independent destination is a different app; the template puts it on the same plan, so destination resource isolation is not established.

The runner writes `port-pressure.json` from attempts, workers, seconds and times, defaulting `status` to `unavailable`; it queries no SNAT counter or detector. The collector tries `port-pressure.json.status` for `snat_port_pressure`, `destination-health.json.status` for destination control and `app-target.json` for binding.
PR #249's evaluator maps `unavailable` to `INCONCLUSIVE` (lines 153–157). Its role combiner (479–497) treats failed controls/recovery as `INCONCLUSIVE`; it also exempts F from stored-verdict rejection (828–842). Thus F's preserved `CONTRADICTED` result is not causal refutation. The evaluator of current `main` handles failed controls and recovery differently, so a replay on `main` may not give the stored outcomes; no replay was made. No evaluator is run here.

## 3. Documented telemetry, by outbound path

Quotes use the seven saved Learn pages, all retrieved `2026-11-04T14:04Z`.
They describe products, not measurements of F or R.

| Configuration | Documented quotation and scope | Applicability to retained B1 runs |
|---|---|---|
| Default multitenant App Service | [Outbound troubleshooting](https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-intermittent-outbound-connection-errors): “You can use App Service Diagnostics to find SNAT port allocation information, and observe the SNAT ports allocation metric of an App Service site.” It names the SNAT Port Exhaustion tile, but also says “Since SNAT port usage isn't available as a metric,” autoscale cannot use it. | Detector allocation information is **Documented**; a normal Azure Monitor SNAT usage counter is not. Basic eligibility/minimum eligible SKU is **Unknown** in these pages. PR provenance says direct telemetry unavailable; the main October 2 prose reports a Basic-tier refusal, not retained October 16 detector output. |
| Diagnostics / hosting model | [Diagnostics](https://learn.microsoft.com/en-us/azure/app-service/overview-diagnostics): “App Service diagnostics works for not only apps on Windows, but also for apps on built-in or custom containers, App Service Environments, and Azure Functions.” [Networking](https://learn.microsoft.com/en-us/azure/app-service/networking-features): “The multitenant public service hosts App Service plans in the Free, Shared, Basic, Standard, Premium, PremiumV2, PremiumV3, and PremiumV4 pricing SKUs.” | **Documented** hosting classification and general tool scope, not a promise of per-detector Basic data or a minimum SKU. |
| Regional VNet integration + NAT Gateway | [Integration](https://learn.microsoft.com/en-us/azure/app-service/networking/nat-gateway-integration): “The virtual network integration must route all internet-bound traffic (application and configuration).” [NAT metrics](https://learn.microsoft.com/en-us/azure/nat-gateway/nat-metrics): “This metric can be filtered by Attempted and Failed connection states. A failed connection volume greater than zero can indicate SNAT port exhaustion.” | **Documented** `SNATConnectionCount` with `Protocol, ConnectionState`, Sum and `PT1M`; `TotalConnectionCount` counts active connections. Neither is a port-utilization gauge or unique causal proof. No such topology/capture is retained here; availability on the existing deployment is **Not Proven**. |
| Azure Firewall egress | [Firewall metrics](https://learn.microsoft.com/en-us/azure/firewall/metrics): “Percentage of outbound SNAT ports currently in use” describes `SNATPortUtilization` (Average/Maximum, Protocol, `PT1M`). “If SNAT ports are used more than 95%, they're considered exhausted” describes its firewall health behavior. | **Documented** direct utilization on the firewall resource, not the App Service hidden pool. No firewall path is established for these runs. Minimum App Service/Firewall tier pairing is **Unknown** in this source set. |
| Customer-managed public Load Balancer | [Outbound connections](https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-outbound-connections): “Outbound rules enable you to explicitly define SNAT (source network address translation) for a standard SKU public load balancer.” It directs readers to “Review SNAT metrics” but gives no metric names/collection specification in this saved page. | **Documented** Standard outbound rules; actual counter details **Unknown** here. App Service's load balancers are “not exposed to customers” (outbound troubleshooting). Customer-LB telemetry cannot be assumed available for multitenant B1. |

TCP counts and local `TIME_WAIT` are supporting, not platform SNAT inventory:
Learn says “TCP connections and SNAT ports aren't directly related.” It also
says “If your app creates connections to a mix of address and port combinations,
you won't use up your SNAT ports.” Broad fan-out alone cannot discriminate SNAT.

## 4. Main playbook and lab claims to qualify

These are source-text observations, not edits to the playbooks/lab. Paths below
are relative to `docs/troubleshooting/`, pinned to the main SHA in section 1.

| Exact quotation / location | Evidentiary limit |
|---|---|
| `playbooks/outbound-network/snat-or-application-issue.md:79`: “If SNAT is not near exhaustion, treat the incident as an application or dependency reliability problem and validate connection pooling, DNS behavior, and downstream health in parallel.” | Stronger than available data if detector coverage/window is missing; a healthy sample does not exclude transient platform contribution. |
| Same file `:307`: “When the app is instrumented with Application Insights, the `dependencies` table exposes the per-target outbound call rate and duration — the signal that separates SNAT pressure (H1, broad degradation across many public targets) from a single-dependency problem (H4).” | Rate/duration support investigation, not separation of platform port inventory from worker queues, DNS or target behavior; see the mixed-destination Learn quote above. |
| Same file `:318`: “A low `DcountTargets` (failures concentrated on one or two targets) points to **H4** (a single downstream dependency) instead.” | Same-target SNAT pressure remains possible; low target cardinality does not separate H1 from H4. The preceding broad-fan-out H1 attribution is likewise not discriminating. |
| `lab-guides/snat-exhaustion.md:230`: “When a Python/Flask app creates a new outbound TCP connection per request without connection pooling, SNAT ports exhaust within minutes under concurrent load, causing timeouts and SIGKILL'd workers.” | A hypothesis, **Not Proven**, not a demonstrated timeline or cause. |
| Same file `:251`: “All of the following must be observed in the same trigger window:” under “Proof criteria” (`:249`) | The list (`:253–262`) requires curl `000`, `499`/`503`, timeout bodies, worker timeout/SIGKILL and recovery, but no independently measured port pressure. Their conjunction still cannot prove SNAT exhaustion. |
| Same file `:847`: “The rerun meets the [2.4](../troubleshooting/lab-guides/snat-exhaustion.md#24-disproof-criteria) disproof criterion "No worker timeout/SIGKILL events during failure period" for the SNAT chain while still showing that pooling removes the inbound degradation.” | Missing console signatures cannot prove events absent; this is reported October 2 prose, not retained raw rows for this comparison. It cannot disprove SNAT generally. |

HTTP `499`/`503` and latency are **symptoms**, not outbound inventory counters.
Gunicorn `WORKER TIMEOUT` / `SIGKILL` show worker lifecycle distress, not which
network hop caused it. Client curl `000` says no HTTP response reached that
client; it does not locate failure on the worker's outbound leg. Recovery after
pooling supports a behavioral change, not a unique cause. The main lab's
`:788` already says “SNAT exhaustion itself was not directly measured”; the
playbook's `:443–446` also preserves “not proven” and requires detector evidence.
The other outbound playbooks investigate DNS, routes and Storage authorization;
their query examples do not supply the missing SNAT counter (inventory §4).

## 5. Competing explanations and minimum follow-up

| Explanation still open | Discriminating evidence needed in a new declaration |
|---|---|
| Platform SNAT pressure | Per-instance allocation/usage and failed-new-connection timeline on the **effective egress path**, aligned with worker-side connect errors and healthy destination controls |
| Connection-pool behavior | Matched timeout/HTTP semantics, socket creation/reuse and pool-wait measurements; distinguish outer probe abandonment from actual app outbound outcomes |
| Worker saturation | Worker/PID occupancy, queue wait, CPU/memory, request arrival and cancellation times; bound pressure below worker capacity for controls |
| Destination throttling | Continuously sampled independently resourced lab target, response/error bodies, rate limits and target-side timing during—not just after—pressure |
| DNS | Worker-side resolved answers, resolver path/cache and lookup timings in the same window |
| Transient network | Time-aligned connection/packet errors and independent path controls; healthy KPIs alone do not rule this out |

**Inferred recommendation:** the gap justifies a **separate, explicitly authorized
run design**, not dispatch now or replay/relabeling of PR #249. First make the
smallest same-path telemetry preflight: one multitenant Linux worker, lab-owned
target on independent resources, default outbound and a plan whose SNAT detector
actually returns per-instance allocation/pressure data. The saved Learn pages
do **not** document a minimum eligible App Service SKU; “production tier” in the
older prose is not proof that S1 (or any named upgrade) exposes it. The numeric
minimum is **Unknown** and must be established before spend approval. Do not
upgrade blindly or substitute TCP counts. If no usable detector/export is
available, keep preparation **BLOCKED** rather than repeat a symptom-only run.

For an explicitly changed topology, the smallest documented NAT configuration
here is regional VNet integration with all internet routing, one Standard NAT
Gateway and a public IP; the supported minimum App Service SKU remains Unknown.
Its failed-connection counter is useful but not unique port-exhaustion proof.
Firewall egress documents an actual utilization counter, but adding a firewall
is not the minimum same-path experiment and cannot settle the old hidden pool.
Neither alternative justifies a blanket SNAT reproduction claim.

Predeclare tests for `discriminating-snat-port-pressure`, genuine worker outbound
failures, destination health, pooling, baseline and recovery; freeze windows,
contrary observations and telemetry completeness rules **before** collecting.
The [protected workflow](azure-e2e-operations.md) currently runs **Scenario A
only**: Scenario B needs a separately reviewed orchestration/collector change on
main, never execution of this PR or unfinished #249. Its first-run snapshot is
`BLOCKED` / `NOT_RUN`; recheck prerequisites rather than assume they changed.
Require protected `azure-e2e` approvals, reviewed SHA/recipe, OIDC/environment
secrets, least-privilege scope, quota and explicit Azure-owner authorization.
Record maximum spend and elapsed time, operator stop/cancellation owner, TTL,
exact run-owned resource tags, cleanup/deletion absence evidence and failure
retention. Arrange private original export/readback before ephemeral expiry;
public sanitized hashes cannot replace raw bytes. No price or budget is invented.

## 6. What this does not establish

- Causal SNAT status is **INCONCLUSIVE**; `COMPLETE` execution is a different axis.
- No fresh Azure run, detector availability, recovery or cleanup was checked here.
- No capture, evaluation or tutorial validation date is refreshed.
- No private-original integrity or stored-verdict correctness is certified.
- Independent human reproduction remains **NOT_MET**; provenance records `NOT_RUN`.
- PR #249 stays separate and unmodified; maintainer and Oracle review remain open.

## See Also

- [Outbound Evidence Gap Matrix](outbound-evidence-gap-matrix.md)
- [Golden Evidence Model](golden-evidence-model.md)
- [Guarded Azure E2E Operations](azure-e2e-operations.md)
- [SNAT or Application Issue](../troubleshooting/playbooks/outbound-network/snat-or-application-issue.md)
- [SNAT Lab](../troubleshooting/lab-guides/snat-exhaustion.md)

## Sources

Saved text retrieval for **each** Learn source: `2026-11-04T14:04Z`; this is not
a platform capture date. Repository observations use the two SHAs in section 1.

- [App Service outbound troubleshooting](https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-intermittent-outbound-connection-errors)
- [App Service networking features](https://learn.microsoft.com/en-us/azure/app-service/networking-features)
- [Load Balancer outbound connections](https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-outbound-connections)
- [NAT Gateway metrics](https://learn.microsoft.com/en-us/azure/nat-gateway/nat-metrics)
- [App Service NAT Gateway integration](https://learn.microsoft.com/en-us/azure/app-service/networking/nat-gateway-integration)
- [App Service diagnostics](https://learn.microsoft.com/en-us/azure/app-service/overview-diagnostics)
- [Azure Firewall metrics](https://learn.microsoft.com/en-us/azure/firewall/metrics)
- [PR #249 pinned tree](https://github.com/yeongseon/azure-app-service-practical-guide/tree/c3b7c750319aafaedc204a1b32c26c5c5c68c6d8), including the five-file packages, declarations, digests, recipe, collector and evaluator
- [#177](https://github.com/yeongseon/azure-app-service-practical-guide/issues/177), [#129](https://github.com/yeongseon/azure-app-service-practical-guide/issues/129), [#387](https://github.com/yeongseon/azure-app-service-practical-guide/issues/387), [#389](https://github.com/yeongseon/azure-app-service-practical-guide/issues/389)
