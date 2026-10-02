#!/usr/bin/env python3
"""Validate that Azure CLI code fences have nearby explanation tables."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


AZ_PATTERN = re.compile(r"(^|[^A-Za-z0-9_-])az\s+[A-Za-z0-9_-]")
FENCE_PATTERN = re.compile(r"^(\s*)```")
TABLE_DELIMITER_ROW = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$")
FENCE_OPENER = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")

@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    message: str


def has_az_command(block: list[str]) -> bool:
    return any(AZ_PATTERN.search(line) for line in block)


def fence_language(line: str) -> str:
    """Return the language token from a fence opener like '```bash {.copy}'.

    Handles fences of arbitrary length (```, ````, `````, ...) by
    stripping all leading backticks before parsing the language token.
    Returns an empty string for closing fences or unlabeled fences.

    >>> fence_language("```bash")
    'bash'
    >>> fence_language("```bash {.copy}")
    'bash'
    >>> fence_language("    ```python")
    'python'
    >>> fence_language("````bash")
    'bash'
    >>> fence_language("`````bash")
    'bash'
    >>> fence_language("```")
    ''
    >>> fence_language("````")
    ''
    """
    info = line.strip().lstrip("`").strip()
    return info.split(maxsplit=1)[0] if info else ""


def has_following_table(lines: list[str], start_index: int) -> bool:
    """Return True when a Markdown table appears shortly after a fence.

    The delimiter row is matched strictly, so prose that merely contains a
    dash run cannot satisfy the explanation-table requirement.

    >>> has_following_table(["", "| Command | Purpose |", "| --- | --- |"], 0)
    True
    >>> has_following_table(["", "| Command | Purpose |", "see | --- | below"], 0)
    False
    """
    checked = 0
    i = start_index
    while i < len(lines) and checked < 8:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            checked += 1
            continue
        if stripped.startswith(("!!!", "???", "##", "```")):
            return False
        if stripped.startswith("|") and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            return bool(TABLE_DELIMITER_ROW.fullmatch(next_line))
        i += 1
        checked += 1
    return False


def find_unterminated_markdown_tables(lines: list[str]) -> list[int]:
    """Return 1-based line numbers where a Markdown table is not blank-line terminated.

    python-markdown's ``tables`` extension absorbs the first non-blank line after
    a table as a phantom row. The defect is a property of the extension, not of
    the header text, so this recognizes any pipe-led line followed by a delimiter
    row -- the 18 tables in ``AGENTS.md`` include only 2 explanation tables.

    >>> ok = ["| Severity | Meaning |", "| --- | --- |", "| Blocking | fails |", "", "next"]
    >>> find_unterminated_markdown_tables(ok)
    []
    >>> bad = ["| Severity | Meaning |", "| --- | --- |", "| Blocking | fails |", "prose"]
    >>> find_unterminated_markdown_tables(bad)
    [4]

    Alignment colons are recognized, and ending at EOF is fine:

    >>> find_unterminated_markdown_tables(["| A | B |", "| :--- | ---: |", "| 1 | 2 |", "x"])
    [4]
    >>> find_unterminated_markdown_tables(["| A | B |", "| :--- | ---: |", "| 1 | 2 |"])
    []

    Fenced regions are skipped, so the deliberately-broken table that AGENTS.md
    shows as an anti-pattern does not flag the file documenting it. The closing
    fence must be at least as long as the opener, so a four-backtick block that
    contains a three-backtick example stays a single region:

    >>> fenced = ["```markdown", "| A | B |", "| --- | --- |", "| 1 | 2 |",
    ...           "Example output:", "```", "prose"]
    >>> find_unterminated_markdown_tables(fenced)
    []
    >>> nested = ["````markdown", "```text", "| A | B |", "| --- | --- |",
    ...           "| 1 | 2 |", "absorbed", "```", "````", "prose"]
    >>> find_unterminated_markdown_tables(nested)
    []

    A closer must also be no deeper and carry no info string, matching
    :func:`bash_fence_blocks`, so neither of these ends the region:

    >>> deep = ["```text", "| A | B |", "| --- | --- |", "| 1 | 2 |",
    ...         "    ```", "absorbed", "```", "after"]
    >>> find_unterminated_markdown_tables(deep)
    []
    >>> info = ["```text", "| A | B |", "| --- | --- |", "| 1 | 2 |",
    ...         "```python", "absorbed", "```", "after"]
    >>> find_unterminated_markdown_tables(info)
    []

    Prose that merely contains pipes is not a delimiter row:

    >>> find_unterminated_markdown_tables(["| not a table", "prose"])
    []
    >>> find_unterminated_markdown_tables(["| A | B |", "see | --- | below", "x"])
    []
    """
    hits: list[int] = []
    index = 0
    total = len(lines)
    fence: str | None = None
    fence_indent = ""
    while index < total:
        opener = FENCE_OPENER.match(lines[index])
        if opener:
            marker = opener.group(2)
            if fence is None:
                fence, fence_indent = marker, opener.group(1)
            elif (
                marker[0] == fence[0]
                and len(marker) >= len(fence)
                and len(opener.group(1)) <= len(fence_indent)
                and not opener.group(3).strip()
            ):
                fence, fence_indent = None, ""
            index += 1
            continue
        is_table_head = (
            fence is None
            and lines[index].lstrip().startswith("|")
            and index + 1 < total
            and TABLE_DELIMITER_ROW.match(lines[index + 1])
        )
        if not is_table_head:
            index += 1
            continue
        end = index
        while end < total and lines[end].lstrip().startswith("|"):
            end += 1
        if end < total and lines[end].strip() != "":
            hits.append(end + 1)
        index = end
    return hits


def validate_contract_file(path: Path) -> list[Finding]:
    """Check table termination only.

    The CLI explanation-table requirement deliberately does not apply here:
    ``AGENTS.md`` documents CLI style using ``az`` examples that illustrate the
    rule rather than instruct a reader to run them.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        Finding(
            path=path,
            line=line_no,
            message="Markdown table must be followed by a blank line "
            "(otherwise the next line is absorbed as a phantom table row).",
        )
        for line_no in find_unterminated_markdown_tables(lines)
    ]


def bash_fence_blocks(lines: list[str]) -> list[tuple[int, int, list[str]]]:
    """Return ``(open_line, close_index, body)`` for each closed ``bash`` fence.

    ``open_line`` is the opening fence's 1-based line number, matching what the
    finding reports; ``close_index`` is the 0-based index of the closing fence,
    where the explanation-table search starts.

    Every fence is tracked, not only ``bash`` ones, so a ``bash`` fence nested
    inside another block cannot open a phantom region. Only ``bash`` fences
    accumulate a body, because other languages (mermaid, kusto, console
    transcripts) may legitimately contain ``az ...`` text and need no
    explanation table per AGENTS.md ("Shell: Use ``bash`` for all CLI
    examples").

    >>> [(o, b) for o, _c, b in bash_fence_blocks(["```bash", "az x", "```"])]
    [(1, ['az x'])]

    A nested ``bash`` fence inside a longer block is content, not an opener:

    >>> bash_fence_blocks(["````markdown", "```bash", "az x", "```", "````"])
    []

    A closing fence must repeat the opener's character, be at least as long,
    and sit no deeper. A shorter run, a different character, and a
    deeper-indented run all fail to close:

    >>> [o for o, _c, _b in bash_fence_blocks(["````bash", "az x", "```", "````"])]
    [1]
    >>> [o for o, _c, _b in bash_fence_blocks(["```bash", "az x", "~~~", "```"])]
    [1]
    >>> [o for o, _c, _b in bash_fence_blocks(["```bash", "az x", "    ```", "```"])]
    [1]

    An info string means content, so it never closes a block:

    >>> bash_fence_blocks(["```bash", "az x", "```python", "print(1)"])
    []

    A longer closer is still a valid close:

    >>> [o for o, _c, _b in bash_fence_blocks(["```bash", "az x", "`````"])]
    [1]
    """
    blocks: list[tuple[int, int, list[str]]] = []
    marker: str | None = None
    indent = ""
    collecting = False
    start = 0
    body: list[str] = []

    for index, line in enumerate(lines):
        opener = FENCE_OPENER.match(line)
        if marker is None:
            if opener:
                marker = opener.group(2)
                indent = opener.group(1)
                collecting = fence_language(line).lower() == "bash"
                start = index + 1
                body = []
            continue

        if (
            opener is not None
            and opener.group(2)[0] == marker[0]
            and len(opener.group(2)) >= len(marker)
            and len(opener.group(1)) <= len(indent)
            and not opener.group(3).strip()
        ):
            if collecting:
                blocks.append((start, index, body))
            marker = None
            indent = ""
            collecting = False
            body = []
            continue

        if collecting:
            body.append(line)

    return blocks


def validate_file(path: Path) -> list[Finding]:
    lines = path.read_text(encoding="utf-8").splitlines()
    findings: list[Finding] = []
    for line_no in find_unterminated_markdown_tables(lines):
        findings.append(
            Finding(
                path=path,
                line=line_no,
                message="Markdown table must be followed by a blank line "
                "(otherwise the next line is absorbed as a phantom table row).",
            )
        )
    for start, close_index, body in bash_fence_blocks(lines):
        if has_az_command(body) and not has_following_table(lines, close_index + 1):
            findings.append(
                Finding(
                    path=path,
                    line=start,
                    message="Azure CLI code fence must be followed by a "
                    "command explanation table.",
                )
            )

    return findings


def validate_docs(docs_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(docs_dir.glob("**/*.md")):
        findings.extend(validate_file(path))
    return findings


def validate_contracts(root: Path) -> list[Finding]:
    """Check every repository-root Markdown contract document.

    Globbed rather than listed so a new root document is covered the day it is
    added, instead of waiting for someone to remember this file.
    """
    findings: list[Finding] = []
    for path in sorted(root.glob("*.md")):
        findings.extend(validate_contract_file(path))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-dir", type=Path, default=Path("docs"))
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path("."),
        help="Directory whose top-level Markdown files are checked for table termination.",
    )
    args = parser.parse_args()

    findings = validate_docs(args.docs_dir) + validate_contracts(args.root_dir)
    if findings:
        for finding in findings:
            print(f"{finding.path}:{finding.line}: {finding.message}")
        raise SystemExit(f"{len(findings)} Markdown table/CLI fence issue(s) found.")

    print("All Azure CLI code fences and Markdown tables are correctly terminated.")


if __name__ == "__main__":
    main()
