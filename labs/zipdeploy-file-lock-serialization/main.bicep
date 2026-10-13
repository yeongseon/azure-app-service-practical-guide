targetScope = 'resourceGroup'

@description('Base name used to construct resource names.')
param baseName string

@description('Azure region for all resources.')
param location string = resourceGroup().location

var uniqueSuffix = uniqueString(resourceGroup().id)
// Resource names are length-limited (Windows plan 40, workspace 63, app 60), so the base name is truncated.
var shortName = take(baseName, 12)
var serverFarmName = 'asp-${shortName}-${uniqueSuffix}'
var webAppName = 'app-${shortName}-${uniqueSuffix}'
var workspaceName = 'log-${shortName}-${uniqueSuffix}'
var diagnosticSettingName = 'diag-${shortName}-${uniqueSuffix}'

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: serverFarmName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
    size: 'B1'
    capacity: 1
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
  kind: 'app'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'WEBSITE_NODE_DEFAULT_VERSION'
          value: '~20'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'false'
        }
      ]
    }
  }
}

resource webAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: diagnosticSettingName
  scope: webApp
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      {
        category: 'AppServiceHTTPLogs'
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
output webAppDefaultHostName string = webApp.properties.defaultHostName
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name
