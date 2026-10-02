using '../main.bicep'

param baseName = 'nodejs-ref-minimal'
param appServicePlanSku = 'B1'
param nodeVersion = '24'
param telemetryMode = 'basic'
param logLevel = 'info'
param nodeEnv = 'production'
param samplingRatio = '1.0'
param logAnalyticsRetentionDays = 30
