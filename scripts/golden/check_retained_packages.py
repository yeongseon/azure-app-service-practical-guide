#!/usr/bin/env python3
"""Reject edits or deletion of retained Golden packages relative to a base ref."""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _base_ref(explicit: str | None) -> str:
    if explicit:
        return explicit
    pull_request_base = os.environ.get("GITHUB_BASE_REF")
    if pull_request_base:
        return f"origin/{pull_request_base}"
    return "origin/main"


def changed_retained_paths(base_ref: str) -> list[str]:
    """Return existing retained-package paths modified or removed since base."""
    completed = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", f"{base_ref}...HEAD", "--"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    violations: list[str] = []
    for line in completed.stdout.splitlines():
        columns = line.split("\t")
        status = columns[0]
        paths = columns[1:]
        if status == "A":
            continue
        for path in paths:
            retained_run = path.startswith("evidence/runs/")
            lab_golden = path.startswith("labs/") and "/golden/" in path
            if retained_run or lab_golden:
                violations.append(path)
    return sorted(set(violations))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref")
    args = parser.parse_args()
    try:
        violations = changed_retained_paths(_base_ref(args.base_ref))
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or "could not compare retained packages", file=sys.stderr)
        return 2
    if violations:
        print("Retained Golden packages are immutable; changed existing paths:", file=sys.stderr)
        for path in violations:
            print(f"- {path}", file=sys.stderr)
        print(
            "Preserve the package and add a new run directory. Deliberate retirement requires "
            "a separately reviewed archive change, never an in-place rewrite.",
            file=sys.stderr,
        )
        return 1
    print("Retained Golden package immutability: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
