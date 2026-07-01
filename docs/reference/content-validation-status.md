---
content_sources:
  references:
    - type: self-generated
      justification: Auto-generated dashboard tracking content validation status
---

# Content Validation Status

This page tracks `content_validation` metadata for **in-scope factual-claim documents** under `docs/best-practices/`, `docs/operations/`, `docs/platform/`, `docs/troubleshooting/`. Pages outside this scope — navigation indexes (`docs/best-practices/index.md`, `docs/operations/deployment/index.md`, `docs/operations/index.md`, `docs/platform/index.md`, `docs/troubleshooting/first-10-minutes/index.md`, `docs/troubleshooting/index.md`, `docs/troubleshooting/playbooks/index.md`), reference-lookup KQL packs and lab guides (`docs/troubleshooting/kql/`, `docs/troubleshooting/lab-guides/`), tutorials, language guides, and start-here landing pages — intentionally omit the metadata and are not counted here. See `AGENTS.md` §Text Content Validation for the full policy and `scripts/lib/content_scope.py` for the executable scope definition.

## Summary

*Generated: 2026-07-02*

| Content Type | Total | Verified | Pending | Unverified | No Metadata |
|---|---:|---:|---:|---:|---:|
| Mermaid Diagrams | 378 | 378 | 0 | 0 | 0 |
| In-Scope Factual-Claim Documents | 74 | 74 | 0 | 0 | 0 |

!!! success "All In-Scope Documents Verified"
    Every in-scope factual-claim document has verified Microsoft Learn sources for its core claims.

<!-- diagram-id: content-validation-status-pie -->
```mermaid
pie title In-Scope Document Validation Status
    "Verified" : 74
```

## By Section

### Platform

| Document | Has Sources | Status | Claims | Last Reviewed |
|---|---|---|---|---|
| [Authentication Architecture](../platform/authentication-architecture.md) | ✅ | ✅ Verified | 5/5 | 2026-04-12 |
| [Deployment Options](../platform/deployment-options.md) | ✅ | ✅ Verified | 5/5 | 2026-05-01 |
| [Deployment Scenarios](../platform/deployment-scenarios.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |
| [Hosting Models](../platform/hosting-models.md) | ✅ | ✅ Verified | 5/5 | 2026-04-12 |
| [Index](../platform/architecture/index.md) | ✅ | ✅ Verified | 4/4 | 2026-04-27 |
| [Index](../platform/containers/index.md) | ✅ | ✅ Verified | 5/5 | 2026-05-01 |
| [Kudu Linux](../platform/kudu-linux.md) | ✅ | ✅ Verified | 5/5 | 2026-07-01 |
| [Kudu Overview](../platform/kudu-overview.md) | ✅ | ✅ Verified | 5/5 | 2026-07-01 |
| [Kudu Windows](../platform/kudu-windows.md) | ✅ | ✅ Verified | 4/4 | 2026-07-01 |
| [Mtls](../platform/mtls.md) | ✅ | ✅ Verified | 4/4 | 2026-04-25 |
| [Networking](../platform/networking.md) | ✅ | ✅ Verified | 8/8 | 2026-04-12 |
| [Request Lifecycle](../platform/request-lifecycle.md) | ✅ | ✅ Verified | 5/5 | 2026-04-12 |
| [Resource Relationships](../platform/resource-relationships.md) | ✅ | ✅ Verified | 5/5 | 2026-04-12 |
| [Scaling](../platform/scaling.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |
| [Security Architecture](../platform/security-architecture.md) | ✅ | ✅ Verified | 5/5 | 2026-04-12 |

### Best Practices

| Document | Has Sources | Status | Claims | Last Reviewed |
|---|---|---|---|---|
| [Common Anti Patterns](../best-practices/common-anti-patterns.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Deployment](../best-practices/deployment.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Mtls](../best-practices/mtls.md) | ✅ | ✅ Verified | 4/4 | 2026-04-25 |
| [Networking](../best-practices/networking.md) | ✅ | ✅ Verified | 7/7 | 2026-04-12 |
| [Production Baseline](../best-practices/production-baseline.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |
| [Reliability](../best-practices/reliability.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |
| [Scaling](../best-practices/scaling.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Security](../best-practices/security.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |

### Operations

| Document | Has Sources | Status | Claims | Last Reviewed |
|---|---|---|---|---|
| [Backup Restore](../operations/backup-restore.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Container Deploy](../operations/deployment/container-deploy.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |
| [Cost Optimization](../operations/cost-optimization.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Deployment Slots](../operations/deployment-slots.md) | ✅ | ✅ Verified | 6/6 | 2026-06-08 |
| [Github Actions](../operations/deployment/github-actions.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Health Recovery](../operations/health-recovery.md) | ✅ | ✅ Verified | 5/5 | 2026-06-08 |
| [Incoming Client Certificates](../operations/incoming-client-certificates.md) | ✅ | ✅ Verified | 4/4 | 2026-04-25 |
| [Networking](../operations/networking.md) | ✅ | ✅ Verified | 5/5 | 2026-04-12 |
| [Outbound Client Certificates](../operations/outbound-client-certificates.md) | ✅ | ✅ Verified | 4/4 | 2026-04-25 |
| [Scaling](../operations/scaling.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |
| [Security](../operations/security.md) | ✅ | ✅ Verified | 5/5 | 2026-04-12 |
| [Slots And Swap](../operations/deployment/slots-and-swap.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |
| [Zip Deploy](../operations/deployment/zip-deploy.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |

### Troubleshooting

| Document | Has Sources | Status | Claims | Last Reviewed |
|---|---|---|---|---|
| [App Startup Failures](../troubleshooting/playbooks/app-startup-failures.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |
| [Architecture Overview](../troubleshooting/architecture-overview.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Auth Redirect Loop](../troubleshooting/playbooks/startup-availability/auth-redirect-loop.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Authentication Failures](../troubleshooting/playbooks/authentication-failures.md) | ✅ | ✅ Verified | 5/5 | 2026-04-12 |
| [Cd Rbac Role Assignment Conflict](../troubleshooting/playbooks/cd-rbac-role-assignment-conflict.md) | ✅ | ✅ Verified | 3/3 | 2026-04-22 |
| [Container Didnt Respond To Http Pings](../troubleshooting/playbooks/startup-availability/container-didnt-respond-to-http-pings.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Cors And Token Errors](../troubleshooting/playbooks/performance/cors-and-token-errors.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Decision Tree](../troubleshooting/decision-tree.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Deployment Failures](../troubleshooting/playbooks/deployment-failures.md) | ✅ | ✅ Verified | 4/4 | 2026-04-12 |
| [Deployment Succeeded Startup Failed](../troubleshooting/playbooks/startup-availability/deployment-succeeded-startup-failed.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Detector Map](../troubleshooting/methodology/detector-map.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Dns Resolution Vnet Integrated App Service](../troubleshooting/playbooks/outbound-network/dns-resolution-vnet-integrated-app-service.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Evidence Map](../troubleshooting/evidence-map.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Failed To Forward Request](../troubleshooting/playbooks/startup-availability/failed-to-forward-request.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Intermittent 5Xx Under Load](../troubleshooting/playbooks/performance/intermittent-5xx-under-load.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Memory Pressure And Worker Degradation](../troubleshooting/playbooks/performance/memory-pressure-and-worker-degradation.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Mental Model](../troubleshooting/mental-model.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Mtls Failures](../troubleshooting/playbooks/mtls-failures.md) | ✅ | ✅ Verified | 3/3 | 2026-04-25 |
| [No Space Left On Device](../troubleshooting/playbooks/performance/no-space-left-on-device.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Outbound Network](../troubleshooting/first-10-minutes/outbound-network.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Performance](../troubleshooting/first-10-minutes/performance.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Performance Degradation](../troubleshooting/playbooks/performance-degradation.md) | ✅ | ✅ Verified | 5/5 | 2026-04-12 |
| [Private Endpoint Custom Dns Route Confusion](../troubleshooting/playbooks/outbound-network/private-endpoint-custom-dns-route-confusion.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Quick Diagnosis Cards](../troubleshooting/quick-diagnosis-cards.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Slot Swap Config Drift](../troubleshooting/playbooks/startup-availability/slot-swap-config-drift.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Slot Swap Failed During Warmup](../troubleshooting/playbooks/startup-availability/slot-swap-failed-during-warmup.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Slow Response But Low Cpu](../troubleshooting/playbooks/performance/slow-response-but-low-cpu.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Slow Start Cold Start](../troubleshooting/playbooks/performance/slow-start-cold-start.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Snat Or Application Issue](../troubleshooting/playbooks/outbound-network/snat-or-application-issue.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Ssl Certificate Issues](../troubleshooting/playbooks/ssl-certificate-issues.md) | ✅ | ✅ Verified | 5/5 | 2026-04-12 |
| [Startup Availability](../troubleshooting/first-10-minutes/startup-availability.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Troubleshooting Method](../troubleshooting/methodology/troubleshooting-method.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Warmup Vs Health Check](../troubleshooting/playbooks/startup-availability/warmup-vs-health-check.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Windows Container Health Probes](../troubleshooting/playbooks/startup-availability/windows-container-health-probes.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Windows Filesystem Quotas](../troubleshooting/playbooks/performance/windows-filesystem-quotas.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |
| [Windows Iis Webconfig Startup](../troubleshooting/playbooks/startup-availability/windows-iis-webconfig-startup.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Windows Kudu Diagnostics](../troubleshooting/playbooks/startup-availability/windows-kudu-diagnostics.md) | ✅ | ✅ Verified | 3/3 | 2026-04-12 |
| [Windows Memory Pressure Worker Recycling](../troubleshooting/playbooks/performance/windows-memory-pressure-worker-recycling.md) | ✅ | ✅ Verified | 2/2 | 2026-04-12 |

## Validation Categories

### Source Types

| Type | Description | Allowed? |
|---|---|---|
| `mslearn` | Content directly from or based on Microsoft Learn | Yes |
| `mslearn-adapted` | Microsoft Learn content adapted for this guide | Yes, with source URL |
| `self-generated` | Original content created for this guide | Requires justification |
| `community` | From community sources | Not for core content |
| `unknown` | Source not documented | Must be validated |

### Validation Status

| Status | Description |
|---|---|
| `verified` | All core claims traced to Microsoft Learn sources |
| `pending_review` | Document exists but claims need source verification |
| `unverified` | New document, no validation performed |

## How to Add Validation

Before adding metadata, confirm the page is in scope. The block is required ONLY for factual-claim pages under `docs/platform/`, `docs/best-practices/`, `docs/operations/`, and `docs/troubleshooting/` (excluding `troubleshooting/kql/`, `troubleshooting/lab-guides/`, and navigation landing pages listed in `scripts/lib/content_scope.NAVIGATION_INDEXES`).

For an in-scope page, add a `content_validation` block to its frontmatter:

```yaml
---
content_sources:
  references:
    - type: mslearn-adapted
      url: https://learn.microsoft.com/en-us/azure/app-service/...
content_validation:
  status: verified
  last_reviewed: 2026-04-12
  reviewer: ai-agent
  core_claims:
    - claim: "App Service supports VNet integration"
      source: https://learn.microsoft.com/en-us/azure/app-service/overview-vnet-integration
      verified: true
---
```

Each `core_claim` MUST be a verifiable factual assertion about Azure App Service behavior (a documented limit, default, or feature). Meta-statements such as "this page uses Microsoft Learn as the primary source basis" are tautological and rejected — the marker text `primary source basis` triggers a fail-fast in both this generator and `tools/validate_frontmatter.py`.

Then regenerate this page:

```bash
python3 scripts/generate_content_validation_status.py
```

## See Also

- [CLI Cheatsheet](cli-cheatsheet.md)
- [Platform Limits](platform-limits.md)

