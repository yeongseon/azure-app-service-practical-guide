@description('Resource group location')
param location string = resourceGroup().location

@description('Base name for resources')
param baseName string = 'dotnet-guide'

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

@description('Application Insights sampling ratio (0.0-1.0)')
param samplingPercentage int = 100

@description('Log Analytics workspace retention in days')
@minValue(30)
@maxValue(730)
param logAnalyticsRetentionDays int = 90

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
  name: 'applicationInsights'
  params: {
    location: location
    name: appInsightsName
    workspaceId: logAnalytics.outputs.id
    samplingPercentage: samplingPercentage
  }
}

module appServicePlan 'modules/appservice-plan.bicep' = {
  name: 'appServicePlan'
  params: {
    location: location
    name: appServicePlanName
    skuName: appServicePlanSku
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
    logAnalyticsWorkspaceId: logAnalytics.outputs.id
  }
}

output resourceGroupName string = resourceGroup().name
output appServicePlanName string = appServicePlan.outputs.name
output webAppName string = webApp.outputs.name
output webAppUrl string = webApp.outputs.url
output appInsightsName string = appInsights.outputs.name
output appInsightsConnectionString string = appInsights.outputs.connectionString
output logAnalyticsWorkspaceName string = logAnalytics.outputs.name
