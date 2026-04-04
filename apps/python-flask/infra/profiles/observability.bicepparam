using '../main.bicep'

param baseName = 'python-ref-obs'
param appServicePlanSku = 'S1'
param pythonVersion = '3.11'
param logLevel = 'DEBUG'
param samplingRatio = '1.0'
param logAnalyticsRetentionDays = 90
param enableGunicornMultiworkers = true
