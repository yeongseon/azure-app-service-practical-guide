---
hide:
  - toc
content_sources:
  diagrams:
    - id: 05-infrastructure-as-code-for-python-app-service
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/
    - id: diagram-2
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/
---

# 05 - Infrastructure as Code for Python App Service

This tutorial provisions Flask hosting infrastructure with Bicep for repeatable environments. It defines Python runtime settings, startup command, and worker-related app settings as code.

!!! info "Infrastructure Context"
    **Service**: App Service (Linux, Standard S1) | **Network**: VNet integrated | **VNet**: ✅

    This tutorial assumes a production-ready App Service deployment with VNet integration, private endpoints for backend services, and managed identity for authentication.

<!-- diagram-id: 05-infrastructure-as-code-for-python-app-service -->
    ```mermaid
    flowchart TD
        INET[Internet] -->|HTTPS| WA[Web App\nApp Service S1\nLinux Python 3.11]

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
    A[Define Bicep resources] --> B[Set linuxFxVersion PYTHON|3.11]
    B --> C[Set gunicorn startup command]
    C --> D[Apply app settings and workers]
    D --> E[Deploy template]
    E --> F[Validate runtime config]
```

## Prerequisites

- Completed [04 - Logging and Monitoring](./04-logging-monitoring.md)
- Azure CLI and Bicep available locally

## Main Content

### Define App Service runtime in Bicep

```bicep
resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appCommandLine: 'gunicorn --bind=0.0.0.0:$PORT src.app:app'
      alwaysOn: true
    }
    httpsOnly: true
  }
}
```

### Configure worker and timeout related settings

```bicep
resource webAppSettings 'Microsoft.Web/sites/config@2023-12-01' = {
  name: '${appName}/appsettings'
  properties: {
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
    PYTHON_ENABLE_GUNICORN_MULTIWORKERS: 'true'
    GUNICORN_CMD_ARGS: '--workers 2 --timeout 120'
    APP_ENV: 'production'
  }
}
```

### Deploy Bicep template

```bash
az deployment group create \
  --resource-group $RG \
  --template-file ./infra/main.bicep \
  --parameters appName=$APP_NAME location=$LOCATION planName=$PLAN_NAME
```

### Validate applied runtime settings

```bash
az webapp config show --resource-group $RG --name $APP_NAME
az webapp config appsettings list --resource-group $RG --name $APP_NAME
```

Masked output excerpt:

```json
{
  "linuxFxVersion": "PYTHON|3.11",
  "appCommandLine": "gunicorn --bind=0.0.0.0:$PORT src.app:app",
  "id": "/subscriptions/<subscription-id>/resourceGroups/rg-flask-tutorial/providers/Microsoft.Web/sites/app-flask-tutorial-abc123/config/web"
}
```

## Advanced Topics

Modularize Bicep by separating compute, monitoring, and networking modules, and use parameter files per environment for deterministic promotion.

## CLI Alternative (No Bicep)

Use these commands when you need an imperative deployment path without changing the existing Bicep workflow.

### Step 1: Set variables

```bash
RG="rg-flask-tutorial"
LOCATION="koreacentral"
PLAN_NAME="plan-flask-tutorial-s1"
APP_NAME="app-flask-tutorial-abc123"
VNET_NAME="vnet-flask-tutorial"
INTEGRATION_SUBNET_NAME="snet-appsvc-integration"
```

### Step 2: Create resource group, plan, and app

```bash
az group create --name $RG --location $LOCATION
az appservice plan create --resource-group $RG --name $PLAN_NAME --is-linux --sku S1
az webapp create --resource-group $RG --plan $PLAN_NAME --name $APP_NAME --runtime "PYTHON|3.11"
```

???+ example "Expected output"
    ```json
    {
      "defaultHostName": "app-flask-tutorial-abc123.azurewebsites.net",
      "state": "Running"
    }
    ```

### Step 3: Configure app settings and startup command

```bash
az webapp config appsettings set --resource-group $RG --name $APP_NAME --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true PYTHON_ENABLE_GUNICORN_MULTIWORKERS=true GUNICORN_CMD_ARGS="--workers 2 --timeout 120" APP_ENV=production
az webapp config set --resource-group $RG --name $APP_NAME --startup-file "gunicorn --bind=0.0.0.0:$PORT src.app:app"
```

???+ example "Expected output"
    ```json
    [
      {
        "name": "SCM_DO_BUILD_DURING_DEPLOYMENT",
        "value": "true"
      },
      {
        "name": "APP_ENV",
        "value": "production"
      }
    ]
    ```

### Step 4 (Optional): Add VNet integration

```bash
az network vnet create --resource-group $RG --name $VNET_NAME --location $LOCATION --address-prefixes 10.0.0.0/16
az network vnet subnet create --resource-group $RG --vnet-name $VNET_NAME --name $INTEGRATION_SUBNET_NAME --address-prefixes 10.0.1.0/24 --delegations Microsoft.Web/serverFarms
az webapp vnet-integration add --resource-group $RG --name $APP_NAME --vnet $VNET_NAME --subnet $INTEGRATION_SUBNET_NAME
```

???+ example "Expected output"
    ```json
    {
      "isSwift": true,
      "subnetResourceId": "/subscriptions/<subscription-id>/resourceGroups/rg-flask-tutorial/providers/Microsoft.Network/virtualNetworks/vnet-flask-tutorial/subnets/snet-appsvc-integration"
    }
    ```

### Step 5: Validate effective configuration

```bash
az webapp config show --resource-group $RG --name $APP_NAME --query "{linuxFxVersion:linuxFxVersion, appCommandLine:appCommandLine}" --output json
az webapp config appsettings list --resource-group $RG --name $APP_NAME --query "[?name=='APP_ENV' || name=='SCM_DO_BUILD_DURING_DEPLOYMENT']" --output json
```

???+ example "Expected output"
    ```json
    {
      "linuxFxVersion": "PYTHON|3.11",
      "appCommandLine": "gunicorn --bind=0.0.0.0:$PORT src.app:app"
    }
    ```

## See Also
- [06 - CI/CD](./06-ci-cd.md)
- [Provision Infrastructure (Existing Guide)](./02-first-deploy.md)

## Sources
- [Bicep documentation (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
- [Quickstart: Create an App Service app using Bicep (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/app-service/quickstart-arm-template)
