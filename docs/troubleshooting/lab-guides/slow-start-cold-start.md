---
content_sources:
  diagrams:
    - id: troubleshooting-lab-guides-slow-start-cold-start-diagram-1
      type: flowchart
      source: self-generated
      justification: "Self-generated troubleshooting diagram synthesized from Microsoft Learn diagnostics and Azure App Service incident guidance for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-http-502-http-503
    - id: troubleshooting-lab-guides-slow-start-cold-start-diagram-2
      type: sequenceDiagram
      source: self-generated
      justification: "Self-generated troubleshooting diagram synthesized from Microsoft Learn diagnostics and Azure App Service incident guidance for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-http-502-http-503
    - id: troubleshooting-lab-guides-slow-start-cold-start-diagram-3
      type: flowchart
      source: self-generated
      justification: "Self-generated troubleshooting diagram synthesized from Microsoft Learn diagnostics and Azure App Service incident guidance for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-http-502-http-503
    - id: troubleshooting-lab-guides-slow-start-cold-start-diagram-4
      type: flowchart
      source: self-generated
      justification: "Self-generated troubleshooting diagram synthesized from Microsoft Learn diagnostics and Azure App Service incident guidance for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-http-502-http-503
    - id: troubleshooting-lab-guides-slow-start-cold-start-diagram-5
      type: graph
      source: self-generated
      justification: "Self-generated troubleshooting diagram synthesized from Microsoft Learn diagnostics and Azure App Service incident guidance for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-http-502-http-503
---
# Lab Guide: Slow Start (Cold Start) vs Real Regression

This Level 3 lab guide reproduces a slow-start scenario on Azure App Service Linux and shows how to separate platform/container startup cost from steady-state request latency. The experiment uses a Python Flask app that intentionally sleeps for 30 seconds during startup and captures HTTP, platform, and app-level evidence.

---

## Lab Metadata

| Attribute | Value |
|---|---|
| Difficulty | Intermediate |
| Estimated Duration | 45-60 minutes |
| Tier | Basic |
| Failure Mode | Slow startup initialization is mistaken for steady-state performance regression |
| Skills Practiced | Cold-start analysis, startup-vs-request latency separation, platform lifecycle interpretation, KQL timing correlation |

!!! info "What this lab is designed to prove"
    This lab is intentionally built to challenge a common assumption: "slow first hit means app regression."
    
    The artifact evidence shows a different outcome:
    
    - Application startup takes ~31.3 seconds.
    - HTTP first-request latency in this run is still sub-second (~0.8-0.9s).
    - Most startup cost is absorbed before customer request timing starts.

---

## 1) Background

Cold start on App Service Linux is not one single operation. It is a multi-stage timeline that includes platform orchestration and application initialization.

For accurate troubleshooting, you must identify **where time is spent**:

1. Platform work (worker assignment, network setup, volume mounts, image pull, container creation).
2. Runtime boot work (Oryx startup script, Python/Gunicorn process boot).
3. Application startup work (module import, global init, user startup logic).
4. Warm-up probes and readiness transitions.
5. First customer request routing.

### 1.1 Cold-start phase model

<!-- diagram-id: troubleshooting-lab-guides-slow-start-cold-start-diagram-1 -->
```mermaid
flowchart TD
    A[Trigger: deploy/restart/recycle/scale-out] --> B[Worker selected and site state enters Starting]
    B --> C[Platform actions: establish network + mount volumes]
    C --> D[Container image pull/check]
    D --> E[Container created and running]
    E --> F[Runtime startup script and process boot]
    F --> G[Application initialization]
    G --> H[Warm-up probe loop]
    H --> I[Warm-up probe success]
    I --> J[Site state Started]
    J --> K[Customer request served]
```

### 1.2 Platform cold start vs app cold start

Two different cold-start scopes matter operationally:

| Scope | What changed | Typical indicators | Common triggers |
|---|---|---|---|
| Platform cold start | New container lifecycle on worker (site not running) | `AppServicePlatformLogs` show `PullingImage`, `CreatingContainer`, `WarmUpProbeSucceeded` | Restart, scale-out, recycle, host movement |
| App cold start | App process restarts within an existing site context | New app process start timestamp, startup logs, changed PID | Code deploy, process crash, app recycle |

In incident response, teams often mix these two and over-attribute latency to application code. This lab separates them with multiple evidence channels.

### 1.3 App under test: why startup is intentionally slow

The lab app contains `time.sleep(30)` during module import:

```python
INITIALIZATION_STARTED_AT = time.time()
...
time.sleep(30)
...
INITIALIZATION_COMPLETED_AT = time.time()
STARTUP_DURATION_SECONDS = INITIALIZATION_COMPLETED_AT - INITIALIZATION_STARTED_AT
```

The app then exposes startup telemetry via `/timing` and `/diag/stats`.

This makes the startup burden explicit and measurable.

### 1.4 Request-path and startup-path timing are not equivalent

A first customer request can be slow because:

- It waits behind startup completion.
- It hits a worker that has not completed warm-up.
- It reaches the app only after a platform probe success boundary.

But a first customer request can also be **fast** if startup cost was already paid during platform warm-up interval. That exact condition is demonstrated in this lab.

### 1.5 Timeline diagram: where cold-start latency can hide

<!-- diagram-id: troubleshooting-lab-guides-slow-start-cold-start-diagram-2 -->
```mermaid
sequenceDiagram
    participant Client as Client
    participant FrontEnd as App Service Front End
    participant Platform as Linux Worker Orchestrator
    participant Container as Site Container
    participant App as Gunicorn/Flask App

    Platform->>Container: Create + start container
    Container->>App: Runtime boot + app import
    Note over App: time.sleep(30) executes
    Platform->>App: Warm-up probe cycle
    App-->>Platform: Probe success
    Platform-->>FrontEnd: Site started and routable
    Client->>FrontEnd: First request /timing
    FrontEnd->>App: Forward request
    App-->>Client: HTTP 200 in ~0.8-0.9s
```

### 1.6 Warm-up and mitigation controls

App Service offers several warm-up and cold-start mitigation knobs. Their effect depends on plan tier, runtime, and deployment pattern.

| Control | Purpose | Lab relevance |
|---|---|---|
| Always On | Keep app active and reduce idle cold starts | Disabled in this lab by design |
| Health check | Keep only healthy instances in rotation | Not set in this lab (`healthCheckPath: null`) |
| `WEBSITE_SWAP_WARMUP_PING_PATH` | Warm path for slot swap readiness | Not used in this single-slot lab |
| Slot warm-up and swap | Shift startup cost pre-cutover | Covered in companion slot-swap lab |

!!! warning "Tier behavior matters"
    On lower tiers, mitigation options may be limited or operationally different from Standard/Premium patterns.
    Always interpret cold-start behavior in context of App Service plan capability.

#### Portal view: General settings (Always on toggle)

[[[ shot("troubleshooting--configuration--01-always-on") ]]]

The `Always on` toggle lives under `Settings > Configuration > General settings`. In this capture it is `disabled` - the same configuration this lab deploys via Bicep so that the cold-start path is exercised on every restart. Toggle this `on` to keep the worker warm between requests, which prevents the platform from unloading the site after the default idle timeout and avoids paying the container plus runtime plus app-import cost on the next user hit. Note the tier and feature limitations from the warning above: `Always on` requires a Basic tier or higher (Free and Shared do not support it), so the mitigation you choose must match the plan you are running on. Use this blade to confirm `Always on` state before drawing conclusions about cold-start frequency or asking app teams to investigate "slow first hit" reports.

### 1.7 Why this matters for troubleshooting quality

Without phase-level attribution, teams may:

- Escalate false regressions to app teams.
- Roll back healthy releases.
- Miss platform lifecycle causes (restart/recycle/startup probe delays).

This guide aligns evidence from:

1. App telemetry (`startup_duration`, process timestamps).
2. HTTP logs (`TimeTaken`, paths, status).
3. Platform logs (container lifecycle and warm-up transitions).

### 1.8 MS Learn grounding for startup behavior

Core conceptual docs used by this runbook:

- App configuration and app settings behavior.
- Diagnostics logging for App Service.
- Hosting plan tier behavior.
- Staging/slot warm-up concepts for production deployments.

Links are listed in [Sources](#sources).

---

## 2) Hypothesis

### 2.1 Formal hypothesis statement

> On a B1 Linux App Service plan, cold start adds measurable latency to lifecycle readiness after restart, with the majority of time spent in container/application initialization rather than in the first user HTTP request itself.

### 2.2 Causal chain

<!-- diagram-id: troubleshooting-lab-guides-slow-start-cold-start-diagram-3 -->
```mermaid
flowchart TD
    A[Restart or deployment trigger] --> B[Container lifecycle starts]
    B --> C[Runtime and app initialization]
    C --> D[Warm-up probe loop]
    D --> E[Site enters Started state]
    E --> F[First customer request]
    F --> G[Observed HTTP latency]

    C --> H["App startup_duration metric (~31s)"]
    D --> I[Platform warm-up success signal]
    G --> J[Request-level TimeTaken in HTTP logs]
```

### 2.3 Proof criteria

All of the following support the hypothesis:

1. Startup telemetry (`/diag/stats`, `/timing`) shows ~30+ second app initialization.
2. Platform logs include explicit startup lifecycle and probe success events.
3. HTTP first-hit latency is not necessarily equal to startup duration.
4. Steady-state warm requests remain in similar low range after startup.
5. Evidence shows startup cost can be paid before first external request.

### 2.4 Disproof criteria

Any of these weakens the hypothesis:

- App startup telemetry is short (<2s), but first request repeatedly spikes high.
- Platform logs show no lifecycle transitions near slow periods.
- Warm requests remain persistently degraded after startup window.
- Latency increase correlates with sustained app-level regression signals (CPU, errors, dependency slowdowns) rather than startup transitions.

### 2.5 Expected outcomes for this specific lab build

Because startup has an intentional `sleep(30)`, we expect:

- Startup metrics around ~31 seconds.
- Warm-up/probe lifecycle in platform logs.
- Warm and "cold-labeled" HTTP requests both in sub-second band for this run.
- Interpretation: startup delay is real, but not visible as a giant first HTTP spike.

### 2.6 Counter-hypothesis tested implicitly

Counter-hypothesis:

> "If startup is 31 seconds, first HTTP request must also be ~31 seconds."

This lab disproves that simplification and demonstrates why startup-window timing and customer request timing can diverge.

---

## 3) Runbook

This section is execution-oriented and uses long-form Azure CLI flags only.

### 3.1 Prerequisites

| Tool | Check command |
|---|---|
| Azure CLI | `az version` |
| Bash | `bash --version` |
| Python 3 | `python3 --version` |
| Authenticated session | `az account show` |

### 3.2 Variables

```bash
export RG="rg-lab-coldstart"
export LOCATION="koreacentral"
export BASE_NAME="labcold"
```

Use these variables in subsequent commands:

### 3.3 Deploy infrastructure

```bash
az group create \
  --name "$RG" \
  --location "$LOCATION"

az deployment group create \
  --resource-group "$RG" \
  --template-file "labs/slow-start-cold-start/main.bicep" \
  --parameters "baseName=$BASE_NAME"
```

| Command/Flag | Purpose |
|---|---|
| `az group create` | Create the resource group for all lab resources |
| `--name` | Resource group name |
| `--location` | Azure region for deployment |
| `az deployment group create` | Deploy lab infrastructure using Bicep template |
| `--resource-group` | Target resource group for the deployment |
| `--template-file` | Path to Bicep template defining App Service plan and web app for cold-start testing |
| `--parameters` | Override base name prefix for resource naming |

Capture app name:

```bash
APP_NAME=$(az webapp list \
  --resource-group "$RG" \
  --query "[0].name" \
  --output tsv)

APP_HOSTNAME=$(az webapp show \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --query "defaultHostName" \
  --output tsv)

APP_URL="https://$APP_HOSTNAME"
```

| Command | Purpose |
|---------|---------|
| `az webapp list --resource-group "$RG" --query "[0].name" --output tsv` | Lists web apps in the lab resource group and returns the first app name. |
| `--resource-group "$RG" --query "[0].name" --output tsv` | Limits the app list to this resource group. |
| `--query "[0].name" --output tsv` | Selects the `name` field from the first item in the returned web-app array. |
| `--output tsv` | Returns the app name as plain text for shell variable assignment. |
| `az webapp show --resource-group "$RG" --name "$APP_NAME" --query "defaultHostName" --output tsv` | Retrieves the app's default hostname so the runbook can build the public URL. |
| `--resource-group "$RG" --name "$APP_NAME" --query "defaultHostName" --output tsv` | Looks up the app in this resource group. |
| `--name "$APP_NAME" --query "defaultHostName" --output tsv` | Targets this web app. |
| `--query "defaultHostName" --output tsv` | Projects only the app's `defaultHostName` field. |
| `--output tsv` | Returns the hostname as plain text for shell variable assignment. |

### 3.4 Verify baseline configuration

Run these before trigger to confirm plan behavior assumptions:

```bash
az webapp config show \
  --resource-group "$RG" \
  --name "$APP_NAME"

curl --silent --show-error "$APP_URL/health"
curl --silent --show-error "$APP_URL/diag/stats"
curl --silent --show-error "$APP_URL/timing"
```

| Command/Flag | Purpose |
|---|---|
| `az webapp config show` | Retrieve app configuration to confirm plan tier and runtime settings |
| `--resource-group` | Resource group containing the app |
| `--name` | Web app name |

Observed baseline artifact evidence (sanitized):

```json
{"status":"healthy"}
```

```json
{"startup_duration_seconds":31.267,"request_count":4,"pid":1896}
```

```json
{"startup_duration":31.267,"uptime_seconds":1116.417}
```

### 3.5 Trigger measurement workflow

Use the provided trigger script:

```bash
bash "labs/slow-start-cold-start/trigger.sh" "$RG" "$BASE_NAME" "$LOCATION"
```

The script performs:

1. Infra deployment and zip deploy.
2. Initial request latency capture.
3. Ten warm `/fast` requests.
4. App restart.
5. Post-restart first request capture.
6. Warm-post request series.

### 3.6 Manual fallback (if you do not use trigger.sh)

#### 3.6.1 Deploy app package

```bash
az webapp deploy \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --src-path "labs/slow-start-cold-start/app.zip" \
  --type zip \
  --clean true \
  --restart true
```

| Command/Flag | Purpose |
|---|---|
| `az webapp deploy` | Deploy application package to the web app |
| `--resource-group` | Resource group containing the app |
| `--name` | Web app name |
| `--src-path` | Path to the pre-built ZIP package |
| `--type zip` | Deploy as ZIP package |
| `--clean true` | Remove existing files before deployment to ensure a clean state |
| `--restart true` | Restart the app to trigger a cold start for measurement |

#### 3.6.2 Measure request latency

```bash
curl --silent --show-error --output /dev/null --write-out "%{time_total}\n" "$APP_URL/timing"
curl --silent --show-error --output /dev/null --write-out "%{time_total}\n" "$APP_URL/fast"
```

#### 3.6.3 Force restart and re-measure

```bash
az webapp restart \
  --resource-group "$RG" \
  --name "$APP_NAME"

curl --silent --show-error --output /dev/null --write-out "%{time_total}\n" "$APP_URL/timing"
```

| Command/Flag | Purpose |
|---|---|
| `az webapp restart` | Force a cold start by restarting the app container |
| `--resource-group` | Resource group containing the app |
| `--name` | Web app name to restart |

### 3.7 Collect KQL evidence

#### Portal view: Log stream (live startup tail)

[[[ shot("troubleshooting--log-analytics--11-slowstart-first-request-slow") ]]]

**Purpose**: Prove programmatically that the pre-restart warm requests and post-restart elevated-latency requests observable in the archived export (section 4.7) are reproducible against a freshly-deployed instance, and that the platform-side aggregate spike shown in section 4.4.1 is composed of real per-request rows with a clear before/after boundary consistent with the restart window that is confirmed independently by the platform events in section 4.8.

**Look for**:

- Query returns exactly 18 rows with all `ScStatus` values equal to 200 (no errors, so the elevation is pure latency, not failure).
- Rows 1-11 (pre-restart warm) show `TimeTaken` values in the 2-43 ms range — these are the same server-side latency shape as the archived HTTP log rows in section 4.7.
- A ~20-second gap exists between row 11 (`1:39:28.137 AM`) and row 12 (`1:39:48.738 AM`) — this gap is consistent with a container restart window during which the app is not serving requests; the causal restart events (`PullingImage`, `CreatingContainer`, `Site startup probe succeeded`) are confirmed independently in section 4.8.
- Rows 12-18 (post-restart) show `TimeTaken` values in the 22-180 ms range with the first `/fast` request after the restart at 122 ms and the last `/timing` at 180 ms — 3-18x slower than the warm baseline for the same endpoint.
- `TimeTaken` for `/timing` is 43 ms pre-restart and 51 ms and 180 ms post-restart — even the intentionally-slow endpoint that already waits internally shows measurable additional overhead in the first post-restart bucket.

**Expected result**: Two distinct latency clusters separated by a ~20-second gap, with the post-restart cluster showing per-request `TimeTaken` values several times larger than the pre-restart cluster, matching the aggregate Response Time spike in section 4.4.1 and the archived HTTP log observations in section 4.7.

**Next step**: Cross-reference the same window in `AppServicePlatformLogs` (section 4.8) to confirm the restart signature (`PullingImage`, `CreatingContainer`, `Site startup probe succeeded`) that explains why the post-restart requests pay this additional overhead.

### 4.8 Platform log observations from export

Representative lifecycle events:

| TimeGenerated (UTC) | Level | Message excerpt |
|---|---|---|
| 2026-04-04T05:13:27.5582572Z | Informational | `Action: PullingImage` |
| 2026-04-04T05:13:30.1113279Z | Informational | `Action: CreatingContainer ... successfully created and is running` |
| 2026-04-04T05:13:30.3607994Z | Informational | `Container start method finished after 2764 ms` |
| 2026-04-04T05:14:38.516515Z | Informational | `Site startup probe succeeded after 68.0508489 seconds.` |
| 2026-04-04T05:14:39.0727291Z | Informational | `Site started.` |
| 2026-04-04T05:45:52.5352677Z | Informational | `Image ... is pulled from registry` |
| 2026-04-04T05:45:54.5837782Z | Informational | `Container start method finished after 6054 ms` |

Interpretation:

- Platform-level startup timeline includes warm-up/probe duration significantly larger than per-request latency.
- This aligns with app-level startup-duration telemetry near 31 seconds.

### 4.9 Core finding and explanation

!!! success "Key finding (validated)"
    Startup duration is ~31.3 seconds, but cold-vs-warm request latency difference is minimal in this run (both mostly ~0.8-1.0 seconds).
    
    The startup penalty is primarily paid during container initialization and warm-up probe progression before customer request timing is observed.

This is exactly the analytical outcome this lab was designed to demonstrate.

### 4.10 Hypothesis verdict

| Criterion | Result | Evidence |
|---|---|---|
| Startup duration around 30+ seconds exists | Supported | `/timing`, `/diag/stats` (~31.267 to 31.305) |
| Platform startup lifecycle visible | Supported | `kql-platform-20260404T060610Z.json` |
| First HTTP request necessarily equals startup duration | Not supported (as expected) | `cold-latency` 0.799-0.938 s |
| Warm steady state remains similar band | Supported | warm and warm-post datasets |

Final verdict: **Hypothesis supported**, with nuanced interpretation that startup cost and request latency can be decoupled in observed telemetry windows.

### 4.11 Practical troubleshooting implications

1. Do not classify startup-duration telemetry as app regression without warm-path comparison.
2. Anchor triage on **time-window correlation** between platform lifecycle and HTTP latency.
3. Maintain separate dashboards/queries for:
    - startup lifecycle transitions,
    - first-hit behavior,
    - warm steady-state behavior.
4. Use slot warm-up strategies for production rollout if startup is expensive.

### 4.12 Reproducibility notes

- All artifact values in this document were copied from sanitized files in the repository.
- Subscription IDs and host domains are redacted where present.
- No synthetic placeholder values were inserted into experiment tables.

---

## Expected Evidence

This section defines what you SHOULD observe at each phase of the lab. Use it to validate your investigation is on track.

### Before Trigger (Baseline)

| Evidence Source | Expected State | What to Capture |
|---|---|---|
| Site runtime state | App is stopped, restarted, or otherwise cold before first measurement | Resource state and trigger/restart timestamp |
| Baseline endpoints (`/health`, `/diag/stats`) | App becomes healthy when started | Baseline health and startup telemetry snapshots |
| Plan/runtime context | Cold-start-prone configuration is present | B1 Linux context and `AlwaysOn=false` for this lab |

### During Incident

| Evidence Source | Expected State | Key Indicator |
|---|---|---|
| App timing endpoint (`/timing`) | First post-cold-start measurement reflects startup burden | `startup_duration` around `31.499s` |
| AppServicePlatformLogs | Startup probe lifecycle explicitly recorded | `Site startup probe succeeded` after startup window |
| AppServiceHTTPLogs | Requests return 200 while warm-state calls are much faster | `/timing` 200 with `TimeTaken=11ms` after warmup |

### After Recovery

| Evidence Source | Expected State | Key Indicator |
|---|---|---|
| Subsequent request timings | Warm requests remain low-latency | Repeated calls in ~`11-41ms` band |
| Worker/process telemetry | Startup cost is no longer paid per request | Stable PID/uptime and normal `/diag/stats` progression |
| Incident conclusion | Cold start explains initial delay, not steady-state regression | Warm traffic remains healthy and fast |

### Evidence Timeline

<!-- diagram-id: troubleshooting-lab-guides-slow-start-cold-start-diagram-5 -->
```mermaid
graph TD
    A[Baseline Capture] --> B[Trigger Fault]
    B --> C[During: Collect Evidence]
    C --> D[After: Compare to Baseline]
    D --> E[Verdict: Confirmed/Falsified]
```

### Evidence Chain: Why This Proves the Hypothesis

!!! success "Falsification Logic"
    If you observe a long startup duration (~31.499s) during cold start, platform startup-probe success events, and then rapid warm-path request timings (for example 11-41ms), the hypothesis is CONFIRMED because initialization cost is front-loaded into container/runtime startup rather than persistent request execution.
    
    If you do NOT observe warm-path recovery (for example requests remain slow after startup stabilizes), the hypothesis is FALSIFIED — consider alternatives such as real app regression, dependency latency, CPU pressure, or plan capacity limits.

## Clean Up

```bash
az group delete --name "$RG" --yes --no-wait
```

| Command/Flag | Purpose |
|---|---|
| `az group delete` | Remove the entire resource group and all lab resources |
| `--name` | Resource group to delete |
| `--yes` | Skip confirmation prompt |
| `--no-wait` | Return immediately without waiting for deletion to complete |

## Related Playbook

- [Slow Start (Cold Start)](../playbooks/performance/slow-start-cold-start.md)

## See Also

- [Playbook: Slow Start (Cold Start)](../playbooks/performance/slow-start-cold-start.md)
- [Playbook: Warm-up vs Health Check](../playbooks/startup-availability/warmup-vs-health-check.md)
- [KQL: Restart Timing Correlation](../kql/restarts/restart-timing-correlation.md)
- [KQL: Slowest Requests by Path](../kql/http/slowest-requests-by-path.md)
- [Troubleshooting Method](../methodology/troubleshooting-method.md)

## Sources

- [Set up staging environments in Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/deploy-staging-slots)
- [Configure an App Service app in Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/configure-common)
- [Enable diagnostic logging for apps in Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs)
- [Monitor Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/monitor-app-service)
- [App Service plan overview](https://learn.microsoft.com/en-us/azure/app-service/overview-hosting-plans)
