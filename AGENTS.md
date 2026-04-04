# AGENTS.md

Guidance for AI agents working in this repository.

## Project Overview

**Azure App Service Practical Guide** — a unified documentation hub, reference applications, and hands-on troubleshooting labs for deploying and operating web apps on Azure App Service (Linux).

- **Live site**: <https://yeongseon.github.io/azure-app-service-practical-guide/>
- **Repository**: <https://github.com/yeongseon/azure-app-service-practical-guide>

## Repository Structure

```text
.
├── .github/
│   └── workflows/              # GitHub Pages deployment
├── apps/
│   ├── dotnet-aspnetcore/      # .NET reference application
│   ├── java-springboot/        # Java reference application
│   ├── nodejs/                 # Node.js reference application
│   └── python-flask/           # Python reference application
├── docs/
│   ├── assets/                 # Images, icons
│   ├── best-practices/         # Production patterns and anti-patterns (8 pages)
│   ├── javascripts/            # Mermaid zoom JS
│   ├── language-guides/
│   │   ├── python/             # Python (Flask) — 7 tutorials + recipes
│   │   ├── nodejs/             # Node.js (Express) — 7 tutorials + recipes
│   │   ├── java/               # Java (Spring Boot) — 7 tutorials + recipes
│   │   └── dotnet/             # .NET (ASP.NET Core) — 7 tutorials + recipes
│   ├── operations/             # Day-2 operational execution (8 pages)
│   ├── platform/               # Architecture and design decisions (9 pages)
│   ├── reference/              # CLI cheatsheet, KQL queries, limits (6 pages)
│   ├── start-here/             # Overview, learning paths, repository map (3 pages)
│   ├── stylesheets/            # Custom CSS (mermaid zoom, etc.)
│   └── troubleshooting/        # Full troubleshooting hub (53 pages)
│       ├── architecture-overview.md
│       ├── decision-tree.md
│       ├── evidence-map.md
│       ├── mental-model.md
│       ├── first-10-minutes/   # Checklists by symptom category (4 pages)
│       ├── kql/                # KQL query packs (14 pages)
│       ├── lab-guides/         # Hands-on labs — 10 labs with Expected Evidence
│       ├── methodology/        # Troubleshooting method, detector map (2 pages)
│       └── playbooks/          # 16 playbooks with real Azure evidence
│           ├── startup-availability/   # 7 playbooks
│           ├── performance/            # 6 playbooks
│           └── outbound-network/       # 3 playbooks
├── infra/                      # Shared Bicep modules
├── labs/                       # Lab infrastructure + app source
│   ├── _shared/scripts/        # Shared trigger/verify scripts
│   ├── container-http-pings/
│   ├── deployment-succeeded-startup-failed/
│   ├── dns-vnet-resolution/
│   ├── failed-to-forward-request/
│   ├── intermittent-5xx/
│   ├── memory-pressure/
│   ├── no-space-left-on-device/
│   ├── slot-swap-config-drift/
│   ├── slow-start-cold-start/
│   └── snat-exhaustion/
└── mkdocs.yml                  # MkDocs Material configuration (7-tab nav)
```

## Content Categories

The documentation is organized by intent and lifecycle stage:

| Section | Purpose | Page Count |
|---|---|---|
| **Start Here** | Entry points, learning paths, repository map | 3 |
| **Platform** | Architecture, design decisions — WHAT and HOW it works | 9 |
| **Best Practices** | Production patterns — HOW to use the platform well | 8 |
| **Language Guides** | Per-language step-by-step tutorials and recipes | 79 |
| **Operations** | Day-2 execution — HOW to run in production | 8 |
| **Troubleshooting** | Diagnosis and resolution — hypothesis-driven | 53 |
| **Reference** | Quick lookup — CLI, KQL, platform limits | 6 |

!!! info "Platform vs Best Practices vs Operations"
    - **Platform** = Understand the concepts and architecture.
    - **Best Practices** = Apply practical patterns and avoid common mistakes.
    - **Operations** = Execute day-2 tasks in production.

## Documentation Conventions

### File Naming

- Tutorial: `XX-topic-name.md` (numbered for sequence)
- All others: `topic-name.md` (kebab-case)

### CLI Command Style

```bash
# ALWAYS use long flags for readability
az webapp create --resource-group $RG --name $APP_NAME --plan $PLAN_NAME

# NEVER use short flags in documentation
az webapp create -g $RG -n $APP_NAME  # ❌ Don't do this
```

### Variable Naming Convention

| Variable | Description | Example |
|----------|-------------|---------|
| `$RG` | Resource group name | `rg-appservice-demo` |
| `$APP_NAME` | Web app name | `app-demo-web` |
| `$PLAN_NAME` | App Service plan | `asp-demo-linux` |
| `$LOCATION` | Azure region | `koreacentral` |
| `$SUBSCRIPTION_ID` | Subscription identifier placeholder | `<subscription-id>` |

### PII Removal (Quality Gate)

**CRITICAL**: All CLI output examples MUST have PII removed.

Patterns to mask:

- UUIDs: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- Subscription IDs: `<subscription-id>`
- Tenant IDs: `<tenant-id>`
- Object IDs: `<object-id>`
- Emails: Remove or mask
- Secrets/Tokens: NEVER include

### Admonition Indentation Rule

For MkDocs admonitions (`!!!` / `???`), every line in the body must be indented by **4 spaces**.

```markdown
!!! warning "Important"
    This line is correctly indented.

    - List item also inside
```

### Mermaid Diagrams

All architectural diagrams use Mermaid. Every documentation page should include at least one diagram. Test with `mkdocs build --strict`.

### Section Structure

Documents follow a consistent structure:

- **See Also** = Internal cross-links within this repository
- **References** = External links to Microsoft Learn (authoritative source)

All content must be based on Microsoft Learn with cited sources.

## Troubleshooting Content Standards

### Playbooks (16 total)

Each playbook includes:

1. Symptom description and hypotheses
2. Evidence collection steps
3. **Sample Log Patterns** — real log lines from Azure deployment
4. **KQL Queries with Example Output** — 2-3 queries with result tables + `!!! tip "How to Read This"` interpretation
5. **CLI Investigation Commands** — with example output and interpretation
6. **Normal vs Abnormal Comparison** — table
7. **Common Misdiagnoses** section
8. **Related Labs** — cross-links to lab guide docs

### Lab Guides (10 total)

Each lab guide includes:

1. Background and failure progression model
2. Falsifiable hypothesis
3. Step-by-step runbook
4. Experiment log with real artifact data
5. **Expected Evidence** section:
    - Before Trigger (Baseline)
    - During Incident
    - After Recovery
    - Evidence Timeline (Mermaid)
    - Evidence Chain: Why This Proves the Hypothesis (falsification logic)
6. Related Playbook cross-links

### Data Verification

All playbook evidence and lab guide data was collected from real Azure deployments:

- 10 App Service Linux (B1, Python 3.11, koreacentral)
- Data sources: AppServiceHTTPLogs, AppServiceConsoleLogs, AppServicePlatformLogs
- KQL collected via REST API: `az rest --method post --uri "https://api.loganalytics.io/v1/workspaces/{CUSTOMER_ID}/query"`
- All data sanitized (PII removed)

## Build & Preview

```bash
# Install MkDocs dependencies
pip install mkdocs-material mkdocs-minify-plugin

# Build documentation (strict mode catches broken links)
mkdocs build --strict

# Local preview
mkdocs serve
```

## Git Commit Style

```text
type: short description
```

Allowed types: `feat`, `fix`, `docs`, `chore`, `refactor`
