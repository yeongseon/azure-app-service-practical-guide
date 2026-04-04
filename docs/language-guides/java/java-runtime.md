# Java Runtime

Runtime reference for Java 17 on Azure App Service Linux with Spring Boot 3.2.x. Use this document as the Java equivalent of a runtime compatibility and tuning sheet.

## Supported baseline in this guide

- Runtime target: **Java 17**
- Packaging target: executable **JAR**
- Hosting model: **Java SE**
- Framework baseline: **Spring Boot 3.2.5**
- Deployment baseline: Maven plugin (`azure-webapp-maven-plugin`)

## Runtime configuration commands

Set Java runtime:

```bash
az webapp config set \
  --resource-group $RG \
  --name $APP_NAME \
  --linux-fx-version "JAVA|17-java17" \
  --output json
```

Inspect runtime settings:

```bash
az webapp config show \
  --resource-group $RG \
  --name $APP_NAME \
  --query "{linuxFxVersion:linuxFxVersion,alwaysOn:alwaysOn,healthCheckPath:healthCheckPath}" \
  --output json
```

## `JAVA_OPTS` reference

Recommended baseline:

```text
-XX:InitialRAMPercentage=25.0 -XX:MaxRAMPercentage=70.0 -XX:+UseG1GC -XX:+ExitOnOutOfMemoryError
```

Apply via app settings:

```bash
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings "JAVA_OPTS=-XX:InitialRAMPercentage=25.0 -XX:MaxRAMPercentage=70.0 -XX:+UseG1GC -XX:+ExitOnOutOfMemoryError" \
  --output json
```

## Startup command patterns

Most Java SE deployments can use platform defaults. For explicit startup control:

```bash
az webapp config set \
  --resource-group $RG \
  --name $APP_NAME \
  --startup-file "java $JAVA_OPTS -jar /home/site/wwwroot/*.jar --server.port=\$PORT" \
  --output json
```

## Spring Boot runtime essentials

Required properties:

```properties
server.port=${PORT:8080}
server.shutdown=graceful
spring.lifecycle.timeout-per-shutdown-phase=20s
```

Optional production-oriented settings:

```properties
management.endpoints.web.exposure.include=health,info
spring.main.banner-mode=off
```

## Memory defaults and tuning heuristics

| Workload type | Suggested max RAM percentage |
|---|---|
| Light API | 65-70% |
| Typical business API | 70-75% |
| Heavy in-memory processing | 75-80% (with testing) |

Leave remaining memory for non-heap allocations and platform overhead.

## Common JVM flags for App Service

| Flag | Purpose |
|---|---|
| `-XX:MaxRAMPercentage` | heap cap relative to container memory |
| `-XX:InitialRAMPercentage` | initial heap sizing |
| `-XX:+UseG1GC` | balanced GC for server workloads |
| `-XX:+ExitOnOutOfMemoryError` | fail fast for clean platform recovery |
| `-Djava.security.egd=file:/dev/urandom` | reduce entropy blocking on startup (if needed) |

## Validate effective runtime at deployment time

```bash
az webapp config appsettings list --resource-group $RG --name $APP_NAME --output table
az webapp log tail --resource-group $RG --name $APP_NAME
```

Look for startup logs confirming Java version, active profiles, and listening port.

## Runtime anti-patterns

- fixed `-Xmx` copied across all SKUs
- production deployments without explicit OOM behavior
- long, unbounded startup hooks
- mixing conflicting runtime settings between startup command and app settings

## Java-Specific Considerations

- Keep runtime policy in version-controlled ops docs, not tribal memory.
- Re-evaluate `JAVA_OPTS` after every SKU or workload profile change.
- Standardize one startup pattern per environment to reduce drift.
- Verify runtime assumptions in staging slot before production swap.

## See Also

- [Reference: CLI Cheatsheet](../../reference/cli-cheatsheet.md)
- [Reference: Platform Limits](../../reference/platform-limits.md)
- [Operations: Scaling](../../operations/scaling.md)
- [Platform: How App Service Works](../../platform/how-app-service-works.md)

## Sources

- [Configure a Java app for Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/configure-language-java)
- [Configure an App Service app](https://learn.microsoft.com/en-us/azure/app-service/configure-common)
