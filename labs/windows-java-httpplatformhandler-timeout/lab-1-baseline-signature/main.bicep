targetScope = 'resourceGroup'

@description('Base name used to build uniquely named Lab 1 resources.')
param baseName string

@description('Azure region for all resources. Defaults to the current resource group location.')
param location string = resourceGroup().location

@description('Spring MVC async request timeout in milliseconds. Default 600000 (10 minutes) removes the Tomcat 30s async default that cut Stage 0 /stream/300 at 32s. Must exceed both the App Service front-end 230s limit and any stream target.')
param springMvcAsyncRequestTimeoutMs int = 600000

var uniqueSuffix = uniqueString(resourceGroup().id)
var appServicePlanName = 'asp-${baseName}-${uniqueSuffix}'
var webAppName = 'app-${baseName}-${uniqueSuffix}'
var logAnalyticsWorkspaceName = 'law-${baseName}-${uniqueSuffix}'

// Windows Basic B1 App Service Plan.
// - kind: 'app' selects Windows (Linux would be 'linux' with reserved: true).
// - No reserved property because Windows plans do not use it.
//
// Same SKU as Stage 0 so any behavioral difference between Stage 0 and Lab 1
// is attributable to the intentional configuration delta (async timeout
// override, adaptive probe count) rather than platform tier variance.
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
    size: 'B1'
    family: 'B'
    capacity: 1
  }
  kind: 'app'
  properties: {}
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Windows Java SE 17 Web App.
//
// Lab 1 reuses the exact Stage 0 JAR (byte-identical, per design-proposal.md
// revision 2 and Oracle Section E3). The only configuration deltas versus
// Stage 0 are:
//
// 1. SPRING_MVC_ASYNC_REQUEST_TIMEOUT app setting (Spring Boot honors
//    SPRING_* env vars via relaxed binding, mapping to
//    spring.mvc.async.request-timeout). Set to 600000 ms so the async request
//    outlasts both the App Service front-end 230s ceiling and the stream
//    target 300s. Stage 0 saw /stream/300 cut at 32s because the Tomcat
//    default async request timeout is 30s; Lab 1 removes that defect so E3
//    can measure the true front-end behavior.
//
// 2. No other siteConfig/appSetting change. autoHealEnabled=false,
//    WEBSITE_PROACTIVE_AUTOHEAL_ENABLED=false, alwaysOn=true, and all
//    diagnostic-log settings are preserved verbatim from Stage 0 to keep
//    the timing signal clean.
//
// Do NOT add downstream service, VNet, custom web.config injection, or
// Auto-Heal rules. Those are reserved for Lab 2.
resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  kind: 'app'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      javaVersion: '17'
      javaContainer: 'JAVA'
      javaContainerVersion: 'SE'
      alwaysOn: true
      autoHealEnabled: false
      httpLoggingEnabled: true
      detailedErrorLoggingEnabled: true
      requestTracingEnabled: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'WEBSITE_JAVA_JAR_FILE_NAME'
          value: 'app.jar'
        }
        {
          name: 'WEBSITE_PROACTIVE_AUTOHEAL_ENABLED'
          value: 'false'
        }
        {
          name: 'SPRING_MVC_ASYNC_REQUEST_TIMEOUT'
          value: string(springMvcAsyncRequestTimeoutMs)
        }
      ]
    }
  }
}

// SCM (Kudu) basic-auth publishing credentials.
//
// Same rationale as Stage 0: Azure changed the default in early 2024 so
// newly-provisioned sites have `allow: false`. Lab 1 E2 (Kudu-only config
// visibility) needs 7 Kudu endpoint fetches to succeed, all of which require
// basic auth via `az webapp deployment list-publishing-credentials`.
//
// This resource does NOT enable FTP basic auth; only SCM (Kudu HTTPS) is
// affected. FTP publishing remains disabled by the site-level `ftpsState:
// 'Disabled'` setting above.
resource scmBasicAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2023-12-01' = {
  parent: webApp
  name: 'scm'
  properties: {
    allow: true
  }
}

resource webAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${webAppName}'
  scope: webApp
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
      }
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
      }
      {
        category: 'AppServicePlatformLogs'
        enabled: true
      }
      {
        category: 'AppServiceIPSecAuditLogs'
        enabled: true
      }
    ]
  }
}

output appName string = webApp.name
output defaultHostName string = webApp.properties.defaultHostName
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name
output resourceGroupName string = resourceGroup().name
output springMvcAsyncRequestTimeoutMs int = springMvcAsyncRequestTimeoutMs
