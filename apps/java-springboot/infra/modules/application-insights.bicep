param location string
param appInsightsName string
param workspaceResourceId string

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspaceResourceId
  }
}

output appInsightsConnectionString string = applicationInsights.properties.ConnectionString
output appInsightsName string = applicationInsights.name
