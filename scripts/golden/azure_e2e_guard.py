#!/usr/bin/env python3
"""Fail-closed helpers for the protected Azure Scenario A workflow."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.golden.azure_e2e_sanitize import (
    RESOURCE_ID_PLACEHOLDER,
    SanitizationError,
    sanitize_tree,
    scan_sanitized_tree,
)

__all__ = ("RESOURCE_ID_PLACEHOLDER", "sanitize_tree", "scan_sanitized_tree")

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_EVIDENCE = (
    "baseline/phase.json",
    "fault/phase.json",
    "recovery/phase.json",
    "console.json",
)
REQUIRED_TARGET_PATHS = (
    "scripts/golden/azure_cleanup.py",
    "scripts/golden/azure_e2e_cli.py",
    "scripts/golden/azure_e2e_guard.py",
    "scripts/golden/azure_e2e_artifact_scan.py",
    "scripts/golden/azure_e2e_sanitize.py",
    "labs/deployment-succeeded-startup-failed/run.py",
)


GuardError = SanitizationError


class RunOutcome(NamedTuple):
    execution_status: str
    exit_code: int
    message: str


class RunSummary(NamedTuple):
    target_commit: str
    run_id: str
    github_run_id: str
    github_run_attempt: str
    environment: str
    execution_status: str
    captured_at: str
    evaluated_at: str
    mode: str


def parse_target_sha(value: str) -> str:
    if not SHA_RE.fullmatch(value):
        raise GuardError("target commit must be a lowercase 40-character SHA")
    return value


def require_target_paths(repository: Path, target_sha: str) -> None:
    sha = parse_target_sha(target_sha)
    for path in REQUIRED_TARGET_PATHS:
        result = subprocess.run(
            ["git", "ls-tree", sha, "--", path],
            cwd=repository,
            capture_output=True,
            text=True,
            check=False,
        )
        fields = result.stdout.split(maxsplit=3)
        if result.returncode != 0 or len(fields) != 4 or fields[0] not in {"100644", "100755"} or fields[1] != "blob":
            raise GuardError(f"target commit lacks a regular helper blob: {path}")


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
    evaluations = sorted(run_dir.glob("evaluation-*.json"))
    if not evaluations:
        return RunOutcome("FAILED", 4, "evaluation result is missing")
    if run.get("execution_status") != "COMPLETE":
        return RunOutcome("FAILED", 4, "runner execution was not COMPLETE")
    artifacts = run.get("artifacts")
    if not isinstance(artifacts, dict):
        return RunOutcome("FAILED", 4, "run artifact manifest is missing")
    for name in REQUIRED_EVIDENCE:
        binding = artifacts.get(name)
        path = run_dir / name
        if not isinstance(binding, dict):
            return RunOutcome("FAILED", 4, f"required evidence is not manifest-bound: {name}")
        data = path.read_bytes()
        if binding.get("size") != len(data) or binding.get("sha256") != hashlib.sha256(data).hexdigest():
            return RunOutcome("FAILED", 4, f"required evidence binding mismatch: {name}")
    try:
        evaluation = json.loads(evaluations[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return RunOutcome("FAILED", 4, f"evaluation result is invalid: {exc}")
    if not isinstance(evaluation, dict):
        return RunOutcome("FAILED", 4, "evaluation result must be an object")
    if evaluation.get("run_id") != run.get("run_id") or run.get("run_id") != run_dir.name:
        return RunOutcome("FAILED", 4, "evaluation run identity is not bound to the run manifest")
    if evaluation.get("evidence_validation") != "PASS":
        return RunOutcome("FAILED", 4, "evidence validation did not PASS")
    if evaluation.get("hypothesis_evaluation") != "SUPPORTED":
        return RunOutcome("FAILED", 4, "hypothesis evaluation was not SUPPORTED")
    try:
        started = datetime.fromisoformat(str(run["started_at"]))
        ended = datetime.fromisoformat(str(run["ended_at"]))
        evaluated = datetime.fromisoformat(str(evaluation["evaluated_at"]))
    except (KeyError, ValueError) as exc:
        return RunOutcome("FAILED", 4, f"capture or evaluation window is invalid: {exc}")
    if started.tzinfo is None or ended.tzinfo is None or evaluated.tzinfo is None or not started <= ended <= evaluated:
        return RunOutcome("FAILED", 4, "evaluation is not bound to an ordered capture window")
    return RunOutcome("COMPLETE", 0, "runner evidence and evaluation are valid and bound")




def render_summary(summary: RunSummary) -> str:
    label = "Offline replay" if summary.mode == "offline" else "Azure execution"
    return "\n".join(
        (
            "## Golden Scenario A",
            f"- Mode: {label}",
            f"- Target commit: `{summary.target_commit}`",
            f"- Run ID: `{summary.run_id}`",
            f"- GitHub run ID: `{summary.github_run_id}` attempt `{summary.github_run_attempt}`",
            f"- Environment: `{summary.environment}`",
            f"- Execution status: `{summary.execution_status}`",
            f"- Captured at: `{summary.captured_at}`",
            f"- Evaluated at: `{summary.evaluated_at}`",
        )
    ) + "\n"


def summary_from_run(
    run_dir: Path,
    target_commit: str,
    environment: str,
    mode: str,
    github_run_id: str,
    github_run_attempt: str,
) -> RunSummary:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    evaluations = sorted(run_dir.glob("evaluation-*.json"))
    evaluated_at = "not-evaluated"
    if evaluations:
        evaluation = json.loads(evaluations[-1].read_text(encoding="utf-8"))
        evaluated_at = str(evaluation.get("evaluated_at", "not-recorded"))
    return RunSummary(
        target_commit=parse_target_sha(target_commit),
        run_id=str(run.get("run_id", run_dir.name)),
        github_run_id=github_run_id,
        github_run_attempt=github_run_attempt,
        environment=environment,
        execution_status=str(run.get("execution_status", "BLOCKED")),
        captured_at=str(run.get("started_at", "not-recorded")),
        evaluated_at=evaluated_at,
        mode=mode,
    )
