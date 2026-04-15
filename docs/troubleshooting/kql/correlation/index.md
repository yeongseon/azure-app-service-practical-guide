---
content_sources:
  diagrams:
    - id: troubleshooting-kql-correlation-index-diagram-1
      type: graph
      source: self-generated
      justification: "Self-generated troubleshooting diagram synthesized from Microsoft Learn diagnostics and Azure App Service incident guidance for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/azure-monitor/logs/get-started-queries
        - https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
---
# Correlation Queries

Use these queries to correlate major signals (latency, error rate, and restart events) in one timeline.

<!-- diagram-id: troubleshooting-kql-correlation-index-diagram-1 -->
```mermaid
graph TD
    A[AppServiceHTTPLogs] --> C[Latency + Error Rate]
    B[AppServicePlatformLogs] --> D[Restart Events]
    C --> E[Unified Timeline]
    D --> E
```

## Available Queries
- [Latency vs Errors](latency-vs-errors.md)
- [Restarts vs Latency](restarts-vs-latency.md)

## See Also

- [KQL Query Library](../index.md)
- [HTTP Queries](../http/index.md)
- [Restart Queries](../restarts/index.md)
