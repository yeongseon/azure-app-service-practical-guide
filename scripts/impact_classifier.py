#!/usr/bin/env python3
"""Select App and Infra CI jobs from Git name-status changes.

Executable Markdown is selected when its old or new document contains a fenced
shell block with an Azure CLI command or a repository/script invocation. The
document-level rule deliberately includes expected-output and recipe edits near
commands; documents with ordinary prose only stay lightweight. Bicep remains a
full apps/ and labs/ compilation gate because the repository has no proven
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
    r"^\s*(?:\$\s*)?(?:az\s|(?:bash|sh|python3?|node|npm|mvn|dotnet)\s|\./|(?:apps|labs|scripts)/\S+\.sh\b)"
)


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
    changed = bool(old_changed or new_changed)
    return changed and (_has_executable_block(old_lines) or _has_executable_block(new_lines))


def _has_executable_block(lines: list[str]) -> bool:
    fence_start: int | None = None
    for index, line in enumerate(lines):
        if fence_start is None and re.match(r"^\s*```(?:bash|sh|shell)\s*$", line):
            fence_start = index
        elif fence_start is not None and re.match(r"^\s*```\s*$", line):
            block = lines[fence_start + 1 : index]
            executable = any(SHELL_COMMAND_RE.search(block_line) for block_line in block)
            if executable:
                return True
            fence_start = None
    return False


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
