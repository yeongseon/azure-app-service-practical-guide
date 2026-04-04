# Azure App Service Practical Guide

Comprehensive guide for running web applications on Azure App Service — from first deployment to production troubleshooting.

## What's Inside

| Section | Description |
|---------|-------------|
| [Start Here](https://yeongseon.github.io/azure-app-service-practical-guide/) | Overview, learning paths, and repository map |
| [Platform](https://yeongseon.github.io/azure-app-service-practical-guide/platform/) | Architecture, hosting models, networking, scaling |
| [Best Practices](https://yeongseon.github.io/azure-app-service-practical-guide/best-practices/) | Production baseline, security, networking, deployment, scaling, reliability |
| [Language Guides](https://yeongseon.github.io/azure-app-service-practical-guide/language-guides/) | Step-by-step tutorials for Python, Node.js, Java, and .NET |
| [Operations](https://yeongseon.github.io/azure-app-service-practical-guide/operations/) | Deployment slots, health checks, security, cost optimization |
| [Troubleshooting](https://yeongseon.github.io/azure-app-service-practical-guide/troubleshooting/) | 16 playbooks, 10 hands-on labs, KQL query packs, decision tree, evidence map |
| [Reference](https://yeongseon.github.io/azure-app-service-practical-guide/reference/) | CLI cheatsheet, KQL queries, platform limits, diagnostics reference |

## Language Guides

- **Python** (Flask + Gunicorn)
- **Node.js** (Express)
- **Java** (Spring Boot)
- **.NET** (ASP.NET Core)

Each guide covers: local development, first deploy, configuration, logging, infrastructure as code, CI/CD, and custom domains.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yeongseon/azure-app-service-practical-guide.git

# Install MkDocs dependencies
pip install mkdocs-material mkdocs-minify-plugin

# Start local documentation server
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

Contributions welcome. Please ensure:
- All CLI examples use long flags (`--resource-group`, not `-g`)
- All documents include mermaid diagrams
- All content references Microsoft Learn with source URLs
- No PII in CLI output examples

## Disclaimer

This is an independent community project. Not affiliated with or endorsed by Microsoft. Azure and App Service are trademarks of Microsoft Corporation.

## License

[MIT](LICENSE)
