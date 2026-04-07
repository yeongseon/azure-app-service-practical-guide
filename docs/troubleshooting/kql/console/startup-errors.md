---
title: Startup Errors
slug: startup-errors
doc_type: kql
section: troubleshooting
topics:
  - kql
  - startup
  - console
products:
  - azure-app-service
used_in:
  - container-didnt-respond-to-http-pings
  - deployment-succeeded-startup-failed
summary: KQL query to find container and application startup errors in console logs.
status: stable
last_reviewed: 2026-04-08
---
# Startup Errors

**Scenario**: Container startup fails or app never becomes healthy after deployment/restart.
**Data Source**: AppServiceConsoleLogs
**Purpose**: Surfaces recent startup/runtime error signatures from console output.

```mermaid
graph LR
    A[AppServiceConsoleLogs] -->|Keyword Filter| B[error / exception / traceback]
    B --> C[Timeline of Error Messages]
    C --> D[Identify Boot Failure Pattern]
```

## Query

```kql
AppServiceConsoleLogs
| where TimeGenerated > ago(1h)
| where ResultDescription has_any ("error", "Error", "ERROR", "exception", "Exception", "failed", "Failed", "traceback", "Traceback")
| project TimeGenerated, ResultDescription
| order by TimeGenerated desc
```

## Interpretation Notes
- Normal: few/no fatal startup errors; expected informational logs dominate.
- Abnormal: repeated exceptions, traceback bursts, or fatal initialization messages.
- Reading tip: look for repeated identical stack traces to identify deterministic boot failures.

## Limitations
- Console log availability depends on diagnostic configuration and app logging behavior.
- Keyword search may include non-fatal lines or miss framework-specific error formats.
- This query cannot prove whether App Service health probes succeeded.

## See Also

- [Console Query Pack](index.md)
- [KQL Query Packs](../index.md)

## Sources

- [Enable diagnostic logging for apps in Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs)
- [Monitor Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/monitor-app-service)
- [Kusto Query Language (KQL) overview](https://learn.microsoft.com/en-us/kusto/query/)
