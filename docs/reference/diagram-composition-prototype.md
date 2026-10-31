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

## 3. Interface Contract

The prototype has three files: the versioned spec `scripts/diagram_composition.json`, the stdlib-only generator `scripts/diagram_compose.py` and its tests `tests/ci/test_diagram_composition.py`.

**Source of truth.** For the diagrams it enrolls, the spec is the authored input. The committed Markdown keeps the literal Mermaid fence, found by the diagram-id comment directly above it, and a check compares the two byte for byte. The frontmatter is never written: the check only compares the spec's diagram identifiers and source links with the `content_sources.diagrams` entries of the page.

**Spec.** `schema_version` and `grammar_version` are both `1`. The JSON is strict: duplicate object keys, unknown keys, wrong types, `NaN` and a boolean version are rejected. Arrays carry order, and object key order never changes the output. The spec contains no raw Mermaid text.

| Key | Content |
|---|---|
| `base` | One named graph: ordered node records (`id`, `component`, `label`, `class`) and edge records (`id`, `from`, `to`, `style`, `label`). `component` is a drawable id of the grammar vocabulary and selects the shape; `style` is `solid`, `dotted` or `fault`. |
| `extensions` | Named additions: `nodes`, `containers` (`id`, `component` of `vnet` or `subnet`, `title`, `tag`, `members`, nested by listing member ids) and `replace_edges`, which swaps one existing edge, in place, for an ordered list of edges (an empty list removes it). |
| `overlays` | Named failure overlays (`type` is `failure`; the normal path is the absence of an overlay): label and class overrides of existing nodes, `replace_edges`, and one `callout` that becomes a callout node with its fault edge. |
| `diagrams` | Ordered outputs: `id`, `page`, `genre` (only `topology`), `accTitle`, `accDescr`, `base`, `extensions`, `overlay`, `sources` and `layout`. |
| `layout` | Per-diagram hints: `link_length` (the number of dots of a dotted arrow, by edge id) and `title_padding` (the number of `&nbsp;` entities in a container title, by container id). |

**Composition rules**

- The order is the base, then the listed extensions in order, then the overlay, then the layout hints.
- A replacement keeps the position of the edge it replaces. Replacing an unknown edge, or the same edge in two extensions, is an error.
- The callout edge is placed after the last replacement span of the overlay.
- Fault edges (`==>`, class `stateFault`) and the fault link style `stroke:#da495d,stroke-width:3px` are fixed by the grammar. The `linkStyle` indices are computed from the final edge list and are never written by hand.
- Every identifier is explicit. The four diagram identifiers are the ones already on the grammar page, so the manifest keys do not change.
- Rejected at load time: references to undeclared nodes, duplicate identifiers, containers with missing members, several parents or cycles, edge labels without a claim prefix, the reserved `[Observed]` level, a callout without its `[Illustrative scenario - not a measurement]` line, and a normal path that contains a fault edge.

One extension, copied from the spec (the comma that closes the member inside `extensions` is omitted), shows the size of the data an author writes:

```json
"ingress-pe": {
  "nodes": [
    {"id": "dns", "component": "dns", "label": "Private DNS zone: privatelink.azurewebsites.net<br/>[linked to the VNet]", "class": "bandMuted"},
    {"id": "private_endpoint", "component": "private-endpoint", "label": "Private Endpoint: App Service Inbound NIC<br/>[Inbound Private IP]", "class": "focusActive"}
  ],
  "containers": [
    {"id": "vnet_in", "component": "vnet", "title": "Customer VNet", "tag": "[VNet boundary]", "members": ["subnet_pe"]},
    {"id": "subnet_pe", "component": "subnet", "title": "Subnet: private endpoints", "tag": "[private endpoint NICs]", "members": ["private_endpoint"]}
  ],
  "replace_edges": {"request": [
    {"id": "dns_in", "from": "client", "to": "dns", "style": "dotted", "label": "[Configured] 1. DNS lookup returns PE private IP"},
    {"id": "pe_in", "from": "client", "to": "private_endpoint", "style": "solid", "label": "[Configured] 2. HTTPS 443 to PE private IP"},
    {"id": "private_in", "from": "private_endpoint", "to": "ingress", "style": "solid", "label": "[Configured] 3. Private Link inbound"}
  ]}
}
```

**Compatibility path**

- Opt-in: nothing changes for a diagram until it has an entry in `diagrams`. The generator never scans other fences.
- Opt-out: remove the three files and their entries in the repository audit. The fences stay as literal Mermaid, so every validator, the manifest and the grammar guard keep seeing the same source. Removing a single entry is also possible, but the tests exercise the live spec, so removing the last entry that uses an extension or an overlay means adapting the tests that mutate it.
- Versions: an unknown `schema_version` or `grammar_version` is a hard error. Mermaid is pinned to 10.9.1 by the site.
- Typed diagrams other than topology stay hand-written under the same identifier and provenance rules, for example the sequence diagram `runtime-request-sequence` in `docs/platform/architecture/index.md`. The generator rejects any other `genre`.
- Sibling guides can use the grammar without the generator. Adoption there is not claimed, and divergent copies of the generator are not acceptable (see the ADR).

## 4. Build and Check Commands

Python 3.11 or later, standard library only, run from the repository root.

```bash
python scripts/diagram_compose.py --check
python scripts/diagram_compose.py --write
python scripts/diagram_compose.py --print topology-grammar-v1-appservice-baseline
python scripts/diagram_compose.py --stats
python -m unittest discover -s tests/ci -p test_diagram_composition.py -v
```

- `--check` is read-only. It composes every enrolled diagram, compares each body with the committed fence and the sources with the frontmatter, and prints `diagram composition: check passed (4 diagrams)`. Any handled spec or page problem prints one line and the exit code is 1; argument errors exit 2.
- `--write` validates every entry first and then rewrites only the enrolled fence bodies, preserving every other byte, including CRLF line endings. A second run changes nothing. Both modes refuse a page that resolves outside the repository, symlinks included, and an enrolled body that contains a Markdown closing delimiter other than the plain three-backtick line (four backticks, a trailing space or an indent), so text outside a fence cannot be rewritten.
- `--print ID` writes one composed body to standard output, and `--stats` prints the counts used by the evaluation.
- The commands are not part of `mkdocs build`. The test suite runs in the existing `tests/ci` job on every pull request, so a drifted fence fails there. No workflow step and no Golden gate was added, so a push to `main` that touches only the spec or the page does not run the check again.

A spec defect and a page drift produce these diagnostics (real output, exit code 1):

```text
edge dns_in: undeclared node
topology-grammar-v1-appservice-baseline: committed fence drift
```

The first comes from an edge of the `ingress-pe` extension that points to a node that does not exist. The second comes from a hand edit of a fence (`flowchart TD` changed to `flowchart LR`); `--write` repairs it and leaves the page byte-identical to the committed one.

## 5. Results

Measured on the pull request that adds the generator, with the commands above. The inline-side numbers come from applying each edit to in-memory copies of the committed page and running the grammar guard with its 450-line page-size rule filtered out, because every edit that adds lines trips it. The composed-side numbers come from `--stats`, the tests and the same edits applied to the spec. The throwaway measuring scripts are not committed. The grammar guard is needed in both approaches and is not counted.

| Metric | Result | Verdict |
|---|---|---|
| M1 Authored volume | The spec has 84 lines against 136 inline lines (38.2% fewer; the limit was 102). As a supplementary figure, the spec has 9,846 bytes against 10,633 bytes of inline fences; the spec also carries the source lists that live in the frontmatter on the inline side. | Pass |
| M2 Edit locality | See the scenarios below. | Pass |
| M3 Defects caught | Composition catches two classes that the guard misses (see below). | Pass; informs only |
| M4 Implementation budget | The generator has 400 lines (limit 400, met without margin) and the tests 290 (limit 260, exceeded by 30). No dependency, directory, workflow step, Golden gate or change to the pinned scanner, the grammar page or its guard was needed. | Fail |
| M5 Layout upkeep | 15 hints (7 dash lengths and 8 title paddings) in 3 of the 4 diagrams: about a third of the roughly 47 spec records. | Reported |
| M6 Break-even | Inferred: about 35 variants for a family shaped like this one, or about 20 diagrams if every further diagram were a one-line entry. At four variants the composed side costs 774 lines (84 spec, 400 generator, 290 tests) against 136. | Reported |

The break-even is a linear extrapolation. Inline, the first fixture costs 23 lines and each further variant 37.7 on average (33, 37 and 43). Composed, the fixed cost is 721 lines (generator, tests and 31 spec lines for the base and the wrapper) and each further variant costs 17.3 on average (extension or overlay blocks of 15, 18 and 16 lines, plus one diagram line). It ignores review effort, the cost of reading generated diffs and layout retuning.

Edit scenarios (M2):

| Scenario | Inline with the guard | Composed |
|---|---|---|
| S1 rename a base node label | 4 fences, 4 lines; an edit of 3 of the 4 fences is caught by the guard | 1 spec line; the 4 fences change by 1 line each |
| S2 add a base node with one edge | 8 lines in 4 fences and 1 line to repair the positional link-style indices of the fault fixture; an edit of 3 of the 4 fences is not caught, because the guard compares only the seven known base nodes | 2 spec lines in 1 place; the indices are regenerated (`6,10,11`) |
| S3 add an extension | a new complete fence, 24 lines for a one-node extension, 19 of them copied from the baseline fence | 10 spec lines (9 for the extension, 1 for the diagram); no generator change |
| S4 insert a fault edge | 2 lines (the edge and the indices); forgetting the indices is caught by the guard | 1 spec line; the indices follow (`5,9,10` becomes `5,9,10,11`) |

Defect classes (M3), each applied to an inline fence and to the spec:

| Defect | Grammar guard on inline fences | Composition on the spec |
|---|---|---|
| Edge to an undeclared node | caught | caught |
| Duplicate node identifier | caught for the seven base nodes only | caught |
| Node declared in two containers | not caught | caught |
| Container cycle | not measured on inline fences | caught (a test) |
| Link-style index drift after an insertion | caught | cannot occur: the indices are computed |
| Replacing a base edge that does not exist; an overlay targeting a missing node | no such concept | caught (these exist only because of the abstraction) |

The cycle class was exercised only on the composed side, so no comparison is claimed for it.

**Option B (macros or snippets)** was not implemented, and the fixtures show what it would cost. In every variant, three of the seven base edges are replaced or retuned, so additive fragments can express a variant only by splitting those edges out of the shared base into per-variant fragments with a hand-assembled include order. That is a fragmentation trade-off and not an impossibility. Fault link styles are positional indices that a fragment cannot compute, and snippets do not validate graph semantics: `check_paths` defaults to `False` in the installed pymdown-extensions 12.3, so a missing include is silently dropped from a strict build, although setting it to `True` would check that included files and sections exist. A macro that emits the fence at build time would hide the diagram from the source-based validators, the diagram-id parity gate and the manifest.

**Reading the result.** M1 and M2 pass and M4 fails, so the necessary conditions of the decision rule are not all met, and by the rule composition is not the default authoring path for this family. The generator meets its limit with no margin (400 lines). The tests exceed theirs: they were at 253 lines when first measured, and the regression tests for two write-safety defects that review found afterwards (a closing delimiter that the fence pattern does not recognise, and a page symlink that leaves the repository) took them to 290; the limit was not changed. M1 compares only the spec, because the protocol did not charge the generator and its tests to it, a gap that became visible when the numbers came in; section 2 was not edited. M6 and the total tooling volume (774 lines against 136) were not part of the decision rule. They support the per-family advice below as judgment, and they point the same way.

Recommendation for the maintainer (the ADR stays Proposed):

1. Do not make composition the default authoring path for the four-variant App Service network family. By the rule it does not qualify, and at four variants the tooling costs 774 lines against 136 inline lines; M6 puts the break-even near 35 variants.
2. Keep the prototype as an opt-in experiment. Opting out means removing the three files and their audit entries, and the fences remain literal Mermaid either way. Removing a single entry is possible, but the tests exercise the live spec, so removing the last entry that uses an extension or an overlay also means adapting the tests that mutate it. While the four fixtures are enrolled, a hand edit of their fences fails the test until the spec is updated and `--write` is run.
3. Decide per family. The one family where the label-free comparison finds large duplication is the language-tutorial topology: 24 diagrams that differ in the one line that names the runtime (commit `3429ca0`, owned by #288). The prototype has no parameter substitution and so demonstrates nothing for them, and they break the grammar, so they need re-authoring first. If #288 re-authors them as one base with four runtime labels, M6 suggests a break-even near 20 diagrams if every further diagram were a one-line entry (Inferred), and this protocol should be run again on that family.
4. For #284 to #288, adopt the grammar and treat composition as optional.

## 6. Exceptions and Limits

- **Layout stays per variant.** The 15 hints are Dagre tuning under Mermaid 10.9.1, and `&nbsp;` padding is a rendering workaround. Stable identifiers are not stable placement (see sections 7 and 10 of the grammar page), so no placement claim is made.
- **Combined views are not published.** Composing both extensions, with and without the failure overlay, passes the grammar parser and renders (12 nodes, 5 containers and 12 edges; with the overlay 13, 5 and 14). The screenshots show the base nodes once, two separate customer VNets and the numbered paths. They also show entry arrows that appear to run through container titles and small text at 390 px; neither was measured. Publishing such a view needs its own hints and a full review.
- **Rendering is checked outside CI.** A standalone check with Mermaid 10.9.1 in headless Chrome parsed and rendered the four generated outputs and the two combined views at 1440x900, at 390x844 and at 720x450 with device scale 2 (an emulation of 200% browser zoom), in the light and dark themes: 36 checks, no parse error, no console error, and the expected node, container and edge counts. It is not the published page, so its appearance differs from the site, and neither the site's own zoom overlay nor real browser zoom was exercised. The author read the screenshots; no human approved them, and they are not committed.
- **Topology only.** The generator rejects other genres. The `runtime-request-sequence` diagram named above is untouched.
- **Extensions and overlays that no diagram uses** have their structure and field types checked, but not their graph-dependent validity (references, containers, conflicts), which is validated through the diagrams that use them.
- **Write safety.** `--write` refuses unsafe pages as described in section 4. Pages are written one after another and not atomically; with one enrolled page, a failed write leaves at most that file, which git restores. The binary-mode output of `--print` is covered by no test on Linux, where text and binary output are identical.
- **The frontmatter comparison** reads the canonical flow-list style (`based_on: [...]`) that the repository's YAML style check enforces.
- **No parameter substitution.** The 24 language-tutorial diagrams are not covered (see section 1).
- **No official Azure icons.** Mermaid 10.9.1 flowcharts do not bundle icon packs (grammar page, section 4).
- **Enrollment has a price.** While the four fixtures are enrolled, a hand edit of their fences fails the test until the spec is edited and `--write` is run.

## 7. Open Items

Not claimed by this page, and left to the maintainer or to later work:

- Human visual review of any render, including the combined views and the legibility at narrow widths.
- Real browser zoom and the site's own zoom overlay, which the standalone check does not exercise.
- Execution on Windows, including the newline handling of `--print` output and symlink behavior.
- A reproducible layout-stability measurement (#289), which the grammar page also defers.
- Appearance on the published site after deployment.
- Accepting or rejecting the recommendation, the ADR status and closing #283.
- Whether the four enrolled fixtures should stay enrolled.
- Re-authoring the language-tutorial diagrams against the grammar (#288) before any shared template could apply.
- Sibling guides: no adoption is claimed and none was checked.

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
