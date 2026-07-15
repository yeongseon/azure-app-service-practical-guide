# Azure App Service Practical Guide

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

📘 Documentation site: <https://yeongseon.github.io/azure-app-service-practical-guide/>

[![Docs](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/docs.yml/badge.svg)](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/docs.yml)
[![CI](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/app-infra-ci.yml/badge.svg)](https://github.com/yeongseon/azure-app-service-practical-guide/actions/workflows/app-infra-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Comprehensive guide for running web applications on Azure App Service — from first deployment to production troubleshooting.

## What's Inside

| Section | Description | Status |
|---------|-------------|--------|
| [Start Here](https://yeongseon.github.io/azure-app-service-practical-guide/) | Overview, learning paths, and repository map | Comprehensive |
| [Platform](https://yeongseon.github.io/azure-app-service-practical-guide/platform/) | Architecture, hosting models, networking, scaling | Comprehensive |
| [Best Practices](https://yeongseon.github.io/azure-app-service-practical-guide/best-practices/) | Production baseline, security, networking, deployment, scaling, reliability | Comprehensive |
| [Language Guides](https://yeongseon.github.io/azure-app-service-practical-guide/language-guides/) | Step-by-step tutorials for Python, Node.js, Java, and .NET | Comprehensive |
| [Operations](https://yeongseon.github.io/azure-app-service-practical-guide/operations/) | Deployment slots, health checks, security, cost optimization | Comprehensive |
| [Troubleshooting](https://yeongseon.github.io/azure-app-service-practical-guide/troubleshooting/) | Playbooks, hands-on labs, KQL query packs, decision tree, evidence map | Lab-validated |
| [Reference](https://yeongseon.github.io/azure-app-service-practical-guide/reference/) | CLI cheatsheet, KQL queries, platform limits, diagnostics reference | Comprehensive |

**Status legend**: **Lab-validated** = Comprehensive + reproducible labs prove the guidance · **Comprehensive** = Full section, MSLearn-verified, production-ready · **Published** = Core content in place, still expanding · **In progress** = Partial content, active development · **Planned** = Placeholder, content not yet started

## Language Guides

- **Python** (Flask + Gunicorn)
- **Node.js** (Express)
- **Java** (Spring Boot)
- **.NET** (ASP.NET Core)

Each guide covers: local development, first deploy, configuration, logging, infrastructure as code, CI/CD, and custom domains.

## Quick Start

```bash
git clone https://github.com/yeongseon/azure-app-service-practical-guide.git
cd azure-app-service-practical-guide

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-docs.txt

mkdocs serve
```

Visit `http://127.0.0.1:8000` to browse the documentation locally.

## Reference Applications

Minimal reference applications demonstrating Azure App Service patterns:

- `apps/python-flask/` — Flask + Gunicorn
- `apps/nodejs/` — Express
- `apps/java-springboot/` — Spring Boot
- `apps/dotnet-aspnetcore/` — ASP.NET Core

## Troubleshooting Labs

10 hands-on labs in `labs/` with Bicep templates that reproduce real-world App Service issues. Each lab includes:

- Falsifiable hypothesis and step-by-step runbook
- Real Azure deployment data (KQL logs, CLI output, diagnostic endpoints)
- Expected Evidence sections (Before / During / After with falsification logic)
- Cross-links to corresponding playbooks

## Contributing

Contributions welcome! Please see our [Contributing Guide](https://yeongseon.github.io/azure-app-service-practical-guide/contributing/) for:

- Repository structure and content organization
- Document templates and writing standards
- CLI command style and PII rules
- Local development setup and build validation
- Pull request process

## Related Projects

| Repository | Description |
|---|---|
| [azure-virtual-machine-practical-guide](https://github.com/yeongseon/azure-virtual-machine-practical-guide) | Azure Virtual Machines practical guide |
| [azure-networking-practical-guide](https://github.com/yeongseon/azure-networking-practical-guide) | Azure Networking practical guide |
| [azure-storage-practical-guide](https://github.com/yeongseon/azure-storage-practical-guide) | Azure Storage practical guide |
| [azure-app-service-practical-guide](https://github.com/yeongseon/azure-app-service-practical-guide) | Azure App Service practical guide |
| [azure-functions-practical-guide](https://github.com/yeongseon/azure-functions-practical-guide) | Azure Functions practical guide |
| [azure-communication-services-practical-guide](https://github.com/yeongseon/azure-communication-services-practical-guide) | Azure Communication Services practical guide |
| [azure-container-apps-practical-guide](https://github.com/yeongseon/azure-container-apps-practical-guide) | Azure Container Apps practical guide |
| [azure-kubernetes-service-practical-guide](https://github.com/yeongseon/azure-kubernetes-service-practical-guide) | Azure Kubernetes Service (AKS) practical guide |
| [azure-architecture-practical-guide](https://github.com/yeongseon/azure-architecture-practical-guide) | Azure Architecture practical guide |
| [azure-monitoring-practical-guide](https://github.com/yeongseon/azure-monitoring-practical-guide) | Azure Monitoring practical guide |

## Migration from Legacy Repos

This repository consolidates experiments previously hosted in individual repositories:

| Legacy Repository | Status | Migrated To |
|---|---|---|
| [lab-memory-pressure](https://github.com/yeongseon/lab-memory-pressure) | Archived | [App Service: Memory Pressure](docs/troubleshooting/lab-guides/memory-pressure.md) |
| [lab-node-memory-pressure](https://github.com/yeongseon/lab-node-memory-pressure) | Archived | [App Service: Memory Pressure](docs/troubleshooting/lab-guides/memory-pressure.md) (Node.js comparison) |

### Why Consolidate?

- **Discoverability**: Single location for all PaaS troubleshooting experiments
- **Cross-referencing**: Easy comparison across services (App Service vs Functions vs Container Apps)
- **Consistent methodology**: Shared experiment template and evidence model
- **Easier maintenance**: Single documentation site, unified CI/CD

### Legacy Repo Policy

Legacy repositories are archived but remain accessible for reference. New experiments should be added to this consolidated repository.

## Disclaimer

This is an independent community project. Not affiliated with or endorsed by Microsoft. Azure and App Service are trademarks of Microsoft Corporation.

## License

[MIT](LICENSE)
