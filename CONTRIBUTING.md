# Contributing

Read [AGENTS.md](AGENTS.md) and the retained [documentation contract](DOCUMENTATION_CONTRACT.md).
Engineering policy belongs at repository root; reader-facing content belongs in
`docs/`. The [authoring guide](https://yeongseon.github.io/azure-app-service-practical-guide/contributing/)
contains the detailed documentation workflow.

## Title Convention

Use `type: description` or `type(scope): description` for issues, PRs and commits.
Allowed types: `feat`, `fix`, `docs`, `test`, `perf`, `refactor`, `ci`, `build`,
`chore`, `style`, `revert`. Type/scope are lowercase; use one space after the
colon and no trailing period. Do not put a trailing `(#123)` suffix in a PR
title: link issues in the body instead. GitHub appends the PR number to the
squash-commit subject automatically. Use `!` before the colon for breaking
changes. This section is the single source of truth and overrides older title
examples in the retained authoring contract.

The standalone `PR title` workflow runs on opened, edited, reopened and
synchronize events. It does not check out code, use secrets or request token
permissions. The broader `PR metadata` workflow also runs after label changes;
it uses only read permissions and treats the event payload as data.

## Issue Workflow

Search for an existing tracking issue before coding. Use these sections in order:
Context / Acceptance Checklist / Out of scope / References. GitHub Issue Forms
render the same field names as third-level headings. Preserve concrete acceptance
criteria, exclusions, evidence and checked/unchecked states.

### Triage

New reports receive `needs-triage`. A maintainer:

1. Checks the repository-specific problem and sanitized evidence, validity,
   duplicates, scope and the smallest useful result. Close duplicates with a link
   instead of opening a second tracker.
2. Confirms a type label: bug, enhancement, documentation, chore, ci or test;
   selects exactly one priority label and exactly one size label.
3. Compares impact and urgency with all currently open issues, including
   dependencies, before confirming priority. Reassess relative priorities when
   new evidence changes impact or scope; age and size do not determine urgency.
4. Verifies in the saved GitHub issue that the type label, exactly one priority
   label and exactly one size label are present before removing `needs-triage`.
   If evidence, scope or a required label is missing, leave it in triage and
   record what is missing.

| Label | Meaning |
|---|---|
| `priority:critical` | Immediate security/data loss or blocked publication pipeline |
| `priority:high` | Serious correctness/reliability issue; before next planned publication |
| `priority:medium` | Normal planned work or limited impact with a workaround |
| `priority:low` | Non-urgent polish or optional expansion |

| Size label | Expected scope |
|---|---|
| `size: XS` | Very small, isolated correction |
| `size: S` | Small, independently reviewable change |
| `size: M` | Several related files or a moderate reproducible scenario |
| `size: L` | Cross-cutting work; split into independently useful issues where possible |
| `size: XL` | Too broad for one PR; define a local tracker and split |

Priority describes impact; size describes scope, not importance. Select both
during triage; issue forms do not assign dynamic priority or size labels.

Priority lives in labels, not title prefixes or another status field. Preserve
unrelated labels. An umbrella tracks only local issues; sibling links are
references. Do not introduce milestones, WIP labels or release grouping labels.
Use blocker only for an actual publication blocker.

### After triage: develop the smallest useful change

1. Reproduce or locate the issue and read the relevant implementation, docs and
   tests. Identify one observable outcome and consider a simpler alternative.
2. Prefer a direct correction or an existing pattern. Ask what can be removed or
   reused before adding abstractions, wrappers, feature flags, duplicate guides
   or validators; do not build for hypothetical future use.
3. Work in one focused branch and PR. Split `L`/`XL` work before implementation;
   every child issue must be independently useful. Do not expand an issue
   silently to justify a larger redesign.
4. Run all checks required by the changed scope and the existing contracts,
   including relevant executable examples, tests, source checks, rendering and
   PII/image checks. A static pass does not certify live Azure execution or a
   Golden evidence outcome. Follow the Pull Request Workflow and every mandatory
   review and merge gate below without exception.
5. After resolving the scoped work, reassess remaining backlog urgency where
   evidence or dependencies changed. Close only fully completed local issue
   scope; use `Refs #N` and state the remainder for partial work.

## Pull Request Workflow

Branch from main using fix/, feat/, docs/, ci/ or chore/. Use the PR template:
Summary / Changes / Type of Change / Validation / Checklist / Related Issues.
Link fully resolved issues with Closes #N. Partial work uses Refs #N with the
remaining scope stated explicitly; do not auto-close an unfinished umbrella.
Use Draft PRs for unfinished implementation. Never mark unrun checks complete.

The `PR metadata` gate requires exactly these ordered level-two headings:
Summary / Changes / Type of Change / Validation / Checklist / Related Issues.
Its issue references are local numeric references only; do not use another
repository's owner/repository syntax in the Related Issues section.

Run `python -m unittest discover -s tests/ci -v`, relevant application/lab checks,
and `mkdocs build --strict` when docs change. Install docs dependencies through
`pip install -r requirements-docs.txt`; preview with `mkdocs serve`.

Existing mandatory review/CI/image gates in DOCUMENTATION_CONTRACT.md remain.
Verify checks on the exact head SHA. No missing, pending or failing check may be
bypassed. This adoption does not change approval counts, branch protection or
release behavior. AI comments are review input, not human approval.

### Repository Audit Coverage

A PR adding, renaming or removing a tracked path must update
`docs/reference/golden-repository-audit.json`. Add the path to the winning
record's `members` or add a more specific record, and delete or rename the
record of a removed or renamed path. The `Repository audit coverage` gate
otherwise fails by path name.

### Writing PR Descriptions

Use the existing ordered headings required by the PR metadata workflow. In
`Summary`, explain what changed and why; in `Changes`, keep the scope and
important compatibility or evidence details; in `Validation`, report only
checks actually run, with relevant source commit, run identity and evidence.
Keep the required checklist and issue references.

Avoid agent transcripts, canceled review attempts, copied audit jargon, empty
risk-level fields and redundant policy explanations. Do not remove required
Golden evidence, independent review, Oracle review, screenshot/PII checks, or
other security/merge information. Verify the final saved PR body for clarity.
These writing rules apply to all coding agents and human contributors without
altering any CI, approval or merge gate.

## Actions and Verification Dates

Pin new/changed external actions to a verified 40-character SHA with a source or
version comment. Treat issue/PR metadata as data, not shell. Ordinary PR jobs use
read-only permissions and no Azure credentials. Privileged jobs never execute
untrusted fork code. Metadata-format checks do not certify the truth of a test
claim; evidence checks and review remain necessary.

Reuse validation.az_cli.last_tested and validation.bicep.last_tested; do not add a
parallel tested_at. Future/malformed dates and unknown result values are invalid.
A failed real test may update last_tested with result: fail, not a success claim.
The existing tutorial stale threshold is more than 90 days, not 90 days or more.

Keep captured_at, evaluated_at and document_updated_at separate. Offline replay
and freshness reports cannot advance real test dates. A recent date does not
validate a changed recipe or an untested environment. INCONCLUSIVE may coexist
with completed execution; stale does not invalidate a historical observation.

## Reference Adoption

Adapted from yeongseon/azure-functions-openapi-python at
f43ca2047eb18f717314b6e555c8eb04d954f3ab: issue-first work, title/template consistency,
priority labels, local trackers and tiered verification. Package publishing,
95% package coverage and its repository-specific approval decisions are excluded.
See #217 and #218. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community rules.

## Versioned Priority Labels

[`.github/priority-labels.json`](.github/priority-labels.json) is the versioned
definition for the four recognized priority labels, including their colors and
descriptions. Run the following read-only drift check before requesting a label
sync; it never creates, edits or deletes labels:

```bash
python scripts/ci/sync_priority_labels.py --repo yeongseon/azure-app-service-practical-guide --check
```

The explicit `--apply` mode creates or updates only those four `priority:*`
labels. It never deletes labels and must not be run against the live repository
as part of this governance change.
