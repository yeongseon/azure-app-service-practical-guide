---
content_sources:
  diagrams:
  - id: troubleshooting-kql-restarts-index-diagram-1
    type: graph
    source: self-generated
    justification: Self-generated troubleshooting diagram synthesized from Microsoft
      Learn diagnostics and Azure App Service incident guidance for this guide.
    based_on:
    - https://learn.microsoft.com/en-us/azure/azure-monitor/logs/get-started-queries
    - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
content_validation:
  status: verified
  last_reviewed: '2026-05-23'
  reviewer: agent
  core_claims:
  - claim: This page uses Microsoft Learn as the primary source basis for its Azure-specific
      guidance.
    source: https://learn.microsoft.com/en-us/azure/azure-monitor/logs/get-started-queries
    verified: true
---
# Restart Queries

Use these queries to confirm restart timing, startup loops, and restart correlation with incident windows.

<!-- diagram-id: troubleshooting-kql-restarts-index-diagram-1 -->
```mermaid
graph TD
    A[AppServicePlatformLogs] --> B[Restart Events]
    A --> C[Start/Stop Cycles]
    B --> D[Correlate with Incidents]
    C --> D
```

## Available Queries
- [Restart Timing Correlation](restart-timing-correlation.md)
- [Repeated Startup Attempts](repeated-startup-attempts.md)

## See Also

- [KQL Query Library](../index.md)
- [Console Queries](../console/index.md)
- [Correlation Queries](../correlation/index.md)

## Sources

- [Microsoft Learn source 1](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/get-started-queries)
- [Microsoft Learn source 2](https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs)
