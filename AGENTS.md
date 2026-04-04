# AGENTS.md

Guidance for AI agents working in this repository.

## Project Overview

**Azure App Service Field Guide** monorepo — documentation, reference applications, and labs for deploying and operating web apps on Azure App Service.

## Repository Structure

```text
.
├── .github/
│   └── workflows/
├── apps/
│   ├── dotnet-aspnetcore/
│   ├── java-springboot/
│   ├── nodejs/
│   └── python-flask/
├── docs/
│   ├── assets/
│   ├── javascripts/
│   ├── language-guides/
│   ├── operations/
│   ├── platform/
│   ├── reference/
│   ├── start-here/
│   ├── stylesheets/
│   └── troubleshooting/
├── infra/
└── labs/
    ├── container-http-pings/
    ├── deployment-succeeded-startup-failed/
    ├── dns-vnet-resolution/
    ├── failed-to-forward-request/
    ├── intermittent-5xx/
    ├── memory-pressure/
    ├── no-space-left-on-device/
    ├── slot-swap-config-drift/
    ├── slow-start-cold-start/
    └── snat-exhaustion/
```

## Documentation Conventions

- Use **kebab-case** filenames for documentation pages.
- Use Azure CLI **long flags** only (for example, `--resource-group`, not `-g`).
- Mermaid diagrams are required for architecture and flow explanations.
- Reference Microsoft Learn as the authoritative source and include source URLs.
- Never include real PII in examples (subscription IDs, tenant IDs, emails, object IDs, secrets, tokens).

## Admonition Indentation Rule

For MkDocs admonitions (`!!!` / `???`), every line in the body must be indented by **4 spaces**.

```markdown
!!! warning "Important"
    This line is correctly indented.
```

## Variable Naming Convention

| Variable | Description | Example |
|----------|-------------|---------|
| `$RG` | Resource group name | `rg-appservice-demo` |
| `$APP_NAME` | Web app name | `app-demo-web` |
| `$PLAN_NAME` | App Service plan | `asp-demo-linux` |
| `$LOCATION` | Azure region | `koreacentral` |
| `$SUBSCRIPTION_ID` | Subscription identifier placeholder | `<subscription-id>` |

## Build & Preview

- Build: `mkdocs build --strict`
- Local preview: `mkdocs serve`

## Git Commit Style

Use:

```text
type: short description
```

Allowed types:
- `feat`
- `fix`
- `docs`
- `chore`
- `refactor`
