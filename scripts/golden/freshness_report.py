#!/usr/bin/env python3
"""Report tutorial validation freshness without modifying validation metadata."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import re
import sys


STALE_AFTER_DAYS = 90
METHOD_RE = re.compile(
    r"^\s{2}(az_cli|bicep):\s*$.*?^\s{4}last_tested:\s*([^\n#]+)",
    re.MULTILINE | re.DOTALL,
)


def _classification(raw_date: str, today: date) -> tuple[str, str]:
    value = raw_date.strip().strip("'\"")
    if value in {"", "null", "~"}:
        return "Not tested", "—"
    try:
        tested = date.fromisoformat(value)
    except ValueError:
        return "Invalid", value
    age = (today - tested).days
    if age < 0:
        return "Invalid", tested.isoformat()
    if age > STALE_AFTER_DAYS:
        return "Stale", tested.isoformat()
    return "Current", tested.isoformat()


def build_report(root: Path, today: date) -> str:
    rows: list[tuple[str, str, str, str]] = []
    pattern = "docs/language-guides/*/tutorial/*.md"
    for path in sorted(root.glob(pattern)):
        text = path.read_text(encoding="utf-8")
        for method, raw_date in METHOD_RE.findall(text):
            status, tested = _classification(raw_date, today)
            rows.append((str(path.relative_to(root)), method, tested, status))
    lines = [
        "# Tutorial Validation Freshness",
        "",
        f"Calculated at `{today.isoformat()}` from existing `last_tested` metadata.",
        "This report is read-only; replay does not update `last_tested` or `captured_at`.",
        "",
        "| Tutorial | Method | Last tested | Freshness |",
        "|---|---|---|---|",
    ]
    lines.extend(f"| `{path}` | `{method}` | {tested} | {status} |" for path, method, tested, status in rows)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    report = build_report(args.root.resolve(), args.today)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
