targetScope = 'resourceGroup'

@description('Base name used to build uniquely named Stage 0 resources.')
param baseName string

@description('Azure region for all resources. Defaults to the current resource group location.')
param location string = resourceGroup().location

var uniqueSuffix = uniqueString(resourceGroup().id)
var appServicePlanName = 'asp-${baseName}-${uniqueSuffix}'
var webAppName = 'app-${baseName}-${uniqueSuffix}'
var logAnalyticsWorkspaceName = 'law-${baseName}-${uniqueSuffix}'

// Windows Basic B1 App Service Plan.
// - kind: 'app' selects Windows (Linux would be 'linux' with reserved: true).
// - No reserved property because Windows plans do not use it.
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
// Stage 0 goal: measure the platform's effective request timeout for a Windows
// Java SE app running Spring Boot behind httpPlatformHandler. To make the
// measurement clean:
//
// - autoHealEnabled: false disables custom Auto-Heal rules. Otherwise a rule
//   could recycle the worker before the front-end timeout fires, contaminating
//   the timing signal.
// - WEBSITE_PROACTIVE_AUTOHEAL_ENABLED: 'false' disables the platform's
//   built-in Proactive Auto-Heal (enabled by default). Its trigger fires when
//   80% of requests in a 2-minute window exceed 200 seconds, which would
//   preempt any custom mitigation and destroy the timing observation.
// - alwaysOn: true prevents the platform from unloading the app between probes.
// - httpLoggingEnabled + detailedErrorLoggingEnabled + requestTracingEnabled
//   maximize the diagnostic surface for post-run correlation.
// - javaVersion / javaContainer / javaContainerVersion is the Windows Java SE
//   trio. Do NOT use linuxFxVersion or windowsFxVersion on a Windows Java SE
//   plan; the platform sets a hidden windowsFxVersion at runtime.
// - WEBSITE_JAVA_JAR_FILE_NAME tells the Windows Java SE runtime which JAR to
//   launch under wwwroot. Deployed by deploy.sh via `az webapp deploy --type jar`.
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
      ]
    }
  }
}

// SCM (Kudu) basic-auth publishing credentials.
//
// Azure changed the App Service default in early 2024 so `allow` is now `false`
// for newly-provisioned sites. When `false`, every Kudu REST call including
// `/api/vfs/site/wwwroot/`, `/api/environment`, `/api/processes`, and
// `/api/command` returns HTTP 401, which breaks `collect-effective-config.sh`
// (both preflight and post-flight modes).
//
// Stage 0 explicitly enables SCM basic auth here because the fetch scripts
// authenticate with `az webapp deployment list-publishing-credentials`, which
// returns credentials that only work when this policy is `true`. Bearer-token
// auth against Kudu is an alternative, but basic-auth keeps the scripts POSIX
// and portable across environments where the operator may not have federated
// identity configured.
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
