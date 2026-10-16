#!/usr/bin/env python3
"""Fail-closed helpers for the protected Azure Scenario A workflow."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import NamedTuple


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
GUID_RE = re.compile(r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
AZURE_HOST_RE = re.compile(r"\b[a-z0-9-]+\.(?:scm\.)?azurewebsites\.net\b", re.IGNORECASE)
RESOURCE_ID_RE = re.compile(
    r"/subscriptions/[^/]+/resourceGroups/[^/]+/providers/[^\s\"']+",
    re.IGNORECASE,
)
BEARER_RE = re.compile(r"(?i)(Authorization\s*[:=]\s*Bearer\s+)[A-Za-z0-9._~+/=-]+")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|connection[_-]?string)\s*[:=]\s*([^\s,;]+)"
)
LONG_HEX_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32,}(?![0-9a-fA-F])")
SECRET_NAME_RE = re.compile(
    r"(?i)(^id_(?:rsa|dsa|ecdsa|ed25519)$|\.(?:pem|pfx|p12|key)$|credential|secret)"
)
REQUIRED_EVIDENCE = (
    "baseline/phase.json",
    "fault/phase.json",
    "recovery/phase.json",
    "console.json",
)


class GuardError(Exception):
    """Workflow input or evidence failed a security boundary."""


class RunOutcome(NamedTuple):
    execution_status: str
    exit_code: int
    message: str


class RunSummary(NamedTuple):
    target_commit: str
    run_id: str
    environment: str
    execution_status: str
    captured_at: str
    evaluated_at: str
    mode: str


def parse_target_sha(value: str) -> str:
    if not SHA_RE.fullmatch(value):
        raise GuardError("target commit must be a lowercase 40-character SHA")
    return value


def inspect_run(run_dir: Path) -> RunOutcome:
    run_file = run_dir / "run.json"
    if not run_file.is_file():
        return RunOutcome("BLOCKED", 3, "run.json is missing")
    try:
        run = json.loads(run_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return RunOutcome("FAILED", 4, f"run.json is invalid: {exc}")
    missing = tuple(name for name in REQUIRED_EVIDENCE if not (run_dir / name).is_file())
    if missing:
        return RunOutcome("FAILED", 4, "required evidence missing: " + ", ".join(missing))
    if not tuple(run_dir.glob("evaluation-*.json")):
        return RunOutcome("FAILED", 4, "evaluation result is missing")
    if run.get("execution_status") != "COMPLETE":
        return RunOutcome("FAILED", 4, "runner execution was not COMPLETE")
    return RunOutcome("COMPLETE", 0, "required runner evidence is present")


def _replace_ipv4(match: re.Match[str]) -> str:
    octets = tuple(int(part) for part in match.group(0).split("."))
    if any(part > 255 for part in octets):
        return match.group(0)
    first, second, _, _ = octets
    private = first == 10 or (first == 172 and 16 <= second <= 31) or (first == 192 and second == 168)
    return "10.0.0.0" if private else "192.0.2.1"


def sanitize_text(value: str) -> str:
    sanitized = GUID_RE.sub("00000000-0000-0000-0000-000000000000", value)
    sanitized = EMAIL_RE.sub("user@example.com", sanitized)
    sanitized = RESOURCE_ID_RE.sub(
        "/subscriptions/00000000-0000-0000-0000-000000000000/"
        "resourceGroups/rg-golden-e2e/providers/Microsoft.Web/sites/app-golden-e2e",
        sanitized,
    )
    sanitized = AZURE_HOST_RE.sub("app-golden-e2e.azurewebsites.net", sanitized)
    sanitized = BEARER_RE.sub(r"\1<REDACTED_BEARER_TOKEN>", sanitized)
    sanitized = SECRET_ASSIGNMENT_RE.sub(r"\1=<REDACTED_SECRET>", sanitized)
    sanitized = LONG_HEX_RE.sub("<REDACTED_HEX_TOKEN>", sanitized)
    return IPV4_RE.sub(_replace_ipv4, sanitized)


def sanitize_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(exist_ok=True)
        elif path.is_file():
            if SECRET_NAME_RE.search(path.name):
                raise GuardError(f"refusing secret-like artifact name: {relative}")
            data = path.read_bytes()
            if b"\x00" in data:
                raise GuardError(f"refusing binary artifact: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise GuardError(f"refusing non-UTF-8 artifact: {relative}") from exc
            target.write_text(sanitize_text(text), encoding="utf-8")


def scan_sanitized_tree(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if BEARER_RE.search(text) or SECRET_ASSIGNMENT_RE.search(text) or LONG_HEX_RE.search(text):
            raise GuardError(f"sanitized artifact still contains a secret-like value: {path.relative_to(root)}")


def render_summary(summary: RunSummary) -> str:
    label = "Offline replay" if summary.mode == "offline" else "Azure execution"
    return "\n".join(
        (
            "## Golden Scenario A",
            f"- Mode: {label}",
            f"- Target commit: `{summary.target_commit}`",
            f"- Run ID: `{summary.run_id}`",
            f"- Environment: `{summary.environment}`",
            f"- Execution status: `{summary.execution_status}`",
            f"- Captured at: `{summary.captured_at}`",
            f"- Evaluated at: `{summary.evaluated_at}`",
        )
    ) + "\n"


def summary_from_run(run_dir: Path, target_commit: str, environment: str, mode: str) -> RunSummary:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    evaluations = sorted(run_dir.glob("evaluation-*.json"))
    evaluated_at = "not-evaluated"
    if evaluations:
        evaluation = json.loads(evaluations[-1].read_text(encoding="utf-8"))
        evaluated_at = str(evaluation.get("evaluated_at", "not-recorded"))
    return RunSummary(
        target_commit=parse_target_sha(target_commit),
        run_id=str(run.get("run_id", run_dir.name)),
        environment=environment,
        execution_status=str(run.get("execution_status", "BLOCKED")),
        captured_at=str(run.get("started_at", "not-recorded")),
        evaluated_at=evaluated_at,
        mode=mode,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    target = subparsers.add_parser("validate-target")
    target.add_argument("sha")
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
    if args.action == "inspect-run":
        outcome = inspect_run(args.run_dir)
        print(json.dumps(outcome._asdict(), indent=2))
        return outcome.exit_code
    if args.action == "sanitize":
        try:
            sanitize_tree(args.source, args.destination)
        except (GuardError, OSError) as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 4
        return 0
    if args.action == "scan-sanitized":
        try:
            scan_sanitized_tree(args.root)
        except (GuardError, OSError, UnicodeDecodeError) as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 4
        return 0
    if args.action != "summary":
        raise GuardError(f"unsupported action: {args.action}")
    try:
        print(render_summary(summary_from_run(args.run_dir, args.target_commit, args.environment, args.mode)), end="")
    except (GuardError, OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
