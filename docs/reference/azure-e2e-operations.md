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

### First Protected Run: BLOCKED / NOT_RUN

Read-only GitHub observations on **2026-11-04, 13:26:04–13:26:08 UTC**:
preparation is **BLOCKED**, protected Scenario A execution is **NOT_RUN**, and
the hypothesis is **NOT_TESTED**. This is a prerequisite snapshot, not an Azure
capture or permission to dispatch.

| Read-only command | Exact output | Meaning and unblocker |
|---|---|---|
| `gh api repos/yeongseon/azure-app-service-practical-guide/environments --jq '{total_count, names: [.environments[].name]}'` | `{"names":["copilot","github-pages"],"total_count":2}` | Observed: no `azure-e2e` environment in the list. A GitHub administrator must create it and verify the protections above before adding secrets. |
| `gh api repos/yeongseon/azure-app-service-practical-guide/actions/secrets --jq .total_count` | `0` | Observed: no repository Actions secrets. This does not inventory organization or environment secrets. A GitHub administrator must configure the three required environment secrets after protection is established. |
| `gh run list --repo yeongseon/azure-app-service-practical-guide --workflow e2e-azure.yml --limit 5 --json databaseId,status,conclusion,headSha` | `[]` | Observed: no returned workflow runs. An explicitly authorized operator, not this checklist's author, must perform the first run after all prerequisites pass. |
| `gh api 'repos/yeongseon/azure-app-service-practical-guide/actions/workflows/e2e-azure.yml/runs?per_page=5' --jq .total_count` | `0` | Observed: the workflow run total is zero at this read. |

These commands only read metadata; `--jq` selects output fields, `--repo`
selects the repository, `--workflow` selects the workflow, `--limit` bounds the
listing, and `--json` names the returned fields. The remote settings, secret
inventory and run history can change after this snapshot; repeat the reads
before authorization. Azure federation, RBAC, permitted scope, quota and spend
approval are **Unknown** (no Azure API was queried); the Azure owner must
establish them. Operator approval and private raw-evidence retention are also
**Unknown** and require the signed-off records below.

No acceptance item in #393 that requires a real run is satisfied by this
documentation. `validation.az_cli.last_tested`, `validation.bicep.last_tested`
and every capture date are untouched; this snapshot refreshes none of them.

Source inspection used `git show origin/main:.github/workflows/e2e-azure.yml`
at `3e6d950dbec05c5e692e3869ce8d19302d183fea`. Its only `on:` trigger is
`workflow_dispatch`; workflow permissions are `contents: read`. The
`scenario-a`, `cleanup` and `ttl-sweep` jobs each declare `environment: azure-e2e`
and `id-token: write`; the sweep also requests `actions: read`.
These are observed source declarations, not proof of deployed protection,
human review or Azure access. Ancestry validation is not review approval.

### First-Run Operator Checklist

Complete these additional records before step 7 above. Unavailable
prerequisites leave preparation **BLOCKED** and execution **NOT_RUN**. This
unchecked checklist is neither authorization nor a run/result record; keep
account identifiers and raw private evidence out of the public record.

- [ ] **Approval and spend:** retain an approval record naming the exact reviewed
    target SHA and workflow revision, approver, operator and separate inspector;
    permitted resource scope, region/SKU/runtime, quota, maximum spend and elapsed
    time, TTL, and cancellation/escalation owner. Evidence: private Azure-owner
    authorization plus a PII-safe review reference and fresh GitHub protection
    readback. Arrange protected approvals for scenario, cleanup and TTL jobs, not
    just the scenario. Stop if scope, spend or review approval is absent.
- [ ] **Declaration and worker activation:** resolve the declaration/template
    choice tracked in #184 with the maintainer, freeze its source SHA/digest,
    assertions, sampling windows, log-arrival deadline and contrary observations
    before dispatch. Evidence: the pre-run declaration and a collection plan for
    a worker-side start/identity signal bound to this run, resource and fault
    window. Configuration acceptance/readback is only control evidence; healthy
    probes plus elapsed time do not prove activation. If that signal cannot be
    collected, record activation **Unknown**, not causal contradiction. The
    current runner's heuristic is not worker-side proof.
- [ ] **Private originals:** agree a reviewed, access-controlled, PII-safe export
    method before authorization and prove it preserves phase JSON, exact console
    rows and raw command/deletion outputs before workspace expiry, including
    failures. Evidence: retention owner, destination/access and expiry policy,
    export/readback verification and a byte/hash inventory. The current public
    artifact cannot reconstruct dropped raw bytes from hashes. If no approved
    preservation method exists, keep the first-run preparation **BLOCKED**; do
    not assume the existing workflow exports private originals.
- [ ] **Identity and conversion:** prepare an inspection record linking GitHub
    run ID/attempt to the runner's different evidence run ID, actual capture
    source, recipe digest, resource/worker bindings and baseline/deployment/
    configuration/probe/console windows. Evidence: privately preserved manifest,
    phase files and raw hashes. For later Golden conversion, record collector
    source/digest and actual derivation/evaluation time separately. The workflow
    invokes the lab runner and guard, not the Golden collector/evaluator.
- [ ] **Typed outcomes:** predeclare how the inspector will reconcile execution,
    evidence validity, hypothesis, recovery, cleanup and independent reproduction
    separately. Evidence: runner `run.json`, evaluation JSON, guard output,
    failure record/job logs and separate cleanup artifact, using the distinctions
    below. Missing evidence is not a successful reproduction; a failed Actions
    gate does not by itself prove a process crash.
- [ ] **Cancellation and inspection:** name the operator who stops the run on
    spend/time limits and the Azure owner who handles interrupted or failed
    cleanup. Evidence: cancellation time/reason, job states, retained failure
    output, exact run-owned name/tag readback, deletion output and subsequent
    absence readback. Do not assume cancellation runs cleanup or that TTL itself
    deletes anything; inspect cleanup and any approved sweep independently and
    escalate missing proof. Never select resources by a name fragment. The
    separate inspector records recovered responses and verified deletion as
    different findings before any metadata or paid-schedule decision; inspection
    alone is not independent human reproduction.

## Execution Outcomes

Missing Azure configuration or a missing runner is a blocked prerequisite. A missing `run.json`, incomplete runner status, or absent baseline, fault, recovery, or console evidence exits nonzero as `BLOCKED` or `FAILED`. Only a complete runner package can exit zero.

The run summary records the target commit, GitHub run identity, protected environment, runner execution status, capture time, and evaluation time. These times remain separate because an offline replay is not a new capture.

At the source revision above, the runner maps hypothesis exits to 0
(`SUPPORTED`), 1 (`CONTRADICTED`), 2 (`INCONCLUSIVE`) and 3 (`NOT_TESTED`), with
4 for invalid evidence. The guard accepts only `COMPLETE` execution with `PASS`
evidence and a `SUPPORTED` hypothesis. The workflow normalizes nonzero runner
or guard outcomes to exit 4 and labels any nonzero runner exit `runner-crash`.
That label alone does not distinguish an honest completed `INCONCLUSIVE` or
`CONTRADICTED` result from a crash: preserve the original evaluation and actual
execution status, and report any disagreement rather than rewriting the result.
For unfinished execution, the Golden hypothesis remains `NOT_TESTED`; preserve
the lab runner's original fields separately if they disagree. Recovery and
cleanup require their own evidence regardless of the hypothesis or job result.

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
