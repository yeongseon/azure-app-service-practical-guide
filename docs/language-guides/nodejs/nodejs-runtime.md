# Node.js Runtime Details

Quick lookup for the Node.js runtime environment on Azure App Service (Linux).

## Supported Node.js Versions

App Service supports current LTS versions. Check available versions via CLI:

```bash
az webapp list-runtimes --linux --output table
```

| Version | Status |
| :--- | :--- |
| **Node.js 20 (LTS)** | Current |
| **Node.js 18 (LTS)** | Supported |
| **Node.js 16 (LTS)** | Maintenance/Retired |

## Oryx Build System

Oryx is the default build engine for App Service.

### Build Behavior
1.  **Detects Node.js:** Looks for `package.json` in the root directory.
2.  **Installs Dependencies:** Runs `npm install` or `yarn install`.
3.  **Build Step:** Runs `npm run build` if the script exists in `package.json`.
4.  **Pruning:** Runs `npm prune --production` to reduce deployment size (can be customized).

### Customizing Oryx
Set these App Settings:
*   `SCM_DO_BUILD_DURING_DEPLOYMENT`: `true` or `false`.
*   `ENABLE_ORYX_BUILD`: `true` (default).
*   `POST_BUILD_COMMAND`: Custom command to run after the build completes.

## Network & Port Binding

### PORT Environment Variable
**CRITICAL:** You MUST bind to `process.env.PORT`.

```javascript
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`Server listening on port ${PORT}`);
});
```

### Protocol Handling
*   App Service handles HTTPS termination at the front-end.
*   The application receives requests via HTTP on the assigned `PORT`.
*   Check `X-Forwarded-Proto` and `X-Forwarded-For` headers for original request info.

## Startup & Shutdown

### Startup Command

By default, the platform detects how to start your application by looking for `npm start`, `yarn start`, or `node server.js` (in that order).

#### Checking and Setting Startup Command

Use the Azure CLI to inspect or update the startup configuration:

```bash
# Check current runtime and startup command
az webapp config show \
  --name $APP_NAME \
  --resource-group $RG \
  --query "{runtime:linuxFxVersion, startup:appCommandLine}" \
  --output json

# Set a custom startup command
az webapp config set \
  --name $APP_NAME \
  --resource-group $RG \
  --startup-file "node dist/server.js"
```

**Common Startup Commands:**
*   `node server.js` - Direct execution (fastest startup)
*   `npm start` - Uses your `package.json` start script
*   `pm2 start ecosystem.config.js --no-daemon` - Use PM2 for process management (only if advanced features like clustering are required)

### Graceful Shutdown (SIGTERM)

App Service sends a **SIGTERM** signal to your process when restarting, scaling down, or deploying. Your application should catch this signal to finish active requests and close database connections.

```javascript
// Example: Graceful shutdown handler
process.on('SIGTERM', () => {
  console.log('SIGTERM received: shutting down gracefully');
  
  server.close(() => {
    console.log('HTTP server closed');
    process.exit(0);
  });
  
  // Force exit after 10 seconds if graceful shutdown fails
  setTimeout(() => {
    console.error('Forced shutdown due to timeout');
    process.exit(1);
  }, 10000);
});
```

**Why this matters:**
*   Prevents dropped HTTP connections during deployments
*   Ensures database connection pools are closed correctly
*   Allows background tasks to finish or checkpoint
*   **Note:** The platform waits for a grace period before sending **SIGKILL**.

## Health Check Configuration

App Service can monitor your application's health and automatically remove unhealthy instances from the load balancer.

```bash
# Enable health check path
az webapp config set \
  --name $APP_NAME \
  --resource-group $RG \
  --generic-configurations '{"healthCheckPath": "/health"}'
```

**Platform Behavior:**
*   **Probing:** The platform probes your health path every 1 minute.
*   **Isolation:** After a certain number of failed probes, the instance is marked unhealthy and removed from the load balancer.
*   **Recovery:** If the instance remains unhealthy, the platform may restart it (Auto-Heal).

## Process & Runtime Behavior

### Instance Resources
*   **Single Process:** By default, Node.js runs as a single process. You typically don't need `cluster` mode unless you are on a high-core SKU and have high-CPU workloads.
*   **Memory Limits:** Based on your App Service Plan SKU. Exceeding limits will cause the platform to restart the container.
*   **Ephemeral Filesystem:** The local filesystem is ephemeral except for `/home`. Any files written outside of `/home` are lost during restarts.

### Environment & Networking
*   **`process.env.PORT`:** Set by the platform to a random port. Your app **must** listen on this port.
*   **Host Binding:** Bind to `0.0.0.0` (all interfaces) rather than `127.0.0.1` or `localhost` to ensure the platform's reverse proxy can reach your process.
*   **Timezone:** Defaults to UTC. Set the `WEBSITE_TIMEZONE` app setting to change it.

## Cold Start Optimization

Cold starts occur when an app scales out or starts after being idle.

*   **Always On:** Enable "Always On" (Standard tier and above) to keep the container loaded.
*   **Dependency Management:** Minimize the number of dependencies. Large `node_modules` increase container startup time.
*   **Lazy Loading:** Use dynamic `import()` for heavy modules that aren't needed during initial startup.
*   **Pre-warming:** Use health checks to ensure the instance is fully initialized before receiving traffic.

## `package.json` Requirements

*   **`engines` field:** Specify the Node.js version to guide Oryx.
    ```json
    "engines": {
      "node": ">=20.0.0"
    }
    ```
*   **`scripts.start`:** The primary way App Service knows how to run your app.
*   **Dependencies:** Ensure all required modules are listed in `dependencies`.

## Package Managers
*   **npm:** Default, uses `package-lock.json` if present.
*   **yarn:** Uses `yarn.lock` if present.
*   **pnpm:** Not natively supported by Oryx without a custom build script.

---

## Advanced Topics

!!! info "Coming Soon"
    - [Custom Node.js versions]
    - [Bun/Deno support]
- [Contribute](https://github.com/yeongseon/azure-app-service-practical-guide/issues)

## See Also
- [Platform Limits](../../reference/platform-limits.md)
- [How App Service Works](../../platform/how-app-service-works.md)
- [CLI Cheatsheet](../../reference/cli-cheatsheet.md)

## Sources
- [Configure Node.js on Azure App Service (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/configure-language-nodejs)
- [Node.js version support in App Service (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/language-support-policy)
