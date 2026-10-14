#!/usr/bin/env python3
"""Validate repository paths published in documentation."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPOSITORY_URL = "https://github.com/yeongseon/azure-app-service-practical-guide"
MARKDOWN_LINK = re.compile(r"!?\[[^]]*]\((?P<target>[^)\s]+)(?:\s+['\"][^)]*['\"])?\)")
GITHUB_MAIN_LINK = re.compile(
    rf"^{re.escape(REPOSITORY_URL)}/(?:blob|tree)/main/(?P<path>[^?#]+)"
)
COMMAND_PATHS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:python3?|bash|sh)\s+[\"']?(?P<path>(?:\./)?labs/[A-Za-z0-9_.\-/]+)"),
    re.compile(r"(?<![A-Za-z0-9_.\-/])(?P<path>\./labs/[A-Za-z0-9_.\-/]+)"),
    re.compile(r"--template-file(?:=|\s+)[\"']?(?P<path>(?:\./)?labs/[A-Za-z0-9_.\-/]+)"),
    re.compile(r"--(?:output|env)(?:=|\s+)[\"']?(?P<path>artifacts/(?:raw(?:/[A-Za-z0-9_.\-/]+)?|\.env))"),
)
PLACEHOLDER_MARKERS = ("<", ">", "{", "}", "$", "*")
GENERATED_REFERENCES = (
    re.compile(r"^artifacts/raw(?:/|$)"),
    re.compile(r"^artifacts/\.env$"),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One documented path that cannot be resolved in the checkout."""

    document: Path
    line: int
    reference: str
    kind: str


def _is_placeholder(reference: str) -> bool:
    return any(marker in reference for marker in PLACEHOLDER_MARKERS)


def _is_generated(reference: str) -> bool:
    return any(pattern.match(reference) for pattern in GENERATED_REFERENCES)


def _exists_with_anchor(path: Path, reference: str) -> bool:
    return path.exists() and ("#" not in reference or path.is_file())


def _relative_link_target(document: Path, target: str) -> Path | None:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith(("#", "/")):
        return None
    return (document.parent / unquote(parsed.path)).resolve()


def _link_findings(root: Path, document: Path, line: int, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for link in MARKDOWN_LINK.finditer(text):
        target = link.group("target").strip("<>")
        github = GITHUB_MAIN_LINK.match(target)
        if github:
            reference = unquote(github.group("path"))
            if not _is_placeholder(reference) and not (root / reference).exists():
                findings.append(Finding(document.relative_to(root), line, reference, "github-main-link"))
            continue
        resolved = _relative_link_target(document, target)
        if resolved is None or _is_placeholder(target):
            continue
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        if not _exists_with_anchor(resolved, target):
            findings.append(Finding(document.relative_to(root), line, target, "relative-link"))
    return findings


def _command_findings(root: Path, document: Path, line: int, text: str) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for pattern in COMMAND_PATHS:
        for match in pattern.finditer(text):
            reference = match.group("path").rstrip(".,;:)").removeprefix("./")
            if reference in seen or _is_placeholder(reference) or _is_generated(reference):
                continue
            seen.add(reference)
            if not (root / reference).exists():
                findings.append(Finding(document.relative_to(root), line, reference, "command-path"))
    return findings


def validate_tree(root: Path) -> tuple[Finding, ...]:
    """Return unresolved documented repository paths below ``root``."""
    findings: list[Finding] = []
    for document in sorted((root / "docs").rglob("*.md")):
        for line, text in enumerate(document.read_text(encoding="utf-8").splitlines(), start=1):
            findings.extend(_link_findings(root, document, line, text))
            findings.extend(_command_findings(root, document, line, text))
    return tuple(findings)


def main() -> int:
    """Validate the current checkout and print actionable findings."""
    root = Path(__file__).resolve().parent.parent
    findings = validate_tree(root)
    for finding in findings:
        print(
            f"{finding.document}:{finding.line}: {finding.kind}: "
            f"missing repository path {finding.reference}"
        )
    print(f"Documented repository path errors: {len(findings)}")
    return int(bool(findings))


if __name__ == "__main__":
    sys.exit(main())
