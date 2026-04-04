# 03. Configuration

Configure runtime behavior, secrets, and identity for your Spring Boot app on Azure App Service without rebuilding the JAR.

## Prerequisites

- Completed [02. First Deploy](02-first-deploy.md)
- `RG` and `APP_NAME` exported in your shell

## What you'll learn

- How App Settings map to Spring Boot properties
- How to apply and tune `JAVA_OPTS`
- When to use App Settings vs Connection Strings
- Managed Identity basics for passwordless access
- How profiles (`development` vs `production`) affect behavior

## Main Content

### Configuration surface area on App Service

| Mechanism | Best for | Spring Boot access pattern |
|---|---|---|
| App Settings | General environment variables | `System.getenv()` or relaxed binding |
| Connection Strings | Legacy typed DB strings | `CUSTOMCONNSTR_*`, `SQLCONNSTR_*` env variables |
| Key Vault Reference | Secret indirection | Appears as resolved environment value |
| Managed Identity | Passwordless auth to Azure resources | Azure Identity SDK (`DefaultAzureCredential`) |

### List current App Settings

```bash
az webapp config appsettings list \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --output table
```

You should see values like `SPRING_PROFILES_ACTIVE=production`, `JAVA_OPTS=...`, and `APPLICATIONINSIGHTS_CONNECTION_STRING`.

### Update runtime settings with long flags

```bash
az webapp config appsettings set \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --settings \
    LOGGING_LEVEL_COM_EXAMPLE_GUIDE=INFO \
    SPRING_PROFILES_ACTIVE=production \
    JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -Djava.security.egd=file:/dev/./urandom" \
  --output json
```

!!! tip "Spring relaxed binding"
    Spring maps uppercase underscore environment keys to dotted properties. Example: `LOGGING_LEVEL_ROOT` maps to `logging.level.root`.

### Use Connection Strings when required

Some teams standardize on Connection Strings for operational visibility.

```bash
az webapp config connection-string set \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --connection-string-type Custom \
  --settings APP_DB="Server=tcp:<server>.database.windows.net,1433;Database=<db>;" \
  --output json
```

In Java, this appears as `CUSTOMCONNSTR_APP_DB`.

### Managed Identity basics

Enable system-assigned managed identity:

```bash
az webapp identity assign \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --output json
```

Example masked output:

```json
{
  "principalId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "<tenant-id>",
  "type": "SystemAssigned"
}
```

After identity exists, grant least-privilege RBAC on target resources (SQL, Key Vault, Storage, etc.).

### Profile behavior: development vs production

Local default for the sample app:

- `spring.profiles.active` falls back to `local` in `/info`

In App Service:

- `SPRING_PROFILES_ACTIVE=production` is set by Bicep
- `logback-spring.xml` switches to JSON log appender in production

Test profile switch quickly:

```bash
SPRING_PROFILES_ACTIVE=production ./mvnw spring-boot:run
```

### Slot-sticky settings for safer swaps

For staging/production slot workflows, make environment-specific settings sticky:

```bash
az webapp config appsettings set \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --slot-settings \
    SPRING_PROFILES_ACTIVE=production \
    API_BASE_URL=https://api.example.internal \
  --output json
```

!!! warning "Do not store secrets in source control"
    Keep secrets in Key Vault and expose them via Key Vault References in App Settings.

!!! info "Platform architecture"
    For platform architecture details, see [Platform: How App Service Works](../../platform/how-app-service-works.md).

## Verification

```bash
az webapp config appsettings list \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --output table

curl "https://$APP_NAME.azurewebsites.net/info"
```

Confirm expected profile and config-driven behavior.

## Troubleshooting

### Settings changed but app behavior unchanged

Restart app to force process recycle:

```bash
az webapp restart \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --output json
```

### JVM memory pressure after scaling down

Reduce `MaxRAMPercentage` in `JAVA_OPTS` and retest startup time + GC behavior.

### Managed Identity enabled but access denied

Identity creation and RBAC propagation can take several minutes; validate role assignment scope and wait briefly.

## Next Steps / See Also

- [04. Logging & Monitoring](04-logging-monitoring.md)
- [Recipes: Key Vault References](./recipes/key-vault-reference.md)
- [Recipes: Managed Identity](./recipes/managed-identity.md)

## References

- [Configure an App Service app](https://learn.microsoft.com/en-us/azure/app-service/configure-common)
- [Configure a Java app for Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/configure-language-java)
- [Use Key Vault references for App Service](https://learn.microsoft.com/en-us/azure/app-service/app-service-key-vault-references)
