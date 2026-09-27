# Golden Model Migration Specification

How a sibling repository in the Azure Practical Guide series adopts the
[Golden evidence model](golden-evidence-model.md).

This specification exists because the model was built here first, against
real App Service labs, and the parts that transfer are not obvious from the
outside. What follows separates the machinery a sibling can take unchanged
from the parts it must author itself, and names the entry criteria a
repository meets before it claims Golden status.

## What transfers unchanged

The evaluator and the reproduction gate contain no App Service references.
They operate on the manifest and result contracts, not on any service, so a
sibling copies them as-is.

| Asset | Change needed |
|---|---|
| `scripts/golden/evaluate_run.py` | None |
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
