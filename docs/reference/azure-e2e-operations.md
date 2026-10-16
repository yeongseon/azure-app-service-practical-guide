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
2. Add required reviewers and prevent administrators from bypassing the protection rule, according to repository policy.
3. Create a Microsoft Entra application or user-assigned managed identity for the workflow.
4. Add a federated credential whose subject is `repo:yeongseon/azure-app-service-practical-guide:environment:azure-e2e`.
5. Grant the identity only the Azure permissions needed to create and delete disposable Scenario A resource groups in the selected test scope.
6. Add `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` as environment secrets.
7. Review the target commit, then dispatch **Azure Golden E2E** with its full SHA, a new resource-group name, region, and TTL.

No credential, environment, federated identity, role assignment, or paid schedule is created by this repository change. The first real workflow run, recovery evidence, and cleanup result require independent inspection before any verified metadata changes.

## Execution Outcomes

Missing Azure configuration or a missing runner is a blocked prerequisite. A missing `run.json`, incomplete runner status, or absent baseline, fault, recovery, or console evidence exits nonzero as `BLOCKED` or `FAILED`. Only a complete runner package can exit zero.

The run summary records the target commit, GitHub run identity, protected environment, runner execution status, capture time, and evaluation time. These times remain separate because an offline replay is not a new capture.

## Evidence Retention

The workflow sanitizes the private run directory before upload and retains the GitHub Actions artifact for 30 days, including failed runs. The artifact is temporary diagnostic evidence, not persistent publication.

To publish evidence permanently, a separate reviewed pull request must transform the private capture into the Golden evidence schema, run the evaluator and PII gates, add append-only retained digests and run declarations, and document the exact capture provenance. Expiry of the workflow artifact does not rewrite or invalidate an already retained package.

## Cleanup and TTL Sweep

Each resource group is tagged with `owner=golden-e2e`, `repository=yeongseon/azure-app-service-practical-guide`, the exact GitHub `run-id`, and an absolute UTC `ttl`. Normal cleanup reads the group and refuses deletion unless the owner, repository, and run ID match. It waits for deletion and fails unless absence is verified.

The separate TTL sweep lists only groups tagged `owner=golden-e2e` and deletes only groups that also carry this repository identity, a valid GitHub run identity, and an already expired parseable TTL. Untagged groups, differently owned groups, groups from another repository, missing run or TTL values, malformed values, and current groups are ignored. It does not use subscription-wide name matching.

## Freshness Reporting

`.github/workflows/validation-freshness.yml` is the only scheduled workflow added by this feature. It is read-only and calculates daily freshness from existing tutorial `last_tested` values. More than 90 days is stale; future or malformed dates are invalid. It writes only to the workflow summary and never edits documentation or evidence.

## See Also

- [Golden Evidence Model](golden-evidence-model.md)
- [Tutorial Validation Status](validation-status.md)
- [Deployment Succeeded but Startup Failed Lab](../troubleshooting/lab-guides/deployment-succeeded-startup-failed.md)

## Sources

- [Use OpenID Connect to access Azure from GitHub Actions](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
- [Assign Azure roles](https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments-portal-managed-identity)
