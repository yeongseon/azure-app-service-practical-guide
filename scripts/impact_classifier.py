#!/usr/bin/env python3
"""Select App and Infra CI jobs from Git name-status changes.

Executable Markdown is selected when changed hunks touch a command fence or its
adjacent or labeled expected-output fences. Unrelated prose stays lightweight.
Bicep remains
a full apps/ and labs/ compilation gate because the repository has no proven
transitive module and parameter dependency graph.
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable, Final


class Job(StrEnum):
    SCRIPTS = "scripts"
    NODEJS = "nodejs"
    NODEJS_CONTAINER = "nodejs_container"
    PYTHON = "python"
    DOTNET = "dotnet"
    JAVA = "java"
    BICEP = "bicep"


ALL_JOBS: Final = frozenset(Job)
APP_JOBS: Final = {
    "apps/nodejs/": Job.NODEJS,
    "apps/python-flask/": Job.PYTHON,
    "apps/dotnet-aspnetcore/": Job.DOTNET,
    "apps/java-springboot/": Job.JAVA,
}
SHELL_COMMAND_RE: Final = re.compile(
    r"^\s*(?:\$\s*)?(?:(?:az|bash|cd|chmod|curl|docker|dotnet|flask|gradle|gunicorn|kubectl|mkdocs|mvn|node|npm|nslookup|pip3?|python3?|sh|sleep|uvicorn|zip)(?:\s|$)|/usr/sbin/sshd(?:\s|$)|\./|(?:apps|labs|scripts)/\S+\.sh\b)"
)
FENCE_OPEN_RE: Final = re.compile(r"^\s*(`{3,}|~{3,})(?:bash|sh|shell)(?:\s+.*)?$")
ANY_FENCE_OPEN_RE: Final = re.compile(r"^\s*(`{3,}|~{3,})(?:\S.*)?$")
OUTPUT_LABEL_RE: Final = re.compile(r"^\s*(?:(?:expected|example)\s+)?output\s*:\s*$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Change:
    status: str
    old_path: str
    new_path: str | None = None

    @classmethod
    def modified(cls, path: str) -> Change:
        return cls("M", path)

    @classmethod
    def deleted(cls, path: str) -> Change:
        return cls("D", path)

    @classmethod
    def renamed(cls, old_path: str, new_path: str) -> Change:
        return cls("R", old_path, new_path)

    @property
    def paths(self) -> tuple[str, ...]:
        return (self.old_path,) if self.new_path is None else (self.old_path, self.new_path)


class InvalidDiffError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Arguments:
    base: str | None
    head: str
    full_regression: bool
    github_output: Path | None
    name_status_input: Path | None


class ArgumentNamespace(argparse.Namespace):
    base: str | None = None
    head: str = "HEAD"
    full_regression: bool = False
    github_output: Path | None = None
    name_status_input: Path | None = None


def parse_name_status_z(raw: bytes) -> tuple[Change, ...]:
    fields = raw.decode("utf-8").split("\0")
    if fields[-1] == "":
        _ = fields.pop()
    changes: list[Change] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if index >= len(fields):
            raise InvalidDiffError("status has no path")
        old_path = fields[index]
        index += 1
        if status.startswith(("R", "C")):
            if index >= len(fields):
                raise InvalidDiffError("rename or copy has no destination path")
            changes.append(Change(status, old_path, fields[index]))
            index += 1
        else:
            changes.append(Change(status, old_path))
    return tuple(changes)


def executable_markdown_changed(old_text: str, new_text: str) -> bool:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    old_changed: set[int] = set()
    new_changed: set[int] = set()
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag != "equal":
            old_changed.update(range(old_start, old_end))
            new_changed.update(range(new_start, new_end))
    return _changed_executable_region(old_lines, old_changed) or _changed_executable_region(
        new_lines, new_changed
    )


def _changed_executable_region(lines: list[str], changed_lines: set[int]) -> bool:
    fences = _fence_ranges(lines)
    executable_indexes = {
        index
        for index, (start, end) in enumerate(fences)
        if FENCE_OPEN_RE.match(lines[start])
        and any(SHELL_COMMAND_RE.search(line) for line in lines[start + 1 : end - 1])
    }
    executable_regions = [fences[index] for index in executable_indexes]
    for index in executable_indexes:
        next_index = index + 1
        while next_index < len(fences) and not any(
            lines[line_index].strip()
            for line_index in range(fences[next_index - 1][1], fences[next_index][0])
        ):
            executable_regions.append(fences[next_index])
            next_index += 1
    for index, (start, end) in enumerate(fences):
        label_index = start - 1
        while label_index >= 0 and not lines[label_index].strip():
            label_index -= 1
        if (
            label_index >= 0
            and OUTPUT_LABEL_RE.match(lines[label_index])
            and any(command_index < index for command_index in executable_indexes)
        ):
            executable_regions.append((start, end))
    return any(
        changed_lines.intersection(range(start, end))
        for start, end in executable_regions
    )


def _fence_ranges(lines: list[str]) -> list[tuple[int, int]]:
    fences: list[tuple[int, int]] = []
    fence_start: int | None = None
    fence_marker = ""
    for index, line in enumerate(lines):
        opening = ANY_FENCE_OPEN_RE.match(line)
        if fence_start is None and opening is not None:
            fence_start = index
            fence_marker = opening.group(1)
        elif fence_start is not None and re.match(
            rf"^\s*{re.escape(fence_marker[0])}{{{len(fence_marker)},}}\s*$", line
        ):
            fences.append((fence_start, index + 1))
            fence_start = None
            fence_marker = ""
    return fences


def classify_changes(
    changes: tuple[Change, ...],
    *,
    root: Path | None = None,
    base_reader: Callable[[str], str] | None = None,
    full_regression: bool = False,
) -> frozenset[Job]:
    if full_regression:
        return ALL_JOBS
    selected: set[Job] = set()
    for change in changes:
        for path in change.paths:
            selected.update(_jobs_for_path(path))
        markdown_paths = tuple(path for path in change.paths if path.startswith("docs/") and path.endswith(".md"))
        for path in markdown_paths:
            old_text = "" if base_reader is None else base_reader(change.old_path)
            current = (root or Path(".")) / path
            new_text = current.read_text(encoding="utf-8") if current.is_file() else ""
            if executable_markdown_changed(old_text, new_text):
                selected.update(ALL_JOBS)
    return frozenset(selected)


def _jobs_for_path(path: str) -> set[Job]:
    if path.startswith((".github/workflows/", "labs/_shared/", "scripts/", "tools/")):
        return set(ALL_JOBS)
    if path.startswith("labs/"):
        return {Job.SCRIPTS, Job.BICEP}
    for prefix, job in APP_JOBS.items():
        if path.startswith(prefix):
            jobs = {job}
            if path.endswith(".sh"):
                jobs.add(Job.SCRIPTS)
            if "/infra/" in path or path.endswith((".bicep", ".bicepparam")):
                jobs.add(Job.BICEP)
            if prefix == "apps/nodejs/" and _in_node_container_context(path):
                jobs.add(Job.NODEJS_CONTAINER)
            return jobs
    if path.startswith("apps/"):
        return set(ALL_JOBS)
    return set()


def _in_node_container_context(path: str) -> bool:
    relative = path.removeprefix("apps/nodejs/")
    return relative in {"Dockerfile", ".dockerignore", "smoke-container.sh"} or not relative.startswith(
        ("test/", "infra/", "node_modules/", "coverage/", ".github/")
    )


def _git_output(*args: str) -> bytes:
    return subprocess.run(
        ("git", *args), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--base", dest="base", default=None)
    _ = parser.add_argument("--head", dest="head", default="HEAD")
    _ = parser.add_argument("--full-regression", action="store_true")
    _ = parser.add_argument("--github-output", type=Path)
    _ = parser.add_argument("--name-status-input", type=Path)
    namespace = ArgumentNamespace()
    _ = parser.parse_args(namespace=namespace)
    args = Arguments(
        base=namespace.base,
        head=namespace.head,
        full_regression=namespace.full_regression,
        github_output=namespace.github_output,
        name_status_input=namespace.name_status_input,
    )
    base = args.base or f"{args.head}^"
    raw = (
        args.name_status_input.read_bytes()
        if args.name_status_input is not None
        else _git_output("diff", "--name-status", "-z", "--find-renames", base, args.head)
    )
    changes = parse_name_status_z(raw)

    def read_base(path: str) -> str:
        result = subprocess.run(
            ("git", "show", f"{base}:{path}"),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return result.stdout if result.returncode == 0 else ""

    selected = classify_changes(
        changes, base_reader=read_base, full_regression=args.full_regression
    )
    lines = [f"{job.value}={'true' if job in selected else 'false'}" for job in Job]
    for change in changes:
        print(f"{change.status}\t{' -> '.join(change.paths)}")
    print("Selected jobs: " + (", ".join(sorted(job.value for job in selected)) or "none"))
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as output:
            _ = output.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
