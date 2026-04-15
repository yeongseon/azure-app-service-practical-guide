# Contributing

Thank you for your interest in contributing to Azure App Service Practical Guide!

## Quick Start

1. Fork the repository
2. Clone: `git clone https://github.com/yeongseon/azure-app-service-practical-guide.git`
3. Install dependencies: `pip install mkdocs-material mkdocs-minify-plugin`
4. Start local preview: `mkdocs serve`
5. Open `http://127.0.0.1:8000` in your browser
6. Create a feature branch: `git checkout -b feature/your-change`
7. Make changes and validate: `mkdocs build --strict`
8. Submit a Pull Request

## Repository Structure

```text
.
├── .github/
│   └── workflows/              # GitHub Pages deployment
├── apps/
│   ├── python-flask/            # Flask + Gunicorn implementation
│   ├── nodejs/                  # Express.js implementation
│   ├── java-springboot/         # Spring Boot implementation
│   └── dotnet-aspnetcore/       # ASP.NET Core implementation
├── docs/
│   ├── assets/                  # Images, icons
│   ├── best-practices/          # Production patterns
│   ├── language-guides/         # Per-language tutorials
│   ├── operations/              # Day-2 operational tasks
│   ├── platform/                # Architecture and concepts
│   ├── reference/               # CLI cheatsheet, platform limits
│   ├── start-here/              # Entry points
│   └── troubleshooting/         # Playbooks, lab guides, KQL
│       ├── playbooks/           # Detailed failure scenario guides
│       ├── lab-guides/          # Step-by-step issue reproduction
│       └── kql/                 # KQL snippets for diagnostics
├── infra/                       # Bicep/Terraform templates
├── labs/                        # Lab infrastructure and scripts
└── mkdocs.yml                   # MkDocs Material configuration
```

## Content Categories

| Section | Purpose |
|---|---|
| **Start Here** | Entry points, learning paths, repository map |
| **Platform** | Architecture, hosting models, networking, scaling — WHAT and HOW it works |
| **Best Practices** | Production patterns — HOW to use the platform well |
| **Language Guides** | Per-language step-by-step tutorials (Python, Node.js, Java, .NET) |
| **Operations** | Day-2 execution — HOW to run in production |
| **Troubleshooting** | Diagnosis and resolution — hypothesis-driven playbooks and labs |
| **Reference** | Quick lookup — CLI cheatsheet, KQL queries, platform limits |

## Document Templates

Every document must follow the template for its section. Do not invent new structures.

### Platform docs

```text
# Title
Brief introduction (1-2 sentences)
## Main Content
### Subsections
## See Also
## Sources
```

### Best Practices docs

```text
# Title
Brief introduction
## Why This Matters
## Recommended Practices
## Common Mistakes / Anti-Patterns
## Validation Checklist
## See Also
## Sources
```

### Operations docs

```text
# Title
Brief introduction
## Prerequisites
## When to Use
## Procedure
## Verification
## Rollback / Troubleshooting
## See Also
## Sources
```

### Tutorial docs (Language Guides)

```text
# Title
Brief introduction
## Prerequisites
## What You'll Build
## Steps
## Verification
## Next Steps / Clean Up (optional)
## See Also
## Sources (optional)
```

### Troubleshooting docs

```text
# Title
## Symptom
## Possible Causes
## Diagnosis Steps
## Resolution
## Prevention
## See Also
## Sources
```

### Lab Guides

```text
# Title
Brief introduction
## Lab Metadata (table: difficulty, duration, tier, etc.)
## 1) Background
## 2) Hypothesis
## 3) Runbook
## 4) Experiment Log
## Expected Evidence
## Clean Up
## Related Playbook
## See Also
## Sources
```

### Reference docs

```text
# Title
Brief introduction
## Topic/Command Groups
## Usage Notes
## See Also
## Sources
```

## Writing Standards

### CLI Commands

```bash
# ALWAYS use long flags for readability
az webapp create --resource-group $RG --name $APP_NAME --plan $PLAN_NAME --runtime "PYTHON:3.11"

# NEVER use short flags in documentation
az webapp create -g $RG -n $APP_NAME  # ❌ Don't do this
```

### Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `$RG` | Resource group name | `rg-appservice-demo` |
| `$APP_NAME` | Web app name | `app-demo` |
| `$PLAN_NAME` | App Service plan | `plan-demo-appservice` |
| `$LOCATION` | Azure region | `koreacentral` |
| `$SUBSCRIPTION_ID` | Subscription identifier placeholder | `<subscription-id>` |

### Mermaid Diagrams

All architectural diagrams use Mermaid. Every documentation page should include at least one diagram.

### Nested Lists

All nested list items MUST use **4-space indent** (Python-Markdown standard).

### Admonitions

For MkDocs admonitions, indent body content by **4 spaces**:

```markdown
!!! warning "Title"
    Body text here.
```

### Tail Sections

Every document ends with these sections in order:

1. `## See Also` — internal cross-links within this guide
2. `## Sources` — external references (Microsoft Learn URLs)

## Content Source Policy

All content must be traceable to official Microsoft Learn documentation.

| Source Type | Description | Allowed? |
|---|---|---|
| `mslearn` | Directly from Microsoft Learn | Required for platform content |
| `mslearn-adapted` | Adapted from Microsoft Learn | Yes, with source URL |
| `self-generated` | Original content | Requires justification |

## PII Rules

NEVER include real Azure identifiers in documentation or examples:

- Subscription IDs: use `<subscription-id>`
- Tenant IDs: use `<tenant-id>`
- Emails: use `user@example.com`
- Secrets, tokens, connection strings: NEVER include

## Build and Validate

```bash
# Install dependencies
pip install mkdocs-material mkdocs-minify-plugin

# Validate (must pass before submitting PR)
mkdocs build --strict

# Local preview
mkdocs serve
```

## Git Commit Style

```
type: short description
```

Allowed types: `feat`, `fix`, `docs`, `chore`, `refactor`

## Review Process

1. Automated CI checks (MkDocs build)
2. Maintainer review for accuracy and completeness
3. Merge to main triggers GitHub Pages deployment

## Code of Conduct

Please read our [Code of Conduct](https://github.com/yeongseon/azure-app-service-practical-guide/blob/main/CODE_OF_CONDUCT.md) before contributing.

## See Also

- [Repository Map](../start-here/repository-map.md)
- [Learning Paths](../start-here/learning-paths.md)
