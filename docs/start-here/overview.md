---
hide:
  - toc
content_sources:
  diagrams:
    - id: start-here-overview-diagram-1
      type: graph
      source: self-generated
      justification: "Self-generated navigation diagram synthesized from official Azure App Service overview documentation for this guide."
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/overview
---
# Azure App Service Practical Guide

This repository is a comprehensive practical guide for building, deploying, operating, and troubleshooting web applications on Azure App Service. Use this Start Here section to understand the guide layout and choose the right path for your role.

## Guide Scope and Audience

This guide is built for:

- Developers deploying web applications to Azure App Service
- SREs and operators running production workloads
- Troubleshooting engineers resolving incidents under pressure

This is an independent community project. Not affiliated with or endorsed by Microsoft.

## Guide Structure

The documentation is organized into seven core sections:

| Section | Purpose | Entry Link |
|---|---|---|
| Start Here | Orientation, learning paths, and repository map | [Start Here](../index.md) |
| Platform | Core App Service architecture and platform behavior | [Platform](../platform/index.md) |
| Best Practices | Production patterns for security, networking, deployment, scaling, reliability | [Best Practices](../best-practices/index.md) |
| Language Guides | End-to-end implementation guides by stack | [Language Guides](../language-guides/index.md) |
| Operations | Day-2 operational execution for production | [Operations](../operations/index.md) |
| Troubleshooting | Methodology, playbooks, KQL, and lab scenarios | [Troubleshooting](../troubleshooting/index.md) |
| Reference | CLI cheatsheet, KQL queries, platform limits | [Reference](../reference/index.md) |

<!-- diagram-id: start-here-overview-diagram-1 -->
```mermaid
graph TD
    A[Start Here] --> B[Platform]
    A --> BP[Best Practices]
    A --> C[Language Guides]
    B --> BP
    BP --> D[Operations]
    C --> D
    D --> E[Troubleshooting]
    E --> D
    E --> R[Reference]
```

## How to Use This Guide

1. Begin with this section to understand navigation and scope.
2. Read Platform before deep implementation or production hardening.
3. Review Best Practices for production patterns and anti-patterns.
4. Select one Language Guide for your runtime stack.
5. Move to Operations to establish reliability, security, and scale practices.
6. Use Troubleshooting during incident response and for preventive learning.
7. Consult Reference for quick CLI, KQL, and limits lookups.

## See Also

- [Learning Paths](./learning-paths.md)
- [Repository Map](./repository-map.md)
- [Platform](../platform/index.md)
- [Operations](../operations/index.md)
- [Troubleshooting](../troubleshooting/index.md)
- [Reference](../reference/index.md)

## Sources

- [Azure App Service overview (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/overview)
- [Azure App Service documentation hub (Microsoft Learn)](https://learn.microsoft.com/azure/app-service/)
