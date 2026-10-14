#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Final


ROOT: Final = Path(__file__).resolve().parent.parent
CLASSIFIER: Final = ROOT / "scripts" / "impact_classifier.py"
JOB_NAMES: Final = (
    "SCRIPTS",
    "NODEJS",
    "NODEJS_CONTAINER",
    "PYTHON",
    "DOTNET",
    "JAVA",
    "BICEP",
    "GOLDEN",
)


class Arguments(argparse.Namespace):
    command: str = ""
    event_name: str = ""
    pr_base: str = ""
    push_base: str = ""
    github_output: Path = Path()


def _valid_push_base(base: str, head: str = "HEAD") -> bool:
    if not base or set(base) == {"0"}:
        return False
    return subprocess.run(
        ("git", "merge-base", "--is-ancestor", base, head),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def select(event_name: str, pr_base: str, push_base: str, github_output: Path) -> int:
    full_regression = event_name in {"workflow_dispatch", "schedule"}
    base = "HEAD"
    if event_name == "pull_request":
        base = pr_base
    elif event_name == "push" and _valid_push_base(push_base):
        base = push_base
    elif event_name == "push":
        full_regression = True

    command = [
        sys.executable,
        str(CLASSIFIER),
        "--base",
        base,
        "--github-output",
        str(github_output),
    ]
    if full_regression:
        command.append("--full-regression")
    return subprocess.run(command, check=False).returncode


def aggregate() -> int:
    selections: dict[str, bool] = {}
    for name in JOB_NAMES:
        variable = f"SELECTED_{name}"
        value = os.environ.get(variable, "")
        if value not in {"true", "false"}:
            print(f"::error::{variable} must be exactly true or false; got {value!r}", file=sys.stderr)
            return 1
        selections[name] = value == "true"

    classify_result = os.environ.get("RESULT_CLASSIFY", "")
    if classify_result != "success":
        print(
            f"::error::Impact classification did not succeed: {classify_result}",
            file=sys.stderr,
        )
        return 1

    failed = False
    for name, selected in selections.items():
        variable = f"RESULT_{name}"
        result = os.environ.get(variable, "")
        expected = "success" if selected else "skipped"
        if result != expected:
            print(
                f"::error::{variable} must be {expected}; got {result!r}",
                file=sys.stderr,
            )
            failed = True
    return int(failed)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    select_parser = subparsers.add_parser("select")
    _ = select_parser.add_argument("--event-name", required=True)
    _ = select_parser.add_argument("--pr-base", default="")
    _ = select_parser.add_argument("--push-base", default="")
    _ = select_parser.add_argument("--github-output", type=Path, required=True)
    _ = subparsers.add_parser("aggregate")
    arguments = Arguments()
    _ = parser.parse_args(namespace=arguments)
    if arguments.command == "aggregate":
        return aggregate()
    return select(
        arguments.event_name,
        arguments.pr_base,
        arguments.push_base,
        arguments.github_output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
