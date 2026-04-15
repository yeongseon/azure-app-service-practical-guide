---
title: 5xx Trend Over Time
slug: 5xx-trend-over-time
doc_type: kql
section: troubleshooting
topics:
  - kql
  - http
  - 5xx
products:
  - azure-app-service
used_in:
  - intermittent-5xx-under-load
summary: KQL query to visualize 5xx error trends over time.
status: stable
last_reviewed: 2026-04-08
content_validation:
  status: verified
  last_reviewed: "2026-04-12"
  reviewer: ai-agent
  core_claims:
    - claim: "With Azure Monitor integration, you can create diagnostic settings to send logs to storage accounts, event hubs, and Log Analytics workspaces."
      source: "https://learn.microsoft.com/azure/app-service/troubleshoot-diagnostic-logs"
      verified: true
    - claim: "Log Analytics in the Azure portal lets you explore and analyze data collected by Azure Monitor Logs."
      source: "https://learn.microsoft.com/azure/azure-monitor/logs/log-analytics-tutorial"
      verified: true
    - claim: "Log Analytics in the Azure portal lets you edit and run log queries to filter records, uncover trends, analyze patterns, and gain meaningful insights into your environment."
      source: "https://learn.microsoft.com/azure/azure-monitor/logs/log-analytics-tutorial"
      verified: true
    - claim: "You can view, modify, and share visuals of query results."
      source: "https://learn.microsoft.com/azure/azure-monitor/logs/log-analytics-tutorial"
      verified: true
content_sources:
  diagrams:
    - id: troubleshooting-kql-http-5xx-trend-over-time-diagram-1
      type: graph
      source: self-generated
      justification: "Self-generated troubleshooting diagram synthesized from Microsoft Learn diagnostics and Azure App Service incident guidance for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/azure-monitor/logs/get-started-queries
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
---
# 5xx Trend Over Time

**Scenario**: Intermittent or sustained server-side errors reported by customers.
**Data Source**: AppServiceHTTPLogs
**Purpose**: Tracks 5xx volume over time and separates by status code to detect spikes and dominant failure types.

<!-- diagram-id: troubleshooting-kql-http-5xx-trend-over-time-diagram-1 -->
```mermaid
graph TD
    A[AppServiceHTTPLogs] -->|ScStatus >= 500| B[Filter 5xx]
    B --> C[Count by 15m bins + ScStatus]
    C --> D[Timechart: Spike Detection]
```

## Query

```kql
AppServiceHTTPLogs
| where TimeGenerated > ago(24h)
| where ScStatus >= 500
| summarize Count=count() by bin(TimeGenerated, 15m), ScStatus
| render timechart
```

## Interpretation Notes
- Normal: low baseline 5xx with occasional isolated blips.
- Abnormal: sustained or bursty 5xx clusters, especially if one status code dominates (for example 502/503/500).
- Reading tip: align spikes with deployments, restarts, and dependency incidents.

## Limitations
- Data freshness may lag a few minutes depending on ingestion.
- In low-volume apps, a small number of errors can appear as large percentage impact.
- This query cannot determine whether the error originated in app code, platform, or downstream dependency.

## See Also

- [HTTP Query Pack](index.md)
- [KQL Query Packs](../index.md)

## Sources

- [Enable diagnostic logging for apps in Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs)
- [Monitor Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/monitor-app-service)
- [Kusto Query Language (KQL) overview](https://learn.microsoft.com/en-us/kusto/query/)
