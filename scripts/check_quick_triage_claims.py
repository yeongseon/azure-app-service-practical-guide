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
>>> find_violations("499 near a repeated 30-second boundary => SNAT exhaustion")
['http_timing_proves_snat']
>>> find_violations("A silent stream shows the process died before logger setup")
['empty_logs_prove_pre_logging_failure']
>>> find_violations("No console logs; therefore the app did not execute")
['empty_logs_prove_pre_logging_failure']
>>> find_violations("503 with high TimeTaken and no console rows shows the app never ran")
['http_and_empty_logs_prove_app_never_ran']
>>> find_violations("499 at 30 seconds means SNAT cannot be involved")
['http_timing_proves_snat']
>>> find_violations("A healthy platform line narrows the next checks but does not exclude platform effects")
[]
>>> find_violations("499 at 30 seconds is not proof of SNAT exhaustion")
[]
>>> find_violations("A silent stream does not prove that the process died before logger setup")
[]
>>> find_violations("499 at 30 seconds does not prove DNS; therefore SNAT exhaustion.")
['http_timing_proves_snat']
>>> find_violations("A silent stream does not prove startup success; the process died before logger setup.")
['empty_logs_prove_pre_logging_failure']
>>> find_violations("A silent stream does not prove startup success.")
[]
>>> find_violations("A 503 and absent rows are inconclusive until logging scope and delay are checked")
[]
>>> find_violations("A 499 ended the request. Thirty seconds later, a SNAT detector ran.")
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
        23,
        25,
        27,
        29,
        31,
        38,
        40,
    }),
}

SENTENCE_RE: Final = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")
CLAUSE_SEPARATOR_RE: Final = re.compile(
    r";|\s+-\s+|,\s*(?:but|therefore|so|because)\b|"
    r"\b(?:therefore|so|because)\b",
    re.IGNORECASE,
)
EXPLICIT_QUALIFICATION_RE: Final = re.compile(
    r"\b(?:is|are) not (?:proof|evidence)\b|"
    r"\b(?:do|does|did) not (?:prove|show|mean|indicate|confirm)\b|"
    r"\bcannot (?:prove|show|confirm)\b",
    re.IGNORECASE,
)

DENYLIST: Final = {
    "healthy_platform_excludes_platform": re.compile(
        r"platform availability[^.!?\n]{0,100}(?:100%|healthy)[^.!?\n]{0,100}"
        r"(?:failure|problem|cause)[^.!?\n]{0,50}(?:is|lies in)[^.!?\n]{0,30}"
        r"(?:your )?(?:container|code|application)",
        re.IGNORECASE,
    ),
    "empty_logs_prove_pre_logging_failure": re.compile(
        r"(?:stream is silent|silent stream|empty log(?: stream)?|no (?:console )?logs?)"
        r"[^.!?\n]{0,100}(?:(?:shows?|means|indicates|confirms|therefore)[^.!?\n]{0,30})?"
        r"(?:container|app|process)[^.!?\n]{0,40}"
        r"(?:(?:failed|failing|crashed|died)[^.!?\n]{0,60}before[^.!?\n]{0,30}"
        r"(?:logger setup|log(?:ging)?(?: framework)? (?:initialized|initializes|started))|"
        r"did not (?:execute|run))",
        re.IGNORECASE,
    ),
    "http_and_empty_logs_prove_app_never_ran": re.compile(
        r"503[^.!?\n]{0,100}(?:high|[><~]\s*\d+)[^.!?\n]{0,30}"
        r"(?:duration|timetaken|ms|seconds?)[^.!?\n]{0,100}"
        r"(?:0|no|empty|absent)[^.!?\n]{0,20}(?:console )?(?:logs?|rows)"
        r"[^.!?\n]{0,80}(?:(?:shows?|means|indicates|confirms|therefore)[^.!?\n]{0,20})?"
        r"(?:app )?never ran",
        re.IGNORECASE,
    ),
    "http_timing_proves_snat": re.compile(
        r"(?:499|503|499/503)[^.!?\n]{0,100}"
        r"(?:time(?:taken)?|duration|seconds?|ms|boundary)[^.!?\n]{0,100}"
        r"(?:=>|proves?\b|confirms?\b|shows?\b|therefore\b|means\b|indicates\b|is\b)"
        r"[^.!?\n]{0,40}snat(?: port)?(?: exhaustion| pressure)?"
        r"(?:[^.!?\n]{0,20}cannot be involved)?",
        re.IGNORECASE,
    ),
}


def sentence_violations(sentence: str) -> list[tuple[str, re.Match[str]]]:
    separators = list(CLAUSE_SEPARATOR_RE.finditer(sentence))
    clause_starts = [0, *(match.end() for match in separators)]
    clause_ends = [
        *(match.start() for match in separators),
        len(sentence),
    ]
    violations: list[tuple[str, re.Match[str]]] = []
    for clause_start, clause_end in zip(clause_starts, clause_ends, strict=True):
        clause = sentence[clause_start:clause_end]
        if EXPLICIT_QUALIFICATION_RE.search(clause):
            continue
        candidate = sentence[:clause_end]
        for name, pattern in DENYLIST.items():
            if (match := pattern.search(candidate)) and match.end() > clause_start:
                violations.append((name, match))
    return list(dict.fromkeys(violations))


def find_violations(text: str) -> list[str]:
    violations: list[str] = []
    for sentence_match in SENTENCE_RE.finditer(text):
        violations.extend(name for name, _match in sentence_violations(sentence_match.group(0)))
    return list(dict.fromkeys(violations))


def scan_file(path: Path) -> list[str]:
    relative = path.relative_to(ROOT).as_posix()
    allowed_lines = ALLOWLIST.get(relative, frozenset())
    text = path.read_text(encoding="utf-8")
    findings: list[str] = []
    for sentence_match in SENTENCE_RE.finditer(text):
        sentence = sentence_match.group(0)
        for name, match in sentence_violations(sentence):
            start = sentence_match.start() + match.start()
            line = text.count("\n", 0, start) + 1
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
