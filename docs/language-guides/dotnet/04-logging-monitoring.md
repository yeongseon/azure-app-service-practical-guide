# 04. Logging & Monitoring

Instrument ASP.NET Core 8 on Azure App Service with `ILogger` and Application Insights, then query operational signals using KQL.

## Prerequisites

- Tutorial [03. Configuration](./03-configuration.md) completed
- Application Insights resource connected to your web app
- Log Analytics workspace configured (recommended)

## What you'll learn

- Structured logging with `ILogger<T>`
- Application Insights SDK behavior in ASP.NET Core
- Request/dependency auto-collection and custom telemetry
- KQL queries for production diagnostics

## Main content

### 1) Confirm SDK registration

The reference app already includes telemetry wiring:

```csharp
builder.Services.AddApplicationInsightsTelemetry();
builder.Services.AddControllers();
```

Package reference in project:

```xml
<PackageReference Include="Microsoft.ApplicationInsights.AspNetCore" Version="2.22.0" />
```

### 2) Add structured request logging

```csharp
[ApiController]
[Route("api/requests")]
public sealed class RequestLogController : ControllerBase
{
    private readonly ILogger<RequestLogController> _logger;
    public RequestLogController(ILogger<RequestLogController> logger) => _logger = logger;

    [HttpGet("sample")]
    public IActionResult Sample([FromQuery] string userId = "anonymous")
    {
        _logger.LogInformation("Sample request received for {UserId}", userId);
        return Ok(new { status = "ok", userId, timestamp = DateTime.UtcNow });
    }
}
```

### 3) Enable/verify App Service diagnostics logs

```bash
az webapp log config \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --name "$WEB_APP_NAME" \
  --application-logging filesystem \
  --level information \
  --web-server-logging filesystem \
  --output json
```

Stream logs live:

```bash
az webapp log tail --resource-group "$RESOURCE_GROUP_NAME" --name "$WEB_APP_NAME"
```

### 4) Understand automatic collection

With Application Insights SDK in ASP.NET Core, these are collected automatically:

- Incoming HTTP requests
- Outgoing dependencies (`HttpClient`, SQL calls in supported providers)
- Exceptions (unhandled + tracked)
- Performance counters and basic host telemetry

!!! tip "When to add custom telemetry"
    Use `TelemetryClient` for business events or domain-specific metrics.
    Keep event cardinality low to avoid noisy, expensive telemetry.

### 5) Add custom event and metric

```csharp
using Microsoft.ApplicationInsights;

public sealed class BusinessTelemetryService
{
    private readonly TelemetryClient _telemetryClient;
    public BusinessTelemetryService(TelemetryClient telemetryClient) => _telemetryClient = telemetryClient;

    public void TrackCheckout(string region, decimal amount)
    {
        _telemetryClient.TrackEvent("CheckoutCompleted", new() { ["region"] = region });
        _telemetryClient.TrackMetric("CheckoutAmount", (double)amount);
    }
}
```

### 6) KQL for .NET app operations

Recent failed requests:

```kusto
requests
| where timestamp > ago(30m)
| where success == false
| project timestamp, name, resultCode, operation_Id, cloud_RoleName
| order by timestamp desc
```

Dependency latency hot spots:

```kusto
dependencies
| where timestamp > ago(1h)
| summarize p95=percentile(duration, 95ms), avg=avg(duration), count() by target, type
| order by p95 desc
```

Correlate exception with request operation:

```kusto
exceptions
| where timestamp > ago(1h)
| join kind=leftouter requests on operation_Id
| project timestamp, outerMessage, requestName=name, resultCode, operation_Id
| order by timestamp desc
```

### 7) Azure DevOps release quality gate example

```yaml
- task: AzureCLI@2
  displayName: Query recent failed requests
  inputs:
    azureSubscription: $(azureSubscription)
    scriptType: bash
    scriptLocation: inlineScript
    inlineScript: |
      az monitor app-insights query \
        --app $(appInsightsName) \
        --resource-group $(resourceGroupName) \
        --analytics-query "requests | where timestamp > ago(10m) | where success == false | count" \
        --output table
```

## Verification

```bash
curl --silent "https://$WEB_APP_NAME.azurewebsites.net/api/requests/sample?userId=ops-check"
```

Then confirm:

1. Request appears in Application Insights `requests` table.
2. Log message appears in App Service log stream.
3. Operation correlation is present across request/dependency/exception telemetry.

## Troubleshooting

### No telemetry arriving

- Check `APPLICATIONINSIGHTS_CONNECTION_STRING` in App Settings
- Ensure outbound access to Azure Monitor endpoints is not blocked
- Restart app after changing telemetry connection settings

### Logs too noisy

Adjust log levels:

```bash
az webapp config appsettings set \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --name "$WEB_APP_NAME" \
  --settings Logging__LogLevel__Default=Warning Logging__LogLevel__Microsoft.AspNetCore=Warning
```

### Missing dependency telemetry

Confirm you are using instrumented libraries and avoid suppressing `DiagnosticSource` activity in custom middleware.

## Sources

- [Enable diagnostics logging for apps in Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs)
- [Monitor Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/monitor-app-service)

## See Also

- [05. Infrastructure as Code](./05-infrastructure-as-code.md)
- [Reference: KQL Queries](../../reference/kql-queries.md)
- For platform details, see [Azure App Service Guide](https://yeongseon.github.io/azure-app-service-practical-guide/)
