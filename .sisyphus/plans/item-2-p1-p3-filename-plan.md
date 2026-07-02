# Item 2 — P1-P3 Lab Portal Capture Filename Plan

**Author**: Sisyphus (autonomous orchestration)
**Purpose**: Enumerate the exact filenames, target `docs/troubleshooting/lab-guides/*.md` anchor sections, and per-capture intent for every new lab-specific Portal screenshot required by Oracle's 14-item strategic plan across the 11 P1-P3 troubleshooting labs. This document exists so Momus and Oracle can pre-approve naming/placement decisions BEFORE any Azure resource is provisioned. No PNG file, lab guide edit, or CI change is authorized by this plan; it is a naming and placement contract only.
**Status**: DRAFT — pending Momus review, then Oracle GO
**Downstream consumers**: Oracle Items 3-13 execution (per-lab lifecycle), Item 14 final polish
**Predecessor**: Item 1 (commit `87ff806` on `origin/main`, PII scan gate live in CI)
**Blockers**: None (Item 1 complete, `.sisyphus/plans/` created, working tree clean)

---

## 1. Oracle Mandate (verbatim)

From Oracle session `ses_0dee15ee0ffepTyQ80YQ3Z0hZz` and the standing 14-item plan:

- **Item 2** (this plan): "Filename plan for 11 P1-P3 labs. Use new lab-specific asset filenames, not in-place overwrites. Preserve every existing shared asset by adding new NN>=04 files under the same `<blade-dir>/`."
- **Item 3**: "dns-vnet-resolution — audit-only. Verify existing 2 captures render correctly; do not re-capture."
- **Items 4-13**: "10 labs sequential lifecycle. Max 2 active lab deployments at any time. Portal capture serially in one browser session. Delete infra immediately after capture + artifact verification."
- **Item 14**: "`docs(labs): final polish` commit."

Estimated total: 20-28 agent-hours, ~$8-20 Azure spend distributed across multiple sessions.

---

## 2. Scope

### 2.1 In scope (11 P1-P3 labs)

| # | Lab | Total lines | Slug | Section 4 anchors available |
|---|---|---:|---|---:|
| 1 | cd-reconnect-rbac-conflict | 340 | `cdrecon` | 0 (Section 4 has no subsections — special handling) |
| 2 | container-http-pings | 846 | `httppings` | 18 (4.1-4.18) |
| 3 | deployment-succeeded-startup-failed | 918 | `depstart` | 9 (4.1-4.9) |
| 4 | dns-vnet-resolution | 912 | `dnsvnet` | 16 (4.1-4.16) — **AUDIT ONLY** |
| 5 | failed-to-forward-request | 779 | `fwdreq` | 13 (4.1-4.13) |
| 6 | intermittent-5xx | 867 | `intmt5xx` | 12 (4.1-4.12) |
| 7 | memory-pressure | 941 | `memlk` | 13 (4.1-4.13) |
| 8 | no-space-left-on-device | 962 | `nolabspace` | 17 (4.1-4.17) |
| 9 | slot-swap-config-drift | 863 | `slotswap` | 20 (4.1-4.20) |
| 10 | slow-start-cold-start | 760 | `slowstart` | 12 (4.1-4.12) |
| 11 | snat-exhaustion | 814 | `snat` | 13 (4.1-4.13) |

**Slug design rules**: ≤10 chars, lowercase alphanumeric, semantically meaningful, unique across all labs. Rationale: matches P0 windows-java pattern where compact slugs prevented long filenames while remaining searchable.

### 2.2 Out of scope

- **P0 (`windows-java-httpplatformhandler-timeout`)**: Already done (commit `f839d67`). 4 lab-specific captures live under `kudu/04-05`, `log-analytics/02`, `configuration/03`.
- **Labs outside `docs/troubleshooting/lab-guides/`**: Tutorials, recipes, playbooks — these do not go through Oracle's lab lifecycle.
- **Non-Portal assets** (Mermaid diagrams, CLI output): Not addressed here. Any Mermaid diagram changes are separately governed by frontmatter `content_sources.diagrams`.

---

## 3. Naming Convention

### 3.1 Pattern

```
docs/assets/troubleshooting/<blade-dir>/<NN>-<lab-slug>-<state>.png
```

| Segment | Rule | Example |
|---|---|---|
| `<blade-dir>` | Existing 14 subdirs under `docs/assets/troubleshooting/` (`activity-log`, `app-insights`, `app-service-plan`, `configuration`, `deployment-center`, `deployment-slots`, `diagnose-and-solve`, `health-check`, `kudu`, `log-analytics`, `log-stream`, `metrics`, `networking`, `vnet-integration`) — REUSE these, and only create a new dir when the capture is a genuinely new Portal blade not represented above (Section 5.1 creates `iam/` for this reason). | `metrics`, `log-analytics`, `kudu` |
| `<NN>` | Two-digit sequence starting at the next unused NN per blade-dir. **Populated dirs**: use next unused NN (typically ≥04 to avoid collision with shared `01-03` and P0's `04-05` under `kudu/`, `configuration/`, `log-analytics/`). **Empty dirs** (e.g., `deployment-slots/`) or **brand-new dirs** (e.g., `iam/`): may start at `01`. Exact per-dir allocation is fixed in Section 3.3. | `04`, `05`, `06`, or `01` for empty/new dirs |
| `<lab-slug>` | See Section 2.1 slug table. Compact, unique per lab. | `memlk`, `snat`, `slotswap` |
| `<state>` | Compact descriptor of what the capture shows. Prefer verbs (`baseline`, `mid-leak`, `recovery`, `post-swap`) or noun-state (`kql-result`, `heap-spike`). | `baseline`, `mid-leak`, `heap-spike-4xx-response` |

### 3.2 Rationale

- **Blade-dir reuse**: Sharing subdirs across labs mirrors the existing 22-file layout. Prevents `docs/assets/troubleshooting/` fanning out into 30+ dirs.
- **NN allocation**: Reserves `01-03` in populated dirs for shared orientation shots that many labs reference. P0 already used `04`, `05` under `kudu/`, so P1-P3 continues from wherever the last file in that populated blade-dir stopped. **Empty dirs (`deployment-slots/`) and brand-new dirs (`iam/` in Section 5.1) may start at `01`** because there is no shared-asset collision risk.
- **Slug in filename**: Enables `grep -l 'memlk-' docs/assets/troubleshooting/` to find every asset owned by a specific lab (critical for future cleanup/refactor).
- **State suffix**: Makes filenames self-documenting. Reader can guess content without opening.

### 3.3 NN allocation table (per blade-dir)

Existing `NN` used per blade-dir. New captures MUST start at the next unused number.

| blade-dir | Existing NN in use | Next available NN |
|---|---|---|
| `activity-log/` | 01 | 02 |
| `app-insights/` | 01 | 02 |
| `app-service-plan/` | 01 | 02 |
| `configuration/` | 01, 03 | 02, 04+ |
| `deployment-center/` | 01 | 02 |
| `deployment-slots/` | (empty dir) | 01 |
| `diagnose-and-solve/` | 01, 02, 03 | 04 |
| `health-check/` | 01 | 02 |
| `kudu/` | 01, 02, 03, 04, 05 | 06 |
| `log-analytics/` | 01, 02 | 03 |
| `log-stream/` | 01 | 02 |
| `metrics/` | 01, 02 | 03 |
| `networking/` | 01 | 02 |
| `vnet-integration/` | 01 | 02 |

**Global rule**: When multiple P1-P3 labs both target the same blade-dir, they get sequential NN. Example: if `memlk` needs a `metrics/` capture and `slowstart` also needs one, they get `03-memlk-*.png` and `04-slowstart-*.png` respectively. The allocation order below (Section 6) determines NN assignment.

---

## 4. Shared Asset Protection

### 4.1 Never overwrite these 22 files

The Item 1 sanitizer bug (SameFileError on in-place binary copy) partially protects us. But this plan MUST also prevent accidental overwrite via re-capture. The following 22 files are the CURRENT tracked assets under `docs/assets/troubleshooting/`. All are referenced from multiple documents. Any new capture that would land on one of these filenames is REJECTED.

```
activity-log/01-activity-log.png
app-insights/01-overview.png
app-service-plan/01-asp-overview.png
configuration/01-always-on.png
configuration/03-autoheal-m2-rules.png              (P0 owned)
deployment-center/01-deployment-center.png
diagnose-and-solve/01-overview.png
diagnose-and-solve/02-detector-web-app-down.png
diagnose-and-solve/03-diagnose-hub.png
health-check/01-health-check.png
kudu/01-overview.png
kudu/02-kudu-home.png
kudu/03-process-explorer.png
kudu/04-process-explorer-java.png                   (P0 owned)
kudu/05-webconfig-verified.png                      (P0 owned)
log-analytics/01-logs.png
log-analytics/02-http-500-121-signature.png         (P0 owned)
log-stream/01-log-stream.png
metrics/01-metrics-empty.png
metrics/02-response-time.png
networking/01-networking-hub.png
vnet-integration/01-vnet-integration.png
```

### 4.2 Hot shared assets (>5 refs each)

Assets referenced from 5+ documents across the entire repo. Extra caution: any regression to these breaks many pages.

- `log-analytics/01-logs.png` (25+ refs) — HOTTEST
- `log-stream/01-log-stream.png` (10+ refs)
- `networking/01-networking-hub.png` (7+ refs)
- `diagnose-and-solve/01-overview.png` (6+ refs)

### 4.3 Enforcement

**Pre-capture check** (mandatory before every Playwright screenshot call): The Playwright `browser_run_code_unsafe` invocation MUST write to a path where `NN >= (existing max NN in that blade-dir + 1)`. This will be enforced by an inline check at capture time in Items 4-13.

**Post-capture check**: `git status` should show a NEW file, never a MODIFIED existing PNG. If `git status` shows an M on an existing PNG under `docs/assets/troubleshooting/`, the capture is rejected and the file must be `git checkout`ed back before proceeding.

---

## 5. Per-Lab Capture Plan

Format:
- **Section anchor**: Section 4 subsection where the new image reference will be inserted
- **Filename**: Following pattern from Section 3
- **Purpose**: What the capture proves that prose alone cannot
- **PII scope**: Any sensitive data the capture will show (all must be masked per AGENTS.md 11-rule PII helper)

**Line-number advisory** (Oracle GO condition, Item 2): The line numbers cited throughout Section 5 (e.g., "line 538", "line 473") reflect the file state at plan-approval time. After the first Item touches a lab guide (adding image references, sanitization edits, or the cd-reconnect structural upgrade), subsequent line numbers in the SAME file will drift. Use **the heading text** (e.g., `### 4.4 Baseline process and health evidence`, `### 4.1 Reproduction evidence`) as the **canonical anchor** during Items 3-13 execution. Line numbers are advisory only and MUST NOT be trusted after the first edit in a file.

### 5.1 cd-reconnect-rbac-conflict — 2 captures

**Structural exception + upgrade**: This lab currently has an empty `## 4) Experiment Log` section with no `4.x` subsections. To satisfy the Section 9 success criterion ("all 11 labs have lab-specific captures in Section 4"), Item 4 in the rollout will:

1. **Add ONE new subsection `### 4.1 Reproduction evidence`** to the lab guide during the same commit that adds the captures. Content: a short paragraph introducing the two captures below and how they falsify/confirm the RBAC conflict.
2. Land both new image references INSIDE that new `### 4.1 Reproduction evidence` subsection.

This is a minimal structural upgrade (one new H3 subsection, ~5 lines of prose) — it does NOT restructure the existing Runbook (Section 3) content. Rationale: Oracle's placement rule ("captures go in Section 4 Experiment Log") reflects a design intent that reproduced evidence lives with the experiment record. Forcing captures into Section 3 Runbook would violate that intent. Structural parity with the other 10 labs is the desired end state.

| # | Section anchor (post-upgrade) | Filename | Purpose | PII scope |
|---|---|---|---|---|
| 1 | `### 4.1 Reproduction evidence` (NEW subsection to be added in Item 4 commit) | `activity-log/02-cdrecon-role-assignment-conflict.png` | Show the actual duplicate/conflicting role assignment row in Activity Log with the RBAC operation timestamp, correlation to CD service principal, and result status. Prose says the assignment exists — image proves the operator can find it in the Portal. | Subscription name, user email of assignment creator, resource ID (all masked by helper). |
| 2 | `### 4.1 Reproduction evidence` (same new subsection, second image) | `iam/01-cdrecon-post-recovery-iam.png` | Show the IAM blade AFTER the corrective role removal, with only the expected assignments remaining. Prose says "recovery verified" — image is the evidence. | Object IDs, subscription. |

**Note 1**: `iam/` is a NEW blade-dir. Adds to `docs/assets/troubleshooting/` inventory (previously 14 dirs → 15 after Item 4). Because it is a brand-new dir with no shared-asset collision risk, its first capture starts at `NN=01` per Section 3.2 exception.
**Note 2**: The `### 4.1 Reproduction evidence` insertion point in the lab guide is immediately after the existing `## 4) Experiment Log` heading (currently line 281) and before `## Expected Evidence` (currently line 292). Insertion is additive; no existing content moves.

### 5.2 container-http-pings — 2 captures

Lab conclusion: original hypothesis DISPROVED. Captures must show the actual (unexpected) behavior, not the assumed failure mode.

| # | Section 4 anchor | Filename | Purpose | PII scope |
|---|---|---|---|---|
| 1 | `### 4.4 Baseline process and health evidence` (line 538) | `health-check/02-httppings-baseline-healthy.png` | Show Health Check blade for the deployed app in healthy state (probes returning 200). Contradicts the naive assumption that mismatched WEBSITES_PORT would surface as unhealthy probes on this Linux build. | App name, subscription. |
| 2 | `### 4.7 HTTP log correlation` (line 594) | `log-analytics/03-httppings-empty-http-window.png` | Show KQL editor with executed `AppServiceHTTPLogs` query returning empty result set during the probe window — the executive finding of the lab. Prose says "empty" — image proves the query ran and returned zero rows. | Workspace name (masked). |

### 5.3 deployment-succeeded-startup-failed — 3 captures

Executive lab that establishes the control-plane vs data-plane distinction. Captures must make this distinction visually obvious.

| # | Section 4 anchor | Filename | Purpose | PII scope |
|---|---|---|---|---|
| 1 | `### 4.2 Baseline observations` (line 596) | `deployment-center/02-depstart-successful-deploy.png` | Show Deployment Center with the "wrong module" deploy showing SUCCESS status. Proves the deployment succeeded despite the app being broken. | Deploy log, commit SHA. |
| 2 | `### 4.3 Trigger and recovery observations` (line 641) | `log-analytics/04-depstart-startup-failed-kql.png` | Show KQL query result in Log Analytics with `AppServiceConsoleLogs` rows containing the `ModuleNotFoundError` traceback around the startup timeout window. | Timestamps, subscription. |
| 3 | `### 4.4 Telemetry evidence from KQL artifacts` (line 688) | `log-analytics/05-depstart-runtime-vs-deploy-timeline.png` | Show KQL time-series bar chart with deploy SUCCESS event and container SIGKILL event visible on same timeline. Visual proof of the two-plane split. | None additional. |

### 5.4 dns-vnet-resolution — AUDIT ONLY (0 new captures) + PII sanitization

Per Oracle mandate: verify existing 2 captures render correctly, no new work on captures. **Item 3 also folds in sanitization of 5 pre-existing PII findings currently in this lab guide** (see Section 7.3 for context on pre-existing findings). This is a co-located edit because the audit already touches the file.

Existing captures (line refs):
- Line 106: `vnet-integration/01-vnet-integration.png` (Section 1.5 Private Endpoints)
- Line 473: `networking/01-networking-hub.png` (Section 3.8 HTTP logs)

Pre-existing PII findings to sanitize in Item 3:
- Line 473 (embedded in KQL output example): public IPs `20.200.197.3`, `20.214.209.150`, `20.214.209.176`, `20.214.209.187` → replace each with `<ip-redacted>` (the canonical placeholder documented at `scripts/scan_lab_pii.py` line 22; safe because it contains no numeric octets that the IP regex would match).
- Line 857 (KQL example row): public IP `20.60.200.161` → `<ip-redacted>`.

Audit checklist (Item 3):
- [ ] Both PNG files exist on disk (verified in Section 4.1 above — YES)
- [ ] Both image tags render at their referenced paths (relative `../../assets/troubleshooting/...`)
- [ ] Alt text still accurately describes current Portal UI (visual verification via read tool)
- [ ] Visual PII checklist (see Section 7.4) passes on both PNGs
- [ ] All 5 pre-existing PII findings sanitized to `<ip-redacted>`
- [ ] After sanitization, `python3 scripts/scan_lab_pii.py --paths docs/troubleshooting/lab-guides/dns-vnet-resolution.md` exits 0
- [ ] Cross-reference in `mkdocs build --strict` (no broken image)

### 5.5 failed-to-forward-request — 2 captures

| # | Section 4 anchor | Filename | Purpose | PII scope |
|---|---|---|---|---|
| 1 | `### 4.3 Trigger probe evidence` (line 496) | `kudu/06-fwdreq-process-not-listening.png` | Show Kudu Process Explorer during the trigger window — no Python process bound to expected port, corroborating "127.0.0.1 refuses" symptom. | PIDs, process tree. |
| 2 | `### 4.5 Console KQL analysis (bind evidence)` (line 575) | `log-analytics/06-fwdreq-bind-line-absent.png` | Show KQL query executed against `AppServiceConsoleLogs` with zero result rows — proving the app never emitted the expected bind line. | Query text (safe), workspace. |

### 5.6 intermittent-5xx — 3 captures

| # | Section 4 anchor | Filename | Purpose | PII scope |
|---|---|---|---|---|
| 1 | `### 4.6 KQL HTTP aggregate summary` (line 678) | `log-analytics/07-intmt5xx-request-starvation-kql.png` | Show KQL result table with columns TotalRequests, Requests_2xx, Requests_5xx binned by 1-minute intervals during starvation trigger — the smoking gun. | Timestamps, app name. |
| 2 | `### 4.7 KQL latency profile by endpoint` (line 699) | `log-analytics/08-intmt5xx-latency-percentiles.png` | Show KQL result with P50/P95/P99 latency per endpoint during starvation — visual proof of the queue-vs-fail dichotomy. | None additional. |
| 3 | `### 4.9 Console and platform exports` (line 726) | `metrics/03-intmt5xx-response-time-spike.png` | Show Metrics blade with Response Time chart showing the sustained P95 spike during trigger window with correlated Http5xx counter. | Time range, app name. |

### 5.7 memory-pressure — 3 captures

| # | Section 4 anchor | Filename | Purpose | PII scope |
|---|---|---|---|---|
| 1 | `### 4.3 Mid-leak snapshot` (line 664) | `metrics/04-memlk-heap-mid-leak.png` | Show Metrics blade with Memory Percentage climbing during leak trigger. Prose claims "60% → 85% within 5 minutes" — image proves the trajectory. | App name, timestamps. |
| 2 | `### 4.4 Post-heavy snapshot` (line 687) | `metrics/05-memlk-heap-post-heavy.png` | Show Memory Percentage AND Http5xx correlation on same chart at post-heavy peak — the causal signature. | None additional. |
| 3 | `### 4.7 Trigger response evidence` (line 734) | `log-analytics/09-memlk-5xx-during-pressure.png` | Show KQL result rows with 5xx responses concentrated at peak memory time — proves the trigger→symptom link. | Timestamps. |

### 5.8 no-space-left-on-device — 2 captures

| # | Section 4 anchor | Filename | Purpose | PII scope |
|---|---|---|---|---|
| 1 | `### 4.5 Disk state progression` (line 677) | `log-analytics/10-nolabspace-quota-alert-kql.png` | Show KQL result with `AppServiceFileAuditLogs` (or equivalent quota events) showing the write-failure signature. | Workspace name. |
| 2 | `### 4.10 Health vs write behavior proof table` (line 765) | `kudu/07-nolabspace-df-output.png` | Show Kudu Debug Console `df -h` output with `/home` at ~100% while `/` still healthy — the persistent-vs-ephemeral distinction. | Mount paths (safe). |

### 5.9 slot-swap-config-drift — 2 captures + PII sanitization

**Item 9 also folds in sanitization of 1 pre-existing PII finding currently in this lab guide** (see Section 7.3 for context on pre-existing findings). This is a co-located edit because the capture work already touches the file.

| # | Section 4 anchor | Filename | Purpose | PII scope |
|---|---|---|---|---|
| 1 | `### 4.7 Process restart evidence` (line 630) | `configuration/04-slotswap-sticky-vs-nonsticky.png` | Show Configuration blade with the "Deployment slot setting" checkbox marked on some entries — proves the sticky/non-sticky classification for this lab. | App name. |
| 2 | `### 4.8 /diag/slots snapshots and config hash evolution` (line 641) | `activity-log/03-slotswap-swap-operation.png` | Show Activity Log with the "Swap Web App Slots" operation row expanded — timestamp, initiator, status. | User email (masked), sub ID (masked). |

Pre-existing PII findings to sanitize in Item 9:
- Line 92 (example hostname in prose): `app-staging.azurewebsites.net` → replace with `staging.azurewebsites.net` (which IS on the scanner's `ALLOWED_HOSTNAMES` list at `scripts/scan_lab_pii.py` line 100). Semantically appropriate because the lab discusses staging slot hostnames, and the allowlisted form communicates the same slot semantic without a real deployment identifier.

Verification for Item 9 (in addition to Section 7.2 gates):
- [ ] Pre-existing PII finding at line 92 sanitized to `staging.azurewebsites.net`
- [ ] After sanitization, `python3 scripts/scan_lab_pii.py --paths docs/troubleshooting/lab-guides/slot-swap-config-drift.md` exits 0

### 5.10 slow-start-cold-start — 3 captures

| # | Section 4 anchor | Filename | Purpose | PII scope |
|---|---|---|---|---|
| 1 | `### 4.2 Baseline evidence snapshot` (line 505) | `configuration/05-slowstart-always-on-off.png` | Show Configuration > General Settings with "Always On" explicitly Off (the lab uses B1, which cannot use Always On on B1, but this proves the intentional cold-start baseline). | App name. |
| 2 | `### 4.4 Latency summary statistics` (line 565) | `metrics/06-slowstart-first-vs-warm-response.png` | Show Metrics blade with Response Time line showing dramatic first-request spike followed by warm baseline. Visual demonstration of cold-start signature. | Time range. |
| 3 | `### 4.7 HTTP log observations from export` (line 618) | `log-analytics/11-slowstart-first-request-slow.png` | Show KQL result of first request row with elapsed_ms >>> subsequent rows. Proves the cold-start latency is on the app boot, not the request path. | Workspace. |

### 5.11 snat-exhaustion — 3 captures + PII sanitization

**Item 13 also folds in sanitization of 6 pre-existing PII findings currently in this lab guide** (see Section 7.3 for context on pre-existing findings). This is a co-located edit because the capture work already touches the file.

| # | Section 4 anchor | Filename | Purpose | PII scope |
|---|---|---|---|---|
| 1 | `### 4.6 HTTP KQL analysis` (line 601) | `log-analytics/12-snat-exhaustion-kql.png` | Show KQL query result with SNAT port exhaustion signature (5xx spike + specific error pattern). | Workspace, timestamps. |
| 2 | `### 4.8 Platform KQL analysis` (line 666) | `metrics/07-snat-outbound-connection-spike.png` | Show Metrics blade with Http5xx and (if available) SNAT/Connection metrics showing outbound connection exhaustion window. | None. |
| 3 | `### 4.9 PID rollover evidence` (line 678) | `kudu/08-snat-worker-pid-rollover.png` | Show Kudu Process Explorer with worker PID changed between two snapshots — evidence of SIGKILL cascade. | PIDs. |

Pre-existing PII findings to sanitize in Item 13:
- Line 417 (KQL output example): public IPs `20.200.197.3`, `20.214.209.150`, `20.214.209.176`, `20.214.209.187` → replace each with `<ip-redacted>` (the canonical placeholder documented at `scripts/scan_lab_pii.py` line 22; safe because it contains no numeric octets that the IP regex would match).
- Line 419 (KQL output example): public IPs `20.214.209.150`, `20.214.209.176` → replace each with `<ip-redacted>`.

Verification for Item 13 (in addition to Section 7.2 gates):
- [ ] All 6 pre-existing PII findings sanitized to `<ip-redacted>`
- [ ] After sanitization, `python3 scripts/scan_lab_pii.py --paths docs/troubleshooting/lab-guides/snat-exhaustion.md` exits 0

---

## 6. Rollout Order (Oracle Items 3-13)

Sequential lifecycle per lab. Oracle mandate: **max 2 active deployments simultaneously, delete infra immediately after capture + verify**.

| Oracle Item | Lab | Captures | Est. duration | Est. Azure cost |
|---|---|---:|---|---:|
| 3 | dns-vnet-resolution (AUDIT + PII sanitization per Section 5.4) | 0 | 15-30 min | $0 |
| 4 | cd-reconnect-rbac-conflict | 2 | 1-1.5 hr | $0.50-1.00 |
| 5 | container-http-pings | 2 | 1-1.5 hr | $0.50-1.00 |
| 6 | deployment-succeeded-startup-failed | 3 | 1.5-2 hr | $0.75-1.50 |
| 7 | failed-to-forward-request | 2 | 1-1.5 hr | $0.50-1.00 |
| 8 | slow-start-cold-start | 3 | 1.5-2 hr | $0.75-1.50 |
| 9 | slot-swap-config-drift (+PII sanitization per Section 5.9) | 2 | 1.5-2 hr | $1.00-2.00 (two slots) |
| 10 | no-space-left-on-device | 2 | 1.5-2 hr | $0.75-1.50 |
| 11 | memory-pressure | 3 | 2-2.5 hr | $1.00-2.00 |
| 12 | intermittent-5xx | 3 | 2-2.5 hr | $1.00-2.00 |
| 13 | snat-exhaustion (+PII sanitization per Section 5.11) | 3 | 2-2.5 hr | $1.00-2.00 |
| 14 | `docs(labs): final polish` | 0 | 30-60 min | $0 |

**Total**: 25 new captures + 2 verified → 27 lab-scoped visual evidence items across 11 labs.
**Total Azure**: ~$8-17.5 (well within Oracle's $8-20 envelope).
**Total agent time**: ~16-24 hours (within Oracle's 20-28 envelope).

### 6.1 Rollout order rationale

Ordered by ascending complexity / cost:

1. **Cheapest and simplest first** (cd-reconnect, container-http-pings, failed-to-forward-request): Small infra, single app, one trigger. Establishes lifecycle rhythm before more complex labs.
2. **Deployment + slot labs mid-sequence** (deployment-succeeded-startup-failed, slot-swap-config-drift): Two-deploy scenarios, higher orchestration cost.
3. **Data-heavy labs last** (memory-pressure, intermittent-5xx, snat-exhaustion): Longer trigger duration, more captures per lab, more Metric/KQL time-window judgment required.

### 6.2 Parallel deployment rule

Oracle's standing 14-item mandate allows "Max 2 active lab deployments." Per Oracle's Item 2 GO advisory, **default to ONE active RG at a time**. The 2-max allowance is reserved for schedule recovery (e.g., if a session is running behind and pipelining Item N deployment with Item N-1 capture-phase would recover time). Sisyphus MUST NOT default to 2 concurrent deployments merely because the mandate permits it. If pipelining is used, Item N deployment can start once Item N-1 has entered its "capture phase" (RG deployed, app responding, ready to trigger). Deletion happens serially after each capture completes.

---

## 7. Verification Protocol (per lab)

### 7.1 Slug-to-directory mapping (required for verification commands)

Slugs in Section 2.1 are for asset filenames only. Verification commands MUST use the actual lab directory name under `labs/`:

| Slug (filename use) | Actual lab directory |
|---|---|
| `cdrecon` | `labs/cd-reconnect-rbac-conflict/` |
| `httppings` | `labs/container-http-pings/` |
| `depstart` | `labs/deployment-succeeded-startup-failed/` |
| `dnsvnet` | `labs/dns-vnet-resolution/` |
| `fwdreq` | `labs/failed-to-forward-request/` |
| `intmt5xx` | `labs/intermittent-5xx/` |
| `memlk` | `labs/memory-pressure/` |
| `nolabspace` | `labs/no-space-left-on-device/` |
| `slotswap` | `labs/slot-swap-config-drift/` |
| `slowstart` | `labs/slow-start-cold-start/` |
| `snat` | `labs/snat-exhaustion/` |

### 7.2 Per-lab quality gates

Every Item 4-13 execution MUST complete ALL of the following before commit:

| # | Check | Command / method | Pass criterion |
|---|---|---|---|
| 1 | PII scan on the lab directory (text artifacts) | `python3 scripts/scan_lab_pii.py --paths labs/<actual-dir-name>/` (see 7.1 mapping) | Exit 0 |
| 2 | PII scan on all tracked lab directories (baseline unchanged) | `python3 scripts/scan_lab_pii.py --paths labs/` | Exit 0 |
| 3 | PII scan on touched lab guide file(s) only | `python3 scripts/scan_lab_pii.py --paths docs/troubleshooting/lab-guides/<lab-name>.md` | Exit 0 |
| 4 | **Visual PII verification on each new PNG** (scanner cannot inspect binary PNG content; see 7.4) | Read tool + look_at tool per PNG + visual checklist | 100% pass on checklist |
| 5 | `git status` shows no MODIFIED PNG under `docs/assets/troubleshooting/` | `git status --porcelain docs/assets/troubleshooting/ \| grep '^ M'` | Empty output |
| 6 | All new PNGs have referring `![]()` in a lab guide | `grep -rl '<filename>' docs/troubleshooting/lab-guides/` (note the `-r` for recursive; without it, grep errors "Is a directory") | ≥1 file per PNG |
| 7 | Alt text ≥ 150 chars per new PNG | manual read | 100% pass |
| 8 | `mkdocs build --strict` | `mkdocs build --strict` | Exit 0 |
| 9 | RG deleted post-capture | `az group show --name <RG>` | Returns `ResourceGroupNotFound` |
| 10 | Oracle GO on the lab | Oracle consultation with per-lab context | Explicit "GO" verdict |

**Failure**: If ANY check fails, do NOT commit. Fix or revert, re-run all checks, then commit.

### 7.3 Pre-existing findings outside this plan's scope

`python3 scripts/scan_lab_pii.py --paths labs/ docs/troubleshooting/` currently exits 1 with **35 total findings under `docs/troubleshooting/`**, distributed as:

- **12 findings in `docs/troubleshooting/lab-guides/`** — these ARE addressed by this plan as co-located sanitization in Items 3 (dns-vnet: 5 findings), 9 (slot-swap: 1 finding), and 13 (snat: 6 findings). See Sections 5.4, 5.9, 5.11.
- **20 findings in `docs/troubleshooting/playbooks/**`** — public IPs like `20.200.197.3`, `168.63.129.16`; example hostnames like `app-contoso.azurewebsites.net`, `app-test-windows-20260608.azurewebsites.net`. **OUT of scope** for this plan.
- **3 findings in `docs/troubleshooting/first-10-minutes/`** — **OUT of scope** for this plan.

All findings predate Item 1. Do NOT include `docs/troubleshooting/` in the Check 2 scope during Items 3-13, because the 23 non-lab-guide findings (20 playbooks + 3 first-10-minutes) will remain until they are sanitized in a dedicated commit **after Item 14** (tracked as P2 backlog per Oracle's Item 2 GO advisory). If any Item 4-13 execution introduces NEW findings under `docs/troubleshooting/lab-guides/` (which are touched by this plan), Check 3 will catch it because it targets only the touched file(s). Success criterion in Section 9 gates only `docs/troubleshooting/lab-guides/` for this reason.

### 7.4 Visual PII checklist (Check 4 detail)

`scripts/scan_lab_pii.py` explicitly SKIPS binary files (see the `BINARY_EXTENSIONS` frozenset in `scripts/scan_lab_pii.py` around line 143). Running the scanner on `.png` paths returns exit 0 trivially without inspecting image content. Therefore PNG PII verification MUST be visual, per-file, using the read tool (which renders the PNG) followed by this checklist:

| # | Visual check | Pass criterion |
|---|---|---|
| a | Subscription ID rendered as `00000000-0000-0000-0000-000000000000` | No real GUID visible |
| b | Subscription name rendered as `Visual Studio Enterprise Subscription` | No `MCAPS-*` visible |
| c | Tenant badge rendered as `Contoso` | No `Microsoft Non-Production` visible |
| d | Employee emails rendered as `user@example.com` | No `@microsoft.com` or `@*.onmicrosoft.com` visible |
| e | Employee alias (`ychoe`) rendered as `demouser`; display name (`Yeongseon Choe`) rendered as `Demo User` | No employee identifier visible |
| f | Custom Domain Verification IDs / long uppercase hex tokens rendered as `AAAA…A` (64 chars) | No real long uppercase hex token visible |
| g | Docker container instance IDs (64-char lowercase hex) rendered as `aaaa…a` | No real container SHA visible |
| h | Account-menu avatar masked with **Portal blue `#0078d4` solid rectangle** | NOT a black rectangle; NOT unmasked pixels |
| i | No transient flyout, drawer, notification panel, or tenant switcher visible in frame | Blade only, no overlays |
| j | Alt text in the referring Markdown accurately describes what the PNG shows | Prose matches image |

If ANY item a-j fails on ANY new PNG, the capture is REJECTED. Delete the PNG (`git clean -f`), diagnose (helper regex miss, blade not settled, transient overlay), fix, and re-capture.

---

## 8. Rollback Strategy (per lab)

### 8.1 If capture fails (Playwright error, PII leak visible)

1. Delete the failed PNG: `git clean -f docs/assets/troubleshooting/<blade-dir>/<NN>-<slug>-*.png`
2. Revert any lab guide edits: `git checkout docs/troubleshooting/lab-guides/<lab>.md`
3. Diagnose root cause (PII rule miss, blade not settled, avatar selector broken).
4. Fix and retry.

### 8.2 If commit fails pre-commit hook (PII scan gate)

1. Read hook output for specific findings.
2. Locate offending file(s).
3. If it's the sanitizer bug (SameFileError on binary in-place): apply manual fix or workaround.
4. Never `--no-verify`.

### 8.3 If push is accepted but Oracle finds an issue post-facto

1. `git revert <commit>` — safe, preserves history.
2. Never `git push --force`.
3. Re-plan the lab from clean state.

### 8.4 If Azure RG delete fails

1. `az group delete --name <RG> --yes --no-wait` (async).
2. Verify with `az group list --query "[?name=='<RG>'].name"`.
3. If still present after 10 minutes, escalate to manual portal delete.
4. Never leave lab RGs alive beyond the lab session (drives cost + PII exposure surface).

---

## 9. Success Criteria (end state after Item 14)

- [ ] All 11 P1-P3 labs have ≥1 lab-specific Portal capture in Section 4 (Experiment Log). For `cd-reconnect-rbac-conflict`, this requires the structural upgrade described in Section 5.1 — adding `### 4.1 Reproduction evidence` as part of the Item 4 commit.
- [ ] dns-vnet-resolution passes audit (existing 2 captures verified per Section 5.4)
- [ ] All 27 new/verified captures pass the visual PII checklist in Section 7.4
- [ ] All new captures reference in a lab guide with descriptive alt text ≥150 chars
- [ ] All 12 pre-existing PII findings in the 3 touched lab guides (dns-vnet: 5, slot-swap: 1, snat: 6) sanitized per Sections 5.4, 5.9, 5.11
- [ ] `python3 scripts/scan_lab_pii.py --paths docs/troubleshooting/lab-guides/` exits 0 on `main` after Item 13 commit
- [ ] `mkdocs build --strict` exits 0 on `main`
- [ ] No pre-existing shared asset (Section 4.1 list) was overwritten
- [ ] Zero Azure RGs remain from lab execution
- [ ] Total Azure spend ≤$20
- [ ] Total agent-hours ≤28
- [ ] Oracle GO on each of Items 3-13
- [ ] Oracle GO on Item 14 (final polish)

---

## 10. Open Questions / Risks for Momus + Oracle

### 10.1 Deferred to Momus review

1. **Slug uniqueness**: Are all 11 slugs (`cdrecon`, `httppings`, `depstart`, `dnsvnet`, `fwdreq`, `intmt5xx`, `memlk`, `nolabspace`, `slotswap`, `slowstart`, `snat`) sufficiently distinct and self-explanatory? Or should any be renamed?
2. **NN=04 starting point**: Should we instead start at NN=10 to reserve room for future shared assets? Trade-off: cleaner separation vs. longer filenames.
3. **New blade-dir creation**: Section 5.1 creates `iam/` (a new blade-dir under `docs/assets/troubleshooting/`). Is this acceptable, or should the capture be moved to an existing dir like `activity-log/` or `configuration/`?
4. **Alt text minimum**: Section 7.2 mandates ≥150 chars per alt text. Is this the correct floor? P0 exemplar averaged ~200 chars. AGENTS.md does not specify a minimum.
5. **Line numbers vs anchor text**: Section 5 uses line numbers as the primary anchor for Section 4 subsections. Line numbers drift when files are edited. Should we switch to heading-name-only anchors (e.g., `### 4.3 Mid-leak snapshot`) with line numbers deprecated to comments?

### 10.2 Deferred to Oracle GO

1. **Total capture count (25 new + 2 verified = 27)**: Is this the right density, or should any lab get more/fewer captures?
2. **Rollout order**: Cheapest-first order in Section 6.1 — does Oracle prefer complexity-first or a different sequencing (e.g., data-heavy labs during off-peak Azure hours)?
3. **cd-reconnect structural upgrade (adding `### 4.1 Reproduction evidence`)**: Approved by this plan (Section 5.1) as the minimal fix for structural parity. Requesting explicit Oracle GO on the upgrade approach vs alternatives (exempt from Section 4 requirement, or defer the lab).
4. **Item 14 scope**: What does "final polish" concretely include? Cross-reference sanity checks, alt-text consistency, image ordering per lab, or something else?
5. **Sanitizer bug interaction**: Item 1's known SameFileError on in-place binary copy — does this affect Items 4-13 (which produce new PNGs, not modify existing ones)? Believed no impact, but worth explicit sign-off.

### 10.3 Known dependencies on external state

- **Explore agents broken**: Currently returning "Model not found: opencode/gpt-5-nano". Sisyphus falling back to direct grep/glob tools. Not blocking, but if fixed, future lab lifecycle sessions could parallelize exploration.
- **App and Infra CI failure**: Pre-existing on `origin/main` (npm audit findings on OpenTelemetry deps). Not introduced by Item 1. Out-of-scope for Item 2 but noted for visibility.
- **Oracle session `ses_0dee15ee0ffepTyQ80YQ3Z0hZz`**: Should be resumed for all subsequent Oracle consultations (Items 3-14) to preserve context and reduce token cost.

---

## 11. Appendix: File and section reference

### 11.1 Existing image references audit (27 total, all shared)

Full inventory used to construct Section 4 protection list — verified by grep on 2026-07-02:

```
docs/troubleshooting/lab-guides/index.md:47                          -> diagnose-and-solve/01-overview.png
docs/troubleshooting/lab-guides/container-http-pings.md:103          -> health-check/01-health-check.png
docs/troubleshooting/lab-guides/container-http-pings.md:401          -> log-stream/01-log-stream.png
docs/troubleshooting/lab-guides/cd-reconnect-rbac-conflict.md:225    -> activity-log/01-activity-log.png
docs/troubleshooting/lab-guides/deployment-succeeded-startup-failed.md:135  -> deployment-center/01-deployment-center.png
docs/troubleshooting/lab-guides/deployment-succeeded-startup-failed.md:513  -> log-stream/01-log-stream.png
docs/troubleshooting/lab-guides/dns-vnet-resolution.md:106           -> vnet-integration/01-vnet-integration.png
docs/troubleshooting/lab-guides/dns-vnet-resolution.md:473           -> networking/01-networking-hub.png
docs/troubleshooting/lab-guides/failed-to-forward-request.md:200     -> diagnose-and-solve/02-detector-web-app-down.png
docs/troubleshooting/lab-guides/failed-to-forward-request.md:393     -> log-stream/01-log-stream.png
docs/troubleshooting/lab-guides/intermittent-5xx.md:434              -> app-insights/01-overview.png
docs/troubleshooting/lab-guides/intermittent-5xx.md:501              -> log-analytics/01-logs.png
docs/troubleshooting/lab-guides/memory-pressure.md:549               -> diagnose-and-solve/03-diagnose-hub.png
docs/troubleshooting/lab-guides/memory-pressure.md:555               -> metrics/01-metrics-empty.png
docs/troubleshooting/lab-guides/no-space-left-on-device.md:109       -> app-service-plan/01-asp-overview.png
docs/troubleshooting/lab-guides/no-space-left-on-device.md:478       -> log-stream/01-log-stream.png
docs/troubleshooting/lab-guides/slot-swap-config-drift.md:353        -> configuration/01-always-on.png
docs/troubleshooting/lab-guides/slot-swap-config-drift.md:437        -> activity-log/01-activity-log.png
docs/troubleshooting/lab-guides/slow-start-cold-start.md:173         -> configuration/01-always-on.png
docs/troubleshooting/lab-guides/slow-start-cold-start.md:398         -> log-stream/01-log-stream.png
docs/troubleshooting/lab-guides/slow-start-cold-start.md:404         -> metrics/02-response-time.png
docs/troubleshooting/lab-guides/snat-exhaustion.md:411               -> diagnose-and-solve/01-overview.png
docs/troubleshooting/lab-guides/snat-exhaustion.md:417               -> networking/01-networking-hub.png
docs/troubleshooting/lab-guides/windows-java-httpplatformhandler-timeout.md:167  -> kudu/04-process-explorer-java.png
docs/troubleshooting/lab-guides/windows-java-httpplatformhandler-timeout.md:499  -> kudu/05-webconfig-verified.png
docs/troubleshooting/lab-guides/windows-java-httpplatformhandler-timeout.md:525  -> log-analytics/02-http-500-121-signature.png
docs/troubleshooting/lab-guides/windows-java-httpplatformhandler-timeout.md:633  -> configuration/03-autoheal-m2-rules.png
```

### 11.2 Confirmed lab structural uniformity

10 of 11 P1-P3 labs use the standard 10-section structure with `## 4) Experiment Log` populated by 4.1-4.N subsections. Exception: `cd-reconnect-rbac-conflict` (340 lines) has an empty Section 4 and uses non-numbered subheadings under Section 3. Section 5.1 above addresses this exception.

### 11.3 Frozen inputs (do not change without re-review)

- Lab slug table (Section 2.1)
- NN allocation table (Section 3.3)
- 22 protected asset filenames (Section 4.1)
- Per-lab capture plan (Section 5)
- Rollout order (Section 6)

If any of these need to change during Items 4-13 execution, HALT the lab, update this plan, re-invoke Momus and Oracle, and only then resume.

---

## 12. Item 3 Discovery: Shared PNG Pixel-Level PII (Oracle-Deferred)

**Added**: 2026-07-02 during Item 3 execution
**Oracle GO**: session `ses_0dea82a38ffefuhEqSBpPnSSPN`, task `bg_da3c6b53`
**Blocks Item 3**: NO (Oracle verdict on GO/NO-GO 2: audit-only mandate stands)

### 12.1 Discovery

During Item 3 visual PII verification of `docs/assets/troubleshooting/networking/01-networking-hub.png` (referenced by 7+ documents per Section 4.2 hot-asset list), the PNG pixels were found to display the same real Azure App Service platform-pool public IPs that Item 3 just sanitized from the referring alt text — `20.200.197.3` (Inbound IPv4) plus ~30 outbound IPv4 addresses (`20.214.209.150`, `20.214.209.176`, etc.). IPv6 outbound addresses (`2603:1040:f05:3::208`, ...) are also visible in pixels and not currently flagged by the scanner.

Text was sanitized to `<ip-redacted>` in the Item 3 commit; pixels remain. This creates a temporary drift on Section 7.4 checklist item (j) "alt text accurately describes the image" for this specific shared PNG.

### 12.2 Oracle-approved deferral rationale

Per Oracle GO/NO-GO 2 (verdict: GO): "The pixel-level visibility does not block Item 3 because your approved scope was audit-only, no re-capture, no shared-asset overwrite. Reverting the text redaction would knowingly reintroduce a scanner-visible leak, which is worse than accepting temporary text/pixel drift on a protected shared PNG."

Per Oracle GO/NO-GO 1 (verdict: MODIFY): Treat public IPs as "redactable sensitive operational identifiers" for docs and screenshots. The scanner behavior is the correct repo-wide precedent; the capture helper's lack of IP masking is a historical gap to close in P2, not a reason to block Item 3.

### 12.3 P2 backlog — split into two independent follow-ups (Oracle GO/NO-GO 3 MODIFY)

Oracle rejected Sisyphus's proposal to bundle everything into one coordinated post-Item-14 commit. Instead, split into:

**P2-A: Text-only cleanup** (low risk, quick, no shared-asset touch)

Scope: sanitize the 23 remaining text-level scanner findings under `docs/troubleshooting/` outside `lab-guides/`:
- 20 findings in `docs/troubleshooting/playbooks/**`
- 3 findings in `docs/troubleshooting/first-10-minutes/`

Method: same `<ip-redacted>` placeholder replacement pattern used in Item 3.
Verification: `python3 scripts/scan_lab_pii.py --paths docs/troubleshooting/` exit 0.
Timing: MAY run in parallel with Items 4-13 (does not touch labs). RECOMMENDED to run after Item 14 to avoid interleaving with lab captures.

**P2-B: Pixel remediation (coordinated commit, higher risk)**

Scope in dependency order:
1. Extend `scripts/portal-capture-helpers.js` `PII_RULES` with a public-IP masking rule (mask real `20.x`, `40.x`, `168.63.129.16` in text nodes / aria-labels of captured Portal blades). **Also decide IPv6 policy** (Oracle-flagged gap; current scanner does not cover IPv6 either).
2. Update `AGENTS.md` "PII Replacement Rules" table with the new public-IP rule.
3. Re-capture shared PNGs affected by pixel-level IP visibility. Known affected shared PNG: `networking/01-networking-hub.png`. Full audit required — may include others (e.g., if other Portal blades display outbound IP lists).
4. Realign alt-text across all 7+ documents referencing each re-captured shared PNG so check (j) invariant is restored repo-wide.
5. `mkdocs build --strict` exit 0 and full scanner clean.

Method: coordinated commit `docs(assets): sanitize pixel-level public IPs on shared PNGs`. MUST be reviewed by both Momus and Oracle before merge because it changes multiple docs simultaneously.
Timing: AFTER Item 14 AND after P2-A. Requires Azure deploy to re-capture (~$0.50-2.00 depending on how many shared PNGs need re-capture).

### 12.4 Repeat-drift risk during Items 4-13 (Oracle-flagged)

Because `networking/01-networking-hub.png` is also referenced by `snat-exhaustion.md` (Item 13 target, line 417 per Section 5.11), Item 13 will produce the same alt-text/pixel drift on the same shared asset when Item 13 sanitizes its 6 pre-existing IPs in the surrounding text.

**Mitigation during Items 4-13**: For each Item that touches a lab guide referencing `networking/01-networking-hub.png`, document the known drift in the commit message rather than treating it as a new discovery. Do NOT modify or re-capture the shared PNG during Items 4-13. Do NOT block the item.

**Central tracking**: This section (12) is the canonical record of the shared-asset drift. Future items should reference it, not re-open it.

### 12.5 IPv6 policy decision (deferred to P2-B design)

Current state:
- `scripts/scan_lab_pii.py`: **does not** flag IPv6 addresses (regex covers IPv4 only).
- `scripts/portal-capture-helpers.js` `PII_RULES`: **does not** cover IPv6.
- Shared PNGs contain real IPv6 outbound addresses (`2603:1040:*::*`) that are Azure-controlled platform ranges.

Decision required in P2-B design: whether to extend both scanner and helper to cover IPv6. Trade-off: IPv6 addresses in Azure's `2603:*` and `2a01:*` ranges are Microsoft-owned aggregates rather than customer-scoped identifiers — arguably lower sensitivity than IPv4 stamp assignments. But consistency with IPv4 policy argues for uniform treatment.

Sisyphus's default recommendation (pending P2-B review): extend both scanner and helper to cover IPv6, using placeholder `<ipv6-redacted>`.

---

**End of plan.**
