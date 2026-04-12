---
hide:
  - toc
content_validation:
  status: verified
  last_reviewed: "2026-04-12"
  reviewer: ai-agent
  core_claims:
    - claim: "Application logging is available on Windows and Linux."
      source: "https://learn.microsoft.com/azure/app-service/troubleshoot-diagnostic-logs"
      verified: true
    - claim: "App Service streams any information written to the console output or files ending in .txt, .log, or .htm that are stored in the /home/LogFiles directory."
      source: "https://learn.microsoft.com/azure/app-service/troubleshoot-diagnostic-logs"
      verified: true
    - claim: "For Linux or custom containers, the ZIP file contains console output logs for both the Docker host and the Docker container."
      source: "https://learn.microsoft.com/azure/app-service/troubleshoot-diagnostic-logs"
      verified: true
content_sources:
  diagrams:
    - id: troubleshooting-kql-console-container-binding-errors-diagram-1
      type: graph
      source: self-generated
      justification: "Self-generated troubleshooting diagram synthesized from Microsoft Learn diagnostics and Azure App Service incident guidance for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/azure-monitor/logs/get-started-queries
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
---
# Container Binding Errors

**Scenario**: App starts but is unreachable, or startup fails with bind/listen issues.
**Data Source**: AppServiceConsoleLogs
**Purpose**: Detects log lines related to port binding, listen socket conflicts, and loopback binding mistakes.

<!-- diagram-id: troubleshooting-kql-console-container-binding-errors-diagram-1 -->
```mermaid
graph LR
    A[AppServiceConsoleLogs] -->|Keyword Filter| B[bind / listen / port / EADDRINUSE]
    B --> C[Binding Event Timeline]
    C --> D[Detect Port Mismatch or Conflict]
```

## Query

```kql
AppServiceConsoleLogs
| where TimeGenerated > ago(1h)
| where ResultDescription has_any ("bind", "listen", "port", "address already in use", "EADDRINUSE", "0.0.0.0", "127.0.0.1")
| project TimeGenerated, ResultDescription
| order by TimeGenerated desc
```

## Interpretation Notes
- Normal: listener starts once on expected `0.0.0.0:<port>` with no bind conflicts.
- Abnormal: `address already in use`, repeated bind failures, or logs showing `127.0.0.1` bind only.
- Reading tip: confirm that logged port matches `WEBSITES_PORT` and container configuration.

## Limitations
- Log message formats vary by runtime/server (Gunicorn, Node, Java, etc.).
- Broad keyword matching can include benign listen information.
- This query cannot validate actual socket state inside the running container.

## See Also

- [Console Query Pack](index.md)
- [KQL Query Packs](../index.md)

## Sources

- [Enable diagnostic logging for apps in Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs)
- [Monitor Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/monitor-app-service)
- [Kusto Query Language (KQL) overview](https://learn.microsoft.com/en-us/kusto/query/)
