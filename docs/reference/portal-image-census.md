---
title: Portal Image Census (#390)
slug: portal-image-census
doc_type: reference
section: reference
summary: Per-file census of the Portal screenshots, legacy PNGs and site images of this repository at one commit, with the registry, reference, collision, duplicate and origin facts that #390 asks for, a disposition for every file, and proposed batches for the remaining legacy-image work.
topics: [documentation-standards, evidence, images]
products: [azure-app-service]
content_sources:
  references:
    - type: self-generated
      justification: A census computed from the tracked files and the Git history of this repository at one commit, as described in section 1. The page makes no Azure-behavior claim, reads no image visually, and changes no image, registry, provenance record or reference.
---

# Portal Image Census (#390)

This page and its machine-readable companion [portal-image-census.json](portal-image-census.json) are the census that issue [#390](https://github.com/yeongseon/azure-app-service-practical-guide/issues/390) asks for, under the tracking issue [#135](https://github.com/yeongseon/azure-app-service-practical-guide/issues/135). The historical counts in #135 (113 legacy PNGs, four onboarded WebP assets and 286 direct references) describe a tree that no longer exists. This census reads the tree as it is: it records for every image file its registry, its references, its collisions and duplicates, and what the repository says and shows about where its bytes came from, and it proposes batches for the work that remains.

It is offline and read-only. It changes no image byte, deletes nothing, edits no registry, provenance record or Markdown reference, and runs nothing in Azure. No image was viewed: the census reads bytes, dimensions and records, and for the origin hint of section 4 it compares pixels. The per-file report is the retained artifact. The script that produced it is not committed, so section 1 states the method that anyone can repeat.

## 1. Basis

| Item | Value |
|---|---|
| Commit | `main` at `d1dde4a0f737da6e76780ab6cbeea0110ba33b68`, the base of the pull request that adds this page. That pull request changes no image, registry, provenance file or Markdown reference, so the census describes its result as well. |
| Computed | By a one-off script on 2026-11-04 (the `computed_at_utc` field of the report) with Python 3.10.12, Pillow 11.3.0, NumPy 2.1.0, PyYAML 6.0.2 and Git 2.34.1. It is a census of that commit, and it goes stale with the next change to an image, a registry or a reference. The live rules stay with the CI validator [`scripts/validate_capture_assets.py`](https://github.com/yeongseon/azure-app-service-practical-guide/blob/main/scripts/validate_capture_assets.py). |
| Inputs | The 114 tracked image files; `scripts/capture/manifest.yaml`, `legacy-assets.yaml`, `provenance.yaml` and `dimension-exceptions.yaml`; every tracked Markdown file; `mkdocs.yml` and `docs/main.html` for configuration references; and the Git history, which was complete (274 commits). A shallow clone cannot reproduce the `history` fields. |
| What counts as a reference | The `image_references` helper of the CI validator over every tracked Markdown file: a `shot()` call or an inline image path, with fenced code, HTML comments and inline code ignored. One change: a closing code fence may not carry an info string, as in CommonMark. The helper accepts one, and it misses one reference because of it (section 6). An image with no `shot()` call, no direct Markdown reference and no configuration reference is an orphan. |
| Origin hint | For each manifest WebP, the PNGs that the commit which added the file removed under `docs/assets` are compared with it. Both are converted to grayscale and resized to 480 px wide with the WebP's aspect (Lanczos), and the mean absolute difference (MAD) is taken, with the share of pixels that differ by more than 16 levels. The closest PNG is recorded, preferring the same directory and stem on a tie. A WebP counts as consistent with a re-encode when its MAD is at most 0.01 and the aspect ratios agree within 1%. The threshold was declared, not calibrated. |
| Claim labels | **Observed**: what the committed report shows for the commit. **Documented**: what a repository file states. **Inferred**: an explanation drawn from several observations. **Not Proven**: a limit of the evidence. The report is a derived artifact of tracked files, and it is not a Golden evidence run. |

## 2. The census at a glance

All values are **Observed** unless a row says otherwise.

| Fact | Value |
|---|---|
| Tracked image files | 114: 106 WebP, 6 PNG and 2 SVG |
| Registered in `manifest.yaml` | 106, all WebP. The identifiers are unique, equal the file stem, and 102 of them are path-qualified and 4 are short. |
| Pinned in `legacy-assets.yaml` | 6, all PNG, all 3148 x 2318 |
| Outside both registries | 2, `docs/assets/logo.svg` and `docs/assets/favicon.svg`, referenced from `mkdocs.yml` (and the favicon from `docs/main.html`) |
| `shot()` calls | 195, on 136 pages. Every identifier resolves, and every manifest entry is called at least once (1 to 12 times). |
| Direct Markdown image references | 16, on 13 pages, all to the six legacy PNGs; every one uses the canonical alt text exactly (0 mismatches) |
| Configuration references | 3 (`mkdocs.yml` twice, `docs/main.html` once) |
| Orphans | 0 |
| Provenance records | 8, all of kind `legacy_reencode`; none of kind `produced` |
| Dimension exceptions | 19: 13 WebP and the 6 legacy PNGs |
| Byte-identical groups | 8: seven pairs of Portal images and the two SVGs |
| Identical file stems | 1: the two legacy PNGs named `01-overview.png` |
| Core-name groups (same name once the section qualifier and number are dropped) | 6 |

The audit block of `legacy-assets.yaml` (reviewed 2026-10-15) reports 106 manifest entries, 106 WebP assets, 6 legacy PNGs, 16 direct legacy references, 0 orphans and 1 remaining stem collision. The census agrees with every one of those counts. The 16 direct references are not the 15 that the CI helper finds; section 6 explains the difference.

## 3. Disposition of every file

Each file has one disposition, which names what to do with it now, and any number of flags. No disposition changes a byte or deletes a file.

| Disposition | Files | Meaning |
|---|---|---|
| `retain-registered` | 93 | A manifest WebP that is referenced and conforms to the capture profile |
| `retain-registered-dimension-exception` | 13 | A manifest WebP that is referenced and is listed in `dimension-exceptions.yaml`; only a recapture under the profile removes the exception |
| `retain-legacy-pinned` | 6 | A legacy PNG pinned by hash and size, referenced directly from Markdown, all with a dimension exception (captured at device pixel ratio 2) |
| `retain-site-asset` | 2 | The site logo and favicon, referenced from the site configuration; they are not Portal captures |

No file is an orphan, unregistered or awaiting review. The flags are `no-provenance-record` (98 WebPs), `duplicate-content` (16 files), `core-name-collision` (14), `short-id` (4) and `identical-stem` (2).

## 4. Re-encoding or new capture

**Documented.** `provenance.yaml` holds 8 records, all `legacy_reencode`, which the file defines as a pre-profile PNG re-encoded to WebP without a recapture, and it holds no `produced` record, which would mark a capture made under a capture profile. The file says that captures made before the profile existed are left out and not stamped. So no image in the repository has a record of being captured under the profile, and 98 WebPs have no record of how their bytes were produced.

**Observed.** The origin hint (section 1) was computed for all 106 WebPs.

| Result | Value |
|---|---|
| WebPs for which the commit that added the file also removed a PNG that agrees with it | 106 of 106 |
| Best MAD | between 0.00016 and 0.00331, median about 0.001 |
| Share of pixels that differ by more than 16 levels | at most 0.00018 |
| Largest aspect-ratio gap between the PNG and the WebP | 0.00031 |
| The removed PNG has the same directory and stem as the WebP | 101 of 106; the other 5 are among the 8 recorded re-encodes, whose records name a source in another directory |
| The 8 recorded re-encodes: the census source equals the recorded `derived_from` (by path or by SHA-256) | 8 of 8 |

The WebPs entered the repository in 12 commits between 2026-07-17 and 2026-10-03: the pipeline pilot (#133, 4 files), ten onboarding commits (the largest adds 23 files) between 2026-07-18 and 2026-07-22, and #201, which added the 8 recorded re-encodes. The source PNGs had entered the repository earlier, between 2026-06-07 and 2026-07-17.

**Inferred.** All 98 WebPs without a record are consistent with a historical re-encode of a PNG that was removed in the commit that added them, and none of the 106 is distinguishable from one. The manifest `captured` field is documented as the date the current image bytes were produced, and for 97 of the 98 it equals the day of the onboarding commit, which fits a conversion date and not a Portal capture date. The original capture dates are older than the source PNGs and unknown.

**Not Proven.** Pixel agreement does not prove byte lineage and cannot rule out a recapture of the same static blade that happens to agree. The census records the source PNG and its SHA-256 for every WebP, which is what a `legacy_reencode` record would need, and it writes no provenance, invents no date and relabels no capture.

## 5. Collisions, duplicates and alt text

- **Identifiers.** There are no duplicate registry identifiers and no identifier that differs from its file stem. The 4 short identifiers are the pilot's, all called from `platform/storage-connectivity.md`.
- **Identical file stems.** One pair: `01-overview.png` in the `diagnose-and-solve` and `app-insights` directories. Their bytes differ and their legacy identifiers are unique, so no identifier collides.
- **Core-name groups.** Six: `deployment-center` (3 files), `overview` (3), and `deployment-slots`, `health-check`, `identity-blade` and `scale-out` (2 each). Qualified identifiers keep every one of them unique.
- **Byte-identical Portal images.** Seven pairs, each stored under two identifiers and two paths, and each with different alt text, whose lengths run from 85 to 1019 characters. A name-based list finds four of the pairs (`scale-out`, `deployment-slots`, `deployment-center` and `identity-blade`); the other three differ in their names and are visible only by content.

| Pair | Identifiers (pages that call each) | Backtick-quoted strings in the alts (first, second) |
|---|---|---|
| scale-out | `best-practices--scaling--01-scale-out` (1), `platform--scaling--01-scale-out` (1) | none; `asp-test-20251107` |
| deployment-slots | `operations--deployment-slots--01-deployment-slots` (1), `platform--deployment-scenarios--01-deployment-slots` (1) | none; `app-test-20251107`, its `-staging` slot and `asp-test-20251107` |
| deployment-center | `platform--deployment-options--01-deployment-center` (1), `troubleshooting--deployment-center--01-deployment-center` (1) | `app-test-20251107`; none |
| authentication | `operations--security--01-authentication` (1), `platform--authentication-architecture--01-authentication-blade` (5) | none; `app-test-20251107` |
| custom domains | `operations--incoming-client-certificates--01-tls-ssl-bindings` (1), `platform--mtls--01-custom-domains-tls` (5) | none; `app-appsvc-guide-recap.azurewebsites.net` and 11 other strings, mostly interface labels |
| identity blade | `best-practices--security--01-identity-blade` (5), `platform--security-architecture--01-identity-blade` (9) | none; `app-test-20251107` |
| networking | `operations--networking--01-networking-hub` (10), `platform--networking--01-networking-blade` (5) | none; `app-appsvc-guide-recap` and two example IP addresses |

Whether two alt texts of a pair contradict each other was not judged. The census shows only that the same bytes carry different descriptions, and that some of the descriptions name different resources.

## 6. Where the census and the CI validator differ

The census finds 195 `shot()` calls and 16 direct references. The CI helper finds the same 195 and 15. The missing one is the reference to `docs/assets/troubleshooting/app-insights/01-overview.png` at line 1008 of `docs/language-guides/nodejs/tutorial/04-logging-monitoring.md`. Lines 274 and 275 of that page are two consecutive bare fence markers. The second one opens a fence, and the helper then treats the next marker, ` ```js ` at line 290, as its closer, because it does not require a closer to be bare. Its fence tracking stays inverted for the rest of the page, so it reads line 1008 as code. The census counts the reference, since the line lies outside any fence once a closer has to be bare. This is an incidental finding. The census fixes neither the page nor the helper.

## 7. Proposed batches

These are proposals. No issue was filed and nothing was changed. Each batch names the files it would touch, and the batches do not overlap.

| Batch | Members | Prerequisite |
|---|---|---|
| 1 to 7: one pair of byte-identical images each, in this order: scale-out, deployment-slots, deployment-center (2 pages each), then authentication and custom domains (6 pages each), identity blade (14), networking (15) | The two manifest entries of the pair (section 5) and the pages that call them | None. Write one alt text per image that describes the visible bytes and keeps the scenario in the page captions. No identifier is renamed or removed, because a manifest identifier is never renamed. Batch 1 is the bounded first group that #391 asks for. |
| 8: provenance backfill | The 98 WebPs without a record, in 11 sub-batches by the commit that added them (1 to 23 files) | A maintainer decision, because `provenance.yaml` leaves such images out on purpose. The report holds the source path and SHA-256 that each record would pin. |
| 9: recapture of the dimension-exception WebPs | 13 files: `troubleshooting` in `configuration` (1), `kudu` (3), `log-analytics` (2), `metrics` (1), `networking` (2), `storage-firewall` (2) and `storage-iam` (2) | An authorized Portal session and the capture runner; blocked until one exists |
| 10: recapture of the legacy PNGs | The 6 PNGs and their 16 direct references, which move to `shot()` calls | The same session |
| 11: a stray code fence | Line 275 of the Node.js logging tutorial (section 6) | None; a separate documentation fix |

## 8. What this does not establish

- Anything about what the images show. No image was viewed, so caption accuracy, final-image PII and the quality of any alt text are not judged here, and the existing gates for them are unchanged.
- Byte lineage. The origin hint compares pixels, and its threshold was declared and not calibrated.
- The state of the repository after `d1dde4a`. The census is a snapshot, and only the CI validator enforces the live rules.
- Reproduction by someone else. The script is not committed, the history fields need a full clone, and no person has reviewed the report or repeated the computation.
- Consumers outside the repository. A page elsewhere that links an image URL is not counted.
- Any Azure behavior, any capture, and any provenance date.

## See Also

- [Diagram Inventory](diagram-inventory.md)
- [Golden Evidence Model](golden-evidence-model.md)
- [Reference](index.md)
- [Issue #390: recount legacy images, capture IDs and orphan assets](https://github.com/yeongseon/azure-app-service-practical-guide/issues/390)
- [Issue #135: migrate remaining legacy Portal assets to the capture manifest](https://github.com/yeongseon/azure-app-service-practical-guide/issues/135)
- [Issue #391: fix capture-identity collisions and alt-text contracts](https://github.com/yeongseon/azure-app-service-practical-guide/issues/391)

## Sources

- [Fenced code blocks (CommonMark specification)](https://spec.commonmark.org/0.31.2/#fenced-code-blocks)
