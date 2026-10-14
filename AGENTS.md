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
