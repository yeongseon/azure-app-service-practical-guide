---
content_sources:
  diagrams:
    - id: python-runtime
      type: flowchart
      source: mslearn-adapted
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/
---
# Python Runtime

Quick lookup reference.

<!-- diagram-id: python-runtime -->
```mermaid
graph TD
    A[Zip Deploy or Source Deploy] --> B[Oryx detects requirements.txt]
    B --> C[Create Python venv + install deps]
    C --> D[Generate startup metadata]
    D --> E[Gunicorn binds to PORT]
    E --> F[Flask app serves requests]
```

## Supported Runtime Versions

### App Service Python Versions (Linux)

Use one of the currently supported major/minor versions for production deployments:

- Python 3.9
- Python 3.10
- Python 3.11
- Python 3.12

Set runtime version:

```bash
az webapp config set \
  --resource-group $RG \
  --name $APP_NAME \
  --linux-fx-version "PYTHON|3.12"
```

Verify runtime:

```bash
az webapp config show \
  --resource-group $RG \
  --name $APP_NAME \
  --query "linuxFxVersion" \
  --output tsv
```

## Oryx Build Process

### What Oryx Does for Python Apps

On Zip Deploy and source-based deployments, App Service uses Oryx to detect Python and build dependencies.

Typical behavior:

1. Detects Python app based on files (for example `requirements.txt`).
2. Creates a virtual environment during build.
3. Installs dependencies from `requirements.txt`.
4. Generates startup script and launch metadata.

Recommended dependency flow:

```bash
pip freeze > requirements.txt
```

Build controls (common app settings):

```bash
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

Use Oryx build logs in deployment center/Kudu to validate install failures.

## Startup Command Patterns

### Default Gunicorn Entrypoint

Use explicit host and port binding:

```bash
gunicorn --bind=0.0.0.0:$PORT src.app:app
```

If your Flask object is in `app/app.py` with `app = Flask(__name__)`, a common command is:

```bash
gunicorn --bind=0.0.0.0:$PORT app:app
```

Set startup command:

```bash
az webapp config set \
  --resource-group $RG \
  --name $APP_NAME \
  --startup-file "gunicorn --bind=0.0.0.0:$PORT src.app:app"
```

### Using gunicorn.conf.py

Alternative startup command:

```bash
gunicorn --config gunicorn.conf.py src.app:app
```

Example `gunicorn.conf.py`:

```python
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_class = "sync"
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
```

### ASGI Frameworks with uvicorn

For ASGI frameworks like FastAPI and Starlette, run `uvicorn` directly or run Gunicorn with the uvicorn worker class. Both patterns bind to the App Service-injected `PORT`.

Direct uvicorn (FastAPI example):

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Set as App Service startup command:

```bash
az webapp config set \
  --resource-group $RG \
  --name $APP_NAME \
  --startup-file "uvicorn main:app --host 0.0.0.0 --port \$PORT"
```

Gunicorn with the uvicorn worker (recommended for production ASGI workloads that benefit from process-level worker management):

```bash
gunicorn main:app --bind=0.0.0.0:$PORT --worker-class uvicorn.workers.UvicornWorker
```

Set as App Service startup command:

```bash
az webapp config set \
  --resource-group $RG \
  --name $APP_NAME \
  --startup-file "gunicorn main:app --bind=0.0.0.0:\$PORT --worker-class uvicorn.workers.UvicornWorker"
```

Pin both `uvicorn` and (when used) `gunicorn` in `requirements.txt` so Oryx installs them during build:

```text
fastapi
uvicorn[standard]
gunicorn
```

Add upper-bound pins (for example `fastapi<1`, `uvicorn[standard]<1`, `gunicorn<24`) once you have an integration-tested baseline; the unpinned form above is intended only to keep this example forward-compatible. Pin exact versions in your own `requirements.txt` for reproducible builds.

Choose direct `uvicorn` for simplicity and small workloads. Choose Gunicorn + uvicorn worker when you need worker recycling, graceful restarts, and the same Gunicorn-style tuning options described in the next section. The Gunicorn settings under [Worker and Timeout Tuning](#worker-and-timeout-tuning) apply equally when `worker_class` is `uvicorn.workers.UvicornWorker`.

## Gunicorn Configuration

### Worker and Timeout Tuning

Core settings:

- `workers`: Number of worker processes.
- `worker_class`: Usually `sync` for standard Flask workloads.
- `timeout`: Hard worker timeout for hung requests.
- `graceful_timeout`: Drain period before forced stop.

Useful environment settings:

- `WEB_CONCURRENCY`: Overrides worker count.
- `PYTHON_ENABLE_GUNICORN_MULTIWORKERS`: Enables App Service multiworker handling for Gunicorn (`true`/`false`).

Example:

```bash
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings \
    WEB_CONCURRENCY=3 \
    PYTHON_ENABLE_GUNICORN_MULTIWORKERS=true
```

Practical tuning guidance:

- Start with `workers=2` for small plans.
- Increase only after checking memory headroom.
- Raise `timeout` for slow external dependencies, but fix root cause where possible.

## Port Binding and Networking

### Always Bind to Platform Port

App Service injects `PORT` at runtime for Linux containers.

Rules:

- Prefer `--bind=0.0.0.0:$PORT` in Gunicorn command.
- For local fallback, use `8000`.
- Never hardcode random ports in production startup command.

Flask development pattern:

```python
import os

port = int(os.getenv("PORT", "8000"))
app.run(host="0.0.0.0", port=port)
```

## File System and Persistence

### /home Is Persistent, App Root Is Not

On Linux App Service:

- `/home` persists across restarts and deployments.
- App content under runtime extraction path can be replaced on redeploy.
- Local temporary paths are ephemeral.

Use `/home` for:

- Uploaded files that must survive restarts.
- Cached artifacts safe to retain.
- Diagnostic dumps/log snapshots.

Avoid storing durable application state on non-persistent paths.

## Common Import and Startup Errors

### Module and Path Failures

1. **`ModuleNotFoundError` after deploy**
    - Cause: Missing package in `requirements.txt` or build skipped.    - Fix: Add package, redeploy with `SCM_DO_BUILD_DURING_DEPLOYMENT=true`.
2. **`Failed to find attribute 'app'` / WSGI import errors**
    - Cause: Incorrect module path in startup command.    - Fix: Match `module:callable` exactly (`src.app:app`, `app:app`, etc.).
3. **`No module named src`**
    - Cause: Wrong working directory assumptions.    - Fix: Adjust startup path to deployed folder layout.
4. **App starts locally but fails in App Service**
    - Cause: OS-level native dependencies missing or case-sensitive import mismatch.    - Fix: Pin compatible wheels and validate Linux import casing.
### Fast Validation Commands

```bash
az webapp log tail --resource-group $RG --name $APP_NAME
```

```bash
az webapp ssh --resource-group $RG --name $APP_NAME
```

Check installed packages and startup process from SSH/Kudu when diagnosing import issues.

## Run It in the Portal

#### Portal view: Environment variables blade (runtime app settings managed here)

![Azure Portal Environment variables blade for app-test-20251107 Web App with the App settings tab selected (Connection strings tab adjacent). The toolbar shows a search box plus the actions plus Add, Refresh, Show values, Advanced edit, and Pull reference values. The settings table has columns Name, Value, Deployment slot setting, Source, and Delete and lists five App Service-sourced rows: APPLICATIONINSIGHTS_CONNECTION_STRING, APPLICATIONINSIGHTSAGENT_EXTENSION_ENABLED, ApplicationInsightsAgent_EXTENSION_VERSION, SCM_DO_BUILD_DURING_DEPLOYMENT, and WEBSITE_HTTPLOGGING_RETENTION_DAYS, each with a Show value link and Source App Service. The left navigation expands Settings with Environment variables highlighted, alongside Configuration, Instances, Authentication, Identity, Backups, Custom domains, Certificates, Networking, and WebJobs; Apply and Discard buttons are disabled at the bottom.](../../assets/operations/deployment/zip-deploy/01-app-settings-run-from-package.png)

The `Environment variables` blade with the `App settings` tab selected is the Portal view of the runtime settings table for this Python app. In this screenshot, the visible row `SCM_DO_BUILD_DURING_DEPLOYMENT` appears alongside other App Service-managed entries in the same `Name`, `Value`, `Deployment slot setting`, and `Source` layout. The `Show value`, `Advanced edit`, and `Pull reference values` actions in the toolbar make this the same surface where those settings are inspected in the Portal. The highlighted `Environment variables` entry in the left navigation confirms the exact blade readers should open when checking runtime configuration.

## See Also
- [CLI Cheatsheet](../../reference/cli-cheatsheet.md)
- [Troubleshooting](../../reference/troubleshooting.md)

## Sources
- [Configure a Linux Python app (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python)
- [Python version support in App Service (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python#supported-python-versions)
