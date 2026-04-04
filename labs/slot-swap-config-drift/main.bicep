targetScope = 'resourceGroup'

@description('Base name used to construct resource names.')
param baseName string

@description('Azure region for all resources.')
param location string = resourceGroup().location

var uniqueSuffix = uniqueString(resourceGroup().id)
var serverFarmName = 'asp-${baseName}-${uniqueSuffix}'
var webAppName = 'app-${baseName}-${uniqueSuffix}'
var workspaceName = 'log-${baseName}-${uniqueSuffix}'
var productionDiagnosticName = 'diag-prod-${baseName}-${uniqueSuffix}'
var stagingDiagnosticName = 'diag-staging-${baseName}-${uniqueSuffix}'
var stagingSlotName = 'staging'

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: serverFarmName
  location: location
  sku: {
    name: 'S1'
    tier: 'Standard'
    size: 'S1'
    capacity: 1
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: workspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: false
      appCommandLine: 'gunicorn --bind=0.0.0.0 --timeout=120 --workers=2 app:app'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'DB_CONNECTION_STRING'
          value: 'prod-server.database.windows.net'
        }
        {
          name: 'FEATURE_FLAG'
          value: 'v1'
        }
      ]
    }
  }
}

resource stagingSlot 'Microsoft.Web/sites/slots@2023-12-01' = {
  name: '${webApp.name}/${stagingSlotName}'
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: false
      appCommandLine: 'gunicorn --bind=0.0.0.0 --timeout=120 --workers=2 app:app'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'DB_CONNECTION_STRING'
          value: 'staging-server.database.windows.net'
        }
        {
          name: 'FEATURE_FLAG'
          value: 'v2'
        }
      ]
    }
  }
}

resource slotConfigNames 'Microsoft.Web/sites/config@2023-12-01' = {
  name: '${webApp.name}/slotConfigNames'
  properties: {
    appSettingNames: [
      'DB_CONNECTION_STRING'
    ]
    connectionStringNames: []
  }
}

resource webAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: productionDiagnosticName
  scope: webApp
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
      }
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
      }
      {
        category: 'AppServicePlatformLogs'
        enabled: true
      }
    ]
    metrics: []
  }
}

resource stagingSlotDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: stagingDiagnosticName
  scope: stagingSlot
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
      }
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
      }
      {
        category: 'AppServicePlatformLogs'
        enabled: true
      }
    ]
    metrics: []
  }
}

output appServicePlanName string = appServicePlan.name
output webAppName string = webApp.name
output productionDefaultHostName string = webApp.properties.defaultHostName
output stagingDefaultHostName string = '${webApp.name}-${stagingSlotName}.azurewebsites.net'
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name
output logAnalyticsWorkspaceResourceId string = logAnalyticsWorkspace.id
