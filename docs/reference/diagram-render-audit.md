---
title: Diagram Render Audit Protocol (#395)
slug: diagram-render-audit
doc_type: reference
section: reference
summary: Minimum protocol and reusable checklist for judging how a Mermaid diagram renders on the published site, with a dated baseline comparison of one fault topology and one sequence diagram recorded as agent-run measurements, and the rules for the render evidence of the migration issues.
topics: [diagrams, documentation-standards, accessibility]
products: [azure-app-service]
content_sources:
  references:
    - type: self-generated
      justification: Measurements made on 2026-11-03 and 2026-11-04 (UTC) in a local build of this repository with a headless browser, as described in section 1. The page makes no Azure-behavior claim, and the measurements describe a local build, not the deployed site.
---

# Diagram Render Audit Protocol (#395)

This page records the protocol that issue [#395](https://github.com/yeongseon/azure-app-service-practical-guide/issues/395) asks for, under the validation parent [#289](https://github.com/yeongseon/azure-app-service-practical-guide/issues/289), and the first comparison made with it. A diagram that parses can still render badly: too small to read, unreadable in one color scheme, drawn through its own labels, or unusable without a pointer. The protocol therefore samples one network and fault topology and one non-topology (sequence or decision) diagram, looks at them in the light and dark schemes at desktop, narrow and zoomed widths, and records what was measured, what was only looked at, and what was not examined.

It adds no harness, CI step or committed image. The [composition ADR](adr-diagram-composition.md) keeps derived renders out of the repository, and #289 still owns the final verification. The first comparison is a baseline of the diagrams as they are today: all 405 entries of the [diagram manifest](diagram-inventory.md) are `not-started`, so it contains no before and after pair. Issue #395 stays open for maintainer review, and until the maintainer adopts it this page is a proposal that the migration issues can cite.

## 1. Basis

| Item | Value |
|---|---|
| Source | `main` at `b879caba3e460eeb62e99d000d74d0d3e3fb47f9`, built with `mkdocs build --strict` (MkDocs 1.6.1 with mkdocs-material 9.7.1, 255 pages) and served from the local machine. It is not the deployed site. |
| Renderer and browser | Mermaid 10.9.1, the version pinned in `mkdocs.yml` and loaded from unpkg. Google Chrome 145.0.7632.67, headless, on Linux x86_64, driven by Playwright 1.64.1 over the Chrome DevTools Protocol (CDP). One browser and one operating system. |
| Samples | **T**: `topology-grammar-v1-appservice-fault-overlay`, the fault overlay of [section 8.4 of the grammar](diagram-topology-grammar.md#84-overlay-dns-and-egress-fault-evidence-overlay), a topology with a customer VNet, two subnets, a Private Endpoint NIC and a fault. **S**: `request-path-sequence`, the sequence diagram under [End-to-end request path](../platform/request-lifecycle.md#end-to-end-request-path), a non-topology diagram. |
| Recorded (UTC) | Screens and a first overlay check on 2026-11-03 from 23:51Z to 23:53Z; the accessibility tree on 2026-11-04 at 00:11Z; SVG boxes, the zoom overlay and synthetic touch from 00:51Z to 00:54Z; painted colors, geometry checks, controls, accessible names and the Tab walk from 08:02Z to 08:03Z; the overlay close paths and the mouse drag from 08:15Z to 08:26Z. In Asia/Seoul that is 08:51 to 17:26 on 2026-11-04. |
| What the dates mean | When the measurements were made against a local build. They are not an Azure verification and say nothing about the deployed site on those days. |
| Retention | The raw output (JSON), the screenshots and the measuring scripts were not committed: the ADR keeps derived renders out of the repository, and #395 asks for no new harness. The tables below are the record, so the measurements are authoring observations in the sense of [section 7 of the grammar](diagram-topology-grammar.md#7-progressive-views) and not retained Golden `Observed` artifacts. |
| Who read the screenshots | The agent that took them. No person reviewed them. |
| Claim labels | **Measured**: a value read in a recorded run. **Source**: what a repository file says at the commit. **Inferred**: an explanation drawn from several measurements. **Not proven**: a limit of the evidence. |

## 2. Protocol

The minimum protocol is eight steps.

1. **Pin the run.** Record the source commit, the build command with the generator versions, the Mermaid version, the browser and operating system, and the UTC time. Build the site from the commit under review and serve it locally, because the deployed site can differ.
2. **Choose the sample.** One network or fault topology diagram and one non-topology diagram (a sequence or decision diagram) are the minimum. A migration pull request takes them from the diagrams it changes; when it changes none of one kind, it says so and uses T or S of this page for that kind. Record the manifest `diagram_id` and the page of each.
3. **Render the matrix.** Each sample in the light and the dark scheme at the four views of the table below, which is 16 views per pair. Zoom is emulated through the viewport and the device pixel ratio, which stands in for real browser zoom and is not the same thing. Screenshots are for reading and are not committed.
4. **Measure the SVG, not its host.** Material for MkDocs attaches each Mermaid diagram in a closed shadow root, so page scripts and ordinary DOM queries cannot see its SVG. In the recorded runs the SVG was reached through CDP `DOM.getDocument` with `pierce: true` (see Sources), resolved once and kept as a remote object, because opening the zoom overlay moves the host element in the DOM. From the SVG read its box and `viewBox` (scale is the box width divided by the `viewBox` width, and effective text is the computed `font-size` times the scale), the computed `fill`, `stroke`, `stroke-width`, `stroke-dasharray` and text color of what is painted, and the boxes of nodes, containers and labels. Two traps were met. On S the host was 1086 CSS px wide while the SVG is capped at 1033 px, so the host box overstated the scale by 5%. For sequence text the `fill` of the `text` element is the box color, and the visible color is on its `tspan`. Flatten translucent colors over the backdrop they sit on before taking a contrast ratio.
5. **Prove that each detector can fail.** A check that has never failed shows nothing, so run it on a variant that must fail and record that it did. Two were used here: the container-title crossing check on the same source with the `&nbsp;` padding of its three container titles removed (section 4.3), and the Tab walk on a page whose diagram host was given `tabindex="0"` (section 4.5).
6. **Exercise the shipped controls.** Open the zoom overlay by click, and by tap at 390 px; zoom with the wheel; pan with the mouse and by touch; close it by Escape, by the close button and by a click on the area outside the card. Record the SVG size at open and after each step, any clipping by the viewport, whether a pan or zoom survives the release of the pointer, the painted contrast against the card the overlay draws, where keyboard focus goes, and the ARIA attributes present.
7. **Read the render and say who read it.** Look at the screenshots for what numbers do not show: control plane and data path, containment, fault meaning, overlaps. Say whether the agent or a person looked; an agent's reading is not a human review.
8. **Record the result and the limits.** Fill the checklist of section 3, state what was not examined, and keep failed, partial and not-examined results as results. A baseline has no before value; a migrated diagram is compared with its pre-migration render (section 6).

| View | Viewport (CSS px) | Device pixel ratio | Stands for |
|---|---|---|---|
| desktop | 1440 x 900 | 1 | a wide window at 100% |
| narrow | 390 x 844 | 2 | a phone |
| 200% | 640 x 512 | 2 | a 1280 px window at 200%, emulated |
| 400% | 320 x 256 | 4 | a 1280 px window at 400%, emulated; the 320 x 256 size is the one that [Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) uses |

## 3. Reusable checklist

One row per check. A migration pull request copies the rows into the Validation section of its description and fills them (section 6). The reference values are recorded to inform the reader's judgment; this page decides no conformance.

| # | Check | How to observe | Reference value |
|---|---|---|---|
| 1 | Render health | No Mermaid error drawing for the diagram, and no console error or failed request caused by it. Name every message that no diagram caused. | None. |
| 2 | Fit and text size | No horizontal scrolling of the page at 390 and 320 CSS px. SVG width, scale and effective text size in each view. | [SC 1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) lists diagrams among content that may need two-dimensional layout. The criteria cited on this page set no minimum text size; [SC 1.4.4](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html) asks that text can be resized up to 200 percent without loss of content. |
| 3 | Contrast on the page | Painted text, edge and outline colors against the backdrop they sit on, in both schemes. | The grammar's own criteria: text inside a node at least 7:1, and every stroke at least 3:1 on both surfaces. [SC 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html): 4.5:1 for text. [SC 1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html): 3:1 for graphical objects. |
| 4 | Contrast in the zoom overlay | The same painted colors against the card the overlay draws, in both schemes. | As row 3. |
| 5 | Icons and non-color cues | Count image, `use` and icon elements. List each cue other than color that the diagram relies on. | [SC 1.4.1](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html): color is not the only visual means of conveying information. |
| 6 | Control plane and data path (topology) | Edge and node classes compared by line pattern, width, outline style and label prefix, not by color. | Grammar sections 2 and 5. |
| 7 | VNet and Private Endpoint containment (topology) | Node boxes inside the VNet and subnet boxes where the topology puts them, and outside where it does not. | The topology that the page documents. |
| 8 | Edge and label hygiene | No edge crosses container title text or an unrelated node, and no label box is crossed by another edge. Run the check on a variant that must fail. | Grammar section 10: an edge must not cross container title text. |
| 9 | Fault meaning (fault diagrams) | Fault edges and nodes carry a text prefix and a cue other than color, and the scenario says that it is illustrative and not a measurement. | Grammar section 5, claim prefixes. |
| 10 | Accessible name | `accTitle` and `accDescr` present as `aria-labelledby`, `<title>` and `<desc>` on the SVG, exposed in the accessibility tree, with the diagram text exposed too. | Grammar section 6: every Mermaid diagram includes both ([Mermaid accessibility](https://mermaid.js.org/config/accessibility.html)). |
| 11 | Keyboard, focus and ARIA | The diagram, or the control that enlarges it, is reachable and operable without a pointer (a Tab walk, with a control). Where focus goes when the overlay opens, and which ARIA attributes it has. | [SC 2.1.1](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html): all functionality is operable through a keyboard interface. |
| 12 | Zoom overlay size, clipping and touch | SVG size at open against inline, clipping at 390 px, wheel steps and touch steps. | None. |

## 4. First comparison (baseline)

Every value in this section is **Measured** in the runs of section 1 unless a row or bullet says otherwise. Light and dark SVG sizes are identical in every view. The nominal text size is 16 px for every label measured: on T 14 node and container label spans and 12 edge label spans, on S 8 actor texts and 6 message texts.

### 4.1 Fit and effective text size

| View | Viewport, DPR | T SVG width | T scale | T text, CSS px | T text, device px | S SVG width | S scale | S text, CSS px | S text, device px |
|---|---|---|---|---|---|---|---|---|---|
| desktop | 1440 x 900, 1 | 1086 | 0.637 | 10.2 | 10.2 | 1033 | 1.000 | 16.0 | 16.0 |
| narrow | 390 x 844, 2 | 358 | 0.210 | 3.4 | 6.7 | 358 | 0.347 | 5.5 | 11.1 |
| 200% | 640 x 512, 2 | 608 | 0.356 | 5.7 | 11.4 | 608 | 0.589 | 9.4 | 18.8 |
| 400% | 320 x 256, 4 | 288 | 0.169 | 2.7 | 10.8 | 288 | 0.279 | 4.5 | 17.8 |

- The page did not scroll horizontally in any of the 16 views.
- The SVG is fitted to the width of the content, so its width in device pixels stays between 1033 and 1216 for both samples when the browser zoom changes: T is 1086, 1216 and 1152 device px wide at 100%, 200% and 400% (608 x 2 and 288 x 4), and its text stays at 10.2, 11.4 and 10.8 device px. **Inferred**: browser zoom does not enlarge the text of these diagrams. Only the emulated views were measured.
- Each page load logged one console error: a request to the GitHub API for the latest release of this repository, which returned HTTP 404 in the last run. It is not a diagram asset, and it is consistent with the repository widget in the theme's header, which was not confirmed. No console message came from a diagram, and no Mermaid error drawing appeared.

### 4.2 Painted contrast on the page

The ratios come from the computed styles of the painted elements, not from the theme variables. T, with the four node roles that the fixture uses:

| Painted element of T | Light | Dark |
|---|---|---|
| `baseNeutral` text on its fill (client, ingress, storage_db) | 14.95 | 14.95 |
| `focusActive` text on its fill (app_runtime, vnet_integration, pe_storage) | 14.30 | 14.30 |
| `bandMuted` text on its fill (control_plane, identity, telemetry) | 16.46 | 16.46 |
| `stateFault` text on its fill (dns_out, fault_note) | 8.43 | 8.43 |
| Outlines of the 11 nodes (`#287ce4`, `#707e93`, `#da495d`) against the page | 4.12 | 3.90 |
| Outlines of the 3 containers (`#287ce4`, dashed) against the page | 4.12 | 3.90 |
| Container titles against the page | 9.80 | 8.04 |
| The 9 normal edges, and the text of all 12 edge labels on their own label background | 9.80 | 8.04 |
| The 3 fault edges (`#da495d`) against the page | 4.12 | 3.90 |

These equal the values of Table 6.1 of the [grammar](diagram-topology-grammar.md#6-visual-system) for the four roles that this fixture uses. Node fills are static, so the text contrast does not change between the schemes.

S:

| Painted element of S | Light | Dark |
|---|---|---|
| Actor text on its box, and message text against the page | 9.80 | 8.04 |
| Outlines of the 8 actor boxes (`#0091eb`, 1 px) against the page | 3.36 | 4.79 |
| Message lines (1.5 px, dotted for responses) against the page | 9.80 | 8.04 |
| The 4 lifelines (2 px, the theme color at 0.32 alpha) against the page | 2.23 | 2.53 |

Both lifeline ratios are below the 3:1 that [SC 1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) uses for graphical objects. Whether a lifeline is a graphical object that the criterion applies to was not decided here.

### 4.3 Topology geometry and fault meaning (T)

- **Containment.** The bounding boxes (1 px tolerance) of `vnet_integration` lie inside `subnet_int` and `vnet_out`, and those of `pe_storage` inside `subnet_pe_out` and `vnet_out`; both subnets lie inside `vnet_out`. The other nine nodes (`client`, `control_plane`, `ingress`, `app_runtime`, `identity`, `storage_db`, `telemetry`, `dns_out`, `fault_note`) lie inside no container. That agrees with two placements that the grammar states for its fixtures: the Private DNS zone outside both containers (section 8.3) and the front-end and worker roles outside customer containers (section 8.2).
- **Control plane and data path.** The 12 edges fall into five classes that differ by line pattern and width as well as by position and label text:

| Edge class | Edges | Pattern and width | Label prefix |
|---|---|---|---|
| Control plane | control_plane to ingress, control_plane to app_runtime | dotted, 2 px | `[Configured]` |
| Identity and telemetry | app_runtime to identity, app_runtime to telemetry | dotted, 2 px | `[Configured]` |
| Data path | client to ingress, ingress to app_runtime, app_runtime to vnet_integration | solid, 2 px | `[Configured]` |
| Unused private path | vnet_integration to pe_storage, pe_storage to storage_db | dotted, 2 px | `[Configured] unused` |
| Fault | app_runtime to dns_out, vnet_integration to storage_db, dns_out to fault_note | solid, 3 px, `#da495d` | `[FAULT / Illustrative]` |

- **Nodes.** The nodes `control_plane`, `identity` and `telemetry` have a dashed outline (`4px, 3px`) and the other eight have solid outlines. All nine normal edges use one color (`#36464e` in the light scheme), so no control-plane or data-path distinction rests on color.
- **Fault meaning.** The three thick edges are exactly the three whose labels begin with `[FAULT / Illustrative]`. The nodes `dns_out` and `fault_note` carry the fault fill and a 3 px outline. The text of `fault_note` begins with `[Illustrative scenario - not a measurement]`, and `dns_out` reads `[unlinked to VNet]`. The fault is therefore marked by width, label text and a callout as well as by color.
- **Edges and container titles.** None of the 301 sample points of any of the 12 edge paths falls inside the 111 character boxes of the container titles (1 px margin). The detector can fail: on the same source with the three `&nbsp;` runs removed from the container titles, two edges cross the title text, app_runtime to vnet_integration at 56 points and vnet_integration to pe_storage at 37. No edge passes through an unrelated node box (2 px inset). Sampling at 301 points per path can miss a crossing that is shorter than the spacing between samples, which is about 1/300 of the path length, so a zero here means that no sample hit, not that no crossing exists.
- **Edges and label boxes.** One of the 12 label boxes is crossed by another edge: the box of the label `[FAULT / Illustrative] 1. Lookup returns public IP` contains 5 of the 301 sample points of the dotted identity-token edge. In the 3x crop that the agent read, the dotted line meets the upper left corner of the label and the text stays readable. Every label box contains between 5 and 85 points of its own edge, which shows that labels and edges are paired correctly and that the detector sees points inside boxes.

### 4.4 Zoom overlay

The overlay is `docs/javascripts/mermaid-zoom.js` with the rules of `docs/stylesheets/extra.css`. Size at open and after zoom steps:

| Case | Inline SVG width | SVG width at open | Text, inline to at open | Clipped by the viewport at open |
|---|---|---|---|---|
| T, desktop | 1086 | 450 | 10.2 to 4.2 | none |
| S, desktop | 1033 | 450 | 16.0 to 7.0 | none |
| T, 390 px | 358 | 450 | 3.4 to 4.2 | 30 px on each side |
| S, 390 px | 358 | 450 | 5.5 to 7.0 | 30 px on each side |

- Each wheel notch adds 0.1 to the scale, which is 30 CSS px of SVG width. On desktop, T measured 1049.9 px wide after 20 notches and 1199.9 after 25 (inline 1086), and S 1049.9 after 20 (inline 1033). After 35 notches the text is 14.1 px on T and 23.2 px on S. **Source**: the scale is clamped to 0.3 to 5 at lines 108 and 161 of the script.
- A two-finger spread from 90 to 190 CSS px changed the transform scale from 1.5 to 3.17, and a one-finger drag of (-50, -40) moved the host by the same amount. These events were synthesized through CDP at 390 px; no real touch device was used.
- Escape and a click on the close button (a `<button>` whose `aria-label` is `Close`) closed the overlay in all four cases, on both samples, by mouse on desktop and by tap at 390 px, and the inline diagram came back at its original size. A click or tap on the dark area outside the card did not close it in any of the four cases; Escape then did. The element at that point is `.mermaid-zoom-container`, which fills the overlay, so the overlay itself is never the target of the handler at lines 97 to 99 of the script (**Inferred** from that element and the **Source**).
- A mouse drag of (80, 40) CSS px moved the diagram only while the button was held (`translate(80px, 40px)` at scale 2, after 5 wheel notches). On release the transform returned to `translate(0px, 0px) scale(1.5)`, and the overlay element had been added a second time and the first removed. The release produces a `click` on the diagram host, whose own handler (lines 181 to 184) calls `openDiagram`, which closes the existing overlay and builds a new one (lines 73 to 75), and closing resets the scale to 1.5 and the pan to zero (lines 54 to 56). This held on both samples with mouse events synthesized through CDP, and wheel zoom stayed until such a click (**Measured**; the mechanism is **Inferred** from the script).
- In the dark scheme the card stays white (`rgb(255,255,255)` in both schemes). **Source**: `extra.css` line 71 sets `background: #fff` for the host inside the overlay. Painted contrast against that card:

| Painted element | Light scheme | Dark scheme |
|---|---|---|
| T normal edges, and T container titles | 9.80 | 1.33 |
| T edge label text, on its own label background | 9.80 | 8.04 |
| T fault edges | 4.12 | 4.12 |
| S message text and message lines | 9.80 | 1.33 |
| S lifelines | 2.23 | 1.08 |
| S actor text, on its own box | 9.80 | 8.04 |

- The open overlay has no `role`, `aria-modal` or `aria-label`. Right after it opens, the active element is `body`, and the next three Tab presses moved focus to links of the page behind the overlay, so none of the three landed inside it. **Source**: the script sets one ARIA attribute, the `aria-label` of the close button, opens the overlay with a `click` handler only, and has one key handler, for Escape (lines 62 to 64), so zooming and panning need a mouse or touch.

### 4.5 Accessibility

- **Accessible names.** All 6 diagrams of the grammar page have `<title>`, `<desc>` and `aria-labelledby`, from `accTitle` and `accDescr`. Neither of the 2 diagrams of the request-lifecycle page (a sequence and a flowchart) has any of the three. In Chrome's accessibility tree the four App Service fixtures appear as `graphics-document` nodes named by their `accTitle` with the `accDescr` as description; the two `graphics-document` nodes of the request-lifecycle page have an empty name and description. The diagram text is exposed as static text in both. No screen reader was used.
- **Keyboard.** A Tab walk that ran until an element repeated passed 109 distinct focus stops on the grammar page and 100 on the request-lifecycle page, and none of them was inside a diagram. The detector can find one: with `tabindex="0"` added to the host, the walk found exactly 1 stop inside a diagram on each page. The measured host is a `div` with no `tabindex`, `role` or `aria-label`, and **Source**: the script gives it a click handler and a pointer cursor and nothing else.
- **Motion.** **Source**: neither `extra.css` nor the script contains a `prefers-reduced-motion` rule, and the overlay fades with a 0.2 s opacity transition. The setting was not exercised.

### 4.6 What was read from the screenshots

All of this is the agent's reading of its own screenshots, not a human review.

- **T, desktop, both schemes.** The control-plane node sits on the top band beside the caller, with a dashed outline and dotted edges, and the request path runs down the middle in solid arrows. The dashed blue customer VNet holds the integration subnet and the private-endpoint subnet, each with its NIC node. Storage (a cylinder), the Private DNS zone (a hexagon), identity and telemetry sit outside it. The fault shows as three thick red edges with the `[FAULT / Illustrative]` prefix and a red callout box. In the dark scheme the nodes keep their light fills with dark text, while edges and labels turn light.
- **T and S, narrow and zoomed views.** Every label is present and nothing overflows. The agent could read the labels at the saved resolution, but the effective text is 3.4 px (T) and 5.5 px (S) at 390 px, and whether a person can read it was not tested.
- **S, both schemes.** Four participants, solid request arrows and dotted responses. The lifelines are faint but visible on the page.
- **Overlay, dark scheme.** On the white card the message text and lines of S and the edges and container titles of T are very faint, while node fills, fault edges, edge-label boxes and the dark actor boxes stay readable.
- **Overlay, 390 px.** The 510 px card is wider than the viewport and the diagram is cut at both edges at open (the identity and telemetry nodes). The hint text wraps over the page text behind it.
- **Icons.** Neither sample has an image, `use` or icon element, so the icon criterion of #395 has nothing to judge here. The one icon-like glyph is the hover magnifier, a pseudo-element of `extra.css` that also appears at the corner of the open card.

## 5. Findings

These are observations. None is fixed here, and this change files no issue for them: whether each belongs to the zoom script, to the migration issues or to #289 is for the maintainer to decide.

| ID | Finding | Claim level |
|---|---|---|
| F1 | The text of both samples keeps about the same size in device pixels when the browser zoom changes (T: 10.2, 11.4 and 10.8 device px at 100%, 200% and 400%). | Inferred from emulated zoom |
| F2 | At 390 px the effective text is 3.4 px on T and 5.5 px on S. Legibility for a person was not tested. | Measured; legibility not proven |
| F3 | The zoom overlay opens with the SVG at 450 CSS px, 41% (T) and 44% (S) of the inline desktop text size. About 20 to 25 wheel notches reach the inline size, and at 390 px it opens 30 px wider than the viewport on each side. | Measured |
| F4 | In the dark scheme the overlay card stays white, so light-on-white elements fall to 1.33:1 (T edges and container titles, S text and message lines) and to 1.08:1 (S lifelines). | Measured; Source (`extra.css` line 71) |
| F5 | The diagram cannot be reached by keyboard (0 of 109 and 0 of 100 Tab stops), so its overlay cannot be opened without a pointer, and once open the only key the script handles is Escape. The open overlay has no dialog semantics, does not take focus and lets Tab move focus to links behind it. | Measured; Source |
| F6 | The two diagrams of the request-lifecycle page have no accessible name, while all 6 on the grammar page have one. | Measured |
| F7 | The sequence lifelines are 2.23:1 (light) and 2.53:1 (dark), below the 3:1 reference for graphical objects. Whether they are graphical objects was not decided. | Measured; applicability not proven |
| F8 | On T, the dotted identity-token edge enters the box of the first fault label (5 of 301 points). The label stays readable. | Measured; agent reading |
| F9 | In the overlay a mouse drag pans only while the button is held; the release resets zoom and pan to scale 1.5 and no offset, because the release fires a click on the diagram host that re-opens the overlay. | Measured with synthesized mouse events; mechanism Inferred from the Source |
| F10 | A click or tap outside the card does not close the overlay (0 of 4). Escape and the close button do. | Measured; mechanism Inferred from the Source |

## 6. Render evidence for the migration issues

The manifest assigns 395 entries to five trackers, and 88 executable child issues slice that work. All 88 were open at the time of writing, and none of the 405 manifest entries has left `not-started`. Each of the 88 child issues already asks for a comparison of the actual render before and after, on narrow and desktop views in the light and dark themes (some add zoom), so this protocol is the procedure they can cite. No pull request migrates a diagram yet: the open ones, #239, #249, #250 and #258, are not diagram migrations. No per-child render evidence therefore exists, and this page creates none.

| Tracker | Scope (from the issue title) | Manifest entries | Child issues | Render evidence at this commit |
|---|---|---|---|---|
| [#284](https://github.com/yeongseon/azure-app-service-practical-guide/issues/284) | migrate runtime and deployment diagrams | 24 | #299 to #304 (6) | None |
| [#285](https://github.com/yeongseon/azure-app-service-practical-guide/issues/285) | migrate networking and dependency diagrams | 38 | #305 to #310 (6) | None |
| [#286](https://github.com/yeongseon/azure-app-service-practical-guide/issues/286) | migrate scaling, health and lifecycle | 13 | #311 to #313 (3) | None |
| [#287](https://github.com/yeongseon/azure-app-service-practical-guide/issues/287) | migrate incident and lab visuals | 143 | #314 to #347 (34) | None |
| [#288](https://github.com/yeongseon/azure-app-service-practical-guide/issues/288) | migrate remaining guide diagrams | 177 | #348 to #386 (39) | None |
| [#289](https://github.com/yeongseon/azure-app-service-practical-guide/issues/289) | validate migration coverage and rendering | 0 (owns no diagram) | Final verification after all five are migrated | None; this page defines no tooling for it |

The 10 remaining entries are excluded from migration and have no owning tracker. The sample S is an entry of #284, and its body still equals the body whose `baseline.source_sha256` the manifest records, so the S measurements above are the before values for that entry.

Each child pull request records its render evidence in the Validation section of its description, so that this page is not edited per child and cannot go stale, and the pull request is linked from its tracker (#284 to #288). The record has these fields:

1. The run pin of step 1, with the head commit of the pull request.
2. The sample of step 2, by manifest `diagram_id` and page, and the reason for the choice.
3. A before value and an after value for each row of the section 3 checklist, from the same views and the same method. The before render is the pre-migration body, identified by the `baseline.source_sha256` of its manifest entry and retained in Git history; the after render is the migrated body. Every migrated diagram gets rows 1, 2 and 10 (render health, fit and text size, accessible name) in both schemes, and the sampled pair gets all rows.
4. A verdict for each row: `no change`, `better`, `worse` or `not examined`. A `worse` row is fixed or explained in the description, not left out.
5. Who read the screenshots. A person's review is recorded as such, and an agent's is not counted as one.
6. What was not examined, as in section 7.

Screenshots, if attached, stay on the pull request and are not committed, as the ADR requires. Final verification stays with #289.

## 7. What this does not establish

- Anything beyond one browser and one operating system: Chrome 145 headless on Linux. No other browser, no mobile browser and no real device was used.
- Real browser zoom or text-only zoom. Zoom was emulated through the viewport and the device pixel ratio.
- A review by a person. The screenshots were read by the agent that took them, and legibility for a person at any width was not tested.
- Screen reader behavior. The accessibility tree is Chrome's, and forced-colors mode, high-contrast themes and reduced-motion settings were not exercised.
- Coverage of the manifest. Two samples and one site build say nothing about the other manifest entries.
- A regression. This is a baseline: all 405 entries are `not-started`, so no before and after pair exists.
- Stability of the renders. Mermaid is pinned at 10.9.1 but loaded from a CDN, the fonts were the loaded Roboto, and a local build can differ from the deployed site.
- A pass or fail for text size. The cited criteria set no minimum, the reference values of section 3 are for the reader's judgment, and no conformance is claimed.
- Checkability against an artifact. The raw output is not retained, so the numbers can be re-derived by repeating the protocol on the commit, and not re-read.
- Independent reproduction. All runs were made by the same agent in one environment, so repeatability at most is shown and independence is not met.
- Input from real devices. Mouse events and touch events were synthesized through CDP, so a physical mouse, a real pinch and a real touch drag were not used.

## See Also

- [Azure Topology Visual Grammar (v1)](diagram-topology-grammar.md)
- [Diagram Composition Prototype (#283)](diagram-composition-prototype.md)
- [ADR: Diagram Composition](adr-diagram-composition.md)
- [Diagram Inventory](diagram-inventory.md)
- [Golden Evidence Model](golden-evidence-model.md)
- [Reference](index.md)
- [Issue #395: publish real render audit protocol and first comparison](https://github.com/yeongseon/azure-app-service-practical-guide/issues/395)
- [Issue #289: validate migration coverage and rendering](https://github.com/yeongseon/azure-app-service-practical-guide/issues/289)

## Sources

- [Understanding SC 1.4.1: Use of Color (W3C)](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html)
- [Understanding SC 1.4.3: Contrast (Minimum) (W3C)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
- [Understanding SC 1.4.4: Resize Text (W3C)](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html)
- [Understanding SC 1.4.10: Reflow (W3C)](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html)
- [Understanding SC 1.4.11: Non-text Contrast (W3C)](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)
- [Understanding SC 2.1.1: Keyboard (W3C)](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html)
- [Accessibility Extensions (Mermaid)](https://mermaid.js.org/config/accessibility.html)
- [DOM domain, getDocument (Chrome DevTools Protocol)](https://chromedevtools.github.io/devtools-protocol/tot/DOM/#method-getDocument)
