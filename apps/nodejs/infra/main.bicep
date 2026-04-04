@description('Resource group location')
param location string = resourceGroup().location

@description('Base name for resources')
param baseName string = 'nodejs-app'

@description('App Service Plan SKU')
@allowed([
  'B1'
  'B2'
  'B3'
  'S1'
  'S2'
  'S3'
  'P1V3'
  'P2V3'
  'P3V3'
])
param appServicePlanSku string = 'B1'

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

@description('Log Analytics workspace retention in days')
@minValue(30)
@maxValue(730)
param logAnalyticsRetentionDays int = 90

@description('Application log level')
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

var appServicePlanName = 'asp-${baseName}'
var webAppName = 'app-${baseName}-${uniqueString(resourceGroup().id)}'
var logAnalyticsName = 'log-${baseName}'
var appInsightsName = 'appi-${baseName}'

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'logAnalytics'
  params: {
    location: location
    name: logAnalyticsName
    retentionInDays: logAnalyticsRetentionDays
  }
}

module appInsights 'modules/application-insights.bicep' = {
  name: 'appInsights'
  params: {
    location: location
    name: appInsightsName
    workspaceId: logAnalytics.outputs.id
  }
}

module appServicePlan 'modules/appservice-plan.bicep' = {
  name: 'appServicePlan'
  params: {
    location: location
    name: appServicePlanName
    sku: appServicePlanSku
  }
}

module webApp 'modules/webapp.bicep' = {
  name: 'webApp'
  params: {
    location: location
    name: webAppName
    appServicePlanId: appServicePlan.outputs.id
    appServicePlanSku: appServicePlanSku
    appInsightsConnectionString: appInsights.outputs.connectionString
    nodeVersion: nodeVersion
    telemetryMode: telemetryMode
    logLevel: logLevel
    nodeEnv: nodeEnv
    samplingRatio: samplingRatio
    logAnalyticsWorkspaceId: logAnalytics.outputs.id
  }
}

output resourceGroupName string = resourceGroup().name
output webAppName string = webApp.outputs.name
output webAppUrl string = webApp.outputs.url
output appInsightsName string = appInsights.outputs.name
output appInsightsInstrumentationKey string = appInsights.outputs.instrumentationKey
output appInsightsConnectionString string = appInsights.outputs.connectionString
output logAnalyticsWorkspaceName string = logAnalytics.outputs.name
output logAnalyticsWorkspaceId string = logAnalytics.outputs.id
