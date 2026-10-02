# Portal capture helpers

Reusable PII-masking utilities for Azure Portal screenshots. Used across every
documentation capture in this repository to keep redactions consistent and to
avoid leaking real Azure account identifiers into the documentation.

## What it does

- Replaces real identifiers in text nodes, `aria-label`, `title`, and `input`/
  `textarea` values with documentation-safe placeholders (see
  [PII Replacement Rules](../AGENTS.md#pii-replacement-rules)).
- Walks the main frame **and** every nested iframe (Portal blades render
  inside iframes).
- Masks only the Account-menu avatar using Playwright's native `mask` option
  with Portal blue (`#0078d4`), so the masked region blends into the UI
  instead of leaving a jarring black rectangle.
- Throws by default if the Account-avatar selector matches nothing (the only
  visual element the helper cannot rewrite). Pass
  `{ requireAvatarMask: false }` to override for blades where the top bar is
  intentionally absent.

## How to capture

Committed Portal screenshots are produced **only** by the capture runner,
[`capture/capture.cjs`](capture/capture.cjs), which imports this module. Do not
call `capturePortalScreenshot()` from an ad-hoc script, and do not paste an
inline copy of the PII rules into an MCP `browser_run_code_unsafe` call: an
inline copy drifts from `PII_RULES` (the copy that used to live here had already
lost the lowercase-hex, IPv4, and IPv6 rules) and a capture taken through it
can leak exactly the identifiers this module exists to remove.

```bash
CAPTURE_CDP_URL=http://<cdp-host>:9222 node scripts/capture/capture.cjs \
  --url 'https://ms.portal.azure.com/#@<tenant>.onmicrosoft.com/resource/...' \
  --ready 'text=<stable text on the target blade>' \
  --out /tmp/<shot-id>.png
```

| Command/Parameter | Purpose |
|---|---|
| `CAPTURE_CDP_URL` | CDP endpoint of the human's signed-in, device-compliant Chrome. |
| `node scripts/capture/capture.cjs` | Applies `capture-profile.json`, verifies it, applies PII replacements, and captures. |
| `--url` | Target Portal blade, always re-navigated so no state carries over. |
| `--ready` | Playwright selector proving the blade has rendered; there is no default. |
| `--out` | Raw PNG path, outside the repository until optimized and reviewed. |

The runner refuses to capture, and deletes any output, unless every condition in
[`capture/capture-profile.json`](capture/capture-profile.json) holds: a 1600x1000
viewport at device pixel ratio 1 and browser zoom 100%, an English Portal, light
color scheme, reduced motion, no forced colors, UTC, and no open dialog, flyout,
or toast. It then checks that the PNG it wrote is exactly 1600x1000. Hand the raw
PNG to `capture-optimize-webp` (new shot) or `capture-diff-gate` (recapture) as
described in [`capture/README.md`](capture/README.md).

## Capture workflow rules

- **Use the runner.** It re-navigates before every capture, so leftover Portal
  CSS from a previous blade cannot leak into the next one.
- **Use `ms.portal.azure.com` with the tenant hint fragment** (e.g.
  `#@<tenant>.onmicrosoft.com/...`). Plain `portal.azure.com` triggers a login
  redirect.
- **English Portal is required, not preferred.** The primary avatar selector
  keys off the English `aria-label` "Account menu", and the runner rejects a
  non-English `document.documentElement.lang`.
- **Close every transient flyout, drawer, and command-bar dropdown.** The
  runner refuses to capture while a dialog, flyout, or toast is visible, because
  those panels surface PII this module cannot rewrite.
- **Always pass a blade-specific `--ready` selector.** The runner also waits for
  fonts and a stable layout, and pauses after replacements, but none of that
  substitutes for proof that the target blade rendered.
- **No full-page captures.** `capturePortalScreenshot()` throws if `fullPage`
  is passed. For below-the-fold content take a second viewport capture.
- **No black-box masking.** If a value cannot be rewritten and is not a known
  avatar/badge, fail the capture and update `PII_RULES` rather than fall back
  to a black rectangle.

If `PII_RULES` is updated, mirror the change in the
[PII Replacement Rules](../AGENTS.md#pii-replacement-rules) table in the same
commit.
