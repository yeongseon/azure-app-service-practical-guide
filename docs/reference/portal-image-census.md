---
title: Portal Image Census (#390)
slug: portal-image-census
doc_type: reference
section: reference
summary: Per-file census of the Portal screenshots, legacy PNGs and site images of this repository at one commit, with the registry, reference, collision, duplicate and origin facts that issue 390 asks for, a disposition for every file, and proposed batches for the remaining legacy-image work.
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
| What counts as a reference | The `image_references` helper of the CI validator over every tracked Markdown file: a `shot()` call or an inline image path, with fenced code, HTML comments and inline code ignored. One change: a closing code fence may not carry an info string, as in CommonMark. The helper accepts one, and it misses one reference because of it (section 6). A configuration reference is a line of `mkdocs.yml` or `docs/main.html` that contains the image's path under `docs/`; each such line is one occurrence. An image with no `shot()` call, no direct Markdown reference and no configuration occurrence is an orphan. |
| Origin hint | For each manifest WebP, the PNGs that the commit which added the file removed under `docs/assets` are its candidate sources. The WebP and each candidate are converted to grayscale (Pillow `convert('L')`) and resized with Lanczos to 480 px wide and `round(480 x height / width)` px tall, with the height and width of the WebP. For each candidate the report stores the mean absolute difference (MAD, as a share of 255), the share of pixels that differ by more than 16 levels, and the aspect-ratio gap `abs(PNG ratio / WebP ratio - 1)`, each rounded to five decimals. Candidates are ranked by their MAD rounded to six decimals; a tie goes to the candidate in the same directory with the same normalized stem (the part of the stem after its last `--`), then to the first path in alphabetical order. The best candidate is recorded. A WebP counts as consistent with a re-encode when the stored MAD is at most 0.01 and the stored aspect-ratio gap is at most 0.01. The threshold was declared, not calibrated. |
| Claim labels | **Observed**: what the committed report shows for the commit. **Documented**: what a repository file states. **Inferred**: an explanation drawn from several observations. **Not Proven**: a limit of the evidence. The report is a derived artifact of tracked files, and it is not a Golden evidence run. |

### Delta since the census — 2026-11-04

**Observed** by reading `origin/main` at `3e6d950dbec05c5e692e3869ce8d19302d183fea` on 2026-11-04 (UTC): [PR #406](https://github.com/yeongseon/azure-app-service-practical-guide/pull/406), squash `3e6d950`, unified the alt text of the scale-out pair (batch 1). Those two byte-identical images no longer differ in alt text; the other six Portal pairs still do. The pair table in section 5 and the JSON retain the descriptions at the census base, not these later alts.

For all 106 manifest alts, Python `len()` of each YAML-decoded `alt` gives a median of 695 characters, a maximum of 1,876, and 70 longer than 500 at that main SHA. The same calculation at the census base `d1dde4a` gives 709 / 1,876 / 72 respectively. Length identifies candidates for review, not a hard limit or proof of a contract violation.

This additive note is not a recount: the census base SHA, computation time, snapshot counts and JSON are unchanged. It neither supplies the pending maintainer review of the census and proposed batches nor establishes image accuracy, PII safety or new capture/provenance dates. The snapshot sections below still describe `d1dde4a`.

## 2. The census at a glance

All values are **Observed** unless a row says otherwise.

| Fact | Value |
|---|---|
| Tracked image files | 114: 106 WebP, 6 PNG and 2 SVG |
| Registered in `manifest.yaml` | 106, all WebP. The identifiers are unique, equal the file stem, and 102 of them are path-qualified and 4 are short. |
| Pinned in `legacy-assets.yaml` | 6, all PNG, all 3148 x 2318 |
| Outside both registries | 2, `docs/assets/logo.svg` and `docs/assets/favicon.svg`; the validator exempts both by name (`UNREGISTERED_OK`) |
| `shot()` calls | 195, on 136 pages. Every identifier resolves, and every manifest entry is called at least once (1 to 12 times). |
| Direct Markdown image references | 16, on 13 pages, all to the six legacy PNGs; every one uses the canonical alt text exactly (0 mismatches) |
| Configuration references | 4 occurrences for 3 distinct asset and file pairs: `mkdocs.yml` line 12 (the favicon) and line 13 (the logo), and `docs/main.html` lines 8 and 16 (the favicon, in the `og:image` and `twitter:image` meta tags) |
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
| `retain-registered` | 93 | A manifest WebP that is referenced and is 1440 x 900 px, the size the validator derives from the capture profile; it has no dimension exception. Nothing else about the profile is established: none of these has a `produced` record, and conditions such as locale, theme, device scale factor and readiness signals cannot be read from the dimensions |
| `retain-registered-dimension-exception` | 13 | A manifest WebP that is referenced and is listed in `dimension-exceptions.yaml`; only a recapture under the profile removes the exception |
| `retain-legacy-pinned` | 6 | A legacy PNG pinned by hash and size, referenced directly from Markdown, all with a dimension exception; the exception records describe these as captures at device pixel ratio 2, which the census did not measure |
| `retain-site-asset` | 2 | The site logo and favicon, referenced from the site configuration; they are not Portal captures |

No file is an orphan, so no asset needs an orphan-retention decision. No image is unexpectedly unregistered: the two site SVGs are outside both registries on purpose, and the validator exempts them by name. A disposition is not a review, because no image content was judged here (section 8). The flags are `no-provenance-record` (98 WebPs), `duplicate-content` (16 files), `core-name-collision` (14), `short-id` (4) and `identical-stem` (2).

## 4. Re-encoding or new capture

**Documented.** `provenance.yaml` holds 8 records, all `legacy_reencode`, which the file defines as a pre-profile PNG re-encoded to WebP without a recapture, and it holds no `produced` record, which would mark a capture made under a capture profile. The file says that captures made before the profile existed are left out and not stamped. So no image in the repository has a record of being captured under the profile, and 98 WebPs have no record of how their bytes were produced. The manifest header documents `captured` as the date the current image bytes were produced. For the 8 recorded re-encodes the manifest also sets `captured_basis: repository_introduced`, which the [capture README](https://github.com/yeongseon/azure-app-service-practical-guide/blob/main/scripts/capture/README.md) defines as the date the PNG entered the repository and not an observed capture date. The manifest header does not mention `captured_basis`. The report carries both fields.

**Observed.** The origin hint (section 1) was computed for all 106 WebPs. The values are those stored in the report, rounded to five decimals.

| Result | Value |
|---|---|
| WebPs for which the commit that added the file also removed a candidate source PNG that agrees with it under the threshold | 106 of 106 |
| Best MAD | between 0.00016 and 0.00331, median about 0.001 |
| Share of pixels that differ by more than 16 levels | largest stored value 0.00018 |
| Aspect-ratio gap between the candidate and the WebP | largest stored value 0.00031 |
| The candidate is in the same directory as the WebP and has the same normalized stem | 101 of 106 |
| The candidate is in another directory than the WebP | 0 of 106 |
| The 8 recorded re-encodes: the candidate equals the recorded `derived_from` | 8 of 8: 7 by path and 1 by SHA-256 only |
| The 8 recorded re-encodes: `captured` equals the day on which the candidate entered the repository | 8 of 8 (2026-06-07 for all) |

The 5 WebPs whose candidate does not have the same directory and normalized stem are all among the 8 recorded re-encodes. For four of them (`operations--deployment--01-create-web-app-container-tab`, `operations--deployment--02-deployment-center-github`, `operations--deployment--03-slot-swap-config-changes` and `operations--deployment--04-app-settings`) the candidate lies in the same directory under another stem, and it is the recorded source. For the fifth, `operations--networking--01-networking-hub`, the candidate `docs/assets/operations/networking/01-networking-overview.png` also lies in the same directory under another stem. Its bytes equal those of the recorded source `docs/assets/troubleshooting/networking/01-networking-hub.png`, which lies in another directory, so the report matches that record by SHA-256 and not by path.

The WebPs entered the repository in 12 commits between 2026-07-17 and 2026-10-03: the pipeline pilot (#133, 4 files), ten onboarding commits (the largest adds 23 files) between 2026-07-18 and 2026-07-22, and #201, which added the 8 recorded re-encodes. The candidate source PNGs had entered the repository earlier, between 2026-06-07 and 2026-07-17.

**Inferred.** All 98 WebPs without a record are consistent with a historical re-encode of a PNG that was removed in the commit that added them, and none of the 106 is distinguishable from one. The original Portal capture dates of these images are not recorded in the repository and are unknown. For 97 of the 98 the manifest `captured` date equals the day of the commit that added the WebP; the exception, `best-practices--mtls--01-client-cert-config`, is dated 2026-07-20, two days before its commit. That match is consistent with `captured` being the conversion date that the manifest header describes. It does not establish when a capture was taken, because a capture and a conversion can fall on the same day.

**Not Proven.** Pixel agreement does not prove byte lineage and cannot rule out a recapture of the same static blade that happens to agree. A candidate source PNG is a hint and not a recorded source. The census records the candidate and its SHA-256 for every WebP, writes no provenance, invents no date and relabels no capture.

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
| custom domains | `operations--incoming-client-certificates--01-tls-ssl-bindings` (1), `platform--mtls--01-custom-domains-tls` (5) | none; `app-appsvc-guide-recap.azurewebsites.net` and 11 other strings, mostly interface labels |
| authentication | `operations--security--01-authentication` (1), `platform--authentication-architecture--01-authentication-blade` (5) | none; `app-test-20251107` |
| identity blade | `best-practices--security--01-identity-blade` (5), `platform--security-architecture--01-identity-blade` (9) | none; `app-test-20251107` |
| networking | `operations--networking--01-networking-hub` (10), `platform--networking--01-networking-blade` (5) | none; `app-appsvc-guide-recap` and two example IP addresses |

Whether two alt texts of a pair contradict each other was not judged. The census shows only that the same bytes carry different descriptions, and that some of the descriptions name different resources.

## 6. Where the census and the CI validator differ

The census finds 195 `shot()` calls and 16 direct references. The CI helper finds the same 195 and 15. The missing one is the reference to `docs/assets/troubleshooting/app-insights/01-overview.png` at line 1008 of `docs/language-guides/nodejs/tutorial/04-logging-monitoring.md`. Lines 274 and 275 of that page are two consecutive bare fence markers. The second one opens a fence, and the helper then treats the next marker, ` ```js ` at line 290, as its closer, because it does not require a closer to be bare. Its fence tracking stays inverted for the rest of the page, so it reads line 1008 as code. In an in-memory copy of the page without line 275, the helper does find that reference. The census counts the reference, since the line lies outside any fence once a closer has to be bare. This is an incidental finding. The census fixes neither the page nor the helper.

## 7. Proposed batches

These are proposals. No issue was filed and nothing was changed. The batches partition the work: each of the 106 files for which work is proposed belongs to exactly one batch, each Markdown page that a batch edits belongs to exactly one batch, and a batch carries every task that applies to its files. The report records both: each file has one `proposed_batch` (null for the 8 files with no proposed work), and each entry of `proposed_batches` lists the pages it edits. The registry files `manifest.yaml`, `provenance.yaml`, `dimension-exceptions.yaml` and `legacy-assets.yaml` each hold one entry per asset, so batches that touch the same registry file edit different entries.

The pair batches are ordered by page count, then alphabetically by the smallest identifier (`method.batches` in the JSON). Within each pair, the generator sorted the repository-relative asset paths alphabetically; for these pairs that also puts `proposed_batches[].identifiers` in alphabetical order, not in order of the number of pages calling each member.

| Batch | Members | Prerequisite |
|---|---|---|
| 1 to 7: one pair of byte-identical images each, ordered by the number of pages that call the pair: scale-out, deployment-slots, deployment-center (2 pages each), custom domains and authentication (6 each), identity blade (14) and networking (15) | The two manifest entries of the pair (section 5) and the 47 pages that call them; no page calls the images of two pairs. The task is to write one alt text per image that describes the visible bytes and keeps the scenario in the page captions. No identifier is renamed or removed, because a manifest identifier is never renamed. | None for the alt text. Batch 1 is proposed as the bounded first collision group that #391 asks for. Twelve of the 14 WebPs have no provenance record; a record for them would be added by their pair batch, after the decision of batch 8. |
| 8a to 8k: provenance backfill | The 73 WebPs without a record that are in no pair and have no dimension exception, in 11 sub-batches by the commit that added them (1 to 23 files). The 12 unrecorded members of the pairs belong to batches 1 to 7, and the 13 dimension-exception WebPs to batch 9, whose recapture replaces their bytes. No page is edited. | A maintainer decision, because `provenance.yaml` leaves such images out on purpose, and a change to the validator or to the record kind. The validator accepts a new `legacy_reencode` record only when its source PNG exists at the base of the pull request and is deleted in the same change, and the candidate sources of these WebPs were removed by the commits that added them. The report holds the candidate path and SHA-256 that each record would pin. |
| 9: recapture of the dimension-exception WebPs | 13 files: `troubleshooting` in `configuration` (1), `kudu` (3), `log-analytics` (2), `metrics` (1), `networking` (2), `storage-firewall` (2) and `storage-iam` (2). No page is edited. | An authorized Portal session and the capture runner; blocked until one exists |
| 10: recapture of the legacy PNGs | The 6 PNGs and their 16 direct references on 13 pages, which move to `shot()` calls. One of those pages is the Node.js logging tutorial with the stray code fence of section 6, so the fence fix (line 275) belongs to this batch. | The same session, for the recapture. The fence fix needs none and can be the first change of the batch; in an in-memory test it makes the CI helper see the 16th reference. |
| none | The 8 files for which no work is proposed: the 6 recorded re-encodes that are in no pair, and the 2 site SVGs | None |

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
