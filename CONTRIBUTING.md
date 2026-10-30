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

Every change starts from a repository-specific issue unless it is a trivial typo or an urgent, documented safety fix. Search for duplicates first. Use **Context / Acceptance Checklist / Out of scope / References** in that order, with observable completion criteria and real (sanitized) evidence; never copy another repository's tracking context.

### Triage

New issues start with `needs-triage`. A maintainer:

1. Checks the problem and evidence, validity, duplicates, scope and the smallest useful result. Close duplicates with a link instead of opening a second tracker.
2. Selects one existing type label (`bug`, `enhancement`, `documentation`, `chore`, `ci` or `test`), exactly one priority label and exactly one size label.
3. Compares the impact and urgency with **all currently open issues**, not just the newest issue. Re-evaluate other priorities if that comparison changes their relative urgency.
4. Verifies in the saved GitHub issue that both labels are present, then removes `needs-triage`. If evidence, scope or a label is still missing, leave it in triage and record the missing decision.

| Label | Meaning |
|---|---|
| `priority:critical` | Immediate security/data loss or blocked publication pipeline |
| `priority:high` | Serious correctness/reliability; fix before the next planned publication |
| `priority:medium` | Normal planned work or limited impact with a workaround |
| `priority:low` | Non-urgent polish or optional expansion |

| Size label | Expected scope |
|---|---|
| `size: XS` | Very small, isolated correction |
| `size: S` | Small, independently reviewable change |
| `size: M` | Several related files or a moderate reproducible scenario |
| `size: L` | Cross-cutting work; split into independently useful issues where possible |
| `size: XL` | Too broad to implement as one PR; define a local tracker and split |

Priority describes impact, not work effort; size describes scope, not importance. Do not infer either from a title, age, lane or PR count. Re-triage if new evidence materially changes scope or priority. Priority and size belong in labels, not titles. Keep tracking local to this repository; sibling references are technical context, not cross-repository umbrella work. Do not invent milestones, release lanes, WIP statuses or labels that duplicate GitHub's native issue/PR state.

### After triage: develop the smallest useful change

1. Reproduce/locate the issue and read the relevant source, current implementation, docs and tests; identify one observable outcome and one simpler alternative.
2. Prefer a direct correction or existing pattern over new abstractions, wrappers, feature flags, duplicate guides or validators. Do not build for hypothetical future use. Ask what can be **removed or reused** before adding files.
3. Work in one focused branch and PR. Split `L`/`XL` work before implementation; every child issue must be independently useful. Do not expand an issue silently to justify a larger redesign.
4. Validate only what the change affects: executable examples, relevant app/lab tests, source claims, docs rendering and PII/image checks. A static pass never certifies live Azure execution or the Golden evidence outcome.
5. Review the final PR head, resolve real findings, obtain the responsible maintainer's decision, then squash merge without bypassing GitHub requirements. Close only fully finished issue scope; use `Refs #N` for partial work.
6. After resolving an issue, revisit the remaining open backlog for changed urgency and update priority labels where justified. Do not automatically reprioritize by issue age or size.

## Pull Request Workflow

Branch from main using fix/, feat/, docs/, ci/ or chore/. Use the PR template:
Summary / Changes / Type of Change / Validation / Checklist / Related Issues.
Link fully resolved issues with Closes #N. Partial work uses Refs #N with the
remaining scope stated explicitly; do not auto-close an unfinished umbrella.
Use Draft PRs for unfinished implementation. Never mark unrun checks complete.

Use the same current-head GitHub CI, factual review, security, image/PII and maintainer-decision process for Codex, Claude, OpenCode, Copilot and human contributions. AI review is advisory, never a required vendor score or substitute for actual tests. Keep a PR small enough to review meaningfully and describe why a simpler option was not enough if new structure was added.

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
