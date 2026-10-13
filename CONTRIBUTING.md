# Contributing

Read [AGENTS.md](AGENTS.md) and the retained [documentation contract](DOCUMENTATION_CONTRACT.md).
Engineering policy belongs at repository root; reader-facing content belongs in
`docs/`. The [authoring guide](https://yeongseon.github.io/azure-app-service-practical-guide/contributing/)
contains the detailed documentation workflow.

## Title Convention

Use `type: description` or `type(scope): description` for issues, PRs and commits.
Allowed types: `feat`, `fix`, `docs`, `test`, `perf`, `refactor`, `ci`, `build`,
`chore`, `style`, `revert`. Type/scope are lowercase; use one space after the
colon, no trailing period and no trailing `(#123)`. Put references in the body.
Use `!` before the colon for breaking changes. This section is the single source
of truth and overrides older title examples in the retained authoring contract.

## Issue Workflow

Search for an existing tracking issue before coding. Use these sections in order:
Context / Acceptance Checklist / Out of scope / References. GitHub Issue Forms
render the same field names as third-level headings. Preserve concrete acceptance
criteria, exclusions, evidence and checked/unchecked states.

Apply a type label: bug, enhancement, documentation, chore, ci or test. New reports
receive needs-triage; a maintainer confirms scope and selects exactly one priority:

| Label | Meaning |
|---|---|
| `priority:critical` | Immediate security/data loss or blocked publication pipeline |
| `priority:high` | Serious correctness/reliability issue; before next planned publication |
| `priority:medium` | Normal planned work or limited impact with a workaround |
| `priority:low` | Non-urgent polish or optional expansion |

Priority lives in labels, not title prefixes or another status field. Preserve
unrelated labels. An umbrella tracks only local issues; sibling links are
references. Do not introduce milestones, WIP labels or release grouping labels.
Use blocker only for an actual publication blocker.

## Pull Request Workflow

Branch from main using fix/, feat/, docs/, ci/ or chore/. Use the PR template:
Summary / Changes / Type of Change / Validation / Checklist / Related Issues.
Link fully resolved issues with Closes #N. Partial work uses Refs #N with the
remaining scope stated explicitly; do not auto-close an unfinished umbrella.
Use Draft PRs for unfinished implementation. Never mark unrun checks complete.

Run `python -m unittest discover -s tests/ci -v`, relevant application/lab checks,
and `mkdocs build --strict` when docs change. Install docs dependencies through
`pip install -r requirements-docs.txt`; preview with `mkdocs serve`.

Existing mandatory review/CI/image gates in DOCUMENTATION_CONTRACT.md remain.
Verify checks on the exact head SHA. No missing, pending or failing check may be
bypassed. This adoption does not change approval counts, branch protection or
release behavior. AI comments are review input, not human approval.

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
