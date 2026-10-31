---
title: ADR - Diagram Composition and Shared Topology Strategy
slug: adr-diagram-composition
doc_type: reference
section: reference
summary: Proposed reuse boundaries, prototype dependency, and inventory-only decisions for App Service diagrams.
topics:
  - diagrams
  - documentation-standards
products:
  - azure-app-service
---

# ADR: Diagram Composition and Shared Topology Strategy

## Status

Proposed. Composition depends on the opt-in shared prototype [#283](https://github.com/yeongseon/azure-app-service-practical-guide/issues/283); this inventory does not approve a renderer or start migration.

## Context and Problem Statement

The [manifest](diagram-manifest.json) records 405 Mermaid occurrences in 246 tracked Markdown files (the baseline commit `036376d` is recorded as metadata; the scanner reads the working tree): 404 published under `docs/` and one authoring example in the repository contract. Of these, 361 are flowchart/graph blocks (89.1%); the remaining 44 are sequence, state, timeline, or chart blocks (10.9%). Ten explicit exclusions (the authoring example, three generated dashboard charts and, since [#296](https://github.com/yeongseon/azure-app-service-practical-guide/issues/296), the six illustrative fixtures of the topology visual grammar) leave 395 migration-required Mermaid occurrences.

Approximate node-label extraction finds `microsoft entra id` in 38 diagrams and `azure sql` in 29. This suggests potential component reuse, not identical semantics or accepted component definitions. Metadata extraction finds 24 IDs reused across pages and two occurrences without frontmatter provenance; page-qualified keys avoid conflating them. Declared sources split into 200 `mslearn-adapted`, 203 `self-generated`, and two absent declarations. None of these declarations has been verified by this inventory.

App Service also publishes Cytoscape navigation graphs, unlike a Mermaid-only guide. The manifest records those separately in `visuals[]`, including their JSON, JavaScript, stylesheet, page, and producer dependencies, plus unwired learning-path graph containers. They must not disappear behind a screenshot exclusion.

Parent [#281](https://github.com/yeongseon/azure-app-service-practical-guide/issues/281) requires a complete migration with preserved meaning, not a standalone diagram platform. Existing MkDocs macros/snippets and Mermaid already provide a local authoring path. The inventory scanner and schema are copied byte-identically from the Container Apps reference implementation; repository-specific rules are separate data, not a forked generator.

## Decision Drivers

- Preserve reader intent and distinctions between topology, sequence, decision, state, and evidence-oriented visuals. Evidence is an instructional purpose, not necessarily a Mermaid syntax keyword.
- Preserve stable IDs, citations, captions, and Golden evidence limits. A diagram does not prove Azure behavior.
- Keep frontend/worker/application boundaries, main-site versus SCM policy, Windows/Linux differences, and inbound versus outbound paths explicit where supported by sources.
- Minimize dependencies and enable deterministic, auditable local preview before considering cross-repository packaging.

## Considered Options

### Option A: Keep Inline Mermaid as Reviewed Source of Truth

Native Mermaid keeps each diagram next to its explanation and avoids a build interface. It is the fallback if composition does not reduce maintenance cost. Repeated resource clusters and visual conventions still require coordinated manual edits; repeated labels alone do not justify merging diagrams.

### Option B: MkDocs Macros or Snippets for Shared Topology Fragments

The current toolchain already enables macros and `pymdownx.snippets`. Reusing those may be simpler than a compiler. Fragment concatenation risks syntax boundaries, identifier collisions, and hidden page-specific wiring; the prototype must demonstrate understandable diffs and source metadata rather than merely shorter files.

### Option C: Small YAML-to-Mermaid Composition Renderer

A minimal declarative base plus named extensions and normal/failure overlays could validate node references and separate shared topology from scenario detail. It adds a schema, a build step, and an authoring language. It is justified only if #283 demonstrates less duplication and lower maintenance cost than direct Mermaid or snippets. The #283 prototype narrowed this option to a stdlib-only JSON spec with generated literal fences; the measured comparison is on the [Diagram Composition Prototype](diagram-composition-prototype.md) page.

### Option D: Standalone Shared Package Across Repositories

A shared package centralizes implementation but adds publishing, version pinning, release coordination, and external availability requirements. It is not automatically needed: Mermaid already meets diagram-as-code needs, and a pinned inventory interchange contract is sufficient for P0. Packaging remains deferred until cross-guide reuse is demonstrated; three divergent copied composition generators are not an acceptable alternative.

## Decision Outcome

Proposed: retain inline Mermaid as the reviewed diagram source, evaluate B against C in #283, and do not convert existing diagrams in this change.

1. Inventory-only tooling: Python 3.11 and PyYAML extract source facts; optional `jsonschema` checks parity with the built-in structural validator. CI installs it for the parity test. The scanner never renders, converts, or verifies source provenance. `--write` writes the manifest and generated inventory-page blocks; `--check` validates consistency, not provenance. `--verify-tree` compares extracted records with the baseline, not extraction completeness; `--check` reports `unrecognized_mermaid_fences`.
2. Versioned interchange: `schema_version: 1` describes inventory, not composition. The manifest pins scanner version and SHA-256, rules SHA-256, and source base commit. Scanner/schema updates must be coordinated byte-identically with sibling guides and followed by regeneration; they must not acquire local composition logic. Any breaking interchange change requires a coordinated schema-version decision, not a silent local reinterpretation.
3. Deferred composition interface: #283 owns component IDs, boundaries, arrow semantics, references, extension/overlay naming and compatibility. It must demonstrate one base, two distinct extensions, and normal/failure overlays before #284 adopts the product base and #285–#288 migrate assigned entries.
4. Typed semantics: sequence, state, timeline, and chart diagrams remain hand-authored unless a later review demonstrates an adequate typed template. Flowchart/graph genre candidates are advisory and all remain unreviewed. Reader intent stays null until reviewed; targets remain provisional and migration stays `not-started`.
5. Ownership: #283 owns no legacy occurrences because its affected scope is an opt-in pipeline, and its acceptance keeps existing diagrams unchanged outside the PoC. #289 owns no diagrams; full migration/render coverage belongs there, not to this committed-snapshot consistency check.
6. Non-Mermaid owner decision: explicitly exclude the generated Cytoscape navigation producers and unwired learning-path containers provisionally, rather than replace them with static topology. Including or excluding them in the migration is an owner decision that must be settled before #281 closes; if included, #288's auxiliary/published-assets scope is the proposed owner. This is not an approved permanent exclusion or proof the widgets work.
7. Prototype result (#283): the prototype regenerates the four App Service fixtures of the topology grammar byte for byte from one base, two extensions and one failure overlay, and meets the necessary conditions of its predeclared protocol (authored volume, edit locality and tool size). At four variants its tooling costs about five times the inline lines and breaks even only near 33 variants (Inferred). The recommendation is to keep inline Mermaid with the grammar guard as the default, to keep the prototype as an opt-in experiment, and to decide per family; the language-tutorial diagrams owned by #288 are the candidate for a new measurement. This is a recommendation: the Status stays Proposed.

## Over-Engineering Assessment

P0 introduces no rendering/conversion/composition code, new top-level directory, diagram platform, or mandatory build dependency beyond the existing Python/PyYAML toolchain and optional schema validation. The scanner is pinned scanning, consistency-validation and reporting logic with manifest and generated-page output; per-repository rules keep ownership review separate from shared code. Python standard library plus PyYAML require no external binary dependencies for inventory scanning; no fixed runtime is promised.

Derived before-screenshots are not committed. The supplied one-time measurement ran on App Service `main` at `3fd06267c1a950437757935d13ceff0ae3861d91`, before merged PR #291 fixed its eight failing blocks. It rendered 398 App Service blocks in headless Chrome 145 using `mermaid@10.9.1`: 390 rendered and eight had parse errors. The regex syntax validator caught none. This historical measurement is not a render verification of the inventory head; no render was run for this adoption.

The supplied render measurement produced 13.0 MB of derived App Service PNGs (about 32 KiB per block). Hundreds of derived binaries would inflate history and invoke this repository's evidence-screenshot caption, capture-profile, provenance, and final-image PII gates without adding Azure evidence. Retain the source commit and per-block hashes/structural counts as the reproducible baseline instead. Before/after rendering, light/dark, narrow-screen readability, and accessibility review remain migration/#289 work; no rendering harness is added here.

## Consequences and Risks

### Positive Consequences

- All 395 migration-required Mermaid occurrences have exactly one owning batch. Ten excluded occurrences and every tracked image have explicit reasons; no asset or assignment is unresolved.
- The manifest preserves declared provenance verbatim, locations, source hashes and approximate structural fields without rewriting source diagrams or evidence.
- The two inventory CI steps validate fixtures and committed-snapshot consistency without cloud credentials, network access, or a rendering runtime.

### Risks and Mitigations

- The PoC may not justify composition. Keep Option A viable and do not prescribe target component names before review.
- Genre signals mislead: a diamond may be decorative, while a topology may have no subgraph. Preserve `unreviewed`, report sample disagreement, and have batch owners read the actual diagram.
- A line-based scanner cannot fully reproduce the site's Markdown container rendering. It errs toward reporting: `blockquote`, `list-marker`, and `indented` findings block `--check`; `html-comment` and plain `indented-code` findings are informational. `--write` warns once per page for blocking findings only. App Service's separate Mermaid format validator already rejects indented Mermaid fences; examples belong inside longer outer fences. See the [inventory's known limitations](diagram-inventory.md#command-reference), including extra info words, prefixed comments, conservative nested-container over-reporting and corrupted fences. The shared scanner's classification was checked against Python-Markdown 3.10.2 / pymdownx 10.21.3 in local experiments run for the Container Apps pull request on 2026-10-30; those experiments are not committed here or rerun for App Service.
- `--check` does not compare the source tree to the committed snapshot. Use advisory `--verify-tree` to see drift; #289 must design future coverage rather than presenting P0 as full migration enforcement.
- Asset `referenced_count` counts Markdown image usages, not `shot()` macro expansion. Manifest-driven WebPs can therefore have zero literal usages without being unused. Capture registration and evidence validity remain separate gates.
- Visual exclusions need an owner decision. Source inspection also finds a stale producer name on the troubleshooting-map page and learning-path containers with no initializer/dataset. Record the limitations rather than repair unrelated visual behavior in P0.

## See Also

- [Diagram Inventory](diagram-inventory.md)
- [Diagram Composition Prototype (#283)](diagram-composition-prototype.md)
- [Diagram Manifest Schema](diagram-manifest.schema.json)
- [Golden Evidence Model](golden-evidence-model.md)
- [Parent Initiative #281](https://github.com/yeongseon/azure-app-service-practical-guide/issues/281)
- [Shared Prototype #283](https://github.com/yeongseon/azure-app-service-practical-guide/issues/283)

## Sources

- [Mermaid Documentation](https://mermaid.js.org/)
- [Inventory acceptance #282](https://github.com/yeongseon/azure-app-service-practical-guide/issues/282)
- [One-time rendering fixes #291](https://github.com/yeongseon/azure-app-service-practical-guide/pull/291)
