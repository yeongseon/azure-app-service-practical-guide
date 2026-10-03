# Screenshot capture pipeline

Portal screenshots are treated as **build artifacts driven by a manifest**, not
hand-placed files. Docs reference a screenshot by a **stable ID**; re-capturing a
blade overwrites the same file and never requires editing markdown.

The implementation lives in the central
[`azure-guide-capture-toolkit`](https://github.com/yeongseon/azure-guide-capture-toolkit)
package (installed via `requirements-docs.txt`). This directory keeps the
repo-specific pieces: `manifest.yaml` (the screenshot registry),
`capture-profile.json` (the fixed capture conditions), `capture.cjs` (the only
supported capture runner), `provenance.yaml` (which profile produced each
image), and `dimension-exceptions.yaml` (frozen historical violations). The PII
helper is `scripts/portal-capture-helpers.js`.

## Components

| Piece | Where | Role |
|---|---|---|
| `manifest.yaml` | this directory | Single source of truth. One entry per screenshot: stable `id`, `file`, `alt`, `captured`/`verified` dates, `diff_threshold`. |
| `screenshot_lib` | toolkit package | Shared manifest access. Reads via PyYAML (present at docs-build time); writes lazily via ruamel round-trip to preserve comments. |
| `optimize_webp` | toolkit package | Downscales a raw PNG to `meta.target_width` (1440px) and encodes WebP, then stamps `captured`. |
| `diff_gate` | toolkit package | Compares a fresh capture to the committed image. Below `diff_threshold` it leaves the image byte-identical and only bumps `verified`; above it, re-encodes and bumps `captured`. |
| `mkdocs_macros` | toolkit package | Defines the `shot()` macro consumed at build time. Wired via the mkdocs-macros `modules:` option in `mkdocs.yml`. |
| `portal-capture-helpers.js` | `scripts/` | Playwright PII text-replacement + avatar masking used during raw capture. |

## Referencing a screenshot in docs

Use the `shot()` macro with the manifest id:

```markdown
[[[ shot("01-app-service-overview-healthy") ]]]
```

This renders the correct relative path plus the manifest `alt` text. The macro
uses custom Jinja delimiters `[[[ ]]]` / `[[% %]]` / `[[# #]]` (configured in
`mkdocs.yml`) so it never collides with the `{{ }}`, `{% %}`, or `{#anchor}`
sequences already present across the docs.

## Adding a new screenshot

1. Capture the raw Portal PNG with the runner, which enforces
   [`capture-profile.json`](capture-profile.json) and refuses to capture if any
   condition fails (see `scripts/portal-capture-helpers.md`):

    ```bash
    CAPTURE_CDP_URL=http://<cdp-host>:9222 node scripts/capture/capture.cjs \
      --url '<blade-url>' --ready '<selector>' --out /tmp/<shot-id>.png
    ```
2. Add an entry to `manifest.yaml` (new `id` = intended file stem).
3. Encode and stamp:

    ```bash
    capture-optimize-webp /path/to/raw.png --id <shot-id>
    ```

4. Record the profile and the committed bytes' SHA-256 in
   [`provenance.yaml`](provenance.yaml).
5. Reference it in markdown with `[[[ shot("<shot-id>") ]]]`.
6. `mkdocs build --strict` to verify it renders; `python3 scripts/validate_capture_assets.py` to verify geometry.

## Re-capturing (drift refresh)

Feed the fresh raw PNG through the diff gate instead of the optimizer:

```bash
capture-diff-gate /path/to/fresh.png --id <shot-id>
```

- **Unchanged** (below threshold): image bytes untouched, only `verified` is
  bumped — no image churn in git.
- **Changed** (at/above threshold): image re-encoded, `captured` bumped.

## Requirements

- Docs build: `mkdocs-macros-plugin` and the `azure-guide-capture-toolkit`
  package (both in `requirements-docs.txt`), plus PyYAML (mkdocs dependency).
  The base toolkit install pulls only PyYAML; `ruamel.yaml` and `Pillow` are
  loaded lazily and are only needed for capture/CLI work.
- Capture/CLI: install the toolkit with its `capture` extra
  (`pip install "azure-guide-capture-toolkit[capture] @ git+https://github.com/yeongseon/azure-guide-capture-toolkit@v0.1.0"`)
  to get `Pillow` and `ruamel.yaml`; Node + Playwright for raw capture.

## Provenance record

Every screenshot added or re-encoded in a pull request needs an entry in
[`provenance.yaml`](provenance.yaml); CI compares against the PR base and fails
otherwise. Key it by manifest id (or repository-relative path for a legacy PNG):

```yaml
assets:
  troubleshooting--kudu--02-kudu-home:
    file: troubleshooting/kudu/troubleshooting--kudu--02-kudu-home.webp
    final_sha256: <sha256 of the committed webp>
    produced:
      profile: portal-desktop-v1
      profile_sha256: <sha256 printed by capture.cjs>
      captured_at: 2026-10-02T12:34:56Z
      browser: Chrome/<version>
```

`dimension-exceptions.yaml` may only shrink: CI rejects any entry absent from
the PR base.

A `kind: legacy_reencode` record documents a pre-profile PNG re-encoded to WebP
without recapture. It carries `derived_from` (source path and its sha256 at the
base revision) and `transform` instead of `produced`, so it never claims a
capture profile. CI accepts a new one only when the source was a 1600x1000 PNG
at the base, is deleted in the same change, and produced exactly one output; an
existing one is immutable. Its manifest entry sets `captured` to the date the
PNG entered the repository with `captured_basis: repository_introduced`, not an
observed capture date.

## Image metadata rules

`scripts/validate_capture_assets.py` also enforces how docs use images:

- Reference manifest screenshots only with `shot("id")`. A direct image path is
  allowed only for an entry of [`legacy-assets.yaml`](legacy-assets.yaml), and its
  alt must equal the registry's canonical `alt`.
- Every image file under `docs/assets` must be in `manifest.yaml` or
  `legacy-assets.yaml`, and every entry in either must be referenced.
- `legacy-assets.yaml` holds the six 3148x2318 PNGs that cannot be re-encoded to
  the profile without cropping. It may only shrink; bytes and size are pinned.
- An image reference added or changed in a pull request must be followed by
  `Purpose:`, `Look for:`, and `Expected result:` lines (in that order, before the
  next image or heading). Existing gaps are reported as advisory.
- Keep `alt` page-neutral: describe the visible pixels. Put page-specific intent
  in the caption lines, so one image can be reused without contradictory alts.
