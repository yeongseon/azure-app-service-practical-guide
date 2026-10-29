# AGENTS.md

## Mission

Maintain a practical Azure App Service guide whose claims are no stronger than
its evidence. Help readers reproduce behavior, distinguish documentation from
measurement and inference, and see uncertainty rather than a manufactured
success. A shorter agent entry point does not weaken the retained authoring or
merge contract.

## Sources of Truth

Read these before changing the repository:

1. [Golden Evidence Model](docs/reference/golden-evidence-model.md) — normative
   experiment, evidence, assertion, hypothesis, status, role, trust, provenance,
   and evaluator vocabulary.
2. [DOCUMENTATION_CONTRACT.md](DOCUMENTATION_CONTRACT.md) — complete authoring,
   PII, screenshot capture, CLI-table, content-validation, Oracle-review, and
   merge requirements. Its mandatory gates remain intact.
3. [CONTRIBUTING.md](CONTRIBUTING.md) — sole source for canonical titles,
   issue/PR sections, branch names, and the one-priority-label convention.
4. The affected documentation, implementation, lab contract, schemas,
   validators, and tests. README summaries are not substitutes for them.

When these sources describe different concerns, apply all of them. The Golden
model governs evidentiary meaning; the documentation contract governs
authoring and merge safety; validators and CI govern mechanical consistency.
Do not copy mechanical rules into this file when an executable check or the
detailed contract already owns them.

## Evidence-Driven Reasoning

Use the one-way chain:

```text
Experiment --collects--> Evidence --> Assertion --> Hypothesis
```

- Define the question, hypothesis, assertions, sampling window, expected
  observations, and observations capable of disproving each assertion before
  execution. Do not select success criteria after inspecting results.
- Collectors preserve observations; they do not decide causes. Evaluators
  derive declared assertions from raw evidence and then derive the hypothesis
  outcome. Raw evidence outranks generated summaries and verdict files.
- Keep claim levels distinct: `Documented` comes from an authoritative source,
  `Observed` records what a named artifact directly shows, `Inferred` explains
  what multiple observations suggest, and `Not Proven` states what the
  evidence cannot establish. Never promote `Inferred` to `Observed`.
- Use `Unknown` in reader-facing evidence notes when data is absent or
  ambiguous. In machine-evaluated outcomes, undecidable evidence leads to
  `INCONCLUSIVE`, not `CONTRADICTED`.
- Record the role of each artifact: `symptom`, `supporting`, `discriminating`,
  `control`, or `recovery`. Record trust independently as
  `trusted-current`, `trusted-historical`, `unverified`, or `invalid`.
  Supporting evidence raises plausibility; only discriminating evidence can
  separate competing explanations. Recovery proves restored behavior, not a
  unique cause.
- A falsification criterion is a predeclared observation that could contradict
  an assertion or hypothesis. It is not merely a successful recovery step.
- Report hypothesis status only as `SUPPORTED`, `CONTRADICTED`,
  `INCONCLUSIVE`, or `NOT_TESTED`. Report execution separately as `COMPLETE`,
  `PARTIAL`, `BLOCKED`, `FAILED`, or `NOT_RUN`. `COMPLETE` plus
  `INCONCLUSIVE` is an honest and publishable result.
- Keep official documentation, local/static checks, live Azure execution,
  evidence validity, hypothesis outcome, recovery, cleanup, freshness, and
  independent reproduction as separate claims. None implies another.

## Judgment Boundaries

- Missing or delayed logs do not prove an event did not happen. Healthy
  platform KPIs do not exclude a platform contribution. HTTP 499 or 503 alone
  does not identify a root cause. State the competing explanations and the
  discriminating evidence still needed.
- State the tested hosting model, runtime, region, SKU, source commit, recipe,
  and known limits. Do not generalize a controlled restart into reproduction of
  a specific maintenance mechanism.
- Do not force a positive lab outcome. Preserve failed, partial, blocked,
  contradictory, and inconclusive runs when they are the truthful result.
- Case-inspired public examples must be anonymized or recreated. Label their
  content `Observed`, `Inferred`, `Not Proven`, or `Unknown` as appropriate;
  do not present a synthetic recreation as customer or Azure reproduction
  evidence.
- Never publish customer identities, tenant details, secrets, account-scoped
  identifiers, private customer evidence, or unapproved internal telemetry.
  Follow the full PII and Portal capture rules in
  [DOCUMENTATION_CONTRACT.md](DOCUMENTATION_CONTRACT.md#pii-removal-quality-gate)
  and visually inspect final committed image bytes when applicable.
- Retain sanitized failure evidence. Clean up only resources owned by the run,
  verify their absence, and never select subscription-wide resources by a name
  fragment.
- Independent reproduction requires a genuinely different human operator and
  separately collected raw evidence. Automation or another AI replay may show
  repeatability but leaves independence `NOT_MET`.

## Dates, Provenance, and Replay

- Preserve `validation.az_cli.last_tested` and
  `validation.bicep.last_tested`. Only an actual execution of that method may
  update its date and result; a real failed rerun records `fail`.
- Keep `captured_at`, `evaluated_at`, and `document_updated_at` separate.
  Capture time belongs to live collection, evaluation time to derivation, and
  document time to prose changes.
- Offline replay, local CI, formatting, dashboard regeneration, or prose edits
  never refresh Azure verification or capture dates.
- Bind runs to their source commit, environment, recipe digest, run identity,
  and evidence identity. Run directories and captured evidence are immutable;
  a new collection creates a new run, while replay creates only a new
  evaluation record.
- Never fabricate a date, result, execution, review, approval, cleanup, or
  independence claim. If evidence is absent, record the appropriate unknown,
  blocked, not-run, or not-tested state.

## Pull Request Descriptions

Follow [CONTRIBUTING.md](CONTRIBUTING.md#writing-pr-descriptions) when drafting PRs.
Write concise summaries and actual validation, while preserving Golden evidence,
mandatory metadata headings, and independent review and image/PII requirements.

## Work and Completion Behavior

- Work issue-first. Preserve acceptance criteria, out-of-scope statements,
  checked and unchecked states, evidence, and concurrent edits. Use
  `Closes #N` only for fully completed local scope; use `Refs #N` and state the
  remainder for partial or umbrella work.
- Formatting or normalizing an issue/PR body is not new verification. Do not
  mark checklist, review, or Azure work complete merely to make metadata pass.
- Read-only PR jobs receive no cloud secrets. Paid Azure execution requires a
  reviewed main commit and an explicitly enabled protected environment.
  Missing prerequisites are `BLOCKED` or `NOT_RUN`, never skipped-as-verified.
- Validate mechanically checkable claims with their owning tools rather than
  prose review. In particular, use `scripts/validate_documented_paths.py` for
  repository-local links and executable command paths; use
  `tools/validate_frontmatter.py` and `scripts/lib/content_scope.py` for
  frontmatter and content-validation scope; use
  `scripts/validate_cli_explanations.py` for CLI explanation tables and table
  termination; and use `scripts/generate_golden_status.py --check` for the gate
  registry and dashboard contract. CI remains the final mechanical authority.
- Run the checks selected by the changed scope, including operating-contract
  and impact-classifier tests when their contracts are affected. Do not claim a
  check passed unless it ran successfully on the reported head.

## Review and Merge Boundary

All mandatory review and merge gates in
[DOCUMENTATION_CONTRACT.md](DOCUMENTATION_CONTRACT.md#mandatory-oracle-review-ai-agent-rule)
remain in force, including Oracle review, fully green CI on the exact head SHA,
caption-to-image accuracy, and final-image PII verification. The merge procedure
and stop conditions in that contract are unchanged.

Do not claim an Oracle score or approval that did not occur. Do not bypass
missing, pending, or failing checks, alter protection settings, or treat AI
comments as human approval. Package-release automation, package coverage
targets, and reference-repository approval-count rules are not adopted here.
