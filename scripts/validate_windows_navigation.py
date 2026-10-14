#!/usr/bin/env python3
"""Validate Windows troubleshooting playbook links from both primary indexes.

The troubleshooting landing page and the playbook index are the two primary
symptom-first entry points. Each must link every intended Windows playbook
directly so readers do not need to discover platform-specific guidance through
the full MkDocs navigation.

Usage::

    python3 scripts/validate_windows_navigation.py

The mutation example is an executable regression check: removing one required
link changes a passing result into a failure.

>>> links = frozenset(REQUIRED_WINDOWS_PLAYBOOKS)
>>> missing_required_links(links)
()
>>> mutated = links - {REQUIRED_WINDOWS_PLAYBOOKS[0]}
>>> missing_required_links(mutated)
('playbooks/startup-availability/windows-iis-webconfig-startup.md',)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path, PurePosixPath
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
TROUBLESHOOTING: Final = ROOT / "docs" / "troubleshooting"
ENTRY_POINTS: Final = (
    TROUBLESHOOTING / "index.md",
    TROUBLESHOOTING / "playbooks" / "index.md",
)
REQUIRED_WINDOWS_PLAYBOOKS: Final = (
    "playbooks/startup-availability/windows-iis-webconfig-startup.md",
    "playbooks/startup-availability/windows-container-health-probes.md",
    "playbooks/startup-availability/windows-kudu-diagnostics.md",
    "playbooks/performance/windows-memory-pressure-worker-recycling.md",
    "playbooks/performance/windows-filesystem-quotas.md",
)
MARKDOWN_LINK_RE: Final = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def troubleshooting_links(path: Path) -> frozenset[str]:
    """Return normalized local Markdown destinations linked from ``path``."""
    links: set[str] = set()
    for raw_destination in MARKDOWN_LINK_RE.findall(path.read_text(encoding="utf-8")):
        destination = raw_destination.split("#", 1)[0]
        if not destination or "://" in destination:
            continue
        resolved = (path.parent / destination).resolve()
        try:
            relative = resolved.relative_to(TROUBLESHOOTING.resolve())
        except ValueError:
            continue
        links.add(PurePosixPath(relative).as_posix())
    return frozenset(links)


def missing_required_links(links: frozenset[str]) -> tuple[str, ...]:
    """Return required Windows playbooks absent from one entry point."""
    return tuple(target for target in REQUIRED_WINDOWS_PLAYBOOKS if target not in links)


def main() -> int:
    """Report missing direct links and return a blocking exit status."""
    failures: list[str] = []
    for entry_point in ENTRY_POINTS:
        missing = missing_required_links(troubleshooting_links(entry_point))
        if missing:
            relative_entry = entry_point.relative_to(ROOT).as_posix()
            failures.extend(f"{relative_entry}: missing {target}" for target in missing)

    if failures:
        print("Windows troubleshooting navigation validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Windows troubleshooting navigation: "
        f"{len(ENTRY_POINTS)} entry points link all "
        f"{len(REQUIRED_WINDOWS_PLAYBOOKS)} required playbooks."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
