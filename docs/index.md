---
content_sources:
  diagrams:
    - id: index-diagram-1
      type: flowchart
      source: self-generated
      justification: "Self-generated navigation diagram synthesized from official Azure App Service overview documentation for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/overview
---
# Azure App Service Practical Guide

Comprehensive, practical documentation for building, deploying, operating, and troubleshooting web applications on Azure App Service.

This site is organized as a learning and operations guide so you can move from fundamentals to production troubleshooting with clear, repeatable workflows.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **New to App Service?**

    ---

    Start with platform fundamentals and deploy your first app in under 30 minutes.

    [:octicons-arrow-right-24: Start Here](start-here/overview.md)

-   :material-server:{ .lg .middle } **Running Production Apps?**

    ---

    Apply battle-tested patterns for security, scaling, deployment, and reliability.

    [:octicons-arrow-right-24: Best Practices](best-practices/index.md)

-   :material-fire:{ .lg .middle } **Investigating an Incident?**

    ---

    Jump straight to hypothesis-driven playbooks with real KQL queries and evidence patterns.

    [:octicons-arrow-right-24: Troubleshooting](troubleshooting/index.md)

</div>

## Navigate the Guide

| Section | Purpose |
|---|---|
| [Start Here](start-here/overview.md) | Orientation, learning paths, and repository map. |
| [Platform](platform/index.md) | Understand core App Service architecture, lifecycle, scaling, and networking. |
| [Best Practices](best-practices/index.md) | Apply production patterns for security, networking, deployment, scaling, and reliability. |
| [Language Guides](language-guides/index.md) | Follow end-to-end implementation tracks for Python, Node.js, Java, and .NET. |
| [Operations](operations/index.md) | Run production workloads with scaling, security, health, and cost practices. |
| [Troubleshooting](troubleshooting/index.md) | Diagnose startup, performance, outbound network, and reliability issues quickly. |
| [Reference](reference/index.md) | Use quick lookups for CLI, limits, KQL, and diagnostic utilities. |

For orientation and study order, start with [Start Here](start-here/overview.md).

## Learning flow

<!-- diagram-id: index-diagram-1 -->
```mermaid
flowchart TD
    A[Start Here] --> B[Platform]
    B --> C[Best Practices]
    C --> D[Language Guides]
    D --> E[Operations]
    E --> F[Troubleshooting]
    F --> G[Reference]
```

## Scope and disclaimer

This is an independent community project. Not affiliated with or endorsed by Microsoft.

Primary product reference: [Azure App Service overview](https://learn.microsoft.com/azure/app-service/overview)
