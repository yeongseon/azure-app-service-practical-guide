---
hide:
  - toc
content_sources:
  diagrams:
    - id: 02-first-deploy
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/quickstart-python
    - id: diagram-2
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/quickstart-python
---

# 02. First Deploy

Deploy the ASP.NET Core 8 app to Azure App Service (Windows) using Bicep infrastructure and zip-based code deployment.

!!! info "Infrastructure Context"
    **Service**: App Service (Windows, Standard S1) | **Network**: VNet integrated | **VNet**: ✅

    This tutorial assumes a production-ready App Service deployment with VNet integration, private endpoints for backend services, and managed identity for authentication.

<!-- diagram-id: 02-first-deploy -->
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

<!-- diagram-id: diagram-2 -->
```mermaid
flowchart LR
    A[Set RG APP PLAN variables] --> B[Create group plan web app]
    B --> C[dotnet publish]
    C --> D[Zip artifacts]
    D --> E[az webapp deploy]
    E --> F[Verify health endpoint]
```

## Prerequisites

- Tutorial [01. Local Run](./01-local-run.md) completed
- Azure CLI logged in (`az login`)
- Permission to create resource groups and App Service resources

## What you'll learn

- Create a resource group with Azure CLI
- Provision Windows App Service infrastructure with Azure CLI
- Publish the app with `dotnet publish`
- Deploy zip package with `az webapp deploy`

## Main Content

### Step 1: Prepare deployment variables

```bash
SUBSCRIPTION_ID="<subscription-id>"
RG="rg-dotnet-tutorial"
LOCATION="koreacentral"
PLAN_NAME="plan-dotnet-tutorial-s1"
APP_NAME="app-dotnet-tutorial-abc123"
VNET_NAME="vnet-dotnet-tutorial"
INTEGRATION_SUBNET_NAME="snet-appsvc-integration"
PE_SUBNET_NAME="snet-private-endpoints"
STORAGE_NAME="stdotnettutorialabc123"
```

???+ example "Expected output"
    ```text
    Variables are set for deployment:
    RG=rg-dotnet-tutorial
    PLAN_NAME=plan-dotnet-tutorial-s1
    APP_NAME=app-dotnet-tutorial-abc123
    ```

### Step 2: Select the target subscription

```bash
az account set --subscription $SUBSCRIPTION_ID
az account show --query "{subscriptionId:id, tenantId:tenantId, user:user.name}" --output json
```

???+ example "Expected output"
    ```json
    {
      "subscriptionId": "<subscription-id>",
      "tenantId": "<tenant-id>",
      "user": "user@example.com"
    }
    ```

### Step 3: Create resource group, App Service plan, and web app

```bash
az group create --name $RG --location $LOCATION
az appservice plan create --resource-group $RG --name $PLAN_NAME --sku S1
az webapp create --resource-group $RG --plan $PLAN_NAME --name $APP_NAME --runtime "DOTNETCORE|8.0"
```

???+ example "Expected output"
    ```json
    {
      "defaultHostName": "app-dotnet-tutorial-abc123.azurewebsites.net",
      "enabledHostNames": [
        "app-dotnet-tutorial-abc123.azurewebsites.net",
        "app-dotnet-tutorial-abc123.scm.azurewebsites.net"
      ],
      "state": "Running"
    }
    ```

### Step 4: Create VNet and delegated integration subnet

```bash
az network vnet create --resource-group $RG --name $VNET_NAME --location $LOCATION --address-prefixes 10.0.0.0/16
az network vnet subnet create --resource-group $RG --vnet-name $VNET_NAME --name $INTEGRATION_SUBNET_NAME --address-prefixes 10.0.1.0/24 --delegations Microsoft.Web/serverFarms
```

???+ example "Expected output"
    ```json
    {
      "addressPrefix": "10.0.1.0/24",
      "delegations": [
        {
          "serviceName": "Microsoft.Web/serverFarms"
        }
      ],
      "name": "snet-appsvc-integration"
    }
    ```

### Step 5: Create private endpoint subnet

```bash
az network vnet subnet create --resource-group $RG --vnet-name $VNET_NAME --name $PE_SUBNET_NAME --address-prefixes 10.0.2.0/24 --disable-private-endpoint-network-policies true
```

???+ example "Expected output"
    ```json
    {
      "addressPrefix": "10.0.2.0/24",
      "name": "snet-private-endpoints",
      "privateEndpointNetworkPolicies": "Disabled"
    }
    ```

### Step 6: Integrate the web app with the VNet

```bash
az webapp vnet-integration add --resource-group $RG --name $APP_NAME --vnet $VNET_NAME --subnet $INTEGRATION_SUBNET_NAME
```

???+ example "Expected output"
    ```json
    {
      "isSwift": true,
      "subnetResourceId": "/subscriptions/<subscription-id>/resourceGroups/rg-dotnet-tutorial/providers/Microsoft.Network/virtualNetworks/vnet-dotnet-tutorial/subnets/snet-appsvc-integration"
    }
    ```

### Step 7: Assign managed identity to the web app

```bash
az webapp identity assign --resource-group $RG --name $APP_NAME
```

???+ example "Expected output"
    ```json
    {
      "principalId": "<object-id>",
      "tenantId": "<tenant-id>",
      "type": "SystemAssigned"
    }
    ```

### Step 8: Build and publish the application

```bash
dotnet publish app/GuideApi/GuideApi.csproj --configuration Release --output ./publish
```

???+ example "Expected output"
    ```text
    Determining projects to restore...
    All projects are up-to-date for restore.
    GuideApi -> /.../publish/GuideApi.dll
    ```

### Step 9: Deploy to App Service

```bash
zip --recurse-paths publish.zip ./publish
az webapp deploy --resource-group $RG --name $APP_NAME --src-path publish.zip --type zip
```

???+ example "Expected output"
    ```json
    {
      "active": true,
      "complete": true,
      "status": "Build successful"
    }
    ```

### Step 10: Verify URL, health, and deployment history

```bash
WEB_APP_URL="https://$(az webapp show --resource-group $RG --name $APP_NAME --query defaultHostName --output tsv)"
curl $WEB_APP_URL/health
az webapp log deployment list --resource-group $RG --name $APP_NAME --output table
```

???+ example "Expected output"
    ```text
    {"status":"ok"}

    Id    Status   Author     Message
    ----  -------  ---------  ----------------------
    1234  Success  N/A        deployment successful
    ```

### Step 11 (Optional): Create a private endpoint for Storage

```bash
az storage account create --resource-group $RG --name $STORAGE_NAME --location $LOCATION --sku Standard_LRS --kind StorageV2
STORAGE_ID="$(az storage account show --resource-group $RG --name $STORAGE_NAME --query id --output tsv)"
az network private-endpoint create --resource-group $RG --name pe-storage-blob --vnet-name $VNET_NAME --subnet $PE_SUBNET_NAME --private-connection-resource-id $STORAGE_ID --group-id blob --connection-name pe-storage-blob-connection
```

???+ example "Expected output"
    ```json
    {
      "name": "pe-storage-blob",
      "privateLinkServiceConnections": [
        {
          "groupIds": [
            "blob"
          ],
          "privateLinkServiceId": "/subscriptions/<subscription-id>/resourceGroups/rg-dotnet-tutorial/providers/Microsoft.Storage/storageAccounts/stdotnettutorialabc123"
        }
      ]
    }
    ```

### Step 12: Stream live logs

```bash
az webapp log config --resource-group $RG --name $APP_NAME --application-logging filesystem --level information
az webapp log tail --resource-group $RG --name $APP_NAME
```

???+ example "Expected output"
    ```text
    2026-04-09T03:11:22  Connected to log-streaming service.
    2026-04-09T03:11:23  Request: GET /health 200 12ms
    ```

### Step 13: Inspect files in Kudu (SCM)

```bash
SCM_URL="https://$(az webapp show --resource-group $RG --name $APP_NAME --query name --output tsv).scm.azurewebsites.net"
printf "SCM URL: %s\n" "$SCM_URL"
az webapp deployment list-publishing-profiles --resource-group $RG --name $APP_NAME --output table
```

???+ example "Expected output"
    ```text
    SCM URL: https://app-dotnet-tutorial-abc123.scm.azurewebsites.net

    Name    PublishMethod    PublishUrl
    ------  ---------------  ---------------------------------------------------
    app-dotnet-tutorial-abc123  MSDeploy  app-dotnet-tutorial-abc123.scm.azurewebsites.net:443
    ```

## Advanced Topics

Use slot-based deployments for zero-downtime swaps, prebuild deterministic release artifacts in CI, and combine VNet integration with private endpoints to keep outbound traffic on private network paths.

## Verification

```bash
WEB_APP_URL="https://$(az webapp show --resource-group $RG --name $APP_NAME --query defaultHostName --output tsv)"
curl --include $WEB_APP_URL/health
```

???+ example "Expected output"
    ```text
    HTTP/1.1 200 OK
    Content-Type: application/json; charset=utf-8

    {"status":"ok"}
    ```

## Troubleshooting

### Deployment succeeded but app returns 500

- Confirm zip contains published output (`.dll`, `.deps.json`, `web.config`)
- Check App Service Log Stream and Event Log messages
- Re-run publish and deploy from clean output directory

### Resource naming conflict

Use a globally unique base name, for example:

```bash
APP_NAME="app-dotnet-tutorial-$RANDOM"
```

### Incorrect runtime stack

Validate App Service configuration after deployment:

```bash
az webapp config show --resource-group $RG --name $APP_NAME --output json
```

## See Also

- [03. Configuration](./03-configuration.md)
- [05. Infrastructure as Code](./05-infrastructure-as-code.md)
- For platform details, see [Azure App Service Guide](https://yeongseon.github.io/azure-app-service-practical-guide/)

## Sources

- [Deploy a ZIP file to Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip)
- [Quickstart: Deploy an ASP.NET web app](https://learn.microsoft.com/en-us/azure/app-service/quickstart-dotnetcore)
- [Azure App Service deployment overview](https://learn.microsoft.com/en-us/azure/app-service/deploy-best-practices)
