---
content_sources:
  diagrams:
  - id: 01-run-flask-locally-with-app-service-parity
    type: flowchart
    source: mslearn-adapted
    mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/
  - id: validate-worker-and-timeout-behavior
    type: flowchart
    source: mslearn-adapted
    mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/
content_validation:
  status: verified
  last_reviewed: '2026-05-23'
  reviewer: agent
  core_claims:
  - claim: This page uses Microsoft Learn as the primary source basis for its Azure-specific
      guidance.
    source: https://learn.microsoft.com/en-us/azure/app-service/
    verified: true
---
# 01 - Run Flask Locally with App Service Parity

This guide sets up a local Flask workflow that mirrors Azure App Service behavior. You will run both development and production-style servers to reduce deployment surprises.

!!! info "Infrastructure Context"
    **Service**: App Service (Linux, Standard S1) | **Network**: VNet integrated | **VNet**: ✅

    This tutorial assumes a production-ready App Service deployment with VNet integration, private endpoints for backend services, and managed identity for authentication.

<!-- diagram-id: 01-run-flask-locally-with-app-service-parity -->
```mermaid
flowchart TD
    INET[Internet] -->|HTTPS| WA[Web App\nApp Service S1\nLinux Python 3.11]

    subgraph VNET["VNet 10.0.0.0/16"]
        subgraph INT_SUB["Integration Subnet 10.0.1.0/24\nDelegation: Microsoft.Web/serverFarms"]
            WA
        end
        subgraph PE_SUB["Private Endpoint Subnet 10.0.2.0/24"]
            PE_KV[PE: Key Vault]
            PE_SQL[PE: Azure SQL]
            PE_ST[PE: Storage]
        end
    end

    PE_KV --> KV[Key Vault]
    PE_SQL --> SQL[Azure SQL]
    PE_ST --> ST[Storage Account]

    subgraph DNS[Private DNS Zones]
        DNS_KV[privatelink.vaultcore.azure.net]
        DNS_SQL[privatelink.database.windows.net]
        DNS_ST[privatelink.blob.core.windows.net]
    end

    PE_KV -.-> DNS_KV
    PE_SQL -.-> DNS_SQL
    PE_ST -.-> DNS_ST

    WA -.->|System-Assigned MI| ENTRA[Microsoft Entra ID]
    WA --> AI[Application Insights]

    style WA fill:#0078d4,color:#fff
    style VNET fill:#E8F5E9,stroke:#4CAF50
    style DNS fill:#E3F2FD
```

## Prerequisites

- Python 3.11 or newer
- Repository cloned locally
- Terminal with Bash, Zsh, or PowerShell

## Main Content

### Create and activate a virtual environment

```bash
cd apps/python-flask
python -m venv .venv
source .venv/bin/activate
```

| Command | Purpose |
|---------|---------|
| `cd apps/python-flask` | Moves into the Flask application directory before creating the environment. |
| `python -m venv .venv` | Creates an isolated Python virtual environment in `.venv`. |
| `source .venv/bin/activate` | Activates the virtual environment in the current shell session. |

On Windows:

```powershell
.venv\Scripts\Activate.ps1
```

### Install dependencies from requirements.txt

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

| Command | Purpose |
|---------|---------|
| `pip install --upgrade pip` | Updates `pip` to the latest available version in the virtual environment. |
| `pip install -r requirements.txt` | Installs all Python packages required by the Flask app. |

### Run with Flask CLI for development

`flask run` provides fast iteration and debug-friendly behavior:

```bash
export FLASK_APP=src.app:app
export FLASK_ENV=development
flask run --port 8000
```

| Command | Purpose |
|---------|---------|
| `export FLASK_APP=src.app:app` | Points Flask CLI to the application object exposed by `src.app`. |
| `export FLASK_ENV=development` | Enables Flask development-friendly behavior for local work. |
| `flask run --port 8000` | Starts the Flask development server on port `8000`. |
| `--port 8000` | Binds the local development server to TCP port `8000`. |

Verify:

```bash
curl http://localhost:8000/health
```

| Command | Purpose |
|---------|---------|
| `curl http://localhost:8000/health` | Sends a test request to the health endpoint to confirm the app is responding. |

### Run with Gunicorn for production parity

App Service Linux runs Python apps via Gunicorn. Validate the same startup shape locally:

```bash
export PORT=8000
gunicorn --bind=0.0.0.0:$PORT src.app:app
```

| Command | Purpose |
|---------|---------|
| `export PORT=8000` | Sets the port variable that matches how App Service passes the listening port. |
| `gunicorn --bind=0.0.0.0:$PORT src.app:app` | Starts the Flask app with Gunicorn for production-style local testing. |
| `--bind=0.0.0.0:$PORT` | Listens on all network interfaces using the port stored in `PORT`. |
| `src.app:app` | Tells Gunicorn which Python module and WSGI app object to load. |

### Validate worker and timeout behavior

Tune worker and timeout values to simulate production load:

```bash
gunicorn --bind=0.0.0.0:$PORT --workers 2 --timeout 120 src.app:app
```

| Command | Purpose |
|---------|---------|
| `gunicorn --bind=0.0.0.0:$PORT --workers 2 --timeout 120 src.app:app` | Runs Gunicorn with explicit worker and timeout settings to simulate production behavior. |
| `--bind=0.0.0.0:$PORT` | Exposes the service on the configured host and port. |
| `--workers 2` | Starts two worker processes to handle concurrent requests. |
| `--timeout 120` | Restarts workers if a request takes longer than 120 seconds. |

<!-- diagram-id: validate-worker-and-timeout-behavior -->
```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Flask as flask run
    participant Guni as gunicorn
    participant App as Flask WSGI app
    Dev->>Flask: Local debug request
    Flask->>App: Execute route
    Dev->>Guni: Production-parity request
    Guni->>App: Worker handles request
```

## Advanced Topics

Add `python-dotenv` for local `.env` loading, then compare request latency and memory profile between Flask development server and Gunicorn workers.

## Run It in the Portal

#### Portal view: App Service plan (Linux) - the deployment target this tutorial emulates locally

![App Service Plan overview blade showing the Linux plan asp-test-20251107 in Korea Central with Pricing tier "Premium0 V3", App Service Plan kind "Linux", Status "Ready", Operating system "Linux", and 1 instance; the right-side charts show CPU Percentage and Memory Percentage time-series for the plan and a list of the apps and slots hosted on the plan including app-test-20251107 and its staging slot.](../../../assets/platform/hosting-models/01-app-service-plan.png)

Your local Flask + Gunicorn setup in this tutorial is intentionally a parity environment for this Linux App Service plan. The visible `Operating system: Linux`, `Pricing tier: Premium0 V3`, and single-instance configuration are what your local Docker-style runtime emulates: a Linux worker that serves a WSGI app over Gunicorn. The right-side `CPU Percentage` and `Memory Percentage` charts are what your local performance testing predicts - if your Flask app exhausts memory locally on the same workload, it will exhaust the `Premium0 V3` worker too. Use this blade to confirm the target plan family and worker size before promoting the local app via `az webapp deploy` in the next tutorial.

## See Also
- [02 - First Deploy](./02-first-deploy.md)

## Sources
- [Configure a Linux Python app (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python)
- [Quickstart: Deploy a Python web app (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
