# AGENTS.md

Guidance for AI agents working in this repository.

## Project Overview

**Azure App Service Practical Guide** — a comprehensive, hands-on guide for running web applications on Azure App Service, covering everything from initial deployment to advanced production troubleshooting.

- **Live site**: <https://yeongseon.github.io/azure-app-service-practical-guide/>
- **Repository**: <https://github.com/yeongseon/azure-app-service-practical-guide>

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

## Content Validation Scope

`content_validation` is required for factual-claim pages, not for every Markdown file.

Required by default:

- `docs/platform/**`
- `docs/best-practices/**`
- `docs/operations/**`
- factual troubleshooting methodology/playbook pages

Usually out of scope:

- `docs/start-here/**`
- `docs/reference/**`
- `docs/language-guides/**`
- `docs/sdk-guides/**`
- `docs/tutorials/**`
- `docs/troubleshooting/kql/**`
- `docs/troubleshooting/lab-guides/**`
- generated dashboards
- navigation-only index pages

Content-type-specific rules:

- Tutorials use `validation`.
- Labs use evidence and falsification integrity.
- KQL packs document query purpose, expected interpretation, required tables, and assumptions.
- KQL packs do not need `content_validation` unless they make factual platform claims outside the query explanation.
- Never fabricate validation dates or test results.

## Mermaid Diagrams

Use Mermaid diagrams when they clarify architecture, flow, dependency, decision logic, or troubleshooting paths.

Required for:

- Platform architecture pages
- Complex operations pages
- Decision trees
- Troubleshooting playbooks with multi-step diagnosis
- Lab guides with failure progression or evidence timelines
- Architecture review or design decision flows

Optional for:

- Reference tables
- CLI cheatsheets
- Glossary pages
- Generated validation dashboards
- Short landing pages
- Simple tutorial steps where prose is clearer

Do not add a diagram just to satisfy a checkbox. A diagram must explain something better than prose or a table.

### Diagram Orientation Rule

- **Sequential flows with 5+ nodes**: Use `flowchart TD` (top-down) to prevent horizontal overflow.
- **Short diagrams with fewer than 5 nodes**: `flowchart LR` (left-right) is acceptable.
- **Layered architecture diagrams** (e.g., network layers, stack diagrams): Always use `flowchart TD`.

```mermaid
%% CORRECT — 5+ node sequential flow uses TD
flowchart TD
    A[Commit] --> B[Build and test]
    B --> C[Package artifact]
    C --> D[Deploy to staging]
    D --> E[Validation]
    E --> F[Swap to production]

%% WRONG — long horizontal overflow
flowchart LR
    A[Commit] --> B[Build and test] --> C[Package] --> D[Deploy] --> E[Validate] --> F[Swap]
```

## Image and Screenshot Rules

Images must support the reader's task. Do not add screenshots only for decoration.

Every referenced image MUST have:

- Descriptive alt text.
- A nearby explanation of what the reader should verify.
- No real subscription IDs, tenant IDs, object IDs, emails, phone numbers, secrets, keys, connection strings, or customer data.
- Visual verification before merge when the image is referenced from Markdown.

Recommended explanation pattern:

```markdown
![App Service overview showing a healthy web app](../assets/example.png)

Purpose: Confirm why this image exists.
Look for: Tell the reader what values or states to confirm.
Expected result: State the healthy or expected condition.
Next step: Link the image to the next action.
```

Portal screenshots:

- Prefer text replacement over black-box redaction.
- Use black-box masking only for unavoidable avatar/profile pixels and only with the repository-approved mask color.
- If a screenshot cannot be visually verified, remove the Markdown reference or disclose the debt explicitly in the PR.

## Microsoft Learn URL Locale

All `learn.microsoft.com` URLs SHOULD use the `en-us` locale prefix.

Canonical form:

```text
https://learn.microsoft.com/en-us/azure/app-service/...
```

Avoid locale-less URLs (URLs missing the `/en-us/` segment immediately after the hostname):

```text
https://learn.microsoft.com/<missing-locale>/azure/app-service/...
```

The `<missing-locale>` placeholder marks the position where `/en-us/` must appear. A real locale-less URL would omit that segment entirely; the placeholder is used here only so this anti-pattern example does not trip the `scripts/normalize_mslearn_locale.py` CI gate.

Reason:

- Stable reader experience.
- Stable reviewer experience.
- Easier link checking.
- Less URL drift across repositories.

### Enforcement

- `scripts/normalize_mslearn_locale.py --check` runs in CI on every PR or push that touches a scannable file — Markdown, Python, YAML, JSON, Bicep, Terraform, or text — under any tracked directory except `.git/` and `.playwright-mcp/` (the latter holds MCP-captured browser DOM dumps, which are not authoritative content). Workflow YAML under `.github/workflows/` IS scanned so a Learn URL pasted into a workflow env var is caught.
- Run `python3 scripts/normalize_mslearn_locale.py --apply` locally to fix drift before pushing.
- The check is a pure text transformation; HTTP reachability of URLs is validated separately by `scripts/validate_mslearn_urls.py`, which runs on push to `main`.

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

## Content Types & Methodology

### Troubleshooting Experiments (Labs)

All labs in `docs/troubleshooting/lab-guides/` must follow this 16-section structure:

1. **Question**: The specific problem being investigated.
2. **Setup**: Infrastructure and environment preparation.
3. **Hypothesis**: The expected cause and behavior.
4. **Prediction**: What should happen if the hypothesis is true.
5. **Experiment**: The steps taken to reproduce the issue.
6. **Execution**: The actual running of the experiment.
7. **Observation**: Raw data and logs collected.
8. **Measurement**: Quantified metrics (e.g., latency, error rates).
9. **Analysis**: Interpreting the observations and measurements.
10. **Conclusion**: Confirming or refuting the hypothesis.
11. **Falsification**: Proving that the fix works and the original theory was correct.
12. **Evidence**: Compiled logs, screenshots, or KQL results.
13. **Solution**: The final fix or mitigation.
14. **Prevention**: How to avoid this issue in the future.
15. **Takeaway**: The core lesson learned.
16. **Support Takeaway**: Key points for support engineers or developers.

### Evidence Levels

When documenting troubleshooting steps or analysis, use these tags to specify the strength of the evidence:

- `[Observed]`: Directly seen in logs, metrics, or UI (e.g., 503 errors in Log Analytics).
- `[Measured]`: Quantified data (e.g., 99th percentile latency is 4.5s).
- `[Correlated]`: Two events happening together without proven causation.
- `[Inferred]`: Conclusion based on logic and multiple pieces of evidence.
- `[Strongly Suggested]`: High confidence inference but missing the "smoking gun".
- `[Not Proven]`: Hypothesis that has not yet been validated.
- `[Unknown]`: Missing data or ambiguous behavior.

### Evidence Annotation Policy

The evidence-tag pattern above is a differentiator for this series, but it is an **evidence-annotation tool, not a global writing style**. Applying tags to every image, paragraph, and orientation page causes *annotation fatigue* (readers stop reading them) and invites the `[Observed]`-as-OCR-dump anti-pattern (dumping the full Portal UI text instead of task-relevant values). Scope the tags by document type.

**Where evidence tags are required:**

- Troubleshooting lab guides
- Experiment logs
- KQL result interpretation
- Portal evidence sections
- Incident-style diagnostic walkthroughs

**Where evidence tags are optional:**

- Troubleshooting playbooks (decision points only)
- Platform deep dives (only where documented facts and observed behavior diverge)
- Operations verification sections
- Advanced diagnostic tutorials

**Where evidence tags should usually be avoided:**

- `Start Here`, `Learning Paths`, repository maps
- README files
- Glossary pages and CLI cheatsheets
- Simple tutorial steps
- Navigation-only index pages

**Writing rules — Do:**

- Keep `[Observed]` short and limited to task-relevant facts.
- Use `[Measured]` for numeric query or metric results.
- Use `[Inferred]` only when the reasoning depends on observations.
- Use `[Not Proven]` when a screenshot or query does not fully prove the claim.
- Put long evidence details in collapsible `??? note "Evidence notes"` blocks.

**Writing rules — Do not:**

- Use `[Observed]` as an OCR dump of the entire screen.
- Put long Portal UI text in image alt text.
- Use evidence tags to make normal prose look more rigorous.
- Treat `[Inferred]` as a substitute for Microsoft Learn sourcing.
- Force evidence tags into Start Here or Learning Paths pages.

Document-type matrix:

| Document type | Usage |
|---|---|
| Troubleshooting lab guide | Required |
| Incident-style experiment log | Required |
| KQL result interpretation | Strongly recommended (`[Measured]` / `[Observed]` / `[Inferred]`) |
| Portal evidence screenshot | Strongly recommended, kept short |
| Troubleshooting playbook | Recommended (decision points only) |
| Platform deep-dive | Optional (only where docs and observations diverge) |
| Language tutorial | Limited ("Verify" step only, short) |
| Start Here / Overview / Learning Paths | Nearly forbidden |
| Reference / CLI cheatsheet / glossary | Nearly forbidden (metric-capture reference pages excepted) |
| README / landing page | Effectively forbidden |

This policy is tracked series-wide in [issue #296](https://github.com/yeongseon/azure-container-apps-practical-guide/issues/296).

### Screenshot Evidence Pattern

For tutorial and Portal screenshots, prefer this structure over inline OCR dumps:

```markdown
![Short descriptive alt text](../assets/example.png)

Purpose: Explain why this screenshot is included.
Look for: List the 2-4 values the reader should verify.
Expected result: State the healthy or expected condition.
Next step: Point to the next action.

??? note "Evidence notes"
    [Observed] Short task-relevant observation.

    [Inferred] Interpretation based on the observation.

    [Not Proven] What this screenshot alone does not prove.
```

Rules:

- Alt text describes the image, not every visible UI value.
- `[Observed]` includes only values relevant to the task.
- Long raw observations move into the collapsible block.
- Never include real public IPs, subscription names, tenant IDs, object IDs, emails, secrets, or connection strings in alt text or evidence notes.

## Documentation Conventions

### File Naming

- Tutorial: `XX-topic-name.md` (numbered for sequence)
- All others: `topic-name.md` (kebab-case)
- Index files: `index.md` in each directory

### CLI Command Style

```bash
# ALWAYS use long flags for readability
az webapp create --resource-group $RG --name $APP_NAME --plan $PLAN_NAME --runtime "PYTHON:3.11"

# NEVER use short flags in documentation
az webapp create -g $RG -n $APP_NAME  # ❌ Don't do this
```

### Variable Naming Convention

| Variable | Description | Example |
|----------|-------------|---------|
| `$RG` | Resource group name | `rg-appservice-demo` |
| `$APP_NAME` | Web app name | `app-demo` |
| `$PLAN_NAME` | App Service plan | `plan-demo-appservice` |
| `$LOCATION` | Azure region | `koreacentral` |
| `$SUBSCRIPTION_ID` | Subscription identifier placeholder | `<subscription-id>` |

### Language Usage

- **Shell**: Use `bash` for all CLI examples.
- **Python**: Use `python` for all script examples.
- **KQL**: Use `kusto` for all Kusto Query Language blocks.
- **Mermaid**: Use `mermaid` for all architecture and flow diagrams.

### PII Removal (Quality Gate)

**CRITICAL**: All CLI output examples MUST have PII removed.

**Must mask (real Azure identifiers):**

- Subscription IDs: `<subscription-id>`
- Tenant IDs: `<tenant-id>`
- Object IDs: `<object-id>`
- Resource IDs containing real subscription/tenant
- Emails: Remove or mask as `user@example.com`
- Secrets/Tokens: NEVER include

**OK to keep (synthetic example values):**

- Demo correlation IDs: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
- Example request IDs in logs
- Placeholder domains: `example.com`, `contoso.com`
- Sample resource names used consistently in docs

The goal is to prevent leaking **real Azure account information**, not to mask obviously-fake example values that aid readability.

### Portal Screenshot Capture (PII Replacement Rules)

Azure Portal screenshots in `docs/assets/**/*.png` and `docs/assets/**/*.webp` MUST use **text replacement** (not black-box redaction). Black rectangles look like leaks and break visual continuity; replaced placeholders read as documentation examples.

Screenshots may be committed as WebP produced by the manifest-driven capture pipeline (`scripts/capture/`), which downscales the raw PNG and re-encodes it. When a capture is optimized to WebP, the **final rendered `.webp`** — not only the raw PNG — MUST be visually verified for PII and caption accuracy before merge. A PII or caption defect introduced or hidden by re-encoding is treated the same as one in a raw PNG.

#### Capture method

Use the reusable helper at [`scripts/portal-capture-helpers.js`](scripts/portal-capture-helpers.js). Usage instructions for both standalone Playwright and MCP `browser_run_code_unsafe` are in [`scripts/portal-capture-helpers.md`](scripts/portal-capture-helpers.md).

The helper applies replacements to text nodes **and** `aria-label` attributes across the main frame and every nested iframe (Portal blades render inside iframes), then masks only the Account-menu avatar using Playwright's native `mask` option with Portal blue (`#0078d4`) so the masked region blends into the UI.

#### Authenticating the capture browser (Conditional Access)

The capture browser MUST reuse a **device-compliant, interactively signed-in** session. A fresh, isolated Chromium — whether launched by standalone Playwright or by the MCP browser tool — is **not** an Intune-enrolled / device-compliant browser, so it CANNOT pass Microsoft Entra Conditional Access for the MSIT (`ms.portal.azure.com`) tenant. It loops on the sign-in / `ConditionalAccess/Enrollment` ("install Company Portal") wall. **Do not** burn cycles trying to defeat this from automation — it is a device-level security control, not a cookie problem.

Working pattern (attach to a real, human-authenticated Chrome over CDP):

1. **Launch the user's Chrome with a dedicated debug profile and a remote-debugging port.** A dedicated `--user-data-dir` avoids Chrome's block on debugging the default profile, and OS-level Platform SSO / Company Portal still satisfies device compliance:
    ```bash
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
      --remote-debugging-port=9222 \
      --user-data-dir="$HOME/.chrome-portal-capture" \
      --no-first-run --no-default-browser-check \
      "https://ms.portal.azure.com/"
    ```
2. **The human signs in interactively (including MFA) and navigates to the target blade.** The agent CANNOT complete MFA — hand this step to the user explicitly and wait.
3. **Verify the port is bound before attaching:** `curl -s http://localhost:9222/json/version`, and poll `http://localhost:9222/json` to detect when the target blade URL has loaded.
4. **Attach Playwright over CDP** with `chromium.connectOverCDP('http://localhost:9222')`, pick the page whose URL contains `portal.azure.com`, apply the PII helper, then screenshot. `browser.close()` on a CDP-attached browser only detaches the debugger; it does NOT close the user's Chrome.

Common failure: relaunching the Chrome binary while Chrome is already running just opens a tab in the existing (non-debug) process and silently ignores `--remote-debugging-port`. Always confirm the port with `curl`/`nc` before assuming the debug instance is up.

#### PII Replacement Rules

| Pattern | Replacement | Rationale |
|---|---|---|
| GUID (subscription, tenant, object, resource ID) | `00000000-0000-0000-0000-000000000000` | Zero-GUID is the documented Azure placeholder convention. Boundary-anchored to avoid eating GUID-shaped substrings inside longer hex tokens. |
| `MCAPS-*` / `MCAPS*` subscription names | `Visual Studio Enterprise Subscription` | MCAPS prefixes leak internal subscription naming. Word-bounded so identifiers like `XMCAPSinternal` are not partially rewritten. |
| `Microsoft Non-Production` tenant badge | `Contoso` | Tenant display name visible in the top-right Account button leaks the internal environment. |
| `*@microsoft.com` | `user@example.com` | Employee emails. Case-insensitive; trailing negative lookahead prevents `user@microsoft.com.uk`-style partial rewrites. |
| `*@*.onmicrosoft.com` | `user@example.com` | Tenant-scoped user emails. Case-insensitive; trailing negative lookahead prevents partial rewrites of longer hostnames. |
| `*.onmicrosoft.com` (bare domain) | `contoso.onmicrosoft.com` | Tenant domains. Trailing negative lookahead prevents partial rewrites of longer hostnames such as `tenant.onmicrosoft.com.uk`. |
| `ychoe` (employee alias) | `demouser` | Author alias, word-bounded so unrelated tokens are not touched. |
| `Yeongseon Choe` (display name) | `Demo User` | Author display name. |
| `yeongseon` (GitHub handle, bare token) | `demouser` | Author GitHub username surfaced in Deployment Center "Signed in as" panels and similar source-control integrations. Case-insensitive and word-bounded; runs AFTER the `Yeongseon Choe` rule so the full display-name form is preserved. |
| Uppercase hex token ≥ 32 chars (Custom Domain Verification ID, other SHA-256-style identifiers) | 64-char `AAAA…A` placeholder | Custom Domain Verification IDs and similar long uppercase hex strings are real account-scoped tokens that the GUID regex does not match. Boundary-anchored so shorter hex substrings inside other tokens are not partially rewritten. |
| Lowercase hex token exactly 64 chars (Docker container instance ID surfaced by KuduLite header and `/api/processes`, other SHA-256-style identifiers) | 64-char `aaaa…a` placeholder | Docker container instance IDs on Linux App Service are 64-char lowercase SHA-256-style identifiers rendered in the modern KuduLite UI header and `/api/processes` JSON responses. The uppercase 32+ rule does not match them because it is case-sensitive. Length-anchored at exactly 64 to avoid rewriting shorter hex substrings inside other tokens (KuduLite also displays a truncated 14-char prefix; the truncated form is not caught by design and is treated as low-risk because it rotates on every container restart). |
| Lowercase hex token exactly 32 chars (ARM `roleAssignmentName` surfaced in `RoleAssignmentExists` error banners, other MD5-style identifiers) | 32-char `0000…0` placeholder | ARM emits `roleAssignmentName` as a 32-char lowercase no-hyphen hex derived from a hash of `(scope, principal, role)`, and surfaces the value verbatim in the `RoleAssignmentExists` error banner rendered on the Portal Deployment Details blade. The GUID rule requires hyphens, the uppercase 32+ rule is case-sensitive, and the 64-char lowercase rule requires exactly 64 chars, so none of the existing rules catch this shape. Length-anchored at exactly 32 to avoid rewriting shorter hex substrings inside other tokens. Placed after the 64-char rule so a 64-char lowercase string is caught by the more specific rule first. |
| RFC1918 private IPv4 address (App Service internal Docker registry endpoint surfaced in `AppServicePlatformLogs` `docker run` messages, other platform-internal endpoints in log rows) | `10.0.0.0` (RFC1918 anchor) | App Service surfaces internal endpoints such as `10.x.y.z:port` for the platform Docker registry in `AppServicePlatformLogs` Msg columns. Although RFC1918 addresses do not identify a customer subscription, they reveal Azure fleet internal topology (registry subnet layout, IP allocation ranges) that MSFT policy treats as not-for-publication. The regex is strict-boundary and validates every octet 0-255, matches `10.0.0.0/8`, `172.16.0.0/12`, and `192.168.0.0/16`, and preserves any trailing `:port` so readers still see the port structure. Placed after the hex rules because it targets a different token class (dotted decimal) and cannot collide with them. |
| Public IPv4 address (Azure platform-pool outbound IPs, customer VIPs, Front Door endpoints, App Service Overview blade inbound IP, Networking-hub Outbound IP lists, Diagnose-and-solve network detectors, or similar Portal blades) | `192.0.2.1` (RFC 5737 TEST-NET-1 documentation range) | Public IPv4 addresses shown in Portal blades reveal Azure stamp assignments, front-end pool topology, and customer VIP mappings. The regex uses negative-lookahead prefix checks to skip RFC1918 ranges (which are caught by the earlier RFC1918 rule with the different `10.0.0.0` replacement) so no double-replacement occurs. Placed BEFORE the RFC1918 rule in the helper's execution order so the RFC1918 replacement value `10.0.0.0` is never seen by this rule. Uses RFC 5737 TEST-NET-1 (`192.0.2.0/24`) as replacement so the Portal screenshot renders a visually plausible documentation IPv4 that will not be misread as a real host. |
| IPv6 address, any form including compressed `::` (Azure platform-pool outbound IPv6, Inbound IPv6 in Overview / Networking blades, `2603:*` / `2a01:*` stamp aggregates, or IPv6 addresses inside `[...]` brackets with `:port` suffix) | `2001:db8::1` (RFC 3849 documentation range) | IPv6 addresses in `2603:*` / `2a01:*` are Microsoft-owned platform aggregates but still identify a specific Azure stamp / region deployment - the same fleet-topology concern that justifies the RFC1918 rule. The regex is the standard 9-branch IPv6-with-compression pattern (based on RFC 4291) with negative lookbehind and lookahead guards `(?<![:.a-fA-F0-9])` / `(?![:.a-fA-F0-9])` to avoid partial matches inside longer hex tokens (GUIDs, 32/64-char hex identifiers). Known limitations: does not match IPv4-mapped IPv6 (`::ffff:192.0.2.1`) or zone identifiers (`fe80::1%eth0`) - neither shape appears in Portal blades that this repository captures. Placed at the END of the helper's rule list so all hex-token rules (GUID, 32-char, 64-char, 32+ uppercase) run first and consume their tokens before this pattern sees them. |
| Account-menu avatar (cannot be rewritten) | Native Playwright mask, `maskColor='#0078d4'` | Blends with Portal command bar. The helper throws if the avatar selector matches nothing. |

The replacement scope covers text nodes, `aria-label`, `title`, and the visible value of `input` / `textarea` controls so search bars and filter chips do not leak resource names.

#### Capture workflow rules

- **Re-navigate between captures.** Portal CSS is cumulative; leftover style injections from a previous capture leak into the next page (e.g. left-nav appearing as a black box). Always call `browser_navigate` to reload before applying the helper.
- **Use the Portal MSIT URL with tenant hint.** `https://ms.portal.azure.com/#@<tenant>.onmicrosoft.com/resource/...`. Plain `portal.azure.com` triggers a login redirect.
- **Prefer the English-language Portal.** The primary avatar selector keys off the English `aria-label` "Account menu"; a localized Portal may still match the `button.fxs-menu-account` fallback class, but that fallback is best-effort and not a stable contract. The helper throws if neither selector matches, so non-English captures should be reviewed manually.
- **Close every transient flyout, drawer, and command-bar dropdown** before capture. Account panel, Recent menu, notifications, and tenant switcher each surface PII the helper cannot fully rewrite (avatar thumbnails, embedded canvases, late-rendered iframe content).
- **Wait for the target blade to finish rendering** before applying replacements. The helper's 400 ms post-replacement pause is not a substitute for a per-blade `browser_wait_for` against stable text or an element on the blade.
- **Viewport: 1600 x 1000.** Captures the standard blade layout without horizontal scrollbars.
- **No black-box masking.** If a value cannot be rewritten and is not a known avatar/badge, fail the capture and update `PII_RULES` rather than fall back to a black rectangle.

If `PII_RULES` in the helper is updated, this table MUST be updated in the same commit.

#### Inline capture pattern (Playwright MCP `browser_run_code_unsafe`)

When capturing via the Playwright MCP `browser_run_code_unsafe` tool (no `require()` access), the PII helper must be **inlined** in the snippet. The inline rules MUST match `scripts/portal-capture-helpers.js` exactly; do not omit or alter any rule.

**Mandatory inline structure (per capture):**

```javascript
async (page) => {
  const PII_SCRIPT = `(() => {
    const subs = [
      { re: /(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])/gi, val: '00000000-0000-0000-0000-000000000000' },
      { re: /\\bMCAPS[-A-Za-z0-9_]*\\b/g, val: 'Visual Studio Enterprise Subscription' },
      { re: /Microsoft\\s+Non-Production/gi, val: 'Contoso' },
      { re: /\\b[A-Za-z0-9._%+-]+@microsoft\\.com(?![A-Za-z0-9.-])/gi, val: 'user@example.com' },
      { re: /\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.onmicrosoft\\.com(?![A-Za-z0-9.-])/gi, val: 'user@example.com' },
      { re: /\\b[A-Za-z0-9-]+\\.onmicrosoft\\.com(?![A-Za-z0-9.-])/gi, val: 'contoso.onmicrosoft.com' },
      { re: /\\bychoe\\b/gi, val: 'demouser' },
      { re: /Yeongseon\\s+Choe/g, val: 'Demo User' },
      { re: /\\byeongseon\\b/gi, val: 'demouser' },
      { re: /\\b[0-9A-F]{32,}\\b/g, val: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' },
      { re: /\\b[0-9a-f]{64}\\b/g, val: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' },
      { re: /\\b[0-9a-f]{32}\\b/g, val: '00000000000000000000000000000000' },
      { re: /\\b(?!10\\.)(?!172\\.(?:1[6-9]|2[0-9]|3[01])\\.)(?!192\\.168\\.)(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])(?:\\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])){3}\\b/g, val: '192.0.2.1' },
      { re: /\\b(?:10\\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])|172\\.(?:1[6-9]|2[0-9]|3[01])\\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])|192\\.168\\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9]))\\b/g, val: '10.0.0.0' },
      { re: /(?<![:.a-fA-F0-9])(?:(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}|:(?:(?::[0-9a-fA-F]{1,4}){1,7}|:))(?![:.a-fA-F0-9])/g, val: '2001:db8::1' },
    ];
    let count = 0;
    const applySubs = (input) => {
      let out = input;
      for (const { re, val } of subs) {
        re.lastIndex = 0;
        out = out.replace(re, val);
      }
      return out;
    };
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    for (const node of nodes) {
      const orig = node.textContent || '';
      const next = applySubs(orig);
      if (next !== orig) {
        node.textContent = next;
        count++;
      }
    }
    document.querySelectorAll('[aria-label]').forEach((el) => {
      const orig = el.getAttribute('aria-label') || '';
      const next = applySubs(orig);
      if (next !== orig) el.setAttribute('aria-label', next);
    });
    document.querySelectorAll('input, textarea').forEach((el) => {
      const orig = el.value || '';
      const next = applySubs(orig);
      if (next !== orig) {
        el.value = next;
        count++;
      }
    });
    document.querySelectorAll('[title]').forEach((el) => {
      const orig = el.getAttribute('title') || '';
      const next = applySubs(orig);
      if (next !== orig) el.setAttribute('title', next);
    });
    return count;
  })()`;
  const mf = page.mainFrame();
  await mf.evaluate(PII_SCRIPT);
  for (const f of page.frames()) { if (f===mf) continue; try { await f.evaluate(PII_SCRIPT); } catch(e){} }
  await page.waitForTimeout(400);

  const selectors = ['button[aria-label*="Account menu"]', 'button.fxs-menu-account'];
  let avatar = null;
  for (const s of selectors) {
    const loc = page.locator(s);
    if ((await loc.count()) > 0) { avatar = loc.first(); break; }
  }
  if (!avatar) {
    throw new Error('No Account-avatar element matched ' + JSON.stringify(selectors) + '. Wait for the blade to settle before capture; non-English Portals may still match the fxs-menu-account fallback but that is best-effort, not guaranteed.');
  }

  await page.screenshot({
    path: 'docs/assets/<section>/<topic>/<NN>-<blade>-<state>.png',
    fullPage: false,
    mask: [avatar],
    maskColor: '#0078d4',
  });
  return 'captured';
}
```

**Backslash escaping rule (`browser_run_code_unsafe` JSON):**

- Regex escapes (`\b`, `\s`, `\.`) must be written as `\\b`, `\\s`, `\\.` in the inline string literal.
- The template literal itself goes inside the JSON `code` parameter, so the entire snippet is double-escaped one more level when passed as JSON.

**Per-capture mandatory steps (in order):**

1. **Navigate** to the target blade URL (`https://ms.portal.azure.com/#@<tenant>.onmicrosoft.com/resource/...`). Always re-navigate; never reuse a stale page.
2. **Wait** for blade-specific text (`browser_wait_for` with stable text on the blade) before applying replacements. The 400 ms post-replacement pause inside the snippet is not a substitute.
3. **Run the inline snippet** above via `browser_run_code_unsafe`. Replace `<section>`, `<topic>`, `<NN>`, `<blade>`, `<state>` in the screenshot path.
4. **Verify** with the `read` tool on the PNG. Confirm visually:
    - No `MICROSOFT NON-PRODUCTION` badge in top-right
    - No `ychoe@microsoft.com` or `Yeongseon Choe` anywhere
    - Subscription ID rendered as `00000000-0000-0000-0000-000000000000`
    - Subscription name rendered as `Visual Studio Enterprise Subscription`
    - Any Custom Domain Verification ID (or other long uppercase hex token) rendered as `AAAA…A`, never as a real value
    - No public IPv4 or IPv6 addresses visible in Networking-hub Outbound IP lists (should render as `192.0.2.1` / `2001:db8::1`) or Custom domains IP address field (should render as `192.0.2.1`). RFC1918 addresses render as `10.0.0.0`.
    - Account avatar masked with solid Portal-blue (`#0078d4`), not a black rectangle
5. **If verification fails** → fix the helper / inline snippet and re-capture. Never ship a capture with raw PII or a black-box mask.

**What the helper does NOT mask (and why it is acceptable):**

- URL bar / browser chrome — not part of the PNG output.
- `href` attribute values in the DOM — not rendered visually.
- Avatar image pixels — masked with solid Portal-blue rectangle (the only acceptable mask color).

If any of the above ever becomes visible in a capture, treat it as a P0 issue: fail the capture, fix the helper, and re-shoot.

### Frontmatter YAML Style

Every Markdown file in `docs/` begins with a YAML frontmatter block delimited by `---`. The serialization style is **enforced by CI** and centralized in [`scripts/lib/yaml_style.py`](scripts/lib/yaml_style.py). Any script that mutates frontmatter MUST import `dump_frontmatter()` (preferred single-call API) or `build_yaml()` (for tools that need to call `load()` and `dump()` on the same instance) from that module — direct use of PyYAML's `yaml.dump()` is forbidden because it silently reformats files on every run (quoting dates, flattening nested sequences, folding multi-line strings), producing noisy diffs and unstable history.

#### Canonical style

| Setting | Value | Why |
|---|---|---|
| Library | `ruamel.yaml` (`typ='rt'`, round-trip mode) | Preserves comments, quoting, and key order across load/dump cycles. PyYAML cannot. |
| `indent(mapping=2, sequence=4, offset=2)` | `mapping=2`, `sequence=4`, `offset=2` | Matches the historical repository layout: list hyphens sit at column 2 under their parent key, list-item content at column 4. |
| `preserve_quotes` | `True` | Existing files are normalized for *structure* only; intentionally quoted dates and strings are kept as-is to avoid surprising semantic changes (e.g., `"2026-04-12"` becoming a `datetime.date` object). |
| `width` | `4096` | Practically disables line folding so long `claim`, `summary`, and `justification` strings stay on one line. Folding produces fragile diffs and harms grep-ability. |
| `explicit_end` | `False` | Frontmatter is delimited by a single closing `---` (no `...` document terminator). |

Example of correct style (matches the canonical output):

```yaml
---
content_sources:
  diagrams:
    - id: deployment-method-selection-flow
      type: flowchart
      source: self-generated
      justification: Synthesized deployment decision flow from Microsoft Learn guidance for ZIP deploy, GitHub Actions, deployment slots, and custom containers.
      based_on:
        - https://learn.microsoft.com/en-us/azure/app-service/deploy-zip
        - https://learn.microsoft.com/en-us/azure/app-service/deploy-github-actions
---
```

#### Workflow

1. **Never write frontmatter with PyYAML.** Any new generator or mutation tool MUST import `build_yaml()` (or the higher-level `dump_frontmatter()` helper) from `scripts/lib/yaml_style.py`. `dump_frontmatter()` is the public single-call API used by `scripts/normalize_yaml_frontmatter.py` itself; prefer it over instantiating `build_yaml()` and managing a `StringIO` buffer manually.
2. **Bulk normalize when needed:**

    ```bash
    python3 scripts/normalize_yaml_frontmatter.py --apply
    ```

3. **CI enforces drift:** the `Validate Content Sources` workflow runs `python scripts/normalize_yaml_frontmatter.py --check` and fails if any frontmatter would change. The workflow triggers on changes to `docs/**/*.md`, `scripts/**/*.py`, or the workflow itself, so that updates to the shared library or the normalizer always re-run the check. `ruamel.yaml` is pinned to a specific version in CI so the canonical bytes are reproducible across runs.
4. **Body is preserved byte-exact for the repo invariant (UTF-8, no BOM, LF line endings).** The normalizer only rewrites the YAML region between the two `---` delimiters; the blank line (or its absence) between the closing `---` and the first body line is preserved as-is. Files with a UTF-8 BOM are silently skipped (the regex won't match), and files with CRLF line endings would be converted to LF on `--apply` -- no such files exist in this repo today, but if that ever changes, update this policy first.

#### When to update this section

If [`scripts/lib/yaml_style.py`](scripts/lib/yaml_style.py) changes (different indent, width, or quoting policy), the table above MUST be updated in the same commit. The shared library is the source of truth; this section is the human-readable mirror.

### Admonition Indentation Rule

For MkDocs admonitions (`!!!` / `???`), every line in the body must be indented by **4 spaces**.

```markdown
!!! warning "Important"
    This line is correctly indented.

    - List item also inside
```

### Nested List Indentation

All nested list items MUST use **4-space indent** (Python-Markdown standard).

```markdown
# CORRECT (4-space)
1. **Item**
    - Sub item
    - Another sub item
        - Third level

# WRONG (2 or 3 spaces)
1. **Item**
  - Sub item          ← 2 spaces ❌
   - Sub item         ← 3 spaces ❌
```

### Tail Section Naming

Every document ends with these tail sections (in this order):

| Section | Purpose | Content |
|---|---|---|
| `## See Also` | Internal cross-links within this repository | Links to other pages in this guide |
| `## Sources` | External authoritative references | Links to Microsoft Learn (primary) |

### Canonical Document Templates

Every document follows one of 9 templates based on its section. Do not invent new structures.

Troubleshooting content specifically supports three template variants: **Troubleshooting docs** (symptom → resolution) for symptom-oriented pages under `docs/troubleshooting/` (excluding `playbooks/`, `first-10-minutes/`, `lab-guides/`, `kql/`), **Numbered Playbook** for hypothesis-driven investigation guides under `docs/troubleshooting/playbooks/`, and **First 10 Minutes Runbook** for rapid-triage decision guides under `docs/troubleshooting/first-10-minutes/`. The document quality validator (`scripts/validate_doc_quality.py`) enforces the section-template check only on the **Numbered Playbook** structure for pages under `docs/troubleshooting/playbooks/` (constant `TROUBLESHOOTING_PLAYBOOK_SECTIONS`). The base symptom-oriented template is documented as guidance but is not machine-enforced, because this repository's actual troubleshooting content is authored as hypothesis-driven playbooks plus conceptual/navigation pages (architecture overview, mental model, decision tree, evidence map, quick-diagnosis cards) — no page currently uses the `## Symptom` template, so enforcing it would flag legitimate conceptual pages. Root-level troubleshooting pages, methodology pages, evidence maps, decision trees, quick-diagnosis cards, `first-10-minutes/` runbooks, `kql/` packs, and `lab-guides/` are distinct content types and are not required to use any symptom or playbook section template unless they are authored under `docs/troubleshooting/playbooks/`. The validator also exempts playbooks and first-10-minutes runbooks from the nearby CLI explanation table requirement because those variants embed CLI in investigation contexts (KQL follow-ups, hypothesis validation) rather than as reader-executable setup steps.

#### Platform docs

```text
# Title
Brief introduction (1-2 sentences)
## Main Content
### Subsections
## See Also
## Sources
```

#### Best Practices docs

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

#### Operations docs

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

Files under `docs/operations/deployment/**/*.md` that describe a deployment mechanism use a separate sub-template — see [Deployment Method Reference (Operations variant)](#deployment-method-reference-operations-variant) below.

#### Deployment Method Reference (Operations variant)

```text
# Title
Brief introduction
## Main Content
### <method-specific subsections>
## Advanced Topics
## See Also
## Sources
```

Scope: files under `docs/operations/deployment/**/*.md` that describe a deployment mechanism (ZIP deploy, slot swap mechanics, GitHub Actions workflow, container deploy) rather than a step-by-step operational procedure. Currently applies to:

- `docs/operations/deployment/zip-deploy.md`
- `docs/operations/deployment/slots-and-swap.md`
- `docs/operations/deployment/github-actions.md`
- `docs/operations/deployment/container-deploy.md`

These files intentionally omit the Prerequisites / When to Use / Procedure / Verification / Rollback structure because their content shape is "how the deployment method works," not "step-by-step procedure to run." Operational runbooks that actually walk a reader through a procedure (for example `docs/operations/deployment-slots.md` at the top level of `operations/`) MUST use the full Operations template.

**Validator status (current)**: `scripts/validate_doc_quality.py` does NOT currently have a path-based carve-out for `docs/operations/deployment/**/*.md`. Running the validator with `--all` flags these 4 files with missing-section errors as historical debt. Change-scoped CI (the default) does NOT fail on unchanged files, so this documented exception does not break normal commit flow.

**When editing these files**: preserve the sub-template shape. Do NOT force-fit into the full Operations template. If the validator's `--all` output is used for cleanup work, treat these 4 files as documented exceptions unless a separate scope adds a formal validator carve-out.

**When adding a new file under `docs/operations/deployment/`**: follow this sub-template if the content is method reference. If the content is a step-by-step runbook, place the file at the top level of `docs/operations/` and follow the full Operations template.

#### Tutorial docs (Language Guides)

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

#### Troubleshooting docs

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

Scope: symptom-oriented pages under `docs/troubleshooting/` that are not playbooks, first-10-minutes runbooks, lab guides, or KQL packs.

#### Numbered Playbook (Troubleshooting variant)

```text
# Title
## 1. Summary
## 2. Common Misreadings
## 3. Competing Hypotheses
## 4. What to Check First
## 5. Evidence to Collect
## 6. Validation and Disproof by Hypothesis
## 7. Likely Root Cause Patterns
## 8. Immediate Mitigations
## 9. Prevention
## See Also
## Sources
```

Scope: hypothesis-driven investigation guides under `docs/troubleshooting/playbooks/`. Playbooks explicitly enumerate competing hypotheses and disproof steps, so the symptom → resolution flow of the base Troubleshooting template does not fit. Section numbering may be adjusted to match the specific investigation but the numbered-section pattern must be preserved. Section names may vary in wording (for example "Summary" vs "Overview", "Immediate Mitigations" vs "Short-Term Fixes") as long as the investigation-hypothesis-evidence-mitigation flow is preserved.

CLI blocks inside playbooks do NOT require a nearby command explanation table because the CLI appears inside investigation steps (KQL follow-ups, hypothesis validation, evidence collection), not as reader-executable setup. Long-flag enforcement (no `-g`, `-n`, `-o`, `-l` shortcuts) still applies.

#### First 10 Minutes Runbook (Troubleshooting variant)

```text
# Title
## Quick Context
## Step 1: <first triage action>
## Step 2: <second triage action>
## Step N: <additional triage steps>
## Decision Points
## Next Steps
## See Also
## Sources
```

Scope: rapid-triage decision guides under `docs/troubleshooting/first-10-minutes/`. Runbooks give an on-call engineer a numbered sequence of actions to take in the first ten minutes of an incident, followed by a decision point that routes to a playbook or lab. The symptom → resolution flow of the base Troubleshooting template does not fit because runbooks are pre-diagnosis triage, not post-diagnosis remediation.

CLI blocks inside first-10-minutes runbooks do NOT require a nearby command explanation table for the same reason as playbooks (CLI appears as triage evidence collection, not reader-executable setup). Long-flag enforcement still applies.

#### Lab Guides

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

#### Reference docs

```text
# Title
Brief introduction
## Topic/Command Groups
## Usage Notes
## See Also
## Sources
```

## Content Source Requirements

### MSLearn-First Policy

All content MUST be traceable to official Microsoft Learn documentation:

- **Platform content** (`docs/platform/`): MUST have direct MSLearn source URLs
- **Architecture diagrams**: MUST reference official Microsoft documentation
- **Troubleshooting playbooks**: MAY synthesize MSLearn content with clear attribution
- **Self-generated content**: MUST have justification explaining the source basis

### Source Types

| Type | Description | Allowed? |
|---|---|---|
| `mslearn` | Directly from Microsoft Learn | Required for platform content |
| `mslearn-adapted` | MSLearn content adapted for this guide | Allowed with source URL |
| `self-generated` | Original content for this guide | Requires justification |
| `community` | From community sources | Not allowed for core content |
| `unknown` | Source not documented | Must be validated |

### Diagram Source Documentation

Every Mermaid diagram MUST have source metadata in frontmatter:

```yaml
content_sources:
  diagrams:
    - id: architecture-overview
      type: flowchart
      source: mslearn
      mslearn_url: https://learn.microsoft.com/en-us/azure/app-service/...
    - id: troubleshooting-flow
      type: flowchart
      source: self-generated
      justification: "Synthesized from MSLearn articles X, Y, Z"
      based_on:
        - https://learn.microsoft.com/en-us/...
```

### Content Validation Tracking

- See [Content Validation Status](docs/reference/content-validation-status.md) for current status.
- See [Tutorial Validation Status](docs/reference/validation-status.md) for tutorial testing.

### Text Content Validation

Factual-claim documents include a `content_validation` block in frontmatter to track the verification status of their core technical assertions.

The single source of truth for "is this page in scope?" is [`scripts/lib/content_scope.py`](scripts/lib/content_scope.py) — specifically the `is_in_scope(rel_path)` function. Both `scripts/generate_content_validation_status.py` and `tools/validate_frontmatter.py` import this helper, so the dashboard and the validator are guaranteed to agree on scope. If you change the scope policy, update both `scripts/lib/content_scope.py` AND this section in the same commit.

#### Scope

The `content_validation` block is **required** on factual-claim pages under these sections:

| Section | Required? | Examples |
|---|---|---|
| `docs/platform/` | Required (including factual subsection landing pages such as `platform/architecture/index.md` and `platform/containers/index.md`) | Hosting models, request lifecycle, scaling architecture |
| `docs/best-practices/` | Required | Security, deployment, reliability patterns |
| `docs/operations/` | Required | Deployment slots, health recovery, backup procedures |
| `docs/troubleshooting/` | Required, except for the `EXCLUDED_SUBPATHS` and `NAVIGATION_INDEXES` listed below | Playbooks, methodology pages, first-10-minutes runbooks, decision tree, evidence map |

The block is **forbidden** on these pages:

- **Out-of-scope sections** — any path that does not start with `platform/`, `best-practices/`, `operations/`, or `troubleshooting/`. This covers `docs/start-here/`, `docs/visualization/`, `docs/meta/`, `docs/about.md`, `docs/index.md`, `docs/contributing/`, `docs/reference/`, and `docs/language-guides/` (tutorials, recipes, playbooks).
- **`EXCLUDED_SUBPATHS`** under `troubleshooting/`:
    - `troubleshooting/kql/` — KQL query packs make no factual assertions of their own
    - `troubleshooting/lab-guides/` — labs use the evidence-integrity model (Falsification step) instead
- **`NAVIGATION_INDEXES`** — section landing pages that only introduce a section and make no factual claims:
    - `platform/index.md`
    - `best-practices/index.md`
    - `operations/index.md`
    - `operations/deployment/index.md`
    - `troubleshooting/index.md`
    - `troubleshooting/first-10-minutes/index.md`
    - `troubleshooting/playbooks/index.md`

Subsection landing pages that DO make factual claims (currently `platform/architecture/index.md` and `platform/containers/index.md`) are intentionally NOT in `NAVIGATION_INDEXES` — they are treated like any other factual-claim page.

#### Schema

```yaml
---
content_sources:
  - type: mslearn-adapted
    url: https://learn.microsoft.com/en-us/azure/app-service/...
content_validation:
  status: verified  # verified | pending_review | unverified
  last_reviewed: 2026-04-12
  reviewer: agent  # agent | human
  core_claims:
    - claim: "App Service supports VNet integration for outbound traffic"
      source: https://learn.microsoft.com/en-us/azure/app-service/overview-vnet-integration
      verified: true
    - claim: "Deployment slots allow zero-downtime deployments"
      source: https://learn.microsoft.com/en-us/azure/app-service/deploy-staging-slots
      verified: true
---
```

#### Validation Status Values

| Status | Description |
|--------|-------------|
| `verified` | All core claims have been traced to Microsoft Learn sources |
| `pending_review` | Document exists but claims need source verification |
| `unverified` | New document, no validation performed |

#### Agent Rules for Content Validation

1. Add `content_validation` only when the page is in scope per `scripts/lib/content_scope.is_in_scope`. Do NOT add it to out-of-scope pages — the validator (`tools/validate_frontmatter.py`) will fail with a "forbidden-but-present" error.
2. If you create a new in-scope page, you MUST add `content_validation` — the validator will fail with a "required-but-missing" error otherwise.
3. Each `core_claim` MUST be a verifiable factual assertion about Azure behavior (a quoted limit, a documented feature behavior, a configuration default). Meta-statements such as "this page uses Microsoft Learn as the primary source basis" are tautological and forbidden — the marker text `primary source basis` (case-insensitive) is rejected by both `tools/validate_frontmatter.py` and `scripts/generate_content_validation_status.py`. To clean up existing tautological blocks, run `python3 scripts/remove_tautological_validation.py --apply`.
4. List 2-5 core claims per page; each MUST cite a Microsoft Learn URL.
5. Set `status: verified` only when ALL core claims have verified sources.
6. Run `python3 scripts/generate_content_validation_status.py` after updates to regenerate `docs/reference/content-validation-status.md`.

## Quality Gates & Verification

1. **PII Check**: Manually verify no subscription IDs, tenant IDs, or private IP addresses are in the documentation.
2. **Link Validation**: Use `mkdocs build --strict` to ensure no broken internal or external links.
3. **Evidence Integrity**: Ensure every troubleshooting lab has a "Falsification" step that proves the hypothesis.
4. **Content Source Validation**: All diagrams and platform content must have documented MSLearn sources.

## Mandatory Oracle Review (AI Agent Rule)

**ALL work performed by AI agents MUST undergo Oracle quality review before completion.**

### Review Protocol

1. **Work Completion**: Agent completes assigned task
2. **Build Verification**: Run `mkdocs build --strict` (must pass)
3. **Oracle Review Request**: Submit all changes to Oracle for quality review
4. **Quality Criteria**:
   - MSLearn-first policy compliance
   - Code explanation tables present for all CLI commands
   - Mermaid diagrams with proper `<!-- diagram-id: -->` comments
   - Long CLI flags only (no `-g`, `-n` shortcuts)
   - No PII in examples
   - Proper frontmatter with `content_sources`
5. **Iteration**: If Oracle identifies issues → fix and re-submit
6. **Completion**: Only mark done when Oracle approves (100% quality)

### Review Loop

```
while not oracle_approved:
    fix_identified_issues()
    run_build_verification()
    submit_to_oracle()
```

**NO WORK IS CONSIDERED COMPLETE WITHOUT ORACLE APPROVAL.**

## Merge Policy (AI Agent Rule)

AI agents MAY merge their own pull requests **autonomously**, but ONLY after ALL of the mandatory gates below pass. There is no separate human approval step — passing every gate IS the approval. If any gate cannot be satisfied, the agent MUST stop and hand the PR to the user instead of merging.

### Mandatory merge gates (ALL required)

| # | Gate | How it is verified |
|---|---|---|
| 1 | **Oracle review ≥ 90/100** | Submit the final diff to Oracle per the Mandatory Oracle Review protocol. Score must be **90 or higher with no merge-blocking issues**. Any must-fix item is a blocker even at ≥ 90. |
| 2 | **CI fully green** | Every required GitHub Actions check on the PR head SHA passes. Verify with `gh pr checks <pr> --watch`; do not merge on `pending` or `failure`. |
| 3 | **Caption ↔ image match** | For every added/changed image referenced from markdown, the caption/alt text MUST accurately describe the actual rendered image (as with the 02 storage-networking alt correction). |
| 4 | **Final-image PII verification** | Every added/changed `.png`/`.webp` referenced from markdown MUST be visually verified (Read/`look_at`) for PII on the **final committed bytes** — zeroed subscription/tenant IDs, no employee identifiers, no black-box masks. WebP re-encodes are re-verified, not assumed from the raw PNG. |

### Merge procedure

1. Confirm gates 1-4 above, in order. Record the Oracle score and the visual-verification result in the PR thread or the final summary.
2. Merge with **squash-and-merge** only:

    ```bash
    gh pr merge <pr> --squash --delete-branch
    ```

3. Never use merge-commit or rebase-merge; squash keeps `main` history linear and collapses fixup commits.
4. Never bypass a failing or pending gate. Never merge with `--admin` to skip checks.

### When to stop instead of merging

- Oracle score < 90, or any unresolved must-fix.
- Any CI check failing or still pending.
- Any referenced image that cannot be visually verified (see the text-only review disclosure rules under Image and Screenshot Rules).
- The PR touches something outside the agent's stated scope.

In these cases, report the blocking gate and hand off to the user.


## Tutorial Validation Tracking

Every tutorial document supports **validation frontmatter** that records when and how it was last tested against a real Azure deployment.

### Frontmatter Schema

Add a `validation` block inside the YAML frontmatter (`---` fences) of any tutorial file:

```yaml
---
hide:
  - toc
validation:
  az_cli:
    last_tested: 2026-04-09
    cli_version: "2.83.0"
    result: pass
  bicep:
    last_tested: null
    result: not_tested
---
```

### Agent Rules for Validation

1. **After deploying a tutorial end-to-end**, add or update the `validation` frontmatter with the current date, CLI version, and `result: pass`.
2. **If a tutorial step fails during validation**, set `result: fail` and note the issue.
3. **Never fabricate validation dates.** Only stamp a tutorial after actually executing all steps.
4. **After updating frontmatter**, regenerate the dashboard:
    ```bash
    python3 scripts/generate_validation_status.py
    ```
5. **Include the regenerated dashboard** (`docs/reference/validation-status.md`) in the same commit as the frontmatter change.
6. **Do not manually edit** `docs/reference/validation-status.md` — it is auto-generated.

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
