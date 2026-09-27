# Azure Practical Guide Series Contract

This file preserves the series-wide structure and navigation contract shared by the Azure Practical Guide repositories. Repository-specific evidence, claim, experiment, and agent rules remain in `AGENTS.md` at the repository root.

## Series-Wide Documentation Contract

This repository is part of the Azure Practical Guide series. All repositories in the series must preserve a consistent reader experience while allowing repository-specific extensions.

### Core Sections

Every service-focused repository SHOULD use these core sections unless the repository-specific addendum explains an exception.

| Section | Required | Purpose |
|---|---:|---|
| `Start Here` | Yes | Entry points, overview, learning paths, repository map |
| `Platform` | Yes | Service concepts, architecture, core behavior |
| `Best Practices` | Yes | Production patterns, anti-patterns, design guidance |
| `Operations` | Yes | Day-2 operational procedures and verification |
| `Troubleshooting` | Yes | Symptom-based diagnosis, playbooks, evidence collection |
| `Reference` | Yes | CLI, KQL, limits, glossary, decision tables |

### Approved Extension Sections

| Section | Use When |
|---|---|
| `Tutorials` | The repository provides hands-on learning or lab sequences |
| `Lab Guides` | Reproducible experiments or validation exercises are first-class content |
| `Language Guides` | The service has language/runtime-specific implementation tutorials |
| `SDK Guides` | The service is primarily consumed through SDKs |
| `Service Guides` | The repository configures or monitors multiple Azure services |
| `Workload Guides` | The repository is architecture/workload oriented |
| `Architecture Reviews` | The repository includes architecture review methodology and playbooks |
| `Design Labs` | The repository includes architecture design exercises |
| `Visualization` | Visual maps are a deliberate learning surface, not generated leftovers |
| `Meta` | Repository taxonomy, content model, or generated metadata |

Do not create a new top-level section if the content can fit under one of the core or approved extension sections.

### App Service-Specific Addendum

This repository is an advanced App Service runtime guide. It uses these approved App Service extension sections in addition to the series core sections.

#### App Service-Specific Extension Sections

| Section | Purpose |
|---|---|
| `Language Guides` | Python, Node.js, Java, and .NET implementation paths |
| `Visualization` | Knowledge graphs and troubleshooting maps |
| `Meta` | Taxonomy and repository content model |
| `Troubleshooting Lab Guides` | Reproducible failure experiments |
| `KQL Query Packs` | Diagnostic queries for App Service scenarios |

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

## Start Here Rules

`Start Here` is orientation content. It must not become a language tutorial, SDK tutorial, operations runbook, troubleshooting playbook, or lab guide.

Required pages:

| Page | Purpose |
|---|---|
| `overview.md` | Who this guide is for, what is in scope, and what is out of scope |
| `learning-paths.md` | Role-based and experience-based reading paths |
| `repository-map.md` | Map of major sections and when to use them |

Optional pages:

| Page Pattern | Purpose |
|---|---|
| `when-to-use-*.md` | Service selection guidance |
| `prerequisites.md` | Required tools, permissions, and accounts |
| `common-scenarios.md` | Common use cases |
| `*-vs-other-compute.md` | Positioning against neighboring Azure services |
| `how-to-use-this-guide.md` | Reader navigation guidance |

`learning-paths.md` MUST:

- Start with role-based or goal-based paths.
- Link to tutorials instead of embedding a full tutorial sequence.
- Avoid service-specific code walkthroughs except short examples.
- Avoid `content_validation` unless this repository explicitly includes Start Here pages in content validation scope.

Preferred title:

```markdown
# Learning Paths
```

Avoid:

```markdown
# Tutorial: {Service} for {Language}
```

## Navigation Budget

The left navigation should help orientation, not expose every file.

Recommended:

- Top-level sections SHOULD stay between 6 and 9 items.
- Direct children under a top-level section SHOULD stay between 5 and 8 items.
- Large collections such as tutorials, recipes, KQL packs, lab guides, and playbooks SHOULD be listed on index pages rather than fully expanded in `mkdocs.yml`.
- Use hub pages, tables, tags, and search for deep inventory.
- Keep `mkdocs.yml` readable enough that a contributor can understand the site structure without scrolling through hundreds of deep links.

Preferred troubleshooting structure:

```text
Troubleshooting
├─ Overview
├─ Quick Diagnosis
├─ Decision Tree
├─ First 10 Minutes
├─ Playbooks
├─ KQL Query Packs
└─ Labs
```

Avoid exposing every individual playbook, KQL query, and lab guide in `mkdocs.yml` unless the repository is intentionally small.

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

## Content Categories

The documentation is organized by intent and lifecycle stage:

| Section | Purpose |
|---|---|
| **Start Here** | Entry points, learning paths, repository map |
| **Platform** | Architecture, hosting models, networking, scaling — WHAT and HOW it works |
| **Best Practices** | Production patterns — HOW to use the platform well |
| **Language Guides** | Per-language step-by-step tutorials (Python, Node.js, Java, .NET) |
| **Operations** | Day-2 execution — HOW to run in production |
| **Troubleshooting** | Diagnosis and resolution — hypothesis-driven playbooks and labs |
| **Reference** | Quick lookup — CLI cheatsheet, KQL queries, platform limits |

## See Also

- [Repository Taxonomy](taxonomy.md)
- [Golden Evidence Model](../reference/golden-evidence-model.md)
- [Golden Migration Specification](../reference/golden-migration-spec.md)

## Sources

- [Azure Practical Guide series repositories](https://github.com/yeongseon)
