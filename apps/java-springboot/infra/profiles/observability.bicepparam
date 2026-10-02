using '../main.bicep'

param baseName = 'java-ref-observability'
param appServicePlanSku = 'B1'
param logAnalyticsRetentionDays = 90
param appInsightsSamplingPercentage = '100'
