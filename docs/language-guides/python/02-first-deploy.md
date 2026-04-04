# 02 - First Deployment to Azure App Service

This chapter deploys a Flask app to Azure App Service using Python build automation. It focuses on `requirements.txt`, Oryx build detection, and explicit startup command settings.

## Prerequisites

- Completed [01 - Local Run](./01-local-run.md)
- Azure CLI authenticated
- Resource naming variables prepared

## Main Content

### Prepare deployment variables

```bash
RG="rg-flask-tutorial"
APP_NAME="app-flask-tutorial-abc123"
PLAN_NAME="plan-flask-tutorial"
LOCATION="koreacentral"
```

### Create resource group, plan, and web app

```bash
az group create --name $RG --location $LOCATION
az appservice plan create --resource-group $RG --name $PLAN_NAME --is-linux --sku B1
az webapp create --resource-group $RG --plan $PLAN_NAME --name $APP_NAME --runtime "PYTHON|3.11"
```

### Ensure Oryx can build Python dependencies

Oryx detects Python projects when `requirements.txt` exists in the deployed package root.

```bash
ls requirements.txt
```

Enable build during deployment:

```bash
az webapp config appsettings set --resource-group $RG --name $APP_NAME --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

### Set explicit startup command (Gunicorn + WSGI)

```bash
az webapp config set --resource-group $RG --name $APP_NAME --startup-file "gunicorn --bind=0.0.0.0:$PORT src.app:app"
```

### Deploy from local source

```bash
az webapp up --resource-group $RG --name $APP_NAME --runtime "PYTHON:3.11"
```

### Verify deployment and find your app

After deploying, verify the application state:

#### 1. Find Your App URL

Your app is reachable at `https://$APP_NAME.azurewebsites.net` as soon as the deployment completes.

To retrieve the URL via CLI:

```bash
az webapp show \
  --resource-group $RG \
  --name $APP_NAME \
  --query defaultHostName -o tsv
```

In the **Azure Portal**: navigate to your App Service → **Overview** → **Default domain**.

#### 2. Check Health Endpoint

```bash
WEB_APP_URL="https://$(az webapp show --resource-group $RG --name $APP_NAME --query defaultHostName -o tsv)"
curl $WEB_APP_URL/health
```

#### 3. View Deployment Status in the Portal

In the **Azure Portal**: App Service → **Deployment Center** — shows deployment history, status, and build logs (commit-level detail is available for source-control-connected deployments).

#### 4. Stream Live Logs

!!! note "Enable logging first"
    `az webapp log tail` only streams output if application logging is enabled. If the stream appears empty, enable it first:
    ```bash
    az webapp log config --resource-group $RG --name $APP_NAME --application-logging filesystem --level information
    ```

```bash
az webapp log tail --resource-group $RG --name $APP_NAME
```

In the **Azure Portal**: App Service → **Monitoring → Log stream** — streams stdout/stderr in real time.

#### 5. Inspect Files via Kudu (SCM)

Open `https://<app-name>.scm.azurewebsites.net` in a browser. The SCM site provides:

- **File browser** — browse `/home/site/wwwroot` and verify deployed files
- **Bash console** — run commands inside the container
- **Log stream** — view raw platform and app logs

#### 6. View Deployment History

```bash
az webapp log deployment list \
  --resource-group $RG \
  --name $APP_NAME \
  --output table
```

## Advanced Topics

Adopt Zip Deploy for deterministic packages, pin transitive dependencies with `pip freeze`, and benchmark startup time with and without prebuilt wheels.

## See Also
- [03 - Configuration](./03-configuration.md)

## References
- [Quickstart: Deploy a Python web app (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
- [Deploy to App Service using GitHub Actions (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/app-service/deploy-github-actions)
- [Kudu service overview (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/resources-kudu)
- [Enable diagnostic logging (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/troubleshoot-diagnostic-logs)
