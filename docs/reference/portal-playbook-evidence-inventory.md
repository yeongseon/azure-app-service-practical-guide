---
title: Portal Playbook Evidence Inventory
slug: portal-playbook-evidence-inventory
doc_type: reference
section: reference
summary: Pinned offline inventory of screenshot references and diagnostic trail gaps in the troubleshooting playbooks, with bounded follow-up proposals and explicit limits.
topics: [documentation-standards, evidence, troubleshooting]
products: [azure-app-service]
content_sources:
  references:
    - type: self-generated
      justification: Offline examination of tracked playbooks and existing screenshot registries at a pinned main commit; no image content, Azure behavior or live capture is verified.
---

# Portal Playbook Evidence Inventory

## Basis and method

The [machine-readable inventory](portal-playbook-evidence-inventory.json) is the
offline slice of [#294](https://github.com/yeongseon/azure-app-service-practical-guide/issues/294)
under [#128](https://github.com/yeongseon/azure-app-service-practical-guide/issues/128).
Its source is `main` at `3e6d950dbec05c5e692e3869ce8d19302d183fea`;
computation and document date are 2026-11-04, not capture dates.

Enumerate tracked Markdown under `docs/troubleshooting/playbooks/`, excluding
every `index.md`, using `git ls-tree -r --name-only` at that SHA. Read blobs with
`git show SHA:path`, not the working tree. Extract screenshot references outside
code fences, inline code and HTML comments, preserving one-based line numbers.
A fence closer must be bare, use the opener's character and be at least as long;
this avoids the census's documented Node.js closing-fence blind spot.

Resolve each occurrence through the capture manifest or legacy registry; hash
its final bytes and check against the [census](portal-image-census.md) file entry.
The JSON links that entry rather than repeating its migration batches or lineage
analysis. Canonical alt/provenance pointers use the pinned registries, since the
census predates later alt changes. Unrecorded live capture time stays **Unknown**.

Diagnostic units are the Portal section's Layer/Step subsections, Kudu's Portal
views, or otherwise section 6's hypothesis subsections/decision matrix. Each has
navigation, observation-support and next-decision pointers, with null for missing
links and a missing-signal explanation. These units are not image counts or an
exhaustive runtime-layer model. As in #405, the artifact is retained, not a
generator; its `method` and `verification_commands` describe the repeatable scan.

**Documented** means the pinned prose/contract states it; **Observed** below means
the source scan found it, not that Azure was observed. Follow-up selection is
**Inferred** prioritization. Completeness, correctness and freshness are **Not Proven**.

## Results and proposed follow-up

Observed: **37 playbooks**, split into 11 general, 4 outbound-network,
9 performance and 13 startup-availability pages. Four have a `Portal Evidence`
section. Twelve embedded screenshot occurrences span five pages; none is a direct
legacy image reference. Heading and image counts are not trail completeness.

| Documentary class | Playbooks | Finding at the pinned source |
|---|---:|---|
| Storage reference | 1 | Six captures for layers 2–4; DNS is intentionally a command procedure with representative text because of canvas sanitation limits. Preserve #127; no replacement capture task. |
| Single-blade card walks | 3 | DNS, Private Endpoint and SNAT each document ordered navigation/decisions using the same non-integrated-app Networking capture. That image cannot observe an integrated resolver, effective route or SNAT port pressure. |
| Windows Kudu caption gap | 1 | Three registered Overview/Kudu/Process Explorer shots have explanatory prose, but lack the prescribed Purpose / Look for / Expected result / Next step trail. Caption-only review first, not automatic recapture. |
| No embedded capture | 32 | Prose, commands and hypothesis decisions exist; no embedded screenshot trail is supplied by these pages. This does not inventory every linked lab's images. |

The JSON's `present` class means a documented trail exists **at its stated limited
scope** (storage or card navigation), never that it is complete. `missing` includes
both absent captures and Kudu's missing caption trail. `stale` requires evidence
of a UI/recipe mismatch; neither age nor a missing caption establishes it here.
Capture access is separately `blocked-manual`; freshness is **Unknown** throughout.
The [outbound matrix](outbound-evidence-gap-matrix.md) owns live signal gaps and
#129 follow-ups; this inventory does not recreate that matrix.

### Proposed single-playbook scopes, in priority order

These are proposals, not filed issues or authorized capture sessions. The JSON
lists expected blades, reusable IDs, missing signals and target-specific access.

1. Reuse **#295**, [Linux deployment succeeded/startup failed](../troubleshooting/playbooks/startup-availability/deployment-succeeded-startup-failed.md): Deployment Center → Log stream/Logs → next startup hypothesis. Review existing deployment/startup-query IDs before defining new ones.
2. **#128 child proposal**, [Windows Kudu](../troubleshooting/playbooks/startup-availability/windows-kudu-diagnostics.md): caption-only completion using the existing three IDs, after final-byte visual review. Coordinate profile-exception recaptures with #135, not a duplicate batch.
3. **#128 child proposal**, [Windows IIS/web.config](../troubleshooting/playbooks/startup-availability/windows-iis-webconfig-startup.md): startup diagnostics → Log stream → Kudu deployed configuration → disproof decision, on a selected Windows/IIS model.
4. **#128 child proposal**, [Windows worker recycling](../troubleshooting/playbooks/performance/windows-memory-pressure-worker-recycling.md): Memory detector → Process Explorer → matched recycle timeline; a static process table cannot decide cause.
5. **#128 child proposal**, [Windows filesystem](../troubleshooting/playbooks/performance/windows-filesystem-quotas.md): confirm available quota diagnostics → Kudu path observation → bounded retention decision; no dump contents or destructive cleanup in a capture.

The Java worker image is already registered and linked from the
[Windows Java lab](../troubleshooting/lab-guides/windows-java-httpplatformhandler-timeout.md),
not an inventoried playbook. Review reuse instead of asking for another capture.
#135 retains asset/profile/provenance work; #129 retains outbound live work.

### Prerequisites for any new capture

A maintainer selects the child; a resource/cost owner approves one controlled app,
hosting model, runtime, region, SKU, diagnostic question and any fault/logging costs.
Confirm RBAC for the selected blades, workspace and SCM actions, not just resource
read access. A compliant-device human signs in, completes MFA and confirms the
contract's account settings; no cookie or enrollment bypass is permitted.
Use only the prescribed runner/profile and PII helper; keep raw PNGs private,
record honest final-byte provenance and inspect the final WebP for PII/caption
accuracy. Unsanitizable canvas output stays text or blocks capture. The JSON's
shared prerequisites link the full contract; this offline task supplies no session.

## Limits

No capture, Azure execution, image-content review or claim of a complete or
correct diagnostic trail is made. Capture time and freshness remain Unknown
where the records cannot establish them.
No image was visually read or changed. Static checks do not certify caption/image
accuracy, current Portal availability, RBAC, retained runtime output, hypothesis
outcomes, independent reproduction or maintainer acceptance. All `trail_complete`
fields remain false: documentary presence is not semantic or pixel verification.

## See Also

- [Portal Image Census](portal-image-census.md)
- [Outbound Evidence Gap Matrix](outbound-evidence-gap-matrix.md)
- [Golden Evidence Model](golden-evidence-model.md)
- [Reference](index.md)

## Sources

- [Issue #294](https://github.com/yeongseon/azure-app-service-practical-guide/issues/294)
- [Pinned capture contract](https://github.com/yeongseon/azure-app-service-practical-guide/blob/3e6d950dbec05c5e692e3869ce8d19302d183fea/DOCUMENTATION_CONTRACT.md#portal-screenshot-capture-pii-replacement-rules)
- [Fenced code blocks (CommonMark)](https://spec.commonmark.org/0.31.2/#fenced-code-blocks)
