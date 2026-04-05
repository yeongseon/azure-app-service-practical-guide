# Troubleshooting

Platform-level troubleshooting reference for Azure App Service across runtimes.

## Overview

```mermaid
flowchart TD
    A[Incident Symptom] --> B[Collect Baseline]
    B --> C{Issue Domain}
    C --> D[Deployment Checks]
    C --> E[Network Checks]
    C --> F[Runtime and Logs]
    D --> G[Validate and Mitigate]
    E --> G
    F --> G
```

## Diagnostic Tools Overview

| Tool | Purpose | Access |
| :--- | :--- | :--- |
| **Kudu (SCM)** | File system, process, environment, deployment diagnostics | `https://${APP_NAME}.scm.azurewebsites.net` |
| **Log Stream** | Real-time application and container logs | Azure Portal or CLI |
| **Application Insights** | Requests, traces, dependencies, exceptions | Azure Portal |
| **Diagnose and solve problems** | Built-in detectors and recommendations | Azure Portal > Web App |

!!! note "Language-specific debugging"
    This document focuses on App Service platform diagnostics.
    For runtime/framework-specific startup and debugging issues, see the language-specific guides linked in
    [Language-Specific Details](#language-specific-details).

## Fast Triage Commands

```bash
az webapp show --resource-group $RG --name $APP_NAME --output table
az webapp log tail --resource-group $RG --name $APP_NAME
az webapp config appsettings list --resource-group $RG --name $APP_NAME --output table
az webapp deployment slot list --resource-group $RG --name $APP_NAME --output table
```

## Common Platform Issues

| Symptom | Likely Cause | Action |
| :--- | :--- | :--- |
| **503 Service Unavailable** | Worker process failed or app is restarting | Check log stream, deployment logs, and latest restart events |
| **502 Bad Gateway** | App failed to start or failed health probe | Verify startup command and health check path |
| **Slow responses / timeouts** | Long-running requests, dependency latency, plan saturation | Check request duration, dependency latency, CPU/memory metrics |
| **Disk quota reached** | Logs or generated files filling persistent storage | Clean unnecessary files in `/home/LogFiles` and app data |
| **Intermittent outbound failures** | SNAT port pressure or firewall allowlist mismatch | Reuse connections, review outbound IPs, add NAT Gateway if needed |
| **DNS resolution failures for private endpoints** | Private DNS Zone linkage issue | Verify Private DNS Zone links to integration VNet |

## Deployment Troubleshooting

### Check deployment history

```bash
az webapp log deployment list \
  --resource-group $RG \
  --name $APP_NAME \
  --output table
```

### Check latest deployment details

```bash
az webapp log deployment show \
  --resource-group $RG \
  --name $APP_NAME \
  --deployment-id latest \
  --output json
```

### Validate build-on-deploy setting

```bash
az webapp config appsettings list \
  --resource-group $RG \
  --name $APP_NAME \
  --query "[?name=='SCM_DO_BUILD_DURING_DEPLOYMENT']"
```

## Networking Troubleshooting

### VNet integration status

```bash
az webapp vnet-integration list \
  --resource-group $RG \
  --name $APP_NAME \
  --output table
```

### Route-all check

```bash
az webapp config appsettings list \
  --resource-group $RG \
  --name $APP_NAME \
  --query "[?name=='WEBSITE_VNET_ROUTE_ALL']"
```

Set route-all when required:

```bash
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings WEBSITE_VNET_ROUTE_ALL=1
```

### Outbound IP allowlist checks

```bash
az webapp show \
  --resource-group $RG \
  --name $APP_NAME \
  --query "{outbound: properties.outboundIpAddresses, possible: properties.possibleOutboundIpAddresses}" \
  --output json
```

!!! warning "Allowlist all possible outbound IPs"
    The active outbound IP set can change as the app scales or moves.
    Add all addresses from `possibleOutboundIpAddresses` to external allowlists.

## Kudu-Based Checks

- Open Kudu: `https://${APP_NAME}.scm.azurewebsites.net`
- Check environment: `/api/environment`
- Check running processes: `/api/processes`
- Review logs under `/home/LogFiles`

See [Kudu API Reference](./kudu-queries.md) for endpoint details.

## Data to Collect Before Escalation

- UTC time window and affected endpoint(s)
- Correlation/operation ID (if available)
- Recent deployment ID and timestamp
- Plan SKU and current instance count
- Relevant error snippets (PII removed)

## See Also

- [KQL Queries](kql-queries.md)
- [Kudu Queries](kudu-queries.md)

## Sources

- [Diagnose and Solve Problems in App Service (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/overview-diagnostics)
- [Troubleshoot Diagnostic Logs in App Service (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/troubleshoot-diagnostic-logs)
- [Networking Features in App Service (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/networking-features)

## Language-Specific Details

Runtime-specific startup failures, package/import issues, framework worker tuning, and language-level exception handling are documented in:

- [Azure App Service Node.js Guide — Troubleshooting](../language-guides/nodejs/index.md)
- [Azure App Service Python Guide — Troubleshooting](../language-guides/python/index.md)
