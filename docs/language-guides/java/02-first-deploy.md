---
hide:
  - toc
---

# 02. First Deploy

Deploy the Java guide application to Azure App Service using Bicep for infrastructure and Maven Plugin for code deployment.

!!! info "Infrastructure Context"
    **Service**: App Service (Linux, Standard S1) | **Network**: VNet integrated | **VNet**: ✅

    This tutorial assumes a production-ready App Service deployment with VNet integration, private endpoints for backend services, and managed identity for authentication.

    ```mermaid
    flowchart TD
        INET[Internet] -->|HTTPS| WA["Web App\nApp Service S1\nLinux Java 17"]

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

## Prerequisites

- Completed [01. Local Run](01-local-run.md)
- Azure CLI logged in: `az login`
- Contributor access to your Azure subscription
- Unique base name ready for globally unique app naming

## What you'll learn

- How `infra/deploy.sh` orchestrates infrastructure + app deployment
- How to deploy Bicep templates manually with Azure CLI
- How to deploy Spring Boot JAR with `azure-webapp-maven-plugin`
- How to verify deployment health in Azure

## Main Content

```mermaid
flowchart LR
    A[Set RG APP PLAN variables] --> B[Create group plan web app]
    B --> C[Build JAR with Maven]
    C --> D[Set startup command]
    D --> E[Deploy JAR package]
    E --> F[Verify health endpoint]
```

### Step 1: Prepare deployment variables

```bash
SUBSCRIPTION_ID="<subscription-id>"
RG="rg-springboot-tutorial"
LOCATION="koreacentral"
PLAN_NAME="plan-springboot-tutorial-s1"
APP_NAME="app-springboot-tutorial-abc123"
VNET_NAME="vnet-springboot-tutorial"
INTEGRATION_SUBNET_NAME="snet-appsvc-integration"
PE_SUBNET_NAME="snet-private-endpoints"
STORAGE_NAME="stspringboottutorialabc123"
```

???+ example "Expected output"
    ```text
    Variables prepared for resource group rg-springboot-tutorial and app app-springboot-tutorial-abc123.
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
az appservice plan create --resource-group $RG --name $PLAN_NAME --is-linux --sku S1
az webapp create --resource-group $RG --plan $PLAN_NAME --name $APP_NAME --runtime "JAVA|17-java17"
```

???+ example "Expected output"
    ```json
    {
      "defaultHostName": "app-springboot-tutorial-abc123.azurewebsites.net",
      "enabledHostNames": [
        "app-springboot-tutorial-abc123.azurewebsites.net",
        "app-springboot-tutorial-abc123.scm.azurewebsites.net"
      ],
      "state": "Running"
    }
    ```

### Step 4: Create VNet and delegated integration subnet

```bash
az network vnet create --resource-group $RG --name $VNET_NAME --location $LOCATION --address-prefixes 10.10.0.0/16
az network vnet subnet create --resource-group $RG --vnet-name $VNET_NAME --name $INTEGRATION_SUBNET_NAME --address-prefixes 10.10.1.0/24 --delegations Microsoft.Web/serverFarms
```

???+ example "Expected output"
    ```json
    {
      "addressPrefix": "10.10.1.0/24",
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
az network vnet subnet create --resource-group $RG --vnet-name $VNET_NAME --name $PE_SUBNET_NAME --address-prefixes 10.10.2.0/24 --disable-private-endpoint-network-policies true
```

???+ example "Expected output"
    ```json
    {
      "addressPrefix": "10.10.2.0/24",
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
      "subnetResourceId": "/subscriptions/<subscription-id>/resourceGroups/rg-springboot-tutorial/providers/Microsoft.Network/virtualNetworks/vnet-springboot-tutorial/subnets/snet-appsvc-integration"
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

### Step 8: Build JAR and configure startup command

```bash
./mvnw clean package -DskipTests
az webapp config set --resource-group $RG --name $APP_NAME --startup-file "java -jar /home/site/wwwroot/app.jar --server.port=$PORT"
```

???+ example "Expected output"
    ```text
    [INFO] BUILD SUCCESS
    {
      "appCommandLine": "java -jar /home/site/wwwroot/app.jar --server.port=$PORT",
      "linuxFxVersion": "JAVA|17-java17"
    }
    ```

### Step 9: Deploy JAR to App Service

```bash
az webapp deploy --resource-group $RG --name $APP_NAME --src-path target/*.jar --type jar
```

???+ example "Expected output"
    ```json
    {
      "active": true,
      "author": "N/A",
      "complete": true,
      "status": 4
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
    {"status":"UP"}

    Id    Status   Author  Message
    ----  -------  ------  ----------------------
    1038  Success  N/A     Deployment successful
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
          "privateLinkServiceId": "/subscriptions/<subscription-id>/resourceGroups/rg-springboot-tutorial/providers/Microsoft.Storage/storageAccounts/stspringboottutorialabc123"
        }
      ]
    }
    ```

### Step 12: Stream live logs

!!! note "Enable logging first"
    `az webapp log tail` only streams output if application logging is enabled.

    ```bash
    az webapp log config --resource-group $RG --name $APP_NAME --application-logging filesystem --level information
    ```

```bash
az webapp log tail --resource-group $RG --name $APP_NAME
```

???+ example "Expected output"
    ```text
    2026-04-09T03:12:18.442Z INFO 1 --- [main] c.example.demo.HealthController : Health endpoint invoked
    2026-04-09T03:12:18.447Z INFO 1 --- [main] o.s.b.w.e.tomcat.GracefulShutdown       : Commencing graceful shutdown checks
    ```

### Step 13: Inspect files in Kudu (SCM)

```bash
az webapp show --resource-group $RG --name $APP_NAME --query "{defaultHostName:defaultHostName, scmHost:repositorySiteName}" --output json
```

???+ example "Expected output"
    ```json
    {
      "defaultHostName": "app-springboot-tutorial-abc123.azurewebsites.net",
      "scmHost": "app-springboot-tutorial-abc123.scm.azurewebsites.net"
    }
    ```

Use `https://app-springboot-tutorial-abc123.scm.azurewebsites.net` to inspect `/home/site/wwwroot`, review deployment logs, and open the SSH console.

## Advanced Topics

For deterministic rollouts, package a versioned JAR artifact in CI and deploy the exact same build across staging and production slots before swap.

## Verification

- Azure CLI commands complete without authorization or validation errors
- App Service reports Linux Java runtime as `JAVA|17-java17`
- Startup command is `java -jar /home/site/wwwroot/app.jar --server.port=$PORT`
- `https://$APP_NAME.azurewebsites.net/health` returns HTTP 200
- Deployment history shows the latest operation with `Success`

## Troubleshooting

### Maven deploy cannot find app

Confirm environment variables are set in the same shell:

```bash
echo "$RESOURCE_GROUP_NAME $APP_NAME $LOCATION"
```

### `az deployment group create` fails with naming conflict

Use a more unique `BASE_NAME`; App Service host names must be globally unique.

### Health check fails after deploy

Tail logs:

```bash
az webapp log tail \
  --resource-group "$RG" \
  --name "$APP_NAME"
```

## See Also

- [03. Configuration](03-configuration.md)
- [05. Infrastructure as Code](05-infrastructure-as-code.md)
- [Recipes: Managed Identity](./recipes/managed-identity.md)

## Sources

- [Deploy a ZIP file to Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip)
- [Quickstart: Deploy a Java app to Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/quickstart-java)
- [Azure App Service deployment overview](https://learn.microsoft.com/en-us/azure/app-service/deploy-best-practices)
