# Console Queries

Use these queries to identify startup/runtime failures from container console output in Azure App Service Linux.

```mermaid
graph LR
    A[AppServiceConsoleLogs] --> B[Startup Errors]
    A --> C[Binding Failures]
    B --> D[Identify Boot Issues]
    C --> D
```

## Available Queries
- [Startup Errors](startup-errors.md)
- [Container Binding Errors](container-binding-errors.md)
