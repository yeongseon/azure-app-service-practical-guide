targetScope = 'resourceGroup'

@description('Base name used to build uniquely named Lab 2 resources.')
@minLength(3)
@maxLength(15)
param baseName string

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Spring MVC async request timeout in milliseconds. Preserved from Lab 1 for symmetry; not used by /slow endpoint.')
param springMvcAsyncRequestTimeoutMs int = 600000

@description('Enable custom Auto-Heal rule. Toggle to true for E4 redeploy. Default false for Pre-E1 baseline.')
param enableCustomAutoHeal bool = false

@description('Auto-Heal action type. Set to LogEvent for E4 preflight (harmless), Recycle for E4 main run.')
@allowed([
  'LogEvent'
  'Recycle'
])
param autoHealActionType string = 'Recycle'

@description('Number of App Service Plan instances. Set to 2 for optional E5.')
@minValue(1)
@maxValue(3)
param planInstanceCount int = 1

var uniqueSuffix = uniqueString(resourceGroup().id)
var appServicePlanName = 'asp-${baseName}-${uniqueSuffix}'
var webAppName = 'app-${baseName}-${uniqueSuffix}'
var logAnalyticsWorkspaceName = 'law-${baseName}-${uniqueSuffix}'
var commonSiteConfig = {
  javaVersion: '17'
  javaContainer: 'JAVA'
  javaContainerVersion: 'SE'
  alwaysOn: true
  httpLoggingEnabled: true
  detailedErrorLoggingEnabled: true
  requestTracingEnabled: true
  minTlsVersion: '1.2'
  ftpsState: 'Disabled'
  appSettings: [
    {
      name: 'WEBSITE_JAVA_JAR_FILE_NAME'
      value: 'app.jar'
    }
    {
      name: 'WEBSITE_PROACTIVE_AUTOHEAL_ENABLED'
      value: 'false'
    }
    {
      name: 'SPRING_MVC_ASYNC_REQUEST_TIMEOUT'
      value: string(springMvcAsyncRequestTimeoutMs)
    }
  ]
}
var autoHealSiteConfig = enableCustomAutoHeal
  ? {
      autoHealEnabled: true
      autoHealRules: {
        triggers: {
          statusCodes: [
            {
              status: 500
              subStatus: 121
              win32Status: 64
              path: '/slow/240'
              count: 5
              timeInterval: '00:02:00'
            }
          ]
        }
        actions: {
          actionType: autoHealActionType
          minProcessExecutionTime: '00:01:00'
        }
      }
    }
  : {
      autoHealEnabled: false
    }

// Windows Basic B1 App Service Plan.
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
    size: 'B1'
    family: 'B'
    capacity: planInstanceCount
  }
  kind: 'app'
  properties: {}
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Windows Java SE 17 Web App.
resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  kind: 'app'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: union(commonSiteConfig, autoHealSiteConfig)
  }
}

// SCM and FTP basic-auth publishing credentials.
resource scmBasicAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2023-12-01' = {
  parent: webApp
  name: 'scm'
  properties: {
    allow: true
  }
}

resource ftpBasicAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2023-12-01' = {
  parent: webApp
  name: 'ftp'
  properties: {
    allow: true
  }
}

resource webAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${webAppName}'
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
        category: 'AppServiceAppLogs'
        enabled: true
      }
      {
        category: 'AppServicePlatformLogs'
        enabled: true
      }
      {
        category: 'AppServiceIPSecAuditLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

output webAppName string = webApp.name
output resourceGroupName string = resourceGroup().name
output appServicePlanName string = appServicePlan.name
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id
output webAppHostname string = webApp.properties.defaultHostName
output webAppResourceId string = webApp.id
