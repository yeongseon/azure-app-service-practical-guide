---
title: Outbound Network Evidence Gap Matrix (#387)
slug: outbound-evidence-gap-matrix
doc_type: reference
section: reference
summary: Dated inventory of the DNS, Private Endpoint and SNAT evidence behind the outbound playbooks, separating retained artifacts, reported runs without retained output, illustrative samples and missing signals.
topics: [troubleshooting, evidence]
products: [azure-app-service]
content_sources:
  references:
    - type: self-generated
      justification: Inventory derived from this repository at main 9d9d71f (the outbound playbooks, lab guides, lab folders, retained evidence, capture manifest and the unmerged pull request 249 branch); it makes no Azure-behavior claim of its own.
---

# Outbound Network Evidence Gap Matrix (#387)

This page inventories the evidence behind the outbound-network playbooks (DNS resolution, Private Endpoint and custom DNS, SNAT, storage connectivity) and names what is missing. It is the offline first slice of [#129](https://github.com/yeongseon/azure-app-service-practical-guide/issues/129). It changes no playbook, lab guide or retained evidence, and it refreshes no verification date.

## 1. Basis

| Item | Value |
|---|---|
| Source commit | `9d9d71ff3247bb29e9a7488c4297c0a734c3c9b1` (`main`, 2026-11-03). Line numbers on this page refer to it. |
| Read but not merged | Pull request [#249](https://github.com/yeongseon/azure-app-service-practical-guide/pull/249), branch `evidence/177-scenario-b-live`, head `c3b7c750319aafaedc204a1b32c26c5c5c68c6d8`, read with `git show`. |
| Method | Reading the playbooks, the lab guides, `labs/`, `evidence/` and `scripts/golden/`, and searching the retained artifact files for the values the pages quote. No Azure command, no KQL query and no live check was run. Screenshots were not read as text. |
| What the date means | 2026-11-03 is when the inventory was taken. It is not a capture, evaluation or test date of any evidence. |

## 2. Categories

| Category | Meaning | What it can support |
|---|---|---|
| Retained artifact | A file in this repository records the output, for example under `labs/*/artifacts-sanitized` or `evidence/runs`. | An observation scoped to what the file shows and to its trust (`trusted-historical` for the April 2026 captures). |
| Reported run | A page states results of a live run, often under `[Observed]` or `[Measured]`, and no file in the repository holds the raw output. | A reader can follow the text but cannot check it. Under the repository's evidence rules (`AGENTS.md`), `Observed` records what a named artifact directly shows, so these statements are not observations in that sense until output is retained. |
| Illustrative | A sample, example or "representative" block that no retained artifact contains. | A shape, not an observation. |
| Documented only | A query, command or Portal path with no retained output. | Documented behavior if it is sourced; nothing observed. |
| Portal capture | A retained image of what the Portal displayed at capture time: a configuration blade or a query result. | What was visibly displayed for that environment and query window. It does not establish a cause and is not a complete export. |

Absence from this inventory is not refutation. "Not retained" means that no file in the repository holds the output; it does not mean that the behavior did not occur on Azure.

## 3. Summary by playbook

| Playbook | Retained artifacts | Reported runs without retained output | Main missing signal |
|---|---|---|---|
| [DNS resolution on a VNet-integrated app](../troubleshooting/playbooks/outbound-network/dns-resolution-vnet-integrated-app-service.md) | 15 April 2026 lab files that the guide calls a non-VNet baseline (the integration state is unsettled, section 4.1); 2 July 2026 Portal query-result captures | 1 (2026-10-02): a public answer with `403`, then a private answer with `409` | A custom or forwarding resolver run (H1) or an app-level override run (H3); the raw dependency rows |
| [Private Endpoint, custom DNS and route confusion](../troubleshooting/playbooks/outbound-network/private-endpoint-custom-dns-route-confusion.md) | None cited | 1 (2026-10-02): a `/32` route fault, added and removed | Effective routes and NSG rules during the fault; a custom resolver run (H2) |
| [SNAT or application issue](../troubleshooting/playbooks/outbound-network/snat-or-application-issue.md) | 25 April 2026 lab files, target a public third-party site; 2 July 2026 Portal query-result captures | 2: the 2026-10-02 rerun (no failed outbound call) and an undated, incomplete first Scenario B attempt (120 successful outbound calls) | SNAT port usage; a connection rate that could exhaust the ports |
| [Storage connectivity, firewall and authorization](../troubleshooting/playbooks/outbound-network/storage-connectivity-firewall-authorization.md) | 6 Portal captures | 0 | Any run; no lab exists |
| [Private Endpoint access restrictions](../troubleshooting/playbooks/private-endpoint-access-restrictions.md) (inbound) | None | 0 | Any run; no lab exists |
| [SCM access, DNS and HTTP failures](../troubleshooting/playbooks/scm-access-dns-and-http-failures.md) (inbound) | None | 0 | Any run; no lab exists |

## 4. Detail by playbook

### 4.1 DNS resolution on a VNet-integrated app

- **Retained artifact:** none is cited by the page. The lab's April 2026 set (section 5) is described by the lab guide as a non-VNet baseline, and the guide concludes that the VNet-integrated failure is not in it (`dns-vnet-resolution.md`, lines 865-874). The retained configuration (`labs/dns-vnet-resolution/artifacts-sanitized/baseline/app-config.json`, line 120) records a populated `vnetName` with `vnetRouteAllEnabled` `false`, so the artifacts do not settle whether the app was VNet-integrated at capture.
- **Reported run:** "Live reproduction evidence (2026-10-02)", lines 494-516. With the zone unlinked, the standard storage name resolved to a public address and the call returned `403` (10 of 10); after the link was created it resolved to the endpoint address and returned `409` (5 of 5); `AppServiceHTTPLogs` showed no `5xx`. No file in the repository holds the rows. The lab app records the status code and not the Storage error body, so the specific error code was not captured (line 506).
- **Illustrative:** "Sample Log Patterns" under the heading "dns-vnet lab", lines 144-175, shows rows such as `/diag/stats 499 24400`. No retained artifact file contains these values, and the lab's retained HTTP export (27 rows, ending 2026-04-04T05:35Z) has only `200` and `202` responses. The page does not say which capture the rows came from. The same excerpts appear under the same heading in the Private Endpoint playbook (lines 117-147).
- **Documented only:** 8 KQL blocks and 7 CLI blocks. Where they show output, the values are placeholders or unattributed.
- **Portal captures:** 1 configuration blade of a public app without VNet integration (`Not configured`), which cannot show a VNet-integrated path; and 2 query results, `troubleshooting--log-analytics--11-dns-vnet-http-status-distribution-kql` (2026-07-18) and `...11-dns-vnet-platform-startup-kql` (2026-07-20), recorded in the capture manifest and not read as text here.
- **Missing signals:** a run with a custom or forwarding resolver (H1) or an app-level override (H3), because the 2026-10-02 run used the default resolver path (`dns-vnet-resolution.md`, line 902); a lookup-error variant (lines 885-906); the raw `AppDependencies` rows; the Storage error body.

### 4.2 Private Endpoint, custom DNS and route confusion

- **Retained artifact:** none. The route-fault lab (`labs/private-endpoint-route-fault`) has no artifact folder, and its guide says "Raw run output stayed outside the repository" (`private-endpoint-route-fault.md`, lines 176-178).
- **Reported run:** "Live reproduction (2026-10-02)", lines 381-394: with DNS, the zone link and the endpoint approval constant, an exact `/32` route added from the integration subnet turned `409` responses into `ResultCode` `0` at about 8 s, and removing it restored them (8 calls per phase).
- **Illustrative:** the same "dns-vnet lab" log excerpts as in section 4.1 (lines 117-147). They are labelled as coming from the DNS lab and dated 2026-04-04, before the route-fault lab existed. The CLI example output (for example `pe-stlabdnsvnet-blob`) occurs in no retained artifact.
- **Documented only:** 8 KQL blocks and 5 CLI blocks.
- **Portal capture:** 1, the same public app without VNet integration; its route-table and NSG rows read `N/A`, and the page says these placeholders do not identify the governing route table or NSG (line 547).
- **Missing signals:** the integration subnet's effective routes and effective NSG rules during the fault, which the page lists as required evidence (line 108); a custom resolver run (H2); a run that varies an NSG or firewall deny, endpoint approval or a stale cache (H4), since the endpoint stayed `Approved` throughout. The route-fault guide marks as not proven which of `vnetRouteAllEnabled` and `WEBSITE_VNET_ROUTE_ALL` governed routing (line 151).

### 4.3 SNAT or application issue

- **Retained artifact:** the April 2026 set under `labs/snat-exhaustion/artifacts-sanitized` (section 5). Its target was the public `httpbin.org`, so its timeouts cannot be separated from that service's own throttling (`snat-exhaustion.md`, line 791), and the lab's own classification says that it supports none of the declared assertions.
- **Reported run:** "Live reproduction evidence (2026-10-02)", lines 429-446: 0 failed outbound calls in either phase; 90 inbound `499` responses without pooling and 0 with it; the SNAT detectors returned only a "non production tier" message on the Basic plan. No file in the repository holds the output.
- **Illustrative:** "Sample Log Patterns", lines 137-176, with rows such as `/outbound 499 29840`; no retained artifact file contains these values (the retained export holds other `499` rows). The "Normal vs Abnormal Comparison" row "SNAT detector expectation: ports near/exceed threshold during incidents" (line 426) is an expectation. No retained or reported run observed it.
- **Reported, incomplete attempt:** `labs/snat-exhaustion/golden/evidence-classification.json` (`known_gaps`, line 61) reports a first live Scenario B run that was started and stopped before completing. Probes were served and the app's own counters reported 120 successful outbound calls, with no failures and no transport failures. It was stopped because fifty probes per phase meant about six thousand requests against a public, rate-limited host and did not finish inside a window that could be supervised. The attempt is undated, no raw output is retained, and `executed_runs` is empty (line 65).
- **Documented only:** 7 KQL blocks and 1 CLI block.
- **Portal captures:** 1 configuration blade of a public app without VNet integration; and 2 query results, `troubleshooting--log-analytics--10-snat-outbound-status-distribution-kql` (2026-07-18) and `...10-snat-outbound-tail-latency-kql` (2026-07-20), recorded in the capture manifest and not read as text here.
- **Missing signals:** SNAT port usage. The page's first required item is the "SNAT port allocation timeline"; no retained or reported output provides port data. The 2026-10-02 rerun used a Basic plan, whose detector returned none, and the April plan SKU was not recorded. The page also says that a `499` cluster supports H1 only when outbound calls fail at the connection level and the detector shows port pressure; no retained or reported run has both. The 2026-10-02 rerun reports about 4.5 new connections per second to one destination and states that this stayed below the rate that would exhaust the preallocated ports (`snat-exhaustion.md`, 4.14).

### 4.4 Storage connectivity, firewall and authorization

- **Retained artifact:** none for a run.
- **Portal captures:** 6, for layers 2 to 4 of the four-layer walk (line 309).
- **Illustrative:** layer 1 is "Representative output" with `<stamp>` and `20.150.x.x` placeholders (line 328). The CLI blocks are documented only.
- **Missing signals:** a run of the four layers. No lab exists for this playbook. The 2026-10-02 DNS run (section 4.1) reported a `403` without the Storage error body, so no retained or reported output separates a firewall `403` from a data-plane authorization `403` (H3 from H4).

### 4.5 Inbound playbooks

[Private Endpoint access restrictions](../troubleshooting/playbooks/private-endpoint-access-restrictions.md) and [SCM access, DNS and HTTP failures](../troubleshooting/playbooks/scm-access-dns-and-http-failures.md) are decision-point playbooks with one CLI block each (the first also has one KQL block). They carry no lab, no retained run and no reported run. Their rule-match audit evidence is described as available only "where enabled and retained" (`private-endpoint-access-restrictions.md`, line 174).

## 5. Retained evidence by lab

| Lab | Golden contract | Retained Golden runs on `main` | Pre-Golden artifacts | Reported live runs |
|---|---|---|---|---|
| `dns-vnet-resolution` | None (`migration-needed`); no `golden/` folder | 0 | 15 files captured 2026-04-04, `trusted-historical`; 3 are empty (`kql-*-20260404T060048Z.json`). The non-empty KQL exports hold 27 HTTP, 94 console and 158 platform rows. The guide calls the set a non-VNet baseline, but `baseline/app-config.json` records a populated `vnetName`. | 2026-10-02 (prose only) |
| `private-endpoint-route-fault` | None (`migration-needed`); no `golden/` folder | 0 | None. `labs/golden-classification.json` describes the lab as containing "retained Azure evidence", but its folder holds only the app, the template and the trigger and verify scripts. | 2026-10-02 (prose only; raw output stayed outside the repository) |
| `snat-exhaustion` | Scenario B: 7 declared assertions, `execution_status` `NOT_RUN` ("never executed against Azure"), plus an evidence classification whose `known_gaps` report one started and stopped live attempt and an empty `executed_runs` | 0 | 25 files captured 2026-04-04, `trusted-historical`; 7 are empty. The HTTP export has 195 rows (129 `499`, 47 `200`, 17 `503`, 2 `202`). The `/diag/net` snapshots (baseline, before, recovered) are single points in time; the one taken after the trigger is a `504` and the one after the target is empty. | 2026-10-02 (prose only); one undated, incomplete first attempt (section 4.3) |

The three runs retained on `main` under `evidence/runs` concern `deployment-succeeded-startup-failed` (2026-09-27 and 2026-10-16) and `slot-swap-config-drift` (2026-09-27). None concerns DNS, a Private Endpoint route or SNAT, and `evidence/run-declarations.json` registers only the 2026-10-16 run. The April captures record neither a source revision nor a plan SKU nor a CLI version (`labs/golden-classification.json`).

Four Portal screenshots of Log Analytics query results for the DNS and SNAT labs are recorded in `scripts/capture/manifest.yaml` (`troubleshooting--log-analytics--10-snat-outbound-status-distribution-kql` and `...11-dns-vnet-http-status-distribution-kql`, captured 2026-07-18; `...10-snat-outbound-tail-latency-kql` and `...11-dns-vnet-platform-startup-kql`, captured 2026-07-20). They are images, and this inventory did not read their contents. No file in the three lab folders carries a July 2026 timestamp in its name or content, so the screenshots are the only retained record of those queries.

## 6. Pull request #249 (not merged)

[#249](https://github.com/yeongseon/azure-app-service-practical-guide/pull/249) is open, has 31 commits and conflicts with `main`. It would add two Scenario B runs for #177. Nothing in it is retained on `main`, and this inventory counts none of it.

| Run | Captured | Execution | Hypothesis | Notes |
|---|---|---|---|---|
| `20261016T124329Z-70fb229a0bd1` | 2026-10-16 | `COMPLETE` | `CONTRADICTED` (stored) | Baseline, destination health and recovery `CONTRADICTED`; SNAT port pressure `INCONCLUSIVE`. The pull request calls it an invalid self-targeting experiment; its manifest still reads `trusted-current`. |
| `20261016T154910Z-a034cccd79d6` | 2026-10-16 | `COMPLETE` | `INCONCLUSIVE` | Baseline, destination health and absence of HTTP errors `SUPPORTED`; pooling reduces transport failures and recovery `CONTRADICTED`; SNAT port pressure `INCONCLUSIVE`. |

Both runs record a verified cleanup (`az group exists` returned `false`). The pull request's own merge-gate review (a comment on it, 66/100, not merged) lists four must-fix findings: outer request failures presented as outbound failures, so the pooling assertion is not supported; a sanitization that cannot reproduce the retained integrity anchors; an exemption that hides a stored-versus-replayed verdict disagreement; and a destination check that redirects or a trailing dot can bypass. The first three concern retained evidence whose private originals this inventory does not have.

## 7. Prerequisites for a future authorized run

- **Exists on `main`:** the manual workflow `.github/workflows/e2e-azure.yml` (a reviewed commit SHA, the protected `azure-e2e` environment, OIDC, a TTL sweep) runs Scenario A only. Scenario B has a contract, `scripts/golden/run_scenario_b.py` and `scripts/golden/collect_scenario_b.py`, but no workflow step calls them. The DNS and route-fault labs have trigger and verify scripts but no contract, collector or workflow step.
- **Not provisioned by the repository:** the environment, the federated credential and its secrets (see [Guarded Azure E2E Operations](azure-e2e-operations.md)). Whether they exist is Unknown here, because the repository cannot read them.
- **Needed for a slice that closes a gap:** a declared contract and a collector for DNS or the route fault; a plan tier whose SNAT detector reports port data, plus a connection rate high enough to need it; an Application Insights or workspace configuration that records dependencies; and a reviewed pull request that turns a private capture into a retained package with the evaluator and PII gates.
- **Authorization:** no approval for a paid run is recorded in the repository, so a slice that needs one stays `NOT_RUN` until it is approved and executed. See [#218](https://github.com/yeongseon/azure-app-service-practical-guide/issues/218) and [#392](https://github.com/yeongseon/azure-app-service-practical-guide/issues/392).

## 8. What this page does not establish

- It does not show that any reported run did not happen or is wrong. It shows that the repository cannot re-derive it.
- It does not show that a missing signal was absent on Azure.
- It supports no SNAT conclusion either way: nothing retained or reported shows port exhaustion, and nothing rules it out on a production tier. An inbound `499`, a long request or worker degradation does not establish it.
- It runs nothing and verifies nothing, so no `last_tested`, `captured_at` or evaluation date changes.

## 9. Next slices

[#389](https://github.com/yeongseon/azure-app-service-practical-guide/issues/389) reviews the retained SNAT conclusions against these gaps, and [#388](https://github.com/yeongseon/azure-app-service-practical-guide/issues/388) is the single controlled DNS and Private Endpoint live slice, which needs authorized access. The Scenario B evidence for #177 is in pull request #249, which is not merged.

## See Also

- [SNAT Evidence Review (#389)](snat-evidence-review.md)
- [Golden Evidence Model](golden-evidence-model.md)
- [Guarded Azure E2E Operations](azure-e2e-operations.md)
- [Lab: DNS Resolution (VNet)](../troubleshooting/lab-guides/dns-vnet-resolution.md)
- [Lab: Private Endpoint Route Fault](../troubleshooting/lab-guides/private-endpoint-route-fault.md)
- [Lab: SNAT Exhaustion](../troubleshooting/lab-guides/snat-exhaustion.md)
- [Parent #129](https://github.com/yeongseon/azure-app-service-practical-guide/issues/129)
- [Inventory #387](https://github.com/yeongseon/azure-app-service-practical-guide/issues/387)

## Sources

- [Golden Evidence Model](golden-evidence-model.md)
- [Guarded Azure E2E Operations](azure-e2e-operations.md)
