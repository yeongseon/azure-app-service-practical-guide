# Golden Model Migration Specification

How a sibling repository in the Azure Practical Guide series adopts the
[Golden evidence model](golden-evidence-model.md).

This specification exists because the model was built here first, against
real App Service labs, and the parts that transfer are not obvious from the
outside. What follows separates the machinery a sibling can take unchanged
from the parts it must author itself, and names the entry criteria a
repository meets before it claims Golden status.

## What transfers unchanged

The reproduction gate and the evaluator's manifest, result and evidence
contract checks contain no App Service names, so a sibling copies them. At the
reviewed commit the evaluator is not service-neutral, however: it also carries
the Scenario A derivation (`_derive_scenario_a`, which matches an exact
`wrong_module` console-row signature) and reads this repository's registry and
recipe files (`evidence/retained-digests.json`,
`evidence/run-declarations.json` and `scripts/golden/scenario-a-recipe.json`).
A sibling keeps the contract checks, replaces that derivation with derivations
for its own scenarios, and supplies its own recipe and registries.

| Asset | Change needed |
|---|---|
| `scripts/golden/evaluate_run.py` | Replace the Scenario A derivation and its recipe and registry inputs; keep the contract checks |
| `scripts/golden/check_reproduction.py` | None |
| `tests/golden/test_evaluate_run.py` | None |
| `tests/golden/test_negative_evidence.py` | None |
| `tests/golden/test_lab_classification.py` | None |
| `tests/golden/test_repository_audit.py` | None |
| `tests/golden/test_readme_claims.py` | None |
| `schemas/golden/*.json` | `$id` host and path only, plus the one `$ref` in `manifest.schema.json` |

The four schemas carry this repository's Pages host in their `$id`. Nothing
resolves those URLs at runtime, so a stale `$id` will not fail a run; it
will quietly assert that two different repositories publish the same
schema. Rewrite the host and path on adoption.

## What each repository authors itself

Per-scenario suites encode the failure being demonstrated and do not
transfer. In this repository those are `test_scenario_a.py`,
`test_scenario_b.py`, `test_scenario_c.py` and `test_reproduction.py`.

A sibling authors, per Golden scenario:

- A manifest template naming the assertions the run must satisfy.
- An evidence-classification file stating what each artifact can support and
  what it cannot.
- A suite whose negative cases fail when the scenario's own classification
  logic is broken.

Collectors are always service-specific. The adopting repository must record
its authentication boundary, supported operating systems and runtimes,
required diagnostic tables, resource naming constraints, paid-resource
assumptions and telemetry delay. Each scenario also needs a bounded recovery
procedure and cleanup that names every resource it owns. A copied evaluator
does not make an App Service collector valid for Functions, Container Apps or
another service.

Reviewed Azure Container Apps work may inform directory layout, schema wiring
and the separation between collection and evaluation. Its predicates are not
portable evidence: every comparison, threshold and discriminating observation
must be re-declared from the destination service's documented behavior and
mutation-tested there.

## Source revision and prerequisites

This specification was validated against App Service commit
`e3428fd8d0713d7e881e8a7b3635e1204791e447`, which contains merged PRs #234,
#235 and #236. Adoption requires a Python version that revision supports (its
workflow runs 3.11), the evaluator (standard library plus the `git`
executable), the reproduction gate (which also imports `jsonschema` and
`referencing`), and a CI job that runs both the portable suites and the
destination repository's scenario suites. Copy source bytes from that commit
or a documented successor; do not combine files from different revisions.

## Vocabulary migration

The frozen hypothesis vocabulary is `SUPPORTED`, `CONTRADICTED`,
`INCONCLUSIVE`, `NOT_TESTED`.

Earlier evaluators in this series use `REFUTED` where the model says
`CONTRADICTED`, and `NOT_EVALUATED` where it says `NOT_TESTED`. A repository
carrying those terms maps them on adoption:

| Earlier term | Golden term |
|---|---|
| `REFUTED` | `CONTRADICTED` |
| `NOT_EVALUATED` | `NOT_TESTED` |

The mapping is not cosmetic. `REFUTED` reads as a finding, and the
distinction the model draws is between evidence that contradicts a
hypothesis and evidence that is merely absent. Repositories that collapse
the two report missing data as disproof.

## Entry criteria

A repository claims Golden status when all of the following hold, each
verifiable by running something rather than by reading a page.

1. The evaluator and reproduction gate are present and their portable
   suites pass unmodified.
2. Every lab is classified, and the classification covers exactly the labs
   on disk with no orphan entries in either direction.
3. At least one scenario ships a manifest template and an
   evidence-classification file.
4. Every negative suite has been mutation-tested: the code it guards is
   broken deliberately and the suite is confirmed to fail.
5. Status wording in the README is supported by evidence the repository
   actually holds. A status asserting the labs prove the guidance requires
   a completed run and an independent reproduction.
6. Any rule the repository's `AGENTS.md` describes as rejecting something is
   invoked by a workflow.

Criteria 5 and 6 are the ones most often missed, because both can be
satisfied in prose without being true.

After reuse, minimum verification is schema conformance, every portable test,
every destination negative/mutation suite, retained-package integrity, PII
scanning, the repository's complete existing gate set and a strict site build.
No sibling repository change is a prerequisite for completing those checks.

## Preserving evidence on adoption

Copying the machinery never moves evidence. An adopting repository preserves
each artifact's original capture date, its `validation.az_cli.last_tested` and
`validation.bicep.last_tested` dates and results, and its run and evidence
identity; run directories and captured evidence stay immutable, and each
artifact keeps its evidence role and trust level. Independent reproduction
still requires a genuinely different human operator and separately collected
raw evidence, as the [Golden evidence model](golden-evidence-model.md)
defines. Copying the evaluator, replaying an evaluation or running static
checks creates neither a fresh capture date nor an independent reproduction: a
new collection creates a new run, and a replay creates only a new evaluation
record.

## Order of adoption

Take the evaluator and its portable suites first and confirm they pass
before authoring any scenario. A suite that passes on first import against
an empty repository is measuring nothing, and the portable suites are the
cheapest place to discover that.

Classify the labs before migrating any of them. Classification is what
distinguishes a lab worth carrying forward from one that should be archived,
and doing it after migration means paying to migrate labs that were never
going to qualify.

## See Also

- [Golden Evidence Model](golden-evidence-model.md)
- [Golden Repository Audit](golden-repository-audit.json)

## Sources

- [Azure Practical Guide series repositories](https://github.com/yeongseon)
