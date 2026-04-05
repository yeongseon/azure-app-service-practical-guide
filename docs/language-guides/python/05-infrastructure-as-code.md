# 05 - Infrastructure as Code for Python App Service

This tutorial provisions Flask hosting infrastructure with Bicep for repeatable environments. It defines Python runtime settings, startup command, and worker-related app settings as code.

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

## See Also
- [06 - CI/CD](./06-ci-cd.md)
- [Provision Infrastructure (Existing Guide)](./02-first-deploy.md)

## Sources
- [Bicep documentation (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
- [Quickstart: Create an App Service app using Bicep (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/app-service/quickstart-arm-template)
