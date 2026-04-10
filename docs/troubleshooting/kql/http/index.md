---
hide:
  - toc
content_sources:
  diagrams:
    - id: troubleshooting-kql-http-index-diagram-1
      type: graph
      source: self-generated
      justification: "Self-generated troubleshooting diagram synthesized from Microsoft Learn diagnostics and Azure App Service incident guidance for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/azure-monitor/logs/get-started-queries
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
---
# HTTP Queries

Use these queries to quickly establish request latency patterns, error concentration, and endpoint-level hotspots on Azure App Service Linux.

<!-- diagram-id: troubleshooting-kql-http-index-diagram-1 -->
```mermaid
graph LR
    A[AppServiceHTTPLogs] --> B[Latency Trends]
    A --> C[5xx Error Patterns]
    A --> D[Endpoint Hotspots]
    B --> E[Identify Slow Paths]
    C --> E
    D --> E
```

## Available Queries
- [Latency Trend by Status Code](latency-trend-by-status-code.md)
- [5xx Trend Over Time](5xx-trend-over-time.md)
- [Slowest Requests by Path](slowest-requests-by-path.md)

## See Also

- [KQL Query Library](../index.md)
- [Console Queries](../console/index.md)
- [Correlation Queries](../correlation/index.md)
