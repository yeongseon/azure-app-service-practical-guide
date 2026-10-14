#!/usr/bin/env python3
"""Validate repository paths published in documentation."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Final, Literal
from urllib.parse import unquote, urlsplit

REPOSITORY_URL: Final = "https://github.com/yeongseon/azure-app-service-practical-guide"
MARKDOWN_LINK: Final = re.compile(
    r"!?\[[^]]*]\((?P<target>[^)\s]+)(?:\s+['\"][^)]*['\"])?\)"
)
REFERENCE_DEFINITION: Final = re.compile(
    r"^ {0,3}\[(?P<label>[^]]+)]\s*:\s*(?P<target><[^>]+>|\S+)"
)
REFERENCE_USAGE: Final = re.compile(r"!?\[(?P<text>[^]]+)]\[(?P<label>[^]]*)]")
GITHUB_MAIN_LINK: Final = re.compile(
    rf"^{re.escape(REPOSITORY_URL)}/(?:blob|tree)/main/(?P<path>[^?#]+)"
)
FENCE: Final = re.compile(r"^\s*(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
EXECUTABLE_FENCE_LANGUAGES: Final = frozenset({"bash", "sh"})
COMMAND_PATHS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"\b(?:python3?|bash|sh)\s+[\"']?(?P<path>(?:\./)?(?:labs|artifacts)/[^\s\"'|]+)"
    ),
    re.compile(r"(?<![A-Za-z0-9_.\-/])(?P<path>\./labs/[^\s\"'|]+)"),
    re.compile(
        r"--template-file(?:=|\s+)[\"']?(?P<path>(?:\./)?labs/[^\s\"'|]+)"
    ),
    re.compile(
        r"--(?:output|env)(?:=|\s+)[\"']?(?P<path>artifacts/[^\s\"'|]+)"
    ),
)

ExceptionCategory = Literal["generated-artifact", "placeholder", "optional-future-step"]


@dataclass(frozen=True, slots=True)
class PathException:
    """A narrowly reviewed documented path that is not checked in."""

    category: ExceptionCategory
    pattern: re.Pattern[str]
    reason: str
    example: str


PATH_EXCEPTIONS: Final[tuple[PathException, ...]] = (
    PathException(
        "generated-artifact",
        re.compile(r"artifacts/raw(?:/[A-Za-z0-9_.\-/]+)?"),
        "Lab commands create raw evidence below this directory at run time.",
        "artifacts/raw/evidence/result.json",
    ),
    PathException(
        "generated-artifact",
        re.compile(r"artifacts/\.env"),
        "The shared deployment script writes this environment file at run time.",
        "artifacts/.env",
    ),
    PathException(
        "placeholder",
        re.compile(r"labs/<name>/main\.bicep"),
        "The lab index uses <name> to represent a reader-selected checked-in lab.",
        "labs/<name>/main.bicep",
    ),
    PathException(
        "placeholder",
        re.compile(r"labs/missing/<app-name>/run\.py"),
        "This exact example demonstrates a path-scoped application-name placeholder.",
        "labs/missing/<app-name>/run.py",
    ),
    PathException(
        "optional-future-step",
        re.compile(
            r"labs/windows-java-httpplatformhandler-timeout/artifacts-sanitized/stage-0/result\.json"
        ),
        "The Stage 0 runbook explicitly identifies this publication as a future optional step.",
        "labs/windows-java-httpplatformhandler-timeout/artifacts-sanitized/stage-0/result.json",
    ),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One documented path that cannot be resolved in the checkout."""

    document: Path
    line: int
    reference: str
    kind: str


@dataclass(frozen=True, slots=True)
class ReferenceDefinition:
    target: str
    line: int


class LocalHtmlTargetParser(HTMLParser):
    """Collect href and src values with their source lines."""

    targets: list[tuple[int, str]]

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.targets = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del tag
        line, _ = self.getpos()
        self.targets.extend(
            (line, value)
            for name, value in attrs
            if name.lower() in {"href", "src"} and value is not None
        )


def _is_exception(reference: str) -> bool:
    return any(exception.pattern.fullmatch(reference) for exception in PATH_EXCEPTIONS)


def _relative_link_target(document: Path, target: str) -> Path | None:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith(("#", "/")):
        return None
    return (document.parent / unquote(parsed.path)).resolve()


def _target_findings(
    root: Path, document: Path, line: int, target: str, kind: str
) -> list[Finding]:
    normalized = target.strip("<>")
    github = GITHUB_MAIN_LINK.match(normalized)
    if github:
        reference = unquote(github.group("path"))
        if not _is_exception(reference) and not (root / reference).exists():
            return [Finding(document.relative_to(root), line, reference, "github-main-link")]
        return []
    resolved = _relative_link_target(document, normalized)
    if resolved is None or _is_exception(normalized):
        return []
    try:
        _ = resolved.relative_to(root)
    except ValueError:
        return []
    if not resolved.exists():
        return [Finding(document.relative_to(root), line, normalized, kind)]
    return []


def _command_findings(root: Path, document: Path, line: int, text: str) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for pattern in COMMAND_PATHS:
        for match in pattern.finditer(text):
            reference = match.group("path").rstrip(".,;:)").removeprefix("./")
            if reference in seen or _is_exception(reference):
                continue
            seen.add(reference)
            if not (root / reference).exists():
                findings.append(Finding(document.relative_to(root), line, reference, "command-path"))
    return findings


def _fence_language(info: str) -> str:
    language = info.strip().split(maxsplit=1)[0].lower() if info.strip() else ""
    return language.removeprefix("{.").removesuffix("}")


def _visible_lines(lines: list[str]) -> tuple[list[str], tuple[tuple[int, str], ...]]:
    visible = [""] * len(lines)
    executable: list[tuple[int, str]] = []
    marker = ""
    language = ""
    for number, text in enumerate(lines, start=1):
        fence = FENCE.match(text)
        if not marker:
            if fence:
                marker = fence.group("marker")
                language = _fence_language(fence.group("info"))
            else:
                visible[number - 1] = text
            continue
        if fence and fence.group("marker")[0] == marker[0] and len(fence.group("marker")) >= len(marker):
            marker = ""
            language = ""
            continue
        if language in EXECUTABLE_FENCE_LANGUAGES:
            executable.append((number, text))
    return visible, tuple(executable)


def _reference_findings(
    root: Path, document: Path, lines: list[str]
) -> list[Finding]:
    definitions: dict[str, ReferenceDefinition] = {}
    for line, text in enumerate(lines, start=1):
        definition = REFERENCE_DEFINITION.match(text)
        if definition:
            definitions[definition.group("label").casefold()] = ReferenceDefinition(
                definition.group("target"), line
            )
    findings: list[Finding] = []
    for label, definition in definitions.items():
        del label
        findings.extend(
            _target_findings(
                root, document, definition.line, definition.target, "reference-definition"
            )
        )
    for line, text in enumerate(lines, start=1):
        if REFERENCE_DEFINITION.match(text):
            continue
        for usage in REFERENCE_USAGE.finditer(text):
            label = (usage.group("label") or usage.group("text")).casefold()
            definition = definitions.get(label)
            if definition is None:
                findings.append(
                    Finding(document.relative_to(root), line, label, "reference-definition")
                )
            else:
                findings.extend(
                    _target_findings(root, document, line, definition.target, "reference-link")
                )
    return sorted(findings, key=lambda finding: finding.line)


def validate_tree(root: Path) -> tuple[Finding, ...]:
    """Return unresolved documented repository paths below ``root``."""
    findings: list[Finding] = []
    for document in sorted((root / "docs").rglob("*.md")):
        lines = document.read_text(encoding="utf-8").splitlines()
        visible, executable = _visible_lines(lines)
        for line, text in enumerate(visible, start=1):
            for link in MARKDOWN_LINK.finditer(text):
                findings.extend(
                    _target_findings(
                        root, document, line, link.group("target"), "relative-link"
                    )
                )
        findings.extend(_reference_findings(root, document, visible))
        parser = LocalHtmlTargetParser()
        parser.feed("\n".join(visible))
        for line, target in parser.targets:
            findings.extend(_target_findings(root, document, line, target, "html-link"))
        for line, text in executable:
            findings.extend(_command_findings(root, document, line, text))
    return tuple(findings)


def main() -> int:
    """Validate the current checkout and print actionable findings."""
    root = Path(__file__).resolve().parent.parent
    findings = validate_tree(root)
    for finding in findings:
        message = (
            f"{finding.document}:{finding.line}: {finding.kind}: missing repository path "
            f"{finding.reference}"
        )
        print(message)
    print(f"Documented repository path errors: {len(findings)}")
    return int(bool(findings))


if __name__ == "__main__":
    sys.exit(main())
