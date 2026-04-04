using '../main.bicep'

param baseName = 'python-ref-min'
param appServicePlanSku = 'B1'
param pythonVersion = '3.11'
param logLevel = 'INFO'
param samplingRatio = '1.0'
param logAnalyticsRetentionDays = 30
param enableGunicornMultiworkers = true
