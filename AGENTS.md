# AGENTS.md

## Project Overview
**Project Name:** Azure App Service Practical Guide
**Description:** A comprehensive, hands-on guide for running web applications on Azure App Service, covering everything from initial deployment to advanced production troubleshooting.
**Core Mission:** Provide reproducible, evidence-based troubleshooting labs and playbooks that bridge the gap between "it's broken" and "it's fixed" using a structured methodology.

## Repository Structure
- `apps/`: Minimal reference applications demonstrating App Service patterns.
    - `python-flask/`: Flask + Gunicorn implementation.
    - `nodejs/`: Express.js implementation.
    - `java-springboot/`: Spring Boot implementation.
    - `dotnet-aspnetcore/`: ASP.NET Core implementation.
- `docs/`: Markdown documentation source for the MkDocs site.
    - `troubleshooting/`: Primary area for methodology, playbooks, and KQL query packs.
        - `playbooks/`: Detailed guides for specific failure scenarios.
        - `lab-guides/`: Step-by-step instructions for reproducing and solving issues.
        - `kql/`: Repository of Kusto Query Language (KQL) snippets for diagnostics.
    - `platform/`, `best-practices/`, `language-guides/`, `operations/`: General guide content.
- `infra/`: Bicep/Terraform templates for infrastructure provisioning.
- `labs/`: Infrastructure and scripts used to reproduce troubleshooting scenarios in the labs.
- `mkdocs.yml`: Configuration for the documentation site, including navigation and plugins.

## Content Types & Methodology

### 1. Troubleshooting Experiments (Labs)
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

### 2. Evidence Levels
When documenting troubleshooting steps or analysis, use these tags to specify the strength of the evidence:
- `[Observed]`: Directly seen in logs, metrics, or UI (e.g., 503 errors in Log Analytics).
- `[Measured]`: Quantified data (e.g., 99th percentile latency is 4.5s).
- `[Correlated]`: Two events happening together without proven causation.
- `[Inferred]`: Conclusion based on logic and multiple pieces of evidence.
- `[Strongly Suggested]`: High confidence inference but missing the "smoking gun".
- `[Not Proven]`: Hypothesis that has not yet been validated.
- `[Unknown]`: Missing data or ambiguous behavior.

## Technical Standards & Conventions

### 1. Language Usage
- **Shell**: Use `bash` for all CLI examples.
- **Python**: Use `python` for all script examples.
- **KQL**: Use `kusto` for all Kusto Query Language blocks.
- **Mermaid**: Use `mermaid` for all architecture and flow diagrams.

### 2. CLI Standards
- Always use long flags for Azure CLI commands (e.g., `--resource-group` instead of `-g`).
- Ensure no Personally Identifiable Information (PII) is included in CLI output examples.

### 3. Documentation Style
- All content must reference official Microsoft Learn documentation with source URLs where applicable.
- Use `admonitions` (note, warning, tip) for highlighting critical information.
- Ensure all documents include a Mermaid diagram to visualize the concept or flow.

## Quality Gates & Verification
1. **PII Check**: Manually verify no subscription IDs, tenant IDs, or private IP addresses are in the documentation.
2. **Link Validation**: Use `mkdocs build --strict` to ensure no broken internal or external links.
3. **Evidence Integrity**: Ensure every troubleshooting lab has a "Falsification" step that proves the hypothesis.

## Build & Contribution
- **Build Command**: `pip install mkdocs-material mkdocs-minify-plugin && mkdocs build`
- **Development Server**: `mkdocs serve`
- **Git Commit Types**:
    - `feat`: New lab, playbook, or guide section.
    - `fix`: Correction of technical inaccuracies or broken links.
    - `docs`: General documentation improvements (typos, clarity).
    - `chore`: Updates to build scripts, dependencies, or metadata.
    - `refactor`: Restructuring existing content without changing the technical meaning.
