#!/usr/bin/env python3
"""Command-line boundary for protected Azure Scenario A helpers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.golden.azure_e2e_guard import (
    GuardError,
    SanitizationError,
    inspect_run,
    parse_target_sha,
    render_summary,
    require_target_paths,
    sanitize_tree,
    scan_sanitized_tree,
    summary_from_run,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    target = subparsers.add_parser("validate-target")
    target.add_argument("sha")
    target_paths = subparsers.add_parser("require-target-paths")
    target_paths.add_argument("repository", type=Path)
    target_paths.add_argument("sha")
    inspect = subparsers.add_parser("inspect-run")
    inspect.add_argument("run_dir", type=Path)
    sanitize = subparsers.add_parser("sanitize")
    sanitize.add_argument("source", type=Path)
    sanitize.add_argument("destination", type=Path)
    summary = subparsers.add_parser("summary")
    summary.add_argument("run_dir", type=Path)
    summary.add_argument("--target-commit", required=True)
    summary.add_argument("--environment", required=True)
    summary.add_argument("--mode", choices=("azure", "offline"), required=True)
    summary.add_argument("--github-run-id", required=True)
    summary.add_argument("--github-run-attempt", required=True)
    scan = subparsers.add_parser("scan-sanitized")
    scan.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.action == "validate-target":
        try:
            print(parse_target_sha(args.sha))
        except GuardError as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 3
        return 0
    if args.action == "require-target-paths":
        try:
            require_target_paths(args.repository, args.sha)
        except GuardError as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 3
        return 0
    if args.action == "inspect-run":
        outcome = inspect_run(args.run_dir)
        print(json.dumps(outcome._asdict(), indent=2))
        return outcome.exit_code
    if args.action == "sanitize":
        try:
            sanitize_tree(args.source, args.destination)
        except (GuardError, SanitizationError, OSError) as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 4
        return 0
    if args.action == "scan-sanitized":
        try:
            scan_sanitized_tree(args.root)
        except (GuardError, SanitizationError, OSError, UnicodeDecodeError) as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 4
        return 0
    try:
        print(render_summary(summary_from_run(
            args.run_dir,
            args.target_commit,
            args.environment,
            args.mode,
            args.github_run_id,
            args.github_run_attempt,
        )), end="")
    except (GuardError, OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
