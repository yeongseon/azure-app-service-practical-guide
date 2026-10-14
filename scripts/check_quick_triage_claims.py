#!/usr/bin/env python3
"""Reject known categorical causal claims on quick-triage surfaces.

This narrow content contract prevents recurrence of phrases removed by issue
#204. It does not assess causal correctness or replace technical review.

Run from the repository root::

    python scripts/check_quick_triage_claims.py

The allowlist is intentionally limited to quoted discussion in this script's
own tests; production documentation has no exemptions.

>>> find_violations("when Platform Availability stays at 100%, the failure is in your code")
['healthy_platform_excludes_platform']
>>> find_violations("If the stream is silent, the container failed before logging initialized")
['empty_logs_prove_pre_logging_failure']
>>> find_violations("503 plus high duration and no console logs means the app never ran")
['http_and_empty_logs_prove_app_never_ran']
>>> find_violations("499 at 30 seconds proves SNAT exhaustion")
['http_timing_proves_snat']
>>> find_violations("A healthy platform line narrows the next checks but does not exclude platform effects")
[]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Final


ROOT: Final = Path(__file__).resolve().parents[1]
SURFACES: Final = (
    "docs/troubleshooting/index.md",
    "docs/troubleshooting/decision-tree.md",
    "docs/troubleshooting/quick-diagnosis-cards.md",
    "docs/troubleshooting/evidence-map.md",
    "docs/troubleshooting/first-10-minutes/startup-availability.md",
    "docs/troubleshooting/first-10-minutes/outbound-network.md",
    "docs/troubleshooting/first-10-minutes/performance.md",
)

# Narrow allowlist: only these doctest lines may quote denied language.
ALLOWLIST: Final = {
    "scripts/check_quick_triage_claims.py": frozenset({
        15,
        17,
        19,
        21,
    }),
}

DENYLIST: Final = {
    "healthy_platform_excludes_platform": re.compile(
        r"platform availability.{0,100}(?:100%|healthy).{0,100}"
        r"(?:failure|problem|cause).{0,50}(?:is|lies in).{0,30}(?:your )?"
        r"(?:container|code|application)(?:.{0,50}(?:not|rather than).{0,30}"
        r"(?:app service )?platform)?",
        re.IGNORECASE | re.DOTALL,
    ),
    "empty_logs_prove_pre_logging_failure": re.compile(
        r"(?:stream is silent|empty log(?: stream)?|no (?:console )?logs?).{0,100}"
        r"(?:container|app|process).{0,40}(?:failed|failing|crashed).{0,60}"
        r"before.{0,30}log(?:ging)?(?: framework)? (?:initialized|initializes|started)",
        re.IGNORECASE | re.DOTALL,
    ),
    "http_and_empty_logs_prove_app_never_ran": re.compile(
        r"503.{0,100}(?:high|[><~]\s*\d+).{0,30}(?:duration|timetaken|ms|seconds?).{0,100}"
        r"(?:0|no|empty).{0,20}(?:console )?logs?.{0,80}(?:app )?never ran",
        re.IGNORECASE | re.DOTALL,
    ),
    "http_timing_proves_snat": re.compile(
        r"(?:499|503|499/503).{0,100}(?:time(?:taken)?|duration|seconds?|ms|boundary).{0,100}"
        r"(?:proves?\b|confirms?\b|means\b|indicates\b|is\b).{0,40}snat(?: port)? exhaustion",
        re.IGNORECASE | re.DOTALL,
    ),
}


def find_violations(text: str) -> list[str]:
    return [name for name, pattern in DENYLIST.items() if pattern.search(text)]


def scan_file(path: Path) -> list[str]:
    relative = path.relative_to(ROOT).as_posix()
    allowed_lines = ALLOWLIST.get(relative, frozenset())
    text = path.read_text(encoding="utf-8")
    findings: list[str] = []
    for name, pattern in DENYLIST.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            if line not in allowed_lines:
                excerpt = " ".join(match.group(0).split())
                findings.append(f"{relative}:{line}: {name}: {excerpt}")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="Repository-relative Markdown paths; defaults to quick-triage surfaces.",
    )
    args = parser.parse_args(argv)
    paths = [ROOT / path for path in args.paths] if args.paths else [ROOT / path for path in SURFACES]
    findings = [finding for path in paths for finding in scan_file(path)]
    if findings:
        print("Quick-triage causal-claim contract failed:")
        print("\n".join(f"- {finding}" for finding in findings))
        print("This contract catches known categorical phrases; it does not prove causal correctness.")
        return 1
    print(f"Quick-triage causal-claim contract passed ({len(paths)} files).")
    print("Scope is a phrase denylist only; technical review remains required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
