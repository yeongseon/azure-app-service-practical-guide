# .NET Guide

This guide covers the end-to-end path for running ASP.NET Core applications on Azure App Service.

## Main Content

```mermaid
flowchart LR
    A[01 Local Run] --> B[02 First Deploy]
    B --> C[03 Configuration]
    C --> D[04 Logging & Monitoring]
    D --> E[05 Infrastructure as Code]
    E --> F[06 CI/CD]
    F --> G[07 Custom Domain & SSL]
```

1. [01 - Local Run](./01-local-run.md)
2. [02 - First Deploy](./02-first-deploy.md)
3. [03 - Configuration](./03-configuration.md)
4. [04 - Logging and Monitoring](./04-logging-monitoring.md)
5. [05 - Infrastructure as Code](./05-infrastructure-as-code.md)
6. [06 - CI/CD](./06-ci-cd.md)
7. [07 - Custom Domain and SSL](./07-custom-domain-ssl.md)

## Advanced Topics

Use .NET recipes to apply identity, data, networking, and deployment patterns.

- [.NET Recipes](./recipes/index.md)

## See Also

- [Language Guides](../index.md)
- [Platform](../../platform/index.md)
- [Operations](../../operations/index.md)
- [Reference](../../reference/index.md)

## Sources

- [Quickstart: Deploy an ASP.NET Core app](https://learn.microsoft.com/azure/app-service/quickstart-dotnetcore)
