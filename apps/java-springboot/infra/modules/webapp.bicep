param location string
param webAppName string
param appServicePlanId string
param appInsightsConnectionString string
param samplingPercentage string = '100'

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlanId
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'JAVA|17-java17'
      healthCheckPath: '/health'
      appCommandLine: 'java -jar /home/site/wwwroot/*.jar --server.port=$PORT'
      alwaysOn: false
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'APPLICATION_INSIGHTS_SAMPLING_PERCENTAGE'
          value: samplingPercentage
        }
        {
          name: 'WEBSITES_PORT'
          value: '8080'
        }
        {
          name: 'SPRING_PROFILES_ACTIVE'
          value: 'production'
        }
        {
          name: 'JAVA_OPTS'
          value: '-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -Djava.security.egd=file:/dev/./urandom'
        }
      ]
    }
  }
}

output webAppName string = webApp.name
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
