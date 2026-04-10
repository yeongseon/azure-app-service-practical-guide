---
hide:
  - toc
content_sources:
  diagrams:
    - id: private-network-deploy
      type: flowchart
      source: self-generated
      justification: "Combines the .NET App Service quickstart with VNet integration, private endpoint, and managed identity guidance into one deployment scenario."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/quickstart-dotnetcore
        - https://learn.microsoft.com/en-us/azure/app-service/configure-vnet-integration-enable
        - https://learn.microsoft.com/en-us/azure/app-service/networking/private-endpoint
        - https://learn.microsoft.com/en-us/azure/app-service/tutorial-connect-msi-azure-database
    - id: private-network-deploy-flow
      type: flowchart
      source: self-generated
      justification: "Summarizes the end-to-end deployment flow for a private .NET App Service scenario."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/configure-vnet-integration-enable
        - https://learn.microsoft.com/en-us/azure/app-service/networking/private-endpoint
        - https://learn.microsoft.com/en-us/azure/app-service/tutorial-connect-msi-azure-database
---

# Private Network Deploy

Use this recipe after [02 - First Deploy](../02-first-deploy.md) when you need outbound VNet integration, private endpoints for dependencies, and managed identity for passwordless access.

<!-- diagram-id: private-network-deploy -->
```mermaid
flowchart TD
    USER[Browser] -->|HTTPS| APP[App Service\n.NET 8 app]

    subgraph VNET[Virtual network]
        APP --> INT[Integration subnet]
        PE_SQL[Private Endpoint: Azure SQL]
        PE_KV[Private Endpoint: Key Vault]
    end

    INT --> PE_SQL
    INT --> PE_KV
    PE_SQL --> SQL[Azure SQL]
    PE_KV --> KV[Key Vault]
    APP -.-> MI[System-assigned managed identity]
    MI -.-> ENTRA[Microsoft Entra ID]

    style APP fill:#0078d4,color:#fff
    style VNET fill:#E8F5E9,stroke:#4CAF50
```

<!-- diagram-id: private-network-deploy-flow -->
```mermaid
flowchart LR
    A[Create VNet and subnets] --> B[Integrate App Service]
    B --> C[Enable managed identity]
    C --> D[Create private endpoints and DNS links]
    D --> E[Grant RBAC and deploy config]
    E --> F[Validate private connectivity]
```

## Prerequisites

- Completed [02 - First Deploy](../02-first-deploy.md)
- App Service plan tier that supports VNet integration
- Existing Azure SQL server and Key Vault, or equivalent private-link capable services
- Permissions to configure networking, private DNS, RBAC, and managed identity

## Main Content

### Step 1: Set advanced deployment variables

```bash
RG="rg-dotnet-guide"
APP_NAME="app-dotnet-guide-abc123"
LOCATION="koreacentral"
VNET_NAME="vnet-dotnet-guide"
INTEGRATION_SUBNET_NAME="snet-appsvc-integration"
PRIVATE_ENDPOINT_SUBNET_NAME="snet-private-endpoints"
SQL_SERVER_NAME="sql-dotnet-guide"
KEY_VAULT_NAME="kv-dotnet-guide"
```

| Command/Code | Purpose |
|--------------|---------|
| `RG`, `APP_NAME`, `LOCATION` | Reuse the baseline values from the first deployment tutorial. |
| `VNET_NAME` | Defines the virtual network that hosts the integration and private endpoint subnets. |
| `INTEGRATION_SUBNET_NAME` | Names the delegated subnet used by App Service VNet integration. |
| `PRIVATE_ENDPOINT_SUBNET_NAME` | Names the subnet that hosts private endpoint network interfaces. |
| `SQL_SERVER_NAME` | Identifies the Azure SQL server used in the private connectivity example. |
| `KEY_VAULT_NAME` | Identifies the Key Vault used with managed identity. |

### Step 2: Create the VNet and required subnets

```bash
az network vnet create --resource-group "$RG" --name "$VNET_NAME" --location "$LOCATION" --address-prefixes "10.0.0.0/16"
az network vnet subnet create --resource-group "$RG" --vnet-name "$VNET_NAME" --name "$INTEGRATION_SUBNET_NAME" --address-prefixes "10.0.1.0/24" --delegations "Microsoft.Web/serverFarms"
az network vnet subnet create --resource-group "$RG" --vnet-name "$VNET_NAME" --name "$PRIVATE_ENDPOINT_SUBNET_NAME" --address-prefixes "10.0.2.0/24" --disable-private-endpoint-network-policies true
```

| Command/Code | Purpose |
|--------------|---------|
| `az network vnet create --resource-group "$RG" --name "$VNET_NAME" --location "$LOCATION" --address-prefixes "10.0.0.0/16"` | Creates the virtual network used by the private deployment pattern. |
| `az network vnet subnet create --resource-group "$RG" --vnet-name "$VNET_NAME" --name "$INTEGRATION_SUBNET_NAME" --address-prefixes "10.0.1.0/24" --delegations "Microsoft.Web/serverFarms"` | Creates the delegated subnet required for App Service outbound VNet integration. |
| `az network vnet subnet create --resource-group "$RG" --vnet-name "$VNET_NAME" --name "$PRIVATE_ENDPOINT_SUBNET_NAME" --address-prefixes "10.0.2.0/24" --disable-private-endpoint-network-policies true` | Creates the subnet that can host private endpoint NICs. |

### Step 3: Integrate the web app and enable managed identity

```bash
az webapp vnet-integration add --resource-group "$RG" --name "$APP_NAME" --vnet "$VNET_NAME" --subnet "$INTEGRATION_SUBNET_NAME"
az webapp identity assign --resource-group "$RG" --name "$APP_NAME"
```

| Command/Code | Purpose |
|--------------|---------|
| `az webapp vnet-integration add --resource-group "$RG" --name "$APP_NAME" --vnet "$VNET_NAME" --subnet "$INTEGRATION_SUBNET_NAME"` | Connects outbound app traffic to the delegated VNet subnet. |
| `az webapp identity assign --resource-group "$RG" --name "$APP_NAME"` | Enables a system-assigned managed identity for passwordless Azure access. |

### Step 4: Create private endpoints and private DNS links

```bash
SQL_SERVER_ID="$(az sql server show --resource-group "$RG" --name "$SQL_SERVER_NAME" --query id --output tsv)"
KEY_VAULT_ID="$(az keyvault show --resource-group "$RG" --name "$KEY_VAULT_NAME" --query id --output tsv)"

az network private-endpoint create --resource-group "$RG" --name "pe-sql-dotnet-guide" --vnet-name "$VNET_NAME" --subnet "$PRIVATE_ENDPOINT_SUBNET_NAME" --private-connection-resource-id "$SQL_SERVER_ID" --group-id sqlServer --connection-name "pe-sql-dotnet-guide-connection"
az network private-endpoint create --resource-group "$RG" --name "pe-kv-dotnet-guide" --vnet-name "$VNET_NAME" --subnet "$PRIVATE_ENDPOINT_SUBNET_NAME" --private-connection-resource-id "$KEY_VAULT_ID" --group-id vault --connection-name "pe-kv-dotnet-guide-connection"

az network private-dns zone create --resource-group "$RG" --name "privatelink.database.windows.net"
az network private-dns zone create --resource-group "$RG" --name "privatelink.vaultcore.azure.net"
az network private-dns link vnet create --resource-group "$RG" --zone-name "privatelink.database.windows.net" --name "sql-link" --virtual-network "$VNET_NAME" --registration-enabled false
az network private-dns link vnet create --resource-group "$RG" --zone-name "privatelink.vaultcore.azure.net" --name "kv-link" --virtual-network "$VNET_NAME" --registration-enabled false
```

| Command/Code | Purpose |
|--------------|---------|
| `SQL_SERVER_ID="$(az sql server show --resource-group "$RG" --name "$SQL_SERVER_NAME" --query id --output tsv)"` | Resolves the Azure SQL resource ID used by the private endpoint. |
| `KEY_VAULT_ID="$(az keyvault show --resource-group "$RG" --name "$KEY_VAULT_NAME" --query id --output tsv)"` | Resolves the Key Vault resource ID used by the private endpoint. |
| `az network private-endpoint create ... --group-id sqlServer ...` | Creates a private endpoint for Azure SQL in the private endpoint subnet. |
| `az network private-endpoint create ... --group-id vault ...` | Creates a private endpoint for Key Vault in the private endpoint subnet. |
| `az network private-dns zone create ...` | Creates the private DNS zones used to resolve service hostnames to private IP addresses. |
| `az network private-dns link vnet create ...` | Links the VNet to the private DNS zones so the web app resolves backend names privately. |

!!! warning "DNS is part of the deployment"
    Private endpoints without private DNS links usually fail at runtime even when the endpoint itself shows as created.

### Step 5: Grant access and configure the app

```bash
WEB_APP_PRINCIPAL_ID="$(az webapp identity show --resource-group "$RG" --name "$APP_NAME" --query principalId --output tsv)"

az role assignment create --assignee-object-id "$WEB_APP_PRINCIPAL_ID" --assignee-principal-type ServicePrincipal --role "Key Vault Secrets User" --scope "$KEY_VAULT_ID"

az webapp config appsettings set --resource-group "$RG" --name "$APP_NAME" --settings \
  ConnectionStrings__SqlServer="Server=tcp:${SQL_SERVER_NAME}.database.windows.net,1433;Database=<database-name>;Encrypt=True;TrustServerCertificate=False;" \
  KeyVault__Uri="https://${KEY_VAULT_NAME}.vault.azure.net/"
```

```csharp
using Azure.Identity;
using Azure.Security.KeyVault.Secrets;
using Microsoft.Data.SqlClient;

var credential = new DefaultAzureCredential();

builder.Services.AddSingleton(_ =>
    new SecretClient(new Uri(builder.Configuration["KeyVault:Uri"]!), credential));

var sqlToken = (await credential.GetTokenAsync(
    new Azure.Core.TokenRequestContext(new[] { "https://database.windows.net/.default" })
)).Token;

var sqlConnection = new SqlConnection(builder.Configuration.GetConnectionString("SqlServer"))
{
    AccessToken = sqlToken
};
```

| Command/Code | Purpose |
|--------------|---------|
| `WEB_APP_PRINCIPAL_ID="$(az webapp identity show --resource-group "$RG" --name "$APP_NAME" --query principalId --output tsv)"` | Retrieves the managed identity object ID for RBAC assignment. |
| `az role assignment create --assignee-object-id "$WEB_APP_PRINCIPAL_ID" --assignee-principal-type ServicePrincipal --role "Key Vault Secrets User" --scope "$KEY_VAULT_ID"` | Grants the web app permission to read secrets from Key Vault. |
| `az webapp config appsettings set ...` | Stores the SQL hostname and Key Vault URI in App Service configuration. |
| `new DefaultAzureCredential()` | Uses local developer identity locally and managed identity in App Service. |
| `AccessToken = sqlToken` | Authenticates SQL connections without embedding passwords in configuration. |

### Step 6: Validate the private deployment

```bash
az webapp vnet-integration list --resource-group "$RG" --name "$APP_NAME" --output table
az network private-endpoint list --resource-group "$RG" --output table
az webapp log tail --resource-group "$RG" --name "$APP_NAME"
```

| Command/Code | Purpose |
|--------------|---------|
| `az webapp vnet-integration list --resource-group "$RG" --name "$APP_NAME" --output table` | Confirms that the web app is attached to the expected integration subnet. |
| `az network private-endpoint list --resource-group "$RG" --output table` | Shows the current private endpoint resources and their approval state. |
| `az webapp log tail --resource-group "$RG" --name "$APP_NAME"` | Streams runtime logs while testing SQL and Key Vault access. |

## Verification

- `az webapp vnet-integration list` shows the correct VNet and subnet
- Private endpoints show as created and approved
- The app can resolve SQL and Key Vault hostnames through private DNS
- `DefaultAzureCredential` succeeds in App Service without secrets

## Troubleshooting

### Private endpoint exists but app cannot connect

- Validate private DNS zone links first.
- Confirm the app is integrated with the expected VNet and subnet.
- Review NSG and route table rules on both subnets.

### Managed identity authentication fails

- Confirm the web app identity is enabled.
- Wait for RBAC propagation after role assignment.
- Verify the SQL or Key Vault permission model matches your target service.

### SQL hostname still resolves publicly

- Check the `privatelink.database.windows.net` zone link.
- Confirm no custom DNS server is overriding Azure private DNS behavior.

## See Also

- [02 - First Deploy](../02-first-deploy.md)
- [VNet Integration](vnet-integration.md)
- [Private Endpoints](private-endpoints.md)
- [Managed Identity](managed-identity.md)

## Sources

- [Integrate your app with an Azure virtual network](https://learn.microsoft.com/en-us/azure/app-service/configure-vnet-integration-enable)
- [Use private endpoints for Azure App Service apps](https://learn.microsoft.com/en-us/azure/app-service/networking/private-endpoint)
- [Tutorial: Connect to Azure SQL Database from ASP.NET Core on App Service without secrets using a managed identity](https://learn.microsoft.com/en-us/azure/app-service/tutorial-connect-msi-azure-database)
