#!/usr/bin/env python3
"""Fail-closed helpers for the protected Azure Scenario A workflow."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
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
JWT_RE = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])")
BASE64_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9+/=_-])(?=[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-]))"
    r"(?=[A-Za-z0-9+/=_-]*[A-Z])(?=[A-Za-z0-9+/=_-]*[a-z])(?=[A-Za-z0-9+/=_-]*\d)"
    r"[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-])"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|account[_-]?key|client[_-]?secret|"
    r"access[_-]?key|credential|connection[_-]?string)\s*[:=]\s*([^\s,;]+)"
)
SAS_RE = re.compile(r"(?i)((?:^|[?&;])(?:sig|sv|se)=)([^&;\s]+)")
CONNECTION_STRING_RE = re.compile(
    r"(?i)DefaultEndpointsProtocol=[^;\s]+(?:;[^;\s=]+=[^;\s]*)+"
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
        started = datetime.fromisoformat(str(run["started_at"]).replace("Z", "+00:00"))
        ended = datetime.fromisoformat(str(run["ended_at"]).replace("Z", "+00:00"))
        evaluated = datetime.fromisoformat(str(evaluation["evaluated_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as exc:
        return RunOutcome("FAILED", 4, f"capture or evaluation window is invalid: {exc}")
    if started.tzinfo is None or ended.tzinfo is None or evaluated.tzinfo is None or not started <= ended <= evaluated:
        return RunOutcome("FAILED", 4, "evaluation is not bound to an ordered capture window")
    return RunOutcome("COMPLETE", 0, "runner evidence and evaluation are valid and bound")


def _replace_ipv4(match: re.Match[str]) -> str:
    octets = tuple(int(part) for part in match.group(0).split("."))
    if any(part > 255 for part in octets):
        return match.group(0)
    first, second, _, _ = octets
    private = first == 10 or (first == 172 and 16 <= second <= 31) or (first == 192 and second == 168)
    return "10.0.0.0" if private else "192.0.2.1"


def sanitize_text(value: str) -> str:
    sanitized = CONNECTION_STRING_RE.sub("DefaultEndpointsProtocol=<REDACTED>;AccountKey=<REDACTED>", value)
    sanitized = SAS_RE.sub(r"\1<REDACTED>", sanitized)
    sanitized = GUID_RE.sub("00000000-0000-0000-0000-000000000000", sanitized)
    sanitized = EMAIL_RE.sub("user@example.com", sanitized)
    sanitized = RESOURCE_ID_RE.sub(
        "/subscriptions/00000000-0000-0000-0000-000000000000/"
        "resourceGroups/rg-golden-e2e/providers/Microsoft.Web/sites/app-golden-e2e",
        sanitized,
    )
    sanitized = AZURE_HOST_RE.sub("app-golden-e2e.azurewebsites.net", sanitized)
    sanitized = BEARER_RE.sub(r"\1<REDACTED>", sanitized)
    sanitized = JWT_RE.sub("<REDACTED>", sanitized)
    sanitized = BASE64_TOKEN_RE.sub("<REDACTED>", sanitized)
    sanitized = SECRET_ASSIGNMENT_RE.sub(r"\1=<REDACTED>", sanitized)
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
        scrubbed = text.replace("<REDACTED>", "").replace("<REDACTED_HEX_TOKEN>", "")
        unsafe_guid = any(match.group(0) != "00000000-0000-0000-0000-000000000000" for match in GUID_RE.finditer(text))
        unsafe_email = any(match.group(0) != "user@example.com" for match in EMAIL_RE.finditer(text))
        unsafe_ip = any(match.group(0) not in {"10.0.0.0", "192.0.2.1"} for match in IPV4_RE.finditer(text))
        unsafe_resource = any(
            "00000000-0000-0000-0000-000000000000" not in match.group(0)
            or "resourceGroups/rg-golden-e2e/" not in match.group(0)
            for match in RESOURCE_ID_RE.finditer(text)
        )
        if (
            BEARER_RE.search(scrubbed)
            or JWT_RE.search(scrubbed)
            or BASE64_TOKEN_RE.search(scrubbed)
            or SECRET_ASSIGNMENT_RE.search(scrubbed)
            or SAS_RE.search(scrubbed)
            or CONNECTION_STRING_RE.search(scrubbed)
            or LONG_HEX_RE.search(scrubbed)
            or unsafe_guid
            or unsafe_email
            or unsafe_ip
            or unsafe_resource
        ):
            raise GuardError(f"sanitized artifact still contains a secret-like value: {path.relative_to(root)}")


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

