#!/usr/bin/env python3
"""Build a minimal, allowlisted diagnostic artifact from private Azure evidence."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

from scripts.golden.azure_e2e_artifact_scan import ArtifactValidationError, validate_artifact_tree

RESOURCE_ID_PLACEHOLDER: Final = (
    "/subscriptions/00000000-0000-0000-0000-000000000000/"
    "resourceGroups/rg-golden-e2e/providers/Microsoft.Web/sites/app-golden-e2e"
)
RUN_ID_RE: Final = re.compile(r"^(?:[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}|[0-9]+-[1-9][0-9]*)$")
SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
TIMESTAMP_RE: Final = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.+-]+Z?$")
GROUP_RE: Final = re.compile(r"^rg-golden-e2e-[0-9]+-[1-9][0-9]*$")
SHORT_RE: Final = re.compile(r"^[A-Za-z0-9._:/ -]{1,160}$")
SAFE_LINE_RE: Final = re.compile(r"^[A-Za-z0-9._:/ -]{1,240}$")
IP_RE: Final = re.compile(r"(?:\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b|[0-9A-Fa-f]*:[0-9A-Fa-f:]+)")
GUID_RE: Final = re.compile(r"\b[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\b")
OPAQUE_RE: Final = re.compile(r"[A-Za-z0-9+/_-]{20,}={0,2}")
UNSAFE_MARKERS: Final = (
    "authorization", "basic ", "bearer ", "x-api-key", "client-secret", "client_secret",
    "password", "passwd", "token", "secret", "sig:", "?", "@", "=", "\\", "{", "}",
    "[", "]", '"', "'",
)
STATUS_VALUES: Final = frozenset({
    "BLOCKED", "COMPLETE", "FAIL", "FAILED", "INCONCLUSIVE", "NOT_RUN", "PASS", "PENDING",
    "SUPPORTED", "CONTRADICTED", "VERIFIED",
})
JsonScalar = None | bool | int | float | str
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class SanitizationError(Exception):
    """Private evidence could not be converted to the public artifact contract."""


def _load_json(path: Path) -> dict[str, JsonValue] | None:
    try:
        value: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _allowed_string(key: str, value: JsonValue) -> str | None:
    if not isinstance(value, str):
        return None
    if key in {"started_at", "ended_at", "captured_at", "evaluated_at", "verified_at"}:
        return value if TIMESTAMP_RE.fullmatch(value) else None
    if key in {"source_commit", "source_sha", "target_commit"}:
        return value if SHA_RE.fullmatch(value) else None
    if key == "run_id":
        return value if RUN_ID_RE.fullmatch(value) else None
    if key == "group_name":
        return value if GROUP_RE.fullmatch(value) else None
    if key == "resource_id":
        return RESOURCE_ID_PLACEHOLDER if value.startswith("/subscriptions/") else None
    if key.endswith("_status") or key in {
        "evidence_validation", "hypothesis_evaluation", "independent_reproduction",
    }:
        return value if value in STATUS_VALUES else None
    return value if SHORT_RE.fullmatch(value) else None


def _copy_fields(source: dict[str, JsonValue], fields: tuple[str, ...]) -> dict[str, JsonScalar]:
    retained: dict[str, JsonScalar] = {}
    for output_key in fields:
        input_key = "source_sha" if output_key == "source_commit" and "source_sha" in source else output_key
        value = source.get(input_key)
        if isinstance(value, bool | int | float) or value is None:
            retained[output_key] = value
        else:
            allowed = _allowed_string(output_key, value)
            if allowed is not None:
                retained[output_key] = allowed
    return retained


def _safe_line(line: str) -> bool:
    lowered = line.casefold()
    return bool(
        SAFE_LINE_RE.fullmatch(line)
        and not any(marker in lowered for marker in UNSAFE_MARKERS)
        and not OPAQUE_RE.search(line)
        and not IP_RE.search(line)
        and not GUID_RE.search(line)
    )


def _log_summary(text: str, exit_code: int | None = None, last_lines: int = 40) -> str:
    lines = text.splitlines()
    start = max(0, len(lines) - last_lines)
    output = [f"source_lines: {len(lines)}", f"exit_code: {exit_code if exit_code is not None else -1}"]
    for index, line in enumerate(lines[start:], start=start + 1):
        output.append(f"line {index}: {line}" if _safe_line(line) else f"line {index}: <line dropped: unsafe>")
    return "\n".join(output) + "\n"


def _command_summary(document: dict[str, JsonValue]) -> str | None:
    exit_code = document.get("exit_code")
    stdout = document.get("stdout")
    stderr = document.get("stderr")
    if not isinstance(exit_code, int) or not isinstance(stdout, str) or not isinstance(stderr, str):
        return None
    combined = stdout + (("\n" if stdout and stderr else "") + stderr)
    return _log_summary(combined, exit_code)


def sanitize_text(value: str) -> str:
    """Return the fixed log-summary form used for unstructured input."""
    return _log_summary(value)


def sanitize_tree(source: Path, destination: Path) -> None:
    """Drop all private input except explicitly allowlisted structured fields and log summaries."""
    destination.mkdir(parents=True, exist_ok=False)
    try:
        validate_artifact_tree(source)
    except ArtifactValidationError:
        pass
    else:
        for path in source.iterdir():
            (destination / path.name).write_bytes(path.read_bytes())
        return
    log_index = 0
    run_candidates: list[dict[str, JsonValue]] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix == ".json":
            document = _load_json(path)
            if document is None:
                continue
            if path.name == "run.json":
                run_candidates.append(document)
                continue
            if path.name.startswith("evaluation-") or path.name == "evaluation.json":
                retained = _copy_fields(document, (
                    "run_id", "evaluated_at", "evidence_validation", "hypothesis_evaluation",
                    "independent_reproduction", "matching_import_errors", "assertion_count",
                    "assertions_passed", "assertions_failed",
                ))
                (destination / "evaluation.json").write_text(json.dumps(retained, indent=2) + "\n", encoding="utf-8")
                continue
            if path.name == "cleanup-result.json":
                retained = _copy_fields(document, (
                    "github_run_id", "github_run_attempt", "run_id", "group_name", "cleanup_status",
                    "exists", "started_at", "ended_at", "verified_at", "exit_code",
                ))
                (destination / path.name).write_text(json.dumps(retained, indent=2) + "\n", encoding="utf-8")
                continue
            summary = _command_summary(document)
            if summary is not None:
                log_index += 1
                (destination / f"log-{log_index:04d}.txt").write_text(summary, encoding="utf-8")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        log_index += 1
        (destination / f"log-{log_index:04d}.txt").write_text(_log_summary(text), encoding="utf-8")
    if run_candidates:
        source_run = max(run_candidates, key=lambda item: int("resource_id" in item))
        retained = _copy_fields(source_run, (
            "run_id", "execution_status", "hypothesis_status", "cleanup_status", "started_at",
            "ended_at", "captured_at", "source_commit", "target_commit", "scenario", "resource_id",
            "exit_code", "command_exit", "assertion_count", "assertions_passed", "assertions_failed",
        ))
        (destination / "run.json").write_text(json.dumps(retained, indent=2) + "\n", encoding="utf-8")
    if not any(destination.iterdir()):
        raise SanitizationError("private evidence contained no allowlisted diagnostic fields")


def scan_sanitized_tree(root: Path) -> None:
    """Validate the output tree with the structurally independent artifact scanner."""
    try:
        validate_artifact_tree(root)
    except ArtifactValidationError as exc:
        raise SanitizationError(str(exc)) from exc
