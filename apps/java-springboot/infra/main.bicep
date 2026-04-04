targetScope = 'resourceGroup'

@description('Base name used for resource naming.')
param baseName string

@description('Azure region for resources.')
param location string = resourceGroup().location

@description('App Service plan SKU (e.g., B1, S1).')
param appServicePlanSku string = 'B1'

@description('Log Analytics retention in days.')
@minValue(30)
@maxValue(730)
param logAnalyticsRetentionDays int = 30

@description('Application Insights sampling percentage.')
param appInsightsSamplingPercentage string = '100'

var uniqueSuffix = toLower(uniqueString(resourceGroup().id, baseName))
var appServicePlanName = 'plan-${baseName}-${uniqueSuffix}'
var webAppName = 'app-${baseName}-${uniqueSuffix}'
var logAnalyticsWorkspaceName = 'law-${baseName}-${uniqueSuffix}'
var appInsightsName = 'appi-${baseName}-${uniqueSuffix}'

module logAnalytics './modules/log-analytics.bicep' = {
  name: 'logAnalyticsDeployment'
  params: {
    location: location
    workspaceName: logAnalyticsWorkspaceName
    retentionInDays: logAnalyticsRetentionDays
  }
}

module applicationInsights './modules/application-insights.bicep' = {
  name: 'applicationInsightsDeployment'
  params: {
    location: location
    appInsightsName: appInsightsName
    workspaceResourceId: logAnalytics.outputs.workspaceId
  }
}

module appServicePlan './modules/appservice-plan.bicep' = {
  name: 'appServicePlanDeployment'
  params: {
    location: location
    appServicePlanName: appServicePlanName
    skuName: appServicePlanSku
  }
}

module webApp './modules/webapp.bicep' = {
  name: 'webAppDeployment'
  params: {
    location: location
    webAppName: webAppName
    appServicePlanId: appServicePlan.outputs.appServicePlanId
    appInsightsConnectionString: applicationInsights.outputs.appInsightsConnectionString
    samplingPercentage: appInsightsSamplingPercentage
  }
}

output webAppName string = webApp.outputs.webAppName
output webAppUrl string = webApp.outputs.webAppUrl
output appServicePlanName string = appServicePlan.outputs.appServicePlanName
output appInsightsName string = applicationInsights.outputs.appInsightsName
output logAnalyticsWorkspaceName string = logAnalytics.outputs.workspaceName
