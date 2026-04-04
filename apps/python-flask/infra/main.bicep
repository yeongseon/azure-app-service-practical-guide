@description('Resource group location')
param location string = resourceGroup().location

@description('Base name for resources')
@minLength(3)
@maxLength(20)
param baseName string = 'pyapp'

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

@description('Python runtime version')
@allowed([
  '3.10'
  '3.11'
  '3.12'
])
param pythonVersion string = '3.11'

@description('Log Analytics workspace retention in days')
@minValue(30)
@maxValue(730)
param logAnalyticsRetentionDays int = 90

@description('Application log level')
@allowed([
  'DEBUG'
  'INFO'
  'WARNING'
  'ERROR'
  'CRITICAL'
])
param logLevel string = 'INFO'

@description('Application Insights sampling ratio (0.0-1.0)')
param samplingRatio string = '1.0'

@description('Enable Gunicorn multi-worker support in App Service')
param enableGunicornMultiworkers bool = true

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
    pythonVersion: pythonVersion
    logLevel: logLevel
    samplingRatio: samplingRatio
    enableGunicornMultiworkers: enableGunicornMultiworkers
    logAnalyticsWorkspaceId: logAnalytics.outputs.id
  }
}

output webAppName string = webApp.outputs.name
output webAppUrl string = webApp.outputs.url
output appInsightsName string = appInsights.outputs.name
output appInsightsConnectionString string = appInsights.outputs.connectionString
output logAnalyticsWorkspaceName string = logAnalytics.outputs.name
