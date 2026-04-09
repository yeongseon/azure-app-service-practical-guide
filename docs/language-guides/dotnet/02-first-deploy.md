---
hide:
  - toc
---

# 02. First Deploy

Deploy the ASP.NET Core 8 app to Azure App Service (Windows) using Bicep infrastructure and zip-based code deployment.

!!! info "Infrastructure Context"
    **Service**: App Service (Windows, Standard S1) | **Network**: VNet integrated | **VNet**: ✅

    This tutorial assumes a production-ready App Service deployment with VNet integration, private endpoints for backend services, and managed identity for authentication.

    ```mermaid
    flowchart TD
        INET[Internet] -->|HTTPS| WA["Web App\nApp Service S1\nWindows .NET 8"]

        subgraph VNET["VNet 10.0.0.0/16"]
            subgraph INT_SUB["Integration Subnet 10.0.1.0/24\nDelegation: Microsoft.Web/serverFarms"]
                WA
            end
            subgraph PE_SUB["Private Endpoint Subnet 10.0.2.0/24"]
                PE_KV[PE: Key Vault]
                PE_SQL[PE: Azure SQL]
                PE_ST[PE: Storage]
            end
        end

        PE_KV --> KV[Key Vault]
        PE_SQL --> SQL[Azure SQL]
        PE_ST --> ST[Storage Account]

        subgraph DNS[Private DNS Zones]
            DNS_KV[privatelink.vaultcore.azure.net]
            DNS_SQL[privatelink.database.windows.net]
            DNS_ST[privatelink.blob.core.windows.net]
        end

        PE_KV -.-> DNS_KV
        PE_SQL -.-> DNS_SQL
        PE_ST -.-> DNS_ST

        WA -.->|System-Assigned MI| ENTRA[Microsoft Entra ID]
        WA --> AI[Application Insights]

        style WA fill:#0078d4,color:#fff
        style VNET fill:#E8F5E9,stroke:#4CAF50
        style DNS fill:#E3F2FD
    ```

```mermaid
flowchart LR
    A[Set variables] --> B[Create resource group]
    B --> C[Deploy Bicep infra]
    C --> D[dotnet publish]
    D --> E[Zip artifacts]
    E --> F[az webapp deploy]
    F --> G[Verify app endpoint]
```

## Prerequisites

- Tutorial [01. Local Run](./01-local-run.md) completed
- Azure CLI logged in (`az login`)
- Permission to create resource groups and App Service resources

## What you'll learn

- Create a resource group with Azure CLI
- Deploy infrastructure using Bicep
- Publish the app with `dotnet publish`
- Deploy zip package with `az webapp deploy`

## Main content

### 1) Set deployment variables

```bash
export RESOURCE_GROUP_NAME="rg-dotnet-guide"
export LOCATION="eastus"
export BASE_NAME="dotnetguide"
```

### 2) Create resource group

```bash
az group create \
  --name "$RESOURCE_GROUP_NAME" \
  --location "$LOCATION" \
  --output table
```

### 3) Deploy Bicep (Windows App Service)

```bash
az deployment group create \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --template-file "infra/main.bicep" \
  --parameters baseName="$BASE_NAME" location="$LOCATION" \
  --output json
```

Capture outputs:

```bash
export WEB_APP_NAME=$(az deployment group show \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --name "main" \
  --query "properties.outputs.webAppName.value" \
  --output tsv)
```

If your deployment name differs, use the name returned by your command output.

### 4) Publish application

```bash
dotnet publish "app/GuideApi/GuideApi.csproj" \
  --configuration Release \
  --output "app/GuideApi/publish"
```

### 5) Zip publish output

```bash
cd "app/GuideApi/publish"
zip --recurse-paths --quiet "../guideapi.zip" .
```

### 6) Deploy to App Service

```bash
az webapp deploy \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --name "$WEB_APP_NAME" \
  --src-path "app/GuideApi/guideapi.zip" \
  --type zip \
  --output json
```

### 7) Validate app startup assumptions

The app binds correctly because `Program.cs` respects platform port variables:

```csharp
var port = Environment.GetEnvironmentVariable("HTTP_PLATFORM_PORT")
    ?? Environment.GetEnvironmentVariable("PORT")
    ?? "5000";
builder.WebHost.UseUrls($"http://+:{port}");
```

### 8) Azure DevOps equivalent deployment task

```yaml
- task: AzureWebApp@1
  inputs:
    azureSubscription: $(azureSubscription)
    appType: webApp
    appName: $(webAppName)
    package: '$(Pipeline.Workspace)/drop/**/*.zip'
```

!!! note "Manual deploy and pipeline deploy should be equivalent"
    Keep your publish profile and runtime assumptions identical so that local/manual deploys and Azure DevOps deploys produce the same behavior.

## Verification

```bash
curl --include "https://$WEB_APP_NAME.azurewebsites.net/health"
curl --silent "https://$WEB_APP_NAME.azurewebsites.net/info"
```

Expected:

- HTTP 200 from `/health`
- JSON payload with `status: healthy`
- `/info` indicates production environment

## Troubleshooting

### Deployment succeeded but app returns 500

- Confirm zip contains published output (`.dll`, `.deps.json`, `web.config`)
- Check App Service Log Stream and Event Log messages
- Re-run publish and deploy from clean output directory

### Resource naming conflict

Use a globally unique base name, for example:

```bash
export BASE_NAME="dotnetguide$RANDOM"
```

### Incorrect runtime stack

Validate App Service configuration after deployment:

```bash
az webapp config show --resource-group "$RESOURCE_GROUP_NAME" --name "$WEB_APP_NAME" --output json
```

## See Also

- [03. Configuration](./03-configuration.md)
- [05. Infrastructure as Code](./05-infrastructure-as-code.md)
- For platform details, see [Azure App Service Guide](https://yeongseon.github.io/azure-app-service-practical-guide/)

## Sources

- [Deploy a ZIP file to Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip)
- [Quickstart: Deploy an ASP.NET web app](https://learn.microsoft.com/en-us/azure/app-service/quickstart-dotnetcore)
- [Azure App Service deployment overview](https://learn.microsoft.com/en-us/azure/app-service/deploy-best-practices)
