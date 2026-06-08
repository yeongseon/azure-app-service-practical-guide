#!/usr/bin/env python3
"""Normalize Microsoft Learn URLs to use the ``en-us`` locale prefix.

Issue: https://github.com/yeongseon/azure-app-service-practical-guide/issues/65

Microsoft Learn URLs accept any locale prefix (``en-us``, ``ja-jp``, ``ko-kr``)
and ALSO accept a locale-free form that redirects to the visitor's
geo-detected locale. This produces three problems:

1. **Inconsistency.** The same article links to multiple URL shapes across
   pages, which leaks into search indexes and confuses readers.
2. **Implicit geo-redirect.** Locale-free URLs serve different content per
   reader location, so screenshots, anchors, and quoted excerpts drift.
3. **Reviewer cognitive load.** Mixed forms force reviewers to mentally
   normalize URLs when comparing sources.

This script enforces a single canonical form: every ``learn.microsoft.com``
URL MUST include the ``en-us`` locale prefix. See ``AGENTS.md``
section *Microsoft Learn URL Locale* for the policy.

The script:

1. Walks the project tree (defaulting to the repo root) with an explicit
   file-type allowlist.
2. Rewrites every Microsoft Learn URL whose path does NOT begin with an
   ``xx-xx/`` BCP-47 locale code by inserting ``en-us/``.
3. Writes back when the result differs.

Modes:

- ``--check`` (default): exit code 1 if any file would change. Suitable
  for CI and pre-commit hooks.
- ``--apply``: write changes to disk.

This script preserves the repo invariant of **UTF-8 without BOM, LF line
endings**. Files outside that invariant are handled defensively: BOM is
preserved byte-for-byte when no rewrite is needed; CRLF files would be
re-encoded as LF on ``--apply`` (no CRLF files exist in this repo today).
Binary files are detected via UTF-8 decode failure and skipped.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Negative lookahead matches the BCP-47-shaped locale Microsoft Learn serves
# (``en-us/``, ``ja-jp/``, ``zh-cn/``). If Microsoft ever ships a non-BCP-47
# token (e.g. bare ``en/`` or mixed-case ``zh-Hans/``), update the regex and
# the LOCALE_RE callers in lock-step or the check will produce false negatives.
LOCALE_RE = re.compile(r"learn\.microsoft\.com/(?![a-z]{2}-[a-z]{2}/)")
REPLACEMENT = "learn.microsoft.com/en-us/"

EXTENSIONS = frozenset(
    {".md", ".py", ".yml", ".yaml", ".json", ".bicep", ".tf", ".txt"}
)
SPECIAL_FILES = frozenset({"Dockerfile", "sshd_config", "AGENTS.md"})

SKIP_DIRS = frozenset(
    {
        ".git",
        ".github",
        "node_modules",
        "site",
        "__pycache__",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".tox",
    }
)


def normalize_text(text: str) -> tuple[str, int]:
    """Return ``(new_text, replacements_made)``.

    ``replacements_made`` is 0 when the file already conforms, so callers
    can detect drift without comparing strings themselves.
    """
    new_text, count = LOCALE_RE.subn(REPLACEMENT, text)
    return new_text, count


def is_scannable(path: Path) -> bool:
    if not path.is_file():
        return False
    if set(path.parts) & SKIP_DIRS:
        return False
    if path.suffix in EXTENSIONS:
        return True
    if path.name in SPECIAL_FILES:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scan-root",
        type=Path,
        default=Path("."),
        help=(
            "Path to scan (default: repo root). MUST be inside the project "
            "root; absolute paths or ``..`` traversal that escape the project "
            "are rejected."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any file would change (CI mode, default)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to disk",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file output",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    scan_root = (project_root / args.scan_root).resolve()
    try:
        scan_root.relative_to(project_root)
    except ValueError:
        print(
            f"Error: --scan-root must be inside the project root "
            f"({project_root}); refusing to scan {scan_root}",
            file=sys.stderr,
        )
        return 1
    if not scan_root.exists():
        print(f"Error: scan root not found: {scan_root}", file=sys.stderr)
        return 1

    changed: list[Path] = []
    skipped_binary: list[Path] = []
    scanned = 0
    total_replacements = 0

    # os.walk + in-place dir mutation prunes descent into SKIP_DIRS. Switching
    # to ``Path.rglob`` with a post-filter would still recurse into ``.git``
    # and ``node_modules`` (~50k files), slowing scans by ~100x.
    for current_dir, dirs, files in os.walk(scan_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for filename in sorted(files):
            path = Path(current_dir) / filename
            if not is_scannable(path):
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                skipped_binary.append(path)
                continue
            except PermissionError as exc:
                print(f"  WARN  {path}  [{exc}]", file=sys.stderr)
                continue

            new_text, count = normalize_text(text)
            if count == 0:
                continue

            changed.append(path)
            total_replacements += count
            try:
                rel = path.relative_to(project_root)
            except ValueError:
                rel = path
            if args.apply:
                path.write_text(new_text, encoding="utf-8")
                if not args.quiet:
                    print(f"  FIXED  {rel}  ({count} URL{'s' if count != 1 else ''})")
            else:
                if not args.quiet:
                    print(f"  DRIFT  {rel}  ({count} URL{'s' if count != 1 else ''})")

    print("")
    print("Summary:")
    print(f"  Files scanned: {scanned}")
    print(f"  Files with locale drift: {len(changed)}")
    print(f"  Total URLs needing en-us prefix: {total_replacements}")
    if skipped_binary and not args.quiet:
        print(f"  Skipped (binary/non-UTF-8): {len(skipped_binary)}")

    if changed and not args.apply:
        print("")
        print(
            "Drift detected. Run "
            "`python3 scripts/normalize_mslearn_locale.py --apply` "
            "to fix."
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
