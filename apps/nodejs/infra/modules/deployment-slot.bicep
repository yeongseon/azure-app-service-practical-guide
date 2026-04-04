@description('Resource group location')
param location string = resourceGroup().location

@description('Parent Web App name')
param webAppName string

@description('Slot name')
param slotName string = 'staging'

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('Node.js LTS version')
param nodeVersion string = '20'

@description('Telemetry mode')
param telemetryMode string = 'basic'

@description('Log level for staging (typically more verbose)')
param logLevel string = 'debug'

@description('Node.js environment')
param nodeEnv string = 'production'

@description('Sampling ratio')
param samplingRatio string = '1.0'

resource webApp 'Microsoft.Web/sites@2022-03-01' existing = {
  name: webAppName
}

resource slot 'Microsoft.Web/sites/slots@2022-03-01' = {
  name: slotName
  parent: webApp
  location: location
  kind: 'app,linux'
  properties: {
    siteConfig: {
      linuxFxVersion: 'NODE|${nodeVersion}-lts'
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
        {
          name: 'SLOT_NAME'
          value: slotName
        }
      ]
    }
  }
}

resource slotConfig 'Microsoft.Web/sites/slots/config@2022-03-01' = {
  name: 'slotConfigNames'
  parent: slot
  properties: {
    appSettingNames: [
      'SLOT_NAME'
      'LOG_LEVEL'
    ]
  }
}

output slotName string = slot.name
output slotUrl string = 'https://${slot.properties.defaultHostName}'
