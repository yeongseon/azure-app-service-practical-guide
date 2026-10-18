---
content_sources:
  references:
    - type: mslearn
      url: https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect
    - type: mslearn
      url: https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments-portal-managed-identity
---

# Guarded Azure E2E Operations

This page describes the one-time repository and Azure setup for the manual Golden Scenario A workflow. The repository does not provision these trust settings and does not schedule paid Azure execution.

## Trust Boundary

`.github/workflows/e2e-azure.yml` accepts only a reviewed 40-character commit SHA that exists on this repository's `main` history. The privileged job checks out that exact SHA, uses the protected `azure-e2e` environment, and requests `id-token: write` only in jobs that authenticate to Azure. Pull requests, including forks, cannot trigger the workflow.

An offline unit test or evidence replay is labeled **Offline replay**. It never creates an **Azure Verified** claim and never advances `captured_at` or tutorial `last_tested` metadata.

## One-Time Manual Setup

1. Create a GitHub environment named `azure-e2e`.
2. Add required reviewers, prevent administrators from bypassing the protection rule, and set the environment deployment-branch restriction to **Selected branches and tags** with only `main` allowed. This main-only environment rule is required defense in depth; the workflow also validates `github.ref` and `github.workflow_ref` before any job can request an OIDC token.
3. Create a Microsoft Entra application or user-assigned managed identity for the workflow.
4. Add a federated credential whose subject is `repo:yeongseon/azure-app-service-practical-guide:environment:azure-e2e`.
5. Grant the identity only the Azure permissions needed to create and delete disposable Scenario A resource groups in the selected test scope.
6. Add `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` as environment secrets.
7. Review the target commit, then dispatch **Azure Golden E2E** from `main` with its full SHA, region, and an integer TTL from 3 through 72 hours. The workflow derives the resource-group name from the GitHub run ID and attempt; callers cannot choose or reuse a name.

No credential, environment, federated identity, role assignment, or paid schedule is created by this repository change. The first real workflow run, recovery evidence, and cleanup result require independent inspection before any verified metadata changes.

## Execution Outcomes

Missing Azure configuration or a missing runner is a blocked prerequisite. A missing `run.json`, incomplete runner status, or absent baseline, fault, recovery, or console evidence exits nonzero as `BLOCKED` or `FAILED`. Only a complete runner package can exit zero.

The run summary records the target commit, GitHub run identity, protected environment, runner execution status, capture time, and evaluation time. These times remain separate because an offline replay is not a new capture.

## Evidence Retention

The workflow converts the private run directory into a closed, allowlisted artifact before upload and retains that GitHub Actions artifact for 30 days. Failed stages retain a typed `failure-record.json`, including target validation and missing OIDC configuration before the runner starts, runner startup and crash failures, failed evaluation, and sanitizer failure. It does not redact arbitrary private files in place.

Structured output is limited to `run.json`, `evaluation.json`, `cleanup-result.json`, `failure-record.json`, and `raw-log-NNNN.json` metadata records. Each file has its own per-key type and value schema: run and GitHub IDs use bounded decimal or run-ID patterns; source commits use lowercase 40-character hexadecimal; statuses, failure stages, scenarios, and raw-log roles use fixed enums; counts, byte lengths, and exit codes use bounded integers; `exists` is Boolean; timestamps must match an explicit ASCII, timezone-aware ISO datetime grammar within the accepted year range; resource-group names must match the workflow-owned naming pattern; and raw-log digests use lowercase 64-character SHA-256 hexadecimal. Duplicate JSON keys, non-finite numbers, and noncanonical JSON bytes are rejected. A resource ID is rewritten to the fixed documentation placeholder. Unknown keys and invalid values are dropped from private input, while every validator-accepted artifact tree is a byte-for-byte sanitizer fixed point.

No free-text log content is uploaded. For each raw `.log` file, the sanitizer retains only a `raw-log-NNNN.json` record containing an enum role, exact byte length, line count, and SHA-256 digest of the raw bytes. A failure record contains only `BLOCKED` or `FAILED`, the closed failure-stage enum, GitHub run ID and attempt, an evidence run ID when known, exit code, and start and end timestamps. The raw file remains only in the ephemeral runner workspace. The retained failure record identifies where execution stopped; deeper diagnosis may still require rerunning the workflow or inspecting the GitHub Actions job log, where GitHub masks registered secrets.

A separate structural validator accepts only those JSON filenames and shapes; `.txt`, `.log`, and every other artifact form are rejected. It independently parses JSON with duplicate-key and non-finite-number rejection and reimplements the per-file and per-key type, range, pattern, enum, timestamp, and digest constraints. It does not import or reuse the sanitizer's field recognizers. If validation fails, the existing upload gate prevents artifact upload. The artifact is temporary diagnostic evidence, not persistent publication.

To publish evidence permanently, a separate reviewed pull request must transform the private capture into the Golden evidence schema, run the evaluator and PII gates, add append-only retained digests and run declarations, and document the exact capture provenance. Expiry of the workflow artifact does not rewrite or invalidate an already retained package.

## Cleanup and TTL Sweep

Each resource group uses the exact name `rg-golden-e2e-<run-id>-<attempt>` and is tagged with `owner=golden-e2e`, `repository=yeongseon/azure-app-service-practical-guide`, the same GitHub run identity, and an absolute UTC `ttl`. Normal cleanup reads the group and refuses deletion unless both the name and all ownership tags bind to the same run. It waits for deletion and fails unless absence is verified. The verified cleanup outcome is sanitized, written to the workflow summary, and retained as a separate artifact associated with that GitHub run ID and attempt.

The separate TTL sweep lists only groups tagged `owner=golden-e2e` and deletes only groups whose exact workflow-derived name, repository tag, run tag, and expired parseable TTL agree. The current workflow run identity is explicitly excluded so a sweep cannot delete its concurrently running scenario. Untagged groups, spoofed tags on foreign names, prefix collisions, groups from another repository, missing run or TTL values, malformed values, future TTLs, and current groups are ignored.

## Freshness Reporting

`.github/workflows/validation-freshness.yml` is the only scheduled workflow added by this feature. It is read-only and calculates daily freshness from existing tutorial `last_tested` values. More than 90 days is stale; future or malformed dates are invalid. It writes only to the workflow summary and never edits documentation or evidence.

## See Also

- [Golden Evidence Model](golden-evidence-model.md)
- [Tutorial Validation Status](validation-status.md)
- [Deployment Succeeded but Startup Failed Lab](../troubleshooting/lab-guides/deployment-succeeded-startup-failed.md)

## Sources

- [Use OpenID Connect to access Azure from GitHub Actions](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
- [Assign Azure roles](https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments-portal-managed-identity)
