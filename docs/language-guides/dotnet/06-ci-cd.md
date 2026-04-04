# 06. CI/CD with Azure DevOps

Implement continuous integration and deployment for the .NET guide using **Azure DevOps Pipelines** as the primary delivery workflow.

## Prerequisites

- Tutorial [05. Infrastructure as Code](./05-infrastructure-as-code.md) completed
- Azure DevOps project with pipeline permissions
- Azure Resource Manager service connection configured

## What you'll learn

- How `azure-pipelines.yml` builds and publishes the app
- How deployment stage pushes package to Windows App Service
- How environments and approvals protect production
- Which variables and service connections are required

## Main content

### 1) Review pipeline structure

The guide uses a two-stage pipeline:

- **Build**: restore, build, test, publish artifact
- **Deploy**: deploy artifact with `AzureWebApp@1`

Pipeline skeleton:

```yaml
trigger:
  branches:
    include:
      - main

pool:
  vmImage: 'windows-latest'

stages:
  - stage: Build
  - stage: Deploy
```

### 2) Build stage details

```yaml
- task: UseDotNet@2
  inputs:
    packageType: sdk
    version: $(dotnetVersion)

- script: dotnet restore
  displayName: Restore dependencies
  workingDirectory: app/GuideApi

- script: dotnet build --configuration $(buildConfiguration) --no-restore
  displayName: Build
  workingDirectory: app/GuideApi

- script: dotnet test --configuration $(buildConfiguration) --no-build
  displayName: Test
  workingDirectory: app/GuideApi
```

### 3) Publish stage artifact

```yaml
- script: dotnet publish --configuration $(buildConfiguration) --output $(Build.ArtifactStagingDirectory)
  displayName: Publish app artifacts
  workingDirectory: app/GuideApi

- publish: $(Build.ArtifactStagingDirectory)
  artifact: drop
```

### 4) Deploy stage to App Service

```yaml
- stage: Deploy
  dependsOn: Build
  condition: succeeded()
  jobs:
    - deployment: Deploy
      environment: 'production'
      strategy:
        runOnce:
          deploy:
            steps:
              - task: AzureWebApp@1
                inputs:
                  azureSubscription: $(azureSubscription)
                  appType: webApp
                  appName: $(webAppName)
                  package: '$(Pipeline.Workspace)/drop/**/*.zip'
```

### 5) Required variables

Define these securely (pipeline variables or variable group):

- `azureSubscription`: service connection name
- `webAppName`: target app service name
- `resourceGroupName`: target resource group
- `dotnetVersion`: `8.0.x`

### 6) Add environment approvals

Use Azure DevOps Environment checks for production:

1. Create `production` environment in Azure DevOps.
2. Add manual approval policy.
3. Attach deployment job to `environment: 'production'`.

### 7) Align application code with pipeline output

```csharp
builder.Services.AddControllers();
builder.Services.AddApplicationInsightsTelemetry();
app.MapControllers();
app.Run();
```

Because pipeline deploys published binaries, startup behavior must not depend on local-only files.

### 8) Optional smoke test in pipeline

```yaml
- task: AzureCLI@2
  displayName: Smoke test health endpoint
  inputs:
    azureSubscription: $(azureSubscription)
    scriptType: bash
    scriptLocation: inlineScript
    inlineScript: |
      curl --fail --silent "https://$(webAppName).azurewebsites.net/health"
```

### 9) Manual equivalent commands

Use these for debugging outside pipeline:

```bash
dotnet publish "app/GuideApi/GuideApi.csproj" --configuration Release --output "/tmp/guideapi-publish"
az webapp deploy --resource-group "$RESOURCE_GROUP_NAME" --name "$WEB_APP_NAME" --src-path "/tmp/guideapi.zip" --type zip --output json
```

!!! tip "Why Azure DevOps is the differentiator"
    This guide is intentionally Azure DevOps-first.
    Keep your YAML as the source of truth for repeatable enterprise deployment.

## Verification

After a successful run:

1. Build stage artifacts contain published .NET output.
2. Deploy stage targets the correct app.
3. `/health` returns HTTP 200.
4. Deployment appears in App Service deployment history.

```bash
curl --include "https://$WEB_APP_NAME.azurewebsites.net/health"
```

## Troubleshooting

### Service connection authorization failure

Re-authorize the Azure Resource Manager service connection and ensure pipeline has permission to use it.

### Package path not found

Confirm artifact name (`drop`) and deploy package glob path exactly match published artifact layout.

### Runtime startup errors after deployment

Inspect Log Stream and Kudu diagnostics; redeploy after a clean publish from the same SDK version as pipeline.

## References

- [Continuous deployment to Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/deploy-continuous-deployment)
- [Use GitHub Actions to deploy to Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/deploy-github-actions)

## See Also

- [07. Custom Domain & SSL](./07-custom-domain-ssl.md)
- [Reference: Azure DevOps Pipeline Variables](../../reference/index.md)
- For platform details, see [Azure App Service Guide](https://yeongseon.github.io/azure-app-service-practical-guide/)
