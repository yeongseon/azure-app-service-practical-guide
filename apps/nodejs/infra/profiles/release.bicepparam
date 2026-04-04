using '../main.bicep'

param baseName = 'nodejs-ref-release'
param appServicePlanSku = 'S1'
param nodeVersion = '20'
param telemetryMode = 'advanced'
param logLevel = 'info'
param nodeEnv = 'production'
param samplingRatio = '0.5'
param logAnalyticsRetentionDays = 90
