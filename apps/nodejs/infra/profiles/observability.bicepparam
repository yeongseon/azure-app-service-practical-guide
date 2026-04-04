using '../main.bicep'

param baseName = 'nodejs-ref-obs'
param appServicePlanSku = 'B1'
param nodeVersion = '20'
param telemetryMode = 'advanced'
param logLevel = 'debug'
param nodeEnv = 'production'
param samplingRatio = '1.0'
param logAnalyticsRetentionDays = 90
