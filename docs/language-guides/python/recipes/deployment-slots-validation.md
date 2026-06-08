---
content_sources:
  diagrams:
    - id: deployment-slots-validation
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/quickstart-python
---
# Deployment Slots Validation

Use staging slots to validate deployments before production swap, with health checks and automated safeguards in GitHub Actions.

<!-- diagram-id: deployment-slots-validation -->
```mermaid
flowchart TD
    A[Create staging slot] --> B[Set slot-sticky config]
    B --> C[Deploy release.zip to staging]
    C --> D[Run /health /info /readyz checks]
    D --> E{All checks pass?}
    E -- Yes --> F[Swap to production]
    E -- No --> G[Stop and fix staging]
```

## Prerequisites

- App Service plan supports deployment slots (Standard, Premium, or Isolated)
- Production app already running on Linux App Service
- GitHub Actions workflow configured for the repository

## Main content

### 1) Create staging slot

Create a new deployment slot named `staging` for your application:

```bash
az webapp deployment slot create \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --slot "staging" \
    --output json
```

### 2) Configure slot-sticky settings

Mark environment-specific values as slot settings so they do not swap with the code:

```bash
az webapp config appsettings set \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --slot "staging" \
    --slot-settings APP_ENV=staging FEATURE_BETA_ENABLED=true \
    --output json
```

### 3) Deploy artifact to staging slot

Deploy your Python application package directly to the staging slot:

```bash
az webapp deploy \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --slot "staging" \
    --src-path "release.zip" \
    --type zip \
    --output json
```

### 4) Add explicit health endpoint checks

Verify the staging slot is responding correctly before proceeding with the swap:

```bash
curl --fail --silent "https://$APP_NAME-staging.azurewebsites.net/health"
curl --fail --silent "https://$APP_NAME-staging.azurewebsites.net/info"
```

### 5) Add version-aware validation endpoint

Implement a `/readyz` route in your Flask application to provide environment and version context:

```python
import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/readyz")
def readyz():
    return jsonify({
        "status": "ready",
        "environment": os.environ.get("APP_ENV", "production"),
        "buildVersion": os.environ.get("BUILD_VERSION", "unknown"),
    })
```

### 6) Swap staging to production

Perform the swap to promote the validated staging code to the production slot:

```bash
az webapp deployment slot swap \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --slot "staging" \
    --target-slot "production" \
    --output json
```

### 7) Optional auto-swap configuration

Enable auto-swap to automatically promote successful deployments to production:

```bash
az webapp deployment slot auto-swap \
    --resource-group "$RG" \
    --name "$APP_NAME" \
    --slot "staging" \
    --auto-swap-slot "production" \
    --output json
```

!!! warning "Linux Limitation"
    Auto-swap is not supported for web apps on Linux and Web App for Containers. Use manual swap or CI/CD-triggered swap instead. See [Deployment Slots](../../../operations/deployment/slots-and-swap.md) for details.

### 8) GitHub Actions staged deployment example

Automate the deployment, validation, and swap process using GitHub Actions:

```yaml
jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Staging Slot
        uses: azure/webapps-deploy@v3
        with:
          app-name: ${{ env.APP_NAME }}
          slot-name: 'staging'
          package: .

  validate:
    needs: deploy-staging
    runs-on: ubuntu-latest
    steps:
      - name: Health Check
        run: |
          curl --fail --retry 5 --retry-delay 5 \
          "https://${{ env.APP_NAME }}-staging.azurewebsites.net/readyz"

  swap:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - name: Swap to Production
        run: |
          az webapp deployment slot swap \
            --resource-group ${{ env.RG }} \
            --name ${{ env.APP_NAME }} \
            --slot staging \
            --target-slot production
```

!!! warning "Validate before swap, always"
    A successful deployment is not the same as a healthy runtime.
    Require endpoint validation and telemetry checks before production swap.

## Verification

- Staging slot serves the expected build version via `/readyz`.
- Production remains stable and unaffected during staging validation.
- Swap completes without environment configuration leakage.
- Post-swap production `/health` endpoint returns a success status.

```bash
curl --include "https://$APP_NAME.azurewebsites.net/health"
```

## Troubleshooting

### Staging healthy, production fails after swap

- Check that slot-sticky configurations (like `APP_ENV`) are correctly marked.
- Verify that database connection strings or external API keys are valid for production.
- Confirm the production App Service plan has sufficient resources for the new build.

### Swap operation blocked

Ensure no other management operations are running on the App Service. Check the Azure Activity Log for specific conflict errors or pending restarts.

### Auto-swap caused unexpected release

Disable auto-swap and revert to manual swap or a controlled GitHub Actions workflow. Ensure that the staging slot is fully warmed up before auto-swap triggers.

## Run It in the Portal

#### Portal view: Deployment slots with Swap dialog (validated promotion)

![Azure Portal Deployment slots blade for app-test-20251107 Web App with the Swap right panel open. The slot list shows app-test-20251107 with a PRODUCTION badge and app-test-20251107-staging; the toolbar exposes Save and Discard (disabled), Add, Swap (highlighted), Logs, Refresh (disabled), and Send us your feedback. The Swap panel has a Source dropdown set to app-test-20251107-staging and a Target dropdown showing app-test-20251107 with a PRODUCTION badge, followed by an info banner reading "Swap with preview can only be used with sites that have deployment slot settings enabled." and a disabled "Perform swap with preview" checkbox. A Config Changes section explains it is the final summary of configuration changes on source and target slots after the swap, with Source slot changes (selected) and Target slot changes tabs. The table columns Setting, Type, Old Value, New Value list SCM_DO_BUILD_DURING_DEPLOYMENT (AppSetting, Not set to true), APPLICATIONINSIGHTS_CONNECTION_STRING (AppSetting, Not set to a long zero-GUID instrumentation string), ApplicationInsightsAgent_EXTENSION_VERSION (AppSetting, Not set to ~3), and APPLICATIONINSIGHTSAGENT_EXTENSION_ENABLED (AppSetting, Not set to true). Bottom buttons are Start Swap (primary) and Close.](../../../assets/operations/deployment/slots-and-swap/01-swap-dialog.png)

The Deployment slots blade with the Swap panel open is the Portal counterpart to the `az webapp deployment slot swap` command this recipe drives from CI. The `Source: app-test-20251107-staging` and `Target: app-test-20251107` selectors mirror the staging-to-production promotion direction the recipe validates against. The `Config Changes` table at the bottom previews how slot-sticky settings will move during the swap, including the `APPLICATIONINSIGHTS_CONNECTION_STRING` and `SCM_DO_BUILD_DURING_DEPLOYMENT` rows visible here — the same delta you should inspect before clicking `Start Swap`. Use this Portal view as the manual checkpoint complementing the automated pre-swap validation calls (health probe, smoke test) the recipe issues against the staging slot.

## See Also

- [Tutorial: 06. CI/CD](../tutorial/06-ci-cd.md)
- [Tutorial: 03. Configuration](../tutorial/03-configuration.md)
- For platform details, see [Azure App Service Guide](https://yeongseon.github.io/azure-app-service-practical-guide/)

## Sources

- [Microsoft Learn source 1](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
