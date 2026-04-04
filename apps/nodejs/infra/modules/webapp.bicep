@description('Resource group location')
param location string = resourceGroup().location

@description('Name of the Web App')
param name string

@description('App Service Plan ID')
param appServicePlanId string

@description('App Service Plan SKU (for alwaysOn configuration)')
param appServicePlanSku string

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('Node.js LTS version')
@allowed([
  '18'
  '20'
  '22'
])
param nodeVersion string = '20'

@description('Telemetry mode: basic (console-only) or advanced (Winston + OTel)')
@allowed([
  'basic'
  'advanced'
])
param telemetryMode string = 'basic'

@description('Log level')
@allowed([
  'debug'
  'info'
  'warn'
  'error'
])
param logLevel string = 'info'

@description('Node.js environment')
@allowed([
  'development'
  'production'
])
param nodeEnv string = 'production'

@description('Application Insights sampling ratio (0.0-1.0)')
param samplingRatio string = '1.0'

@description('Log Analytics workspace ID for diagnostic settings')
param logAnalyticsWorkspaceId string

var basicSkus = ['B1', 'B2', 'B3']
var alwaysOn = !contains(basicSkus, appServicePlanSku)

resource webApp 'Microsoft.Web/sites@2022-03-01' = {
  name: name
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlanId
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'NODE|${nodeVersion}-lts'
      alwaysOn: alwaysOn
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      appSettings: [
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'ApplicationInsightsAgent_EXTENSION_VERSION'
          value: '~3'
        }
        {
          name: 'TELEMETRY_MODE'
          value: telemetryMode
        }
        {
          name: 'LOG_LEVEL'
          value: logLevel
        }
        {
          name: 'NODE_ENV'
          value: nodeEnv
        }
        {
          name: 'SAMPLING_RATIO'
          value: samplingRatio
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'WEBSITE_NODE_DEFAULT_VERSION'
          value: '~${nodeVersion}'
        }
      ]
      logsDirectorySizeLimit: 100
    }
  }
}

resource webAppLogs 'Microsoft.Web/sites/config@2022-03-01' = {
  name: 'logs'
  parent: webApp
  properties: {
    applicationLogs: {
      fileSystem: {
        level: 'Verbose'
      }
    }
    httpLogs: {
      fileSystem: {
        enabled: true
        retentionInMb: 100
        retentionInDays: 7
      }
    }
    failedRequestsTracing: {
      enabled: true
    }
    detailedErrorMessages: {
      enabled: true
    }
  }
}

resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${name}-diagnostics'
  scope: webApp
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'AppServiceAppLogs'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

output id string = webApp.id
output name string = webApp.name
output defaultHostName string = webApp.properties.defaultHostName
output url string = 'https://${webApp.properties.defaultHostName}'
