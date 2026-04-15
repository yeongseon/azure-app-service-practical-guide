---
content_sources:
  diagrams:
    - id: 03-configure-flask-app-settings-on-app-service
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/configure-common
    - id: diagram-2
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/configure-common
---

# 03 - Configure Flask App Settings on App Service

This guide standardizes runtime configuration for Flask on Azure App Service. You will set environment settings, separate dev/prod behavior, and secure secrets with Key Vault references.

!!! info "Infrastructure Context"
    **Service**: App Service (Linux, Standard S1) | **Network**: VNet integrated | **VNet**: ✅

    This tutorial assumes a production-ready App Service deployment with VNet integration, private endpoints for backend services, and managed identity for authentication.

<!-- diagram-id: 03-configure-flask-app-settings-on-app-service -->
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
flowchart TD
    A[Set App Settings] --> B[Read env vars in Flask]
    B --> C[Separate local and production profiles]
    C --> D[Add Key Vault references]
    D --> E[List and validate effective settings]
```

## Prerequisites

- Completed [02 - First Deploy](./02-first-deploy.md)
- Deployed web app running in App Service

## Main Content

### Configure application settings in App Service

```bash
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings FLASK_ENV=production APP_ENV=production LOG_LEVEL=INFO
```

| Command | Purpose |
|---------|---------|
| `az webapp config appsettings set` | Creates or updates environment variables for the App Service app. |
| `--resource-group $RG` | Targets the resource group that contains the web app. |
| `--name $APP_NAME` | Selects the web app whose settings should be updated. |
| `--settings FLASK_ENV=production APP_ENV=production LOG_LEVEL=INFO` | Sets production runtime values for Flask environment, app environment, and log level. |

In Flask code, read settings from environment variables:

```python
import os

FLASK_ENV = os.getenv("FLASK_ENV", "production")
APP_ENV = os.getenv("APP_ENV", "production")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
```

| Code | Purpose |
|------|---------|
| `import os` | Loads Python's standard library module for reading environment variables. |
| `os.getenv("FLASK_ENV", "production")` | Reads `FLASK_ENV` and falls back to `production` when it is not set. |
| `os.getenv("APP_ENV", "production")` | Reads the custom application environment setting with a safe default. |
| `os.getenv("LOG_LEVEL", "INFO")` | Reads the configured log level and defaults to `INFO`. |

### Use environment strategy for local vs cloud

Recommended pattern:

- Local development: `FLASK_ENV=development`, `APP_ENV=local`
- App Service: `FLASK_ENV=production`, `APP_ENV=production`

### Add Key Vault reference for secrets

```bash
KEYVAULT_NAME="kv-flask-tutorial"
SECRET_NAME="DbPassword"

az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings "DB_PASSWORD=@Microsoft.KeyVault(SecretUri=https://$KEYVAULT_NAME.vault.azure.net/secrets/$SECRET_NAME/)"
```

| Command | Purpose |
|---------|---------|
| `KEYVAULT_NAME="kv-flask-tutorial"` | Stores the Key Vault name used to build the secret reference. |
| `SECRET_NAME="DbPassword"` | Stores the Key Vault secret name. |
| `az webapp config appsettings set` | Adds or updates an app setting on the web app. |
| `--resource-group $RG` | Targets the correct resource group. |
| `--name $APP_NAME` | Applies the setting to the selected web app. |
| `--settings "DB_PASSWORD=@Microsoft.KeyVault(...)"` | Configures `DB_PASSWORD` as an App Service Key Vault reference instead of a plain-text secret. |

### Validate effective settings

```bash
az webapp config appsettings list --resource-group $RG --name $APP_NAME
```

| Command | Purpose |
|---------|---------|
| `az webapp config appsettings list --resource-group $RG --name $APP_NAME` | Lists the effective application settings currently configured on the web app. |
| `--resource-group $RG` | Reads settings from the target resource group. |
| `--name $APP_NAME` | Reads settings for the specified App Service app. |

Masked example:

```json
[
  {
    "name": "DB_PASSWORD",
    "value": "@Microsoft.KeyVault(SecretUri=https://kv-flask-tutorial.vault.azure.net/secrets/DbPassword/)"
  },
  {
    "name": "WEBSITE_RUN_FROM_PACKAGE",
    "value": "1"
  }
]
```

## Advanced Topics

Move from single-secret references to identity-based SDK retrieval for dynamic secret versioning and reduced configuration drift across environments.

## See Also
- [04 - Logging and Monitoring](./04-logging-monitoring.md)
- [Key Vault References Recipe](../recipes/key-vault-reference.md)

## Sources
- [Configure an App Service app (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/app-service/configure-common)
- [Use Key Vault references as app settings (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/app-service/app-service-key-vault-references)
