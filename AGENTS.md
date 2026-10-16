# AGENTS.md

## Mission

Maintain an evidence-driven Azure App Service guide. Publish practical conclusions
with actual verification dates, environment, source commit and evidence. Official
sources, local tests, Azure execution, causal support, recovery, cleanup and
independent reproduction are separate claims.

## Read First

- [CONTRIBUTING.md](CONTRIBUTING.md): canonical title, template and priority-label rules.
- [DOCUMENTATION_CONTRACT.md](DOCUMENTATION_CONTRACT.md): the complete previous
  authoring contract, retained byte-for-byte, including templates, screenshots,
  PII, navigation, validators and mandatory merge gates.
- README.md and the affected playbook, runbook and implementation.
- [Golden Evidence Model](docs/reference/golden-evidence-model.md): normative
  vocabulary, run identity, evidence roles, trust levels, and evaluator contract.

The detailed contract is not deleted or weakened. Its older title examples and
falsification wording are superseded by the explicit rules below.

Titles and templates must point to the [Title Convention](CONTRIBUTING.md#title-convention),
the one source of truth for the 11 types, optional scope and breaking marker.

## Project Operations

Work issue-first. Search the existing backlog; use the canonical issue/PR
sections and exactly one priority:critical/high/medium/low label. New reports
receive needs-triage; maintainers confirm validity, scope, type and priority.
Preserve unrelated labels. Use local umbrella issues, not milestones, WIP
labels or trackers that require sibling repository work to finish.

Use Closes #N for fully completed scope, or Refs #N with an explicit remainder
for partial work. Do not auto-close unfinished umbrellas. Preserve concurrent
edits, original acceptance states and evidence. Formatting is not new
verification and must not reopen or close work, merge PRs or rewrite commits.

## Evidence and Dates

- Preserve validation.az_cli.last_tested and validation.bicep.last_tested.
  Only actual execution updates them. A real failed rerun records fail.
- captured_at is actual collection; evaluated_at is analysis;
  document_updated_at is a text change. Replay never refreshes a capture date.
- Keep source commit, environment, recipe digest and evidence identity with runs.
- Execution, evidence validity, hypothesis, recovery, cleanup, freshness and
  independence are separate axes. Missing required evidence cannot pass.
- Falsification means predeclared observations capable of contradicting a
  hypothesis. Recovery after a change does not uniquely prove its cause.
- Missing logs do not prove the app never started. A healthy platform detector
  alone cannot exclude platform contributions. HTTP 499 does not prove SNAT.
- A completed experiment may be INCONCLUSIVE. Stale means recheck freshness,
  not that the historical result is false. Do not force positive lab outcomes.
- State hosting/runtime/SKU limits. A controlled restart is not a reproduction
  of a specific ASE maintenance mechanism.
- Never publish secrets, customer identifiers or unapproved internal telemetry.
  Synthetic observations must not be relabeled as real customer or Azure runs.
- Raw evidence outranks generated summaries. Collectors record observations;
  evaluators derive declared assertions and never invent root cause.
- Declare hypotheses, assertions, sampling, and disproof criteria before a run.
  Run directories and captured evidence are immutable; replay creates only a
  new evaluation record.
- Hypothesis outcomes are `SUPPORTED`, `CONTRADICTED`, `INCONCLUSIVE`, or
  `NOT_TESTED`. Execution is separately `COMPLETE`, `PARTIAL`, `BLOCKED`,
  `FAILED`, or `NOT_RUN`.
- Independent reproduction requires a genuinely different human operator and
  independently collected raw evidence. Automation or another AI-agent replay
  demonstrates repeatability only and leaves independence `NOT_MET`.

## Validation and Privilege Boundaries

Run python -m unittest discover -s tests/ci -v and applicable application,
lab, documentation and Golden gates. Read-only PR checks receive no cloud
secrets. Paid Azure runs require a reviewed main commit and an explicitly
enabled protected azure-e2e environment. Missing prerequisites remain blocked,
not skipped-as-verified. This adoption does not provision credentials or enable
paid recurring runs.

`tools/validate_frontmatter.py` rejects invalid document types, duplicate slugs,
and required-or-forbidden `content_validation` placement; keep it wired into PR
CI whenever its contract is cited.

The priority-label definition is versioned in `.github/priority-labels.json`.
Its synchronization utility has an explicit read-only `--check` mode and never
deletes unrelated labels; do not apply it to the live repository for this work.

Retain sanitized evidence on failure. Cleanup only run-owned resources and
verify absence; never delete subscription-wide resources by a name fragment.

## Merge and Review

All existing mandatory merge gates in DOCUMENTATION_CONTRACT.md remain in
force, including Oracle review and applicable final-image checks. Verify
required checks on the exact head SHA. Do not bypass missing, pending or failing
checks, claim an Oracle review that did not occur, or change protection settings.
AI review comments are not human approvals. Package-release automation and the
reference repository's approval-count decisions are not imported.

### GitHub review before merge

This is an agent operating rule, not proof that GitHub settings enforce it.
The maintainer requested this additional review loop on 2026-10-16 (#247).

1. After opening a PR, inspect GitHub review requests, submissions and threads.
   Confirm a review for the current head rather than assuming automatic review
   ran. If no current request or run exists, request the configured reviewer.
   For the connected Codex integration, use a top-level `@codex review` comment
   with the target head SHA and scope. Do not duplicate an active request.
2. Record reviewer identity, review URL/ID, reviewed head SHA and outcome in the
   PR's Validation section. Use REQUESTED while awaiting a result, COMPLETE for
   a completed review, FINDINGS_OPEN for unresolved findings, and BLOCKED when
   the service or required evidence is unavailable. COMPLETE is not merge approval.
   No response, an acknowledgement reaction, quota failure or an empty comment
   list is not review success. Do not submit an approval as the PR author to
   stand in for a review from another reviewer.
3. Address findings with fixes and relevant tests, or an evidence-backed
   disposition agreed with the reviewer/maintainer. Resolve threads only after
   addressing them; clicking Resolve alone does not fix a finding. Any active
   changes-requested review or unresolved must-fix blocks merge.
4. A new head SHA requires a fresh review. Preserve earlier results as history,
   not approval of changed code. Reassess base-branch changes and conflicts too.
5. Before merging, re-read the head and verify complete declared scope, a
   non-draft PR, current review evidence, applicable required approvals, resolved
   review conversations, and all mandatory CI, Oracle and image gates. A missing
   required check is BLOCKED. A passing summary cannot override a failed job.
   Merge by squash only with an expected-head guard; a changed head restarts
   validation. Never use an admin bypass or auto-close unfinished issue scope.

Do not enable native auto-merge until repository-level requirements are verified
and cover this review loop and all mandatory gates. A 403 reading protection is
UNKNOWN protection state, not permission to bypass it. Native review triggers,
branch protection and auto-merge configuration are separate from this document.
See [Codex review in GitHub](https://developers.openai.com/codex/third-party/github)
and [GitHub auto-merge](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request).

## Code Review Rules

- Reject unsupported causal certainty: a nearby restart, healthy detector, empty
  log query, HTTP status, or successful mitigation alone does not establish RCA.
- Check executable documentation as code: actual paths, scoped resource/time
  filters, documented fields/units, bounded probes and read-only investigation.
- Preserve the distinction between source review, static tests, live execution,
  retained evidence and independent human reproduction; check dates and provenance.
- Confirm symptom-first navigation reaches new playbooks. Do not route a user's
  inbound SCM/DNS problem to app-side outbound diagnosis without stating the path.
