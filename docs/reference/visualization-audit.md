---
title: Visualization Audit (#397)
slug: visualization-audit
doc_type: reference
section: reference
summary: Browser audit of the three published non-Mermaid visuals of the visualization section, with the disposition chosen for each, the check of their generator, data and MkDocs wiring, and the smallest corrections proposed for separate changes.
topics: [diagrams, documentation-standards, accessibility]
products: [azure-app-service]
content_sources:
  references:
    - type: self-generated
      justification: Measurements made on 2026-11-04 (UTC) in headless Chrome against the published site, and repository facts read at one commit, as described in section 1. The page makes no Azure-behavior claim, changes no visual, script, dataset or workflow, and records the measurements as unretained agent-run observations.
---

# Visualization Audit (#397)

This page records the audit that issue [#397](https://github.com/yeongseon/azure-app-service-practical-guide/issues/397) asks for. Three published surfaces of the visualization section are not Mermaid diagrams, so the [diagram inventory](diagram-inventory.md) kept them apart with a pending owner decision: the interactive Core Knowledge Graph, the interactive Troubleshooting Map and the learning-path graph containers. The audit rendered each of them in a real browser, exercised what can be exercised, checked the generator, the committed data and the MkDocs wiring, and chose one of the four dispositions that the issue allows for each. The dispositions are recorded in the diagram inventory.

It is an agent-run audit of the published site on one day with one browser. The measurements, the screenshots and the scripts are not committed, so section 1 states the method. The audit changes no page, script, dataset or workflow; the corrections that it proposes in section 7 are for separate changes.

## 1. Basis

| Item | Value |
|---|---|
| Published site | `https://yeongseon.github.io/azure-app-service-practical-guide/`, which redirects to `https://yeongseon.dev/azure-app-service-practical-guide/`. The pages were built from `main` at `3e6d950`. |
| Measured | On 2026-11-04 (UTC), in four scripted runs. |
| Browser | Google Chrome 145.0.7632.67 headless on Linux x86_64, driven by Playwright over the Chrome DevTools Protocol. One browser and one operating system. |
| Matrix | Each page at 1440 x 900 (scale 1) and 390 x 844 (scale 2), in the light palette (`default`) and the dark palette (`slate`). For the dark palette the palette toggle was clicked and the page was reloaded before measuring, so that the graph initialised under the dark palette. |
| Further runs | Search, filter, reset, one node click, Tab order, mouse wheel, mouse drag, a synthetic touch swipe (DevTools touch events, not a device), an HTTP `HEAD` request for every node link, a run with `unpkg.com` blocked, and a contrast measurement. |
| Instruments | The graph state (node and edge counts, zoom, the resolved label style) was read from the Cytoscape instance that the library keeps on the container, through its internal `_cyreg` property. Names and roles came from the Chrome accessibility tree. Screenshots were read by the agent that took them. |
| Claim labels | **Observed**: what the runs measured or showed on the published site. **Documented**: what a repository file states. **Inferred**: an explanation drawn from several observations. **Not Proven**: a limit of the evidence. |

## 2. The three visuals

All rows are **Documented**.

| Visual | Page | Data | Scripts and styles | Initialiser |
|---|---|---|---|---|
| Core Knowledge Graph | `visualization/core-knowledge-graph.md` | `assets/graph/core-knowledge.json` | `document-graph.js`, `document-graph.css`, Cytoscape from unpkg | An inline script on the page calls `initCoreKnowledgeGraph` on `DOMContentLoaded`. |
| Troubleshooting Map | `visualization/troubleshooting-map.md` | `assets/graph/troubleshooting-map.json` | `troubleshooting-map.js`, `document-graph.css`, Cytoscape from unpkg | An inline script on the page calls `initTroubleshootingMap`. |
| Language graph containers | `visualization/learning-paths.md` | None | None | None: four `div` elements with an id and a height, and no script. |

## 3. Core Knowledge Graph

**Observed** on the published page, unless a row says otherwise.

| Check | Result |
|---|---|
| Rendering | Draws in all four combinations of width and palette: 30 nodes, 69 edges and three canvases, after 3.3 to 5.3 seconds. |
| Controls | Searching `scal` highlights 1 node and dims 29. The type `concept` highlights 4 and dims 26. Reset View restores all 30 and clears the controls. |
| Links | All 30 distinct node targets return HTTP 200. A click on a node (tested on one) opens its page. |
| Label colour | The label colour resolves to `rgb(0,0,0)` in both palettes. Against the page background, `rgb(255,255,255)` in the light palette and `rgb(39,42,53)` in the dark one, that is a contrast ratio of 21:1 and 1.47:1 (4.5:1 is the WCAG AA minimum for normal text). The screenshots show the dark-palette labels as nearly unreadable. The console reports the style `font-family: var(--md-text-font-family, ...)` as invalid. |
| Text size | The label font is 11 px at a zoom of 0.70 on a 1440 px viewport (7.7 px effective) and at a zoom of 0.30 on a 390 px viewport (3.3 px effective). |
| Keyboard | Ten Tab presses from the search box visit the type selector, the Reset View button and then page links. The graph container (role `generic`, no name, no tabindex) and its canvases took no focus. |
| Accessible names | The type selector has an empty accessible name. The search box is named by its placeholder only. The Reset View button is named. |
| Text equivalent | 1 of the 30 node targets is linked from the body of the page. |
| Gestures | Four mouse wheel steps over the graph changed its zoom from 0.57 to 0.30 and scrolled the page by 0 px. A synthetic vertical touch swipe on the graph at 390 px panned the graph and scrolled the page by 0 px. |
| Selection panel | At the moment the page unloaded after a click, the "Selected" panel still read "None". |
| Library dependency | Cytoscape 3.30.4 and Mermaid 10.9.1 load from unpkg on every page. With unpkg blocked, the graph box shows "Loading visualization library..." and nothing else, and the console reports that Cytoscape.js is not loaded. |
| Layout at 390 px | No horizontal overflow. The three controls stack and fit the viewport. |
| Committed data | 30 nodes and 69 edges. The generator now produces more (section 6). |

**Disposition: retain as working interactive navigation.** The visual renders, answers its controls and every node link works, so its producer is not broken. Replacing it with a static Mermaid topology would remove the interaction, which the issue rules out. The defects above (the data snapshot, the dark-palette labels, the keyboard and name gaps, the gesture traps and the library dependency) are recorded and not fixed here.

## 4. Troubleshooting Map

**Observed** on the published page, unless a row says otherwise.

| Check | Result |
|---|---|
| Rendering | Draws in all four combinations of width and palette: 24 nodes, 57 edges and three canvases, after 3.7 to 5.5 seconds. |
| Controls | Searching `scal` highlights no node and dims all 24 (no label or topic matches). The category `startup` highlights 5 nodes and the type `playbook` highlights 8. Reset View restores all 24 and clears both selectors. |
| Links | All 24 distinct node targets return HTTP 200. A click on a node (tested on one) opens its page. |
| Label colour | Resolves to `rgb(0,0,0)` in both palettes, a contrast ratio of 21:1 in the light palette and 1.47:1 in the dark one. The screenshots show most dark-palette labels as nearly unreadable. |
| Text size | The label font is 12 px at a zoom of 0.64 on a 1440 px viewport (7.7 px effective) and at a zoom of 0.27 on a 390 px viewport (3.2 px effective). |
| Keyboard | Ten Tab presses from the search box visit the category selector, the type selector, the Reset View button and then page links. The graph container and its canvases took no focus. |
| Accessible names | Both selectors have an empty accessible name. The search box is named by its placeholder only. |
| Text equivalent | 5 of the 24 node targets are linked from the body of the page. |
| Gestures | Four mouse wheel steps over the graph changed its zoom from 0.67 to 0.20 and scrolled the page by 0 px. A synthetic vertical touch swipe on the graph at 390 px panned the graph and scrolled the page by 0 px. |
| Layout at 390 px | No horizontal overflow. The four controls stack and fit the viewport. |
| Committed data | 24 nodes and 57 edges. The generator now produces more (section 6). |
| Producer name | **Documented**: lines 301 and 310 of the page name `tools/build_troubleshooting_map.py`. No such file exists. |

**Disposition: retain as working interactive navigation**, for the reasons given for the core graph. The map has the same defects. The nonexistent producer name is a documentation error and is a proposal in section 7.

## 5. Learning-path placeholders

| Check | Result |
|---|---|
| Containers | **Observed**: four, `python-graph`, `nodejs-graph`, `java-graph` and `dotnet-graph`, each under the heading of its language. |
| Content | **Observed**: each has no child element, no text and no canvas, and the library holds no instance on it. |
| Appearance | **Observed**: empty boxes with a 1 px border, 400 px high, 1086 px wide on a 1440 px viewport and 358 px wide at 390 px, in both palettes. A screenshot shows the box under the Python heading with nothing in it. |
| Accessibility | **Observed**: no role and no name. |
| Initialiser and data | **Documented**: there is no script on the page, no function for them in `document-graph.js` or `troubleshooting-map.js`, and no learning-path dataset in `docs/assets/graph/`. |
| Generator | **Documented**: `tools/build_doc_graph.py` defines `--learning-paths` and never reads it. The page (line 270) tells readers to run it. |
| Companions | **Observed**: the three Mermaid diagrams on the page render; they are 842, 138 and 624 px high. |

**Disposition: remove only if justified and reviewed.** The removal is justified. There is nothing interactive to retain, and no producer to repair: the flag does nothing and no builder, data or initialiser exists. Writing a learning-path builder would be a new feature, which the issue excludes. This audit and its review are the justification and the review; the removal of the four containers and of the instruction is proposed as a separate change. Until it is made, the containers stay excluded from the migration counts. The page's three Mermaid diagrams remain in migration scope.

## 6. Generator, data and wiring

| Item | Finding |
|---|---|
| Generator | **Documented**: `tools/build_doc_graph.py` writes `core-knowledge.json` and `troubleshooting-map.json` to `docs/assets/graph/`. Its `main()` parses `--learning-paths` and never reads the result. |
| Generator against the committed data | **Observed**, by running the generator on `main` in a throwaway worktree: 159 documents with frontmatter. The core graph has 159 nodes and 75 edges (committed: 30 and 69) and the troubleshooting map has 77 nodes and 67 edges (committed: 24 and 57). Every committed node is in the new output; 129 and 53 nodes are new. The generator makes one node for each document, so 103 of the new core nodes carry the default type `concept`, and the new map has 52 playbooks where the committed one has 8. |
| History | **Documented**: the committed files date from 2026-04-27 (core) and 2026-04-08 (map). The generator has not changed since 2026-04-08. |
| Automation | **Documented**: no workflow, script or test runs or checks the generator. `tests/golden/test_repository_audit.py` asserts that CI does not invoke it. |
| What the pages promise | **Documented**: the front matter of the core page calls the graph an interactive visualization of "the entire documentation structure", and its text a "bird's-eye view of the entire Azure App Service Practical Guide". |
| MkDocs wiring | **Documented**: `mkdocs.yml` loads `document-graph.css`, and on every page Mermaid 10.9.1 and Cytoscape 3.30.4 from unpkg, `mermaid-zoom.js`, `document-graph.js` and `troubleshooting-map.js`. The three pages are in the navigation. `navigation.instant` is not enabled, so the inline initialisers run on each page load. |
| Style values | **Documented**: `document-graph.js` lines 104 and 105 and `troubleshooting-map.js` lines 105 and 106 pass CSS variables (`var(--md-text-font-family, ...)` and `var(--md-default-fg-color, #333)`) as Cytoscape style values. The wheel sensitivity is set to 0.3 and 0.25 (lines 218 and 279). |
| Producer name | **Documented**: the troubleshooting-map page names `tools/build_troubleshooting_map.py`, which does not exist; `tools/build_doc_graph.py` writes the map. |

**Inferred.** The committed data is consistent with a snapshot from a time when fewer documents carried the frontmatter that the generator reads. The producer works, and nothing keeps its output current. The CSS-variable style values explain the black labels, because the library reports them as invalid and falls back to black.

**Not Proven.** What the regenerated graphs would look like. They were not rendered, and 159 nodes may be too many for the layout.

## 7. Dispositions and proposed corrections

| Manifest key | Disposition | Reason |
|---|---|---|
| `docs/visualization/core-knowledge-graph.md#core-graph` | Retain as working interactive navigation (`excluded-retained-interactive-navigation`) | It renders, answers its controls and every link works. The defects are in the data and the implementation. |
| `docs/visualization/troubleshooting-map.md#troubleshooting-graph` | Retain as working interactive navigation (`excluded-retained-interactive-navigation`) | The same, with a wrong producer name on its page. |
| `docs/visualization/learning-paths.md#language-graph-containers` | Remove, justified and reviewed here, to be made separately (`excluded-remove-unwired-placeholders`) | Empty containers with no initialiser, data or working producer. |

The corrections below are proposals for separate changes. None is made here, and no issue was filed.

1. **Name the real producer.** In `troubleshooting-map.md` lines 301 and 310, replace `tools/build_troubleshooting_map.py` with `tools/build_doc_graph.py`. This is the smallest correction for the nonexistent reference.
2. **Decide the scope of the two graphs, then refresh them.** Either regenerate them with `python tools/build_doc_graph.py` and check that the graphs of 159 and 77 nodes are legible, or word the pages as a snapshot of a chosen set. Decide also whether a freshness check should exist, because nothing runs the generator.
3. **Remove the placeholders.** Remove the four empty containers and the `--learning-paths` instruction from the learning-paths page, and the unused flag from the generator.
4. **Fix the implementation defects of the two graphs**, one narrowly scoped change for each concern: resolved colours instead of CSS variables, so that the dark palette is legible; labelled selectors; a role, a name and a text equivalent for the graph; wheel and touch gestures that do not trap the page; a fallback when the library fails to load; and larger initial text at narrow widths.

## 8. What this does not establish

- Anything about screen readers. The accessibility tree is Chrome's, and no screen reader was used.
- Real touch devices, real browser zoom, other browsers, other operating systems or a slow network. The touch swipe was synthetic, and there was one browser on one operating system.
- How the regenerated graphs look, the hover and selection states, or any keyboard operation of the nodes, because nothing in the graph can take focus.
- Any Azure behavior.
- Reproduction by someone else. The measurements are unretained, the scripts are not committed, and no human review of this page or of the screenshots is recorded.

## See Also

- [Diagram Inventory](diagram-inventory.md)
- [Diagram Render Audit Protocol](diagram-render-audit.md)
- [Diagram Composition ADR](adr-diagram-composition.md)
- [Core Knowledge Graph](../visualization/core-knowledge-graph.md)
- [Troubleshooting Map](../visualization/troubleshooting-map.md)
- [Learning Paths](../visualization/learning-paths.md)
- [Issue #397: resolve ownership of three non-Mermaid navigation visuals](https://github.com/yeongseon/azure-app-service-practical-guide/issues/397)

## Sources

- [Understanding Success Criterion 1.4.3: Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
