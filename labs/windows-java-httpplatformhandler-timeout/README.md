# Windows App Service Java SE + httpPlatformHandler timeout lab

Multi-stage troubleshooting lab for a production symptom seen on Azure App Service Windows Java SE:

- IIS returns HTTP `502 Bad Gateway` with sub-status `500.121.64` on a fraction of long-running requests.
- The observed cutoff sits near the App Service front-end's ~230s ceiling rather than the httpPlatformHandler documented default of 120s.
- Under load, a burst of `500.121.64` errors correlates with an increase in loopback (`127.0.0.1`) traffic between the IIS worker (`w3wp.exe`) and the Java SE worker (`java.exe`).

Windows Java SE is under-documented in the App Service troubleshooting corpus (all 10 existing labs in this repo are Linux). This lab establishes the first Windows Java SE reproduction and mitigation playbook.

## Status

| Stage | Status | Purpose |
|---|---|---|
| Stage 0: Effective config discovery | Ready to run | Gate before Lab 1 / Lab 2. Answers four falsifiable questions about front-end timeout, effective `web.config`, idle-vs-absolute timeout, and Auto-Heal isolation. |
| Lab 1: Baseline timeout + `500.121.64` signature | Gated on Stage 0 | Reproduce the timeout signature without downstream load or mitigation. Confirms hypotheses H1 (front-end limit) + H2 (handler default) + H4 (effective config) + H7 (idle vs absolute). |
| Lab 2: Loopback saturation + mitigation | Gated on Lab 1 | Add controlled loopback pressure and Auto-Heal / config-tuning mitigations. Confirms hypothesis H3 (loopback backlog) + H6 (queue saturation) and validates mitigations M1 (`requestTimeout` extension) and M2 (custom Auto-Heal). |

Lab 1 and Lab 2 will not be committed until Stage 0 output confirms or refutes the design assumptions the Oracle review flagged. See [`stage-0-config-discovery/README.md`](stage-0-config-discovery/README.md) for the discovery matrix.

## Why a discovery gate

The Oracle review of the initial 3-hypothesis / 2-mitigation design identified four fatal flaws:

1. Timer-chain contradiction: `httpPlatformHandler.requestTimeout` default is 120s but the production ticket observes ~230s. Which is authoritative was left unresolved.
2. Load-model math error: 200 k6 closed-loop VUs produce ~200 concurrent in-flight requests, not 12000. The original Stage 2 load model was internally inconsistent.
3. Downstream-first attribution loss: adding a downstream service before establishing the loopback-only baseline destroys the ability to attribute a mid-request cut to IIS <-> Java SE.
4. Proactive Auto-Heal preemption: `WEBSITE_PROACTIVE_AUTOHEAL_ENABLED` defaults to true, and its trigger (80% of requests over 200s in a 2-minute window) fires before any custom Auto-Heal rule the lab could add. Without disabling it, custom mitigation M2 is unfalsifiable.

Stage 0 addresses flaw #1 (empirical timer measurement) and flaw #4 (Auto-Heal is disabled in `stage-0-config-discovery/main.bicep`). Flaws #2 and #3 are structural and are addressed by splitting the original single-lab design into Lab 1 (no downstream, sequential probes) and Lab 2 (open-model load, only after Lab 1 confirms the signature).

## Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| Azure subscription | Any | Deployment target |
| Azure CLI | 2.60+ | All deploy / query / cleanup commands |
| Maven | 3.8+ | Build the Spring Boot JAR |
| JDK | 17 (matching App Service) | Local `mvn package` |
| `curl`, `python3` | Any recent | Probes and Kudu API parsing |
| Bash | 4+ | Scripts use `set -euo pipefail` and arrays |

Stage 0 costs less than $0.50 at B1 Basic in Korea Central. Lab 1 is projected in the same order. Lab 2 introduces higher-tier plans and open-model load and is projected between $5 and $30 based on the Oracle cost review.

## Scope

In scope for the full lab:

- Windows App Service Java SE 17 on Basic and Standard plans
- httpPlatformHandler as the IIS <-> Java bridge
- IIS `500.121.64` sub-status attribution
- Front-end (230s) vs handler (`requestTimeout`) vs client timers
- Proactive Auto-Heal vs custom Auto-Heal interaction
- Loopback (`127.0.0.1`) traffic under burst load

Out of scope:

- Linux Java (Tomcat + Java SE on Linux use a different reverse-proxy stack)
- WAR / EAR / JBoss / Tomcat Windows containers (only Java SE JAR is covered)
- Cross-region or cross-tenant issues
- Application Insights instrumentation beyond what App Service diagnostic logs provide

## Directory layout

```
labs/windows-java-httpplatformhandler-timeout/
|-- README.md                              # This file
`-- stage-0-config-discovery/
    |-- README.md                          # Stage 0 objectives, decision matrix
    |-- main.bicep                         # B1 Windows Java SE with Auto-Heal disabled
    |-- deploy.sh                          # Deploy + build + upload JAR
    |-- warm-up.sh                         # /actuator/health poll + JIT settle
    |-- run-timeout-probe.sh               # Sequential /slow probes + /stream/300
    |-- collect-effective-config.sh        # Kudu API + az CLI config dump
    |-- cleanup.sh                         # az group delete
    `-- app/
        |-- pom.xml                        # Spring Boot 3.3.4 Java 17
        `-- src/main/java/com/example/stage0/
            `-- Stage0Application.java     # /slow/{n}, /stream/{n}, actuator
```

## Related

- Design review that shaped this lab: consult session `ses_0e3693952ffe5js7RkwAkUB3el` if reproducing the Oracle analysis
- Existing Linux labs for cross-reference: `../intermittent-5xx/`, `../failed-to-forward-request/`, `../slow-start-cold-start/`
- Repository troubleshooting index: [`../../docs/troubleshooting/index.md`](../../docs/troubleshooting/index.md)

## Sources

- Windows App Service Java SE runtime:
  <https://learn.microsoft.com/en-us/azure/app-service/configure-language-java-deploy-run>
- App Service front-end 230-second request timeout:
  <https://learn.microsoft.com/en-us/troubleshoot/azure/app-service/web-request-times-out-app-service>
- `httpPlatformHandler` configuration reference:
  <https://learn.microsoft.com/en-us/iis/extensions/httpplatformhandler/httpplatformhandler-configuration-reference>
- App Service environment variables:
  <https://learn.microsoft.com/en-us/azure/app-service/reference-app-settings>
- App Service language support policy (Java 17 on Windows Server 2022):
  <https://learn.microsoft.com/en-us/azure/app-service/language-support-policy>
