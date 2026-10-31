---
title: Diagram Composition Prototype (#283)
slug: diagram-composition-prototype
doc_type: reference
section: reference
summary: Opt-in prototype that regenerates the App Service topology fixtures from one base, with a pre-declared maintenance-cost evaluation against inline Mermaid.
topics:
  - diagrams
  - documentation-standards
products:
  - azure-app-service
---

# Diagram Composition Prototype (#283)

This page records the scope, the evaluation protocol and the results of the opt-in prototype for [#283](https://github.com/yeongseon/azure-app-service-practical-guide/issues/283). It tests one question from the [composition ADR](adr-diagram-composition.md): does composing a diagram from a shared base, named extensions and an overlay reduce duplication and maintenance cost enough to justify more tooling than inline Mermaid plus the [grammar guard](diagram-topology-grammar.md)? A negative answer is an acceptable result.

## 1. Scope and Interpretation

- **What it is:** an opt-in way to author the four App Service fixtures of the [Azure Topology Visual Grammar (v1)](diagram-topology-grammar.md) once (one base, two extensions, one failure overlay) and to regenerate their literal Mermaid. The committed Markdown keeps the Mermaid fences, so the existing validators, the diagram manifest and the grammar guard keep working unchanged.
- **What it is not:** a renderer, an editor, a MkDocs macro or plugin, a migration, or a decision to adopt composition.

Where the issue text allows more than one reading, this prototype takes the following ones. Each can be overturned in review.

1. *No identical base graph duplicated across variants* is read as authored sources. The generated fences repeat the seven base nodes by construction, because the validators, the manifest and the guard read Markdown source; the fences are drift-checked against the spec instead of being edited by hand.
2. *Existing diagrams unchanged* means that the prototype regenerates the four fixtures already on the grammar page byte for byte and changes no existing fence, identifier, manifest record or validator. The two extensions on that page (an inbound Private Endpoint, and VNet integration with a Storage private endpoint) serve as the VNet/Storage extension and the second distinct extension. The failure overlay is its fault overlay, and the normal overlay is the unmodified numbered path, so no new palette role and no new Azure claim is introduced.
3. *Renders* means that the generated Mermaid parses and renders under Mermaid 10.9.1 in a local, agent-run check whose observations are recorded in the pull request. It is not a CI step, no screenshot or rendering harness is committed, and appearance on the published site stays open until after deployment.
4. Typed diagrams other than topology stay hand-written. The contract admits them under the same identifier and provenance rules; the prototype ships no generator for them.
5. The ADR stays Proposed. The pull request refers to the issue with `Refs`, because visual approval, a reproducible layout measurement and the decision to close belong to the maintainer.

Out of scope: migrating any legacy diagram, a third extension, Functions or Container Apps adapters, new Azure claims, CI steps or Golden gates, committed screenshots, and anything in a sibling repository.

The largest block of duplicated legacy diagrams is deliberately not used. Comparing the 395 migration-required diagrams with their labels removed (commit `3429ca0`) shows 24 language-tutorial topology diagrams (four runtimes, six tutorials, all owned by #288) that differ only in the one line that names the runtime. They draw the web app inside the integration subnet and give CIDR sizes in container titles, which the grammar forbids, so they need re-authoring in #288 before any shared template could apply.

## 2. Evaluation Protocol

This section was written before the spec and the generator existed: it is the first commit of the pull request that added this page. The criteria were therefore not chosen after seeing the results.

**Options compared**

- **A. Inline Mermaid with the grammar guard** (today's baseline): every fixture is a complete fence, and the guard enforces identical base nodes and identical `control_plane` edges.
- **B. MkDocs macros or snippets** (ADR Option B): assessed against the fixture constructs below; the prototype does not implement it.
- **C. Generated literal fences** (ADR Option C, narrowed): a stdlib-only generator and a versioned JSON spec; the Markdown keeps literal fences that a check compares with the spec.

**Baseline facts for A** (committed fences on `3429ca0`; lines of the four fence bodies)

- The four fixtures have 23, 33, 37 and 43 lines: 136 in total, none blank. They contain 73 distinct line texts, and 13 lines are identical in all four.
- Each variant keeps four of the seven base edges verbatim and replaces or retunes three. The Private Endpoint variant replaces `client → ingress` and lengthens the dashes of the two `control_plane` edges. The Storage and fault variants replace `app_runtime → storage_db` and lengthen the dashes of the `identity` and `telemetry` edges.
- Fault link styles are positional indices into the edge list.

**Metrics and thresholds**

Line counts are nonblank physical lines of each committed file. The spec is formatted with one record per line, never minified.

| Metric | How it is measured | Pass condition |
|---|---|---|
| M1 Authored volume | Lines of the spec that produces the four fixtures, against the 136 inline lines; accessible names and descriptions count on both sides | The spec has at most 102 lines (25% fewer than inline) |
| M2 Edit locality | Four fixed scenarios, counted as authored places touched and whether an incomplete edit is caught: S1 rename a base node label; S2 add a base node with one edge; S3 add an extension (a test-only one, not published); S4 insert a fault edge into the failure overlay | S1 and S2 need one authored place where inline needs four; S3 changes no generator code and copies no base data; S4 needs no hand-written link-style index |
| M3 Defects caught | Apply each defect to an inline fence (checked by the grammar guard) and to the spec (checked by the composition tests): an edge to an undeclared node, a duplicate node id, an extension replacing a base edge that does not exist, an overlay targeting a missing node or edge, a container cycle, link-style index drift after an insertion | The composition catches at least two classes that the guard does not; this informs the decision and does not decide it |
| M4 Implementation budget | Line counts of the generator and of its tests; dependency, directory, workflow, Golden gate and pinned-file changes | The generator has at most 400 lines and the tests at most 260 lines, and none of the changes listed is needed |
| M5 Layout upkeep | Number of per-variant layout hints (dash lengths, title paddings) needed for byte equality | Reported only |
| M6 Break-even | Variant count at which the total composed lines (generator, tests, spec) fall below the total inline lines, extrapolated from the measured marginal cost of one more variant on each side | Labelled Inferred; reported only |

**Decision rule.** Recommend composition as the default authoring path for a topology family only if M1, M2 and M4 all pass. If M1 or M2 fails, recommend inline Mermaid with the grammar guard as the default for that family and keep the prototype as an opt-in experiment. Another family, such as the language-tutorial diagrams in #288, needs its own measurement against this protocol. M3, M5 and M6 inform the recommendation and do not decide it. The prototype's own line counts are part of the result, not overhead to be excluded.

## See Also

- [ADR: Diagram Composition and Shared Topology Strategy](adr-diagram-composition.md)
- [Azure Topology Visual Grammar (v1)](diagram-topology-grammar.md)
- [Diagram Inventory and Migration Manifest](diagram-inventory.md)
- [Parent Initiative #281](https://github.com/yeongseon/azure-app-service-practical-guide/issues/281)
- [Prototype #283](https://github.com/yeongseon/azure-app-service-practical-guide/issues/283)
- [Validation #289](https://github.com/yeongseon/azure-app-service-practical-guide/issues/289)

## Sources

- [Mermaid Documentation](https://mermaid.js.org/)
- [MkDocs Macros plugin](https://mkdocs-macros-plugin.readthedocs.io/en/latest/)
- [pymdown-extensions: Snippets](https://facelessuser.github.io/pymdown-extensions/extensions/snippets/)
