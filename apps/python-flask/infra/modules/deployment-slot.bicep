@description('Resource group location')
param location string = resourceGroup().location

@description('Parent Web App name')
param webAppName string

@description('Slot name')
param slotName string = 'staging'

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('Python runtime version')
@allowed([
  '3.10'
  '3.11'
  '3.12'
])
param pythonVersion string = '3.11'

@description('Log level for slot (typically more verbose)')
@allowed([
  'DEBUG'
  'INFO'
  'WARNING'
  'ERROR'
  'CRITICAL'
])
param logLevel string = 'DEBUG'

@description('Sampling ratio')
param samplingRatio string = '1.0'

@description('Enable Gunicorn multi-worker support')
param enableGunicornMultiworkers bool = true

var startupCommand = 'gunicorn --bind=0.0.0.0:8000 --chdir src app:app'

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
      linuxFxVersion: 'PYTHON|${pythonVersion}'
      appCommandLine: startupCommand
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
          name: 'LOG_LEVEL'
          value: logLevel
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
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        {
          name: 'PYTHON_ENABLE_GUNICORN_MULTIWORKERS'
          value: '${enableGunicornMultiworkers}'
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
