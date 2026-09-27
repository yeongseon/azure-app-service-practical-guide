# Golden Evidence Model

The Golden v1 model defines how this repository represents an experiment, the evidence it collects, and what that evidence is allowed to claim. Microsoft Learn documents how App Service behaves. This model exists to answer a different question: how does an engineer reproduce that behaviour, observe it, and know what the observation does and does not prove?

## The chain

```text
Experiment --collects--> Evidence --> Assertion --> Hypothesis
```

Each arrow is deliberately one-way. Collectors gather facts and never decide a cause. Assertions are declared before execution, so a run cannot choose its success criteria after seeing the result. The hypothesis verdict is derived from assertion outcomes, never asserted directly.

## Vocabulary

| Axis | Values |
|---|---|
| Claim level | `Documented`, `Observed`, `Inferred`, `Not Proven` |
| Hypothesis status | `SUPPORTED`, `CONTRADICTED`, `INCONCLUSIVE`, `NOT_TESTED` |
| Execution status | `COMPLETE`, `PARTIAL`, `BLOCKED`, `FAILED`, `NOT_RUN` |
| Evidence role | `symptom`, `supporting`, `discriminating`, `control`, `recovery` |
| Evidence trust | `trusted-current`, `trusted-historical`, `unverified`, `invalid` |

`Inferred` may never be promoted to `Observed`. The evaluator raises rather than allowing it, because an inference that acquires the authority of an observation is indistinguishable from a measurement that was never taken.

## Three rules that carry the model

### Execution status is separate from hypothesis status

A run that did not finish has not tested anything, whatever its partial evidence happens to show. Folding the two axes together produces the most common failure in this repository's history: a hypothesis derived from the evidence verdict, which leaves `CONTRADICTED` unreachable and silently collapses four documented outcomes into two.

### Absence is not refutation

Evidence that cannot decide an assertion yields `INCONCLUSIVE`. It never yields `CONTRADICTED`. A missing field, a truncated capture, and a log that has not arrived yet are all states of not knowing. Treating them as disproof manufactures findings that the evidence does not support.

`INCONCLUSIVE` is a normal, publishable result.

### Raw evidence wins over any generated verdict

A run may carry a `result.json`. The evaluator never reads it as input. It recomputes the outcome from raw evidence, compares, and reports `generated_verdict_rejected` on disagreement. A verdict file that can decide its own outcome is not evidence.

## Timestamps

Three distinct instants, never interchangeable:

| Field | Meaning |
|---|---|
| `captured_at` | When the evidence was collected from the live system |
| `evaluated_at` | When the gates were re-derived offline from that evidence |
| `document_updated_at` | When the prose was last edited |

Re-running an offline evaluator over an older cohort must not restate that evidence as freshly captured. A field named for capture that actually holds evaluation time will silently republish months-old evidence as current on every re-run.

## Run layout

```text
evidence/<run-id>/
├── manifest.json     run identity, timestamps, declared assertions
├── baseline/         raw evidence, healthy state
├── fault/            raw evidence, fault applied
├── recovery/         raw evidence, after remediation
├── assertions/       per-assertion raw inputs
└── result.json       derived, regenerable, never an input
```

Run directories are immutable and never overwrite a previous run. A collector re-run creates a new `run-id`.

## Evaluator

`scripts/golden/evaluate_run.py` is stdlib-only and re-derives every assertion outcome from raw evidence.

```bash
python3 scripts/golden/evaluate_run.py evidence/<run-id>
```

| Exit code | Meaning |
|---|---|
| `0` | `SUPPORTED` |
| `1` | `CONTRADICTED` |
| `2` | `INCONCLUSIVE` |
| `3` | `NOT_TESTED` — execution did not complete |

A refutation does not share exit `0` with a confirmation. Exit `0` reads as "the reproduction worked", and a disproof is a different result, not a successful one.

The evaluator does not name a root cause. It reports whether declared assertions held.

## Schemas

| Schema | Purpose |
|---|---|
| [`manifest.schema.json`](https://github.com/yeongseon/azure-app-service-practical-guide/blob/main/schemas/golden/manifest.schema.json) | Run identity, the three timestamps, declared assertions |
| [`assertion.schema.json`](https://github.com/yeongseon/azure-app-service-practical-guide/blob/main/schemas/golden/assertion.schema.json) | One machine-evaluable claim about a named evidence field |
| [`result.schema.json`](https://github.com/yeongseon/azure-app-service-practical-guide/blob/main/schemas/golden/result.schema.json) | Derived output, regenerable from raw |

## Predicate guidance

A gate whose weak path subsumes its strong path is unsound. Written as `strong or fallback` where `fallback` is one of `strong`'s conjuncts, boolean absorption reduces the whole predicate to `fallback` alone, and every other condition becomes dead code while the gate keeps its reassuring name.

This is not hypothetical. It is the defect class that allowed a verdict file to pass a sub-gate whose raw data contradicted it.

Write the weak path so it cannot subsume the strong one, or place the shared invariant outside the choice:

```python
# Unsound: reduces to `fallback` alone.
result = (a and b) or b

# Sound: the invariant applies to both paths.
result = (strong or fallback) and invariant
```

## See Also

- [Content Validation Status](content-validation-status.md)
- [Validation Status](validation-status.md)

## Sources

- [Azure App Service documentation](https://learn.microsoft.com/en-us/azure/app-service/)
