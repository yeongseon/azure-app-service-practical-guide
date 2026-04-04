# 01. Local Run

Run the ASP.NET Core 8 reference API locally using the same port and environment conventions expected by Azure App Service on Windows.

## Prerequisites

- .NET 8 SDK installed (`dotnet --info`)
- Local clone of `azure-app-service-practical-guide`
- Terminal with access to `app/GuideApi`

## What you'll learn

- How to start the API with `dotnet run`
- Why `HTTP_PLATFORM_PORT` matters on Windows App Service
- How to validate `/health` and `/info`
- How Development and Production modes differ

## Main content

### 1) Run the app

```bash
dotnet restore "app/GuideApi/GuideApi.csproj"
dotnet run --project "app/GuideApi/GuideApi.csproj"
```

By default, the app listens on port `5000` if no environment variable is provided.

### 2) Understand port binding logic

`Program.cs` uses a Windows-first App Service binding sequence:

```csharp
var port = Environment.GetEnvironmentVariable("HTTP_PLATFORM_PORT")
    ?? Environment.GetEnvironmentVariable("PORT")
    ?? "5000";

builder.WebHost.UseUrls($"http://+:{port}");
```

- `HTTP_PLATFORM_PORT`: provided by IIS integration on Windows App Service
- `PORT`: fallback used in some hosting environments
- `5000`: local fallback for developer machines

!!! warning "Do not hardcode localhost-only binding"
    `UseUrls("http://localhost:5000")` can fail in hosted environments.
    `http://+:{port}` ensures the worker accepts traffic from the platform front end.

### 3) Test core endpoints

```bash
curl --silent "http://localhost:5000/health"
curl --silent "http://localhost:5000/info"
```

Expected `/health` shape:

```json
{
  "status": "healthy",
  "timestamp": "2026-04-04T10:00:00.000Z"
}
```

### 4) Toggle environments locally

Run in Development:

```bash
ASPNETCORE_ENVIRONMENT=Development dotnet run --project "app/GuideApi/GuideApi.csproj"
```

Run in Production:

```bash
ASPNETCORE_ENVIRONMENT=Production dotnet run --project "app/GuideApi/GuideApi.csproj"
```

Typical differences:

- Developer exception pages are disabled in Production
- Logging filters may be stricter
- Production appsettings override behavior applies

### 5) Generate request logs

If your app includes sample logging routes, invoke them now to create telemetry baseline before cloud deployment.

```bash
curl --silent "http://localhost:5000/api/requests/log-levels?userId=local-user"
```

### 6) Azure DevOps context (why this matters)

Local behavior should mirror pipeline-produced artifacts. A minimal pipeline step for local parity:

```yaml
- script: dotnet publish --configuration Release --output $(Build.ArtifactStagingDirectory)
  displayName: Publish app artifacts
  workingDirectory: app/GuideApi
```

## Verification

- Terminal shows startup without port conflict
- `/health` returns HTTP 200 and JSON payload
- `/info` reports expected `environment` value
- No unhandled exception appears during test requests

```bash
curl --include --request GET "http://localhost:5000/health"
```

## Troubleshooting

### Port already in use

Stop the previous process and rerun, or test with platform-style port simulation:

```bash
HTTP_PLATFORM_PORT=5050 dotnet run --project "app/GuideApi/GuideApi.csproj"
```

### Missing .NET SDK

```bash
dotnet --list-sdks
```

Install .NET 8 SDK if not listed.

### Wrong environment behavior

Print current environment at startup:

```csharp
Console.WriteLine($"ASPNETCORE_ENVIRONMENT={builder.Environment.EnvironmentName}");
```

## Sources

- [Configure a .NET app for Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/configure-language-dotnetcore)
- [Quickstart: Deploy an ASP.NET web app](https://learn.microsoft.com/en-us/azure/app-service/quickstart-dotnetcore)

## See Also

- [02. First Deploy](./02-first-deploy.md)
- [03. Configuration](./03-configuration.md)
- For platform details, see [Azure App Service Guide](https://yeongseon.github.io/azure-app-service-practical-guide/)
