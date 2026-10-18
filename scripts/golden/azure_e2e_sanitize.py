#!/usr/bin/env python3
"""Build a minimal, allowlisted diagnostic artifact from private Azure evidence."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Final, TypeAlias

from scripts.golden.azure_e2e_artifact_scan import (
    ArtifactValidationError,
    validate_artifact_tree,
)

RESOURCE_ID_PLACEHOLDER: Final = (
    "/subscriptions/00000000-0000-0000-0000-000000000000/"
    "resourceGroups/rg-golden-e2e/providers/Microsoft.Web/sites/app-golden-e2e"
)
RUN_ID_RE: Final = re.compile(r"^(?:[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}|[0-9]+-[1-9][0-9]*)$")
SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
GROUP_RE: Final = re.compile(r"^rg-golden-e2e-[0-9]+-[1-9][0-9]*$")
GITHUB_ID_RE: Final = re.compile(r"^[0-9]{1,20}$")
GITHUB_ATTEMPT_RE: Final = re.compile(r"^[1-9][0-9]{0,5}$")
SAFE_LINE_RE: Final = re.compile(r"^[A-Za-z0-9._:/ -]{1,240}$")
IP_RE: Final = re.compile(r"(?:\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b|[0-9A-Fa-f]*:[0-9A-Fa-f:]+)")
GUID_RE: Final = re.compile(r"\b[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\b")
OPAQUE_RE: Final = re.compile(r"[A-Za-z0-9+/_-]{20,}={0,2}")
SHORT_OPAQUE_LINE_RE: Final = re.compile(r"[A-Za-z0-9+/_-]{12,19}")
SUMMARY_HEADER_RE: Final = re.compile(r"source_lines: ([0-9]+)\nexit_code: (-?[0-9]+)\n")
SUMMARY_LINE_RE: Final = re.compile(r"line ([1-9][0-9]*): (.*)")
UNSAFE_MARKERS: Final = (
    "authorization", "basic ", "bearer ", "x-api-key", "client-secret", "client_secret",
    "password", "passwd", "token", "secret", "sig:", "?", "@", "=", "\\", "{", "}",
    "[", "]", '"', "'",
)
STATUS_VALUES: Final = frozenset({
    "BLOCKED", "COMPLETE", "FAIL", "FAILED", "INCONCLUSIVE", "NOT_RUN", "PASS", "PENDING",
    "SUPPORTED", "CONTRADICTED", "VERIFIED",
})
SCENARIO_VALUES: Final = frozenset({"deployment-succeeded-startup-failed"})
JsonScalar = None | bool | int | float | str
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
Recognizer: TypeAlias = Callable[[JsonValue], JsonScalar | None]


class SanitizationError(Exception):
    """Private evidence could not be converted to the public artifact contract."""


def _reject_constant(value: str) -> None:
    raise SanitizationError(f"non-finite JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise SanitizationError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, JsonValue] | None:
    try:
        value: JsonValue = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _matching_string(value: JsonValue, pattern: re.Pattern[str]) -> str | None:
    return value if isinstance(value, str) and pattern.fullmatch(value) else None


def _timestamp(value: JsonValue) -> str | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return value if parsed.tzinfo is not None and 2000 <= parsed.year <= 2100 else None


def _enum(value: JsonValue, values: frozenset[str]) -> str | None:
    return value if isinstance(value, str) and value in values else None


def _bounded_int(value: JsonValue, minimum: int, maximum: int) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum else None


def _boolean(value: JsonValue) -> bool | None:
    return value if isinstance(value, bool) else None


def _resource_id(value: JsonValue) -> str | None:
    return RESOURCE_ID_PLACEHOLDER if isinstance(value, str) and value.startswith("/subscriptions/") else None


SCHEMAS: Final[dict[str, dict[str, Recognizer]]] = {
    "run.json": {
        "run_id": lambda value: _matching_string(value, RUN_ID_RE),
        "execution_status": lambda value: _enum(value, STATUS_VALUES),
        "hypothesis_status": lambda value: _enum(value, STATUS_VALUES),
        "cleanup_status": lambda value: _enum(value, STATUS_VALUES),
        "started_at": _timestamp, "ended_at": _timestamp, "captured_at": _timestamp,
        "source_commit": lambda value: _matching_string(value, SHA_RE),
        "target_commit": lambda value: _matching_string(value, SHA_RE),
        "scenario": lambda value: _enum(value, SCENARIO_VALUES), "resource_id": _resource_id,
        "exit_code": lambda value: _bounded_int(value, -255, 255),
        "command_exit": lambda value: _bounded_int(value, -255, 255),
        "assertion_count": lambda value: _bounded_int(value, 0, 1_000_000),
        "assertions_passed": lambda value: _bounded_int(value, 0, 1_000_000),
        "assertions_failed": lambda value: _bounded_int(value, 0, 1_000_000),
    },
    "evaluation.json": {
        "run_id": lambda value: _matching_string(value, RUN_ID_RE), "evaluated_at": _timestamp,
        "evidence_validation": lambda value: _enum(value, STATUS_VALUES),
        "hypothesis_evaluation": lambda value: _enum(value, STATUS_VALUES),
        "independent_reproduction": lambda value: _enum(value, STATUS_VALUES),
        "matching_import_errors": lambda value: _bounded_int(value, 0, 1_000_000),
        "assertion_count": lambda value: _bounded_int(value, 0, 1_000_000),
        "assertions_passed": lambda value: _bounded_int(value, 0, 1_000_000),
        "assertions_failed": lambda value: _bounded_int(value, 0, 1_000_000),
    },
    "cleanup-result.json": {
        "github_run_id": lambda value: _matching_string(value, GITHUB_ID_RE),
        "github_run_attempt": lambda value: _matching_string(value, GITHUB_ATTEMPT_RE),
        "run_id": lambda value: _matching_string(value, RUN_ID_RE),
        "group_name": lambda value: _matching_string(value, GROUP_RE),
        "cleanup_status": lambda value: _enum(value, STATUS_VALUES), "exists": _boolean,
        "started_at": _timestamp, "ended_at": _timestamp, "verified_at": _timestamp,
        "exit_code": lambda value: _bounded_int(value, -255, 255),
    },
}


def _copy_fields(source: dict[str, JsonValue], filename: str) -> dict[str, JsonScalar]:
    retained: dict[str, JsonScalar] = {}
    for output_key, recognize in SCHEMAS[filename].items():
        input_key = "source_sha" if output_key == "source_commit" and "source_sha" in source else output_key
        if input_key not in source:
            continue
        value = source.get(input_key)
        allowed = recognize(value)
        if allowed is not None:
            retained[output_key] = allowed
    return retained


def _write_json(path: Path, document: dict[str, JsonScalar]) -> None:
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _safe_line(line: str) -> bool:
    lowered = line.casefold()
    return bool(
        SAFE_LINE_RE.fullmatch(line)
        and not any(marker in lowered for marker in UNSAFE_MARKERS)
        and not OPAQUE_RE.search(line)
        and SHORT_OPAQUE_LINE_RE.fullmatch(line) is None
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


def _canonical_log_summary(text: str) -> str:
    header = SUMMARY_HEADER_RE.match(text)
    if header is None:
        return _log_summary(text)
    output = [f"source_lines: {header.group(1)}", f"exit_code: {header.group(2)}"]
    for line in text[header.end():].splitlines():
        match = SUMMARY_LINE_RE.fullmatch(line)
        if match is None:
            return _log_summary(text)
        payload = match.group(2)
        retained = payload if payload == "<line dropped: unsafe>" or _safe_line(payload) else "<line dropped: unsafe>"
        output.append(f"line {match.group(1)}: {retained}")
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
    source_is_valid = True
    try:
        validate_artifact_tree(source)
    except ArtifactValidationError:
        source_is_valid = False
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
                retained = _copy_fields(document, "evaluation.json")
                if retained:
                    _write_json(destination / "evaluation.json", retained)
                continue
            if path.name == "cleanup-result.json":
                retained = _copy_fields(document, path.name)
                if retained:
                    _write_json(destination / path.name, retained)
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
        summary = _canonical_log_summary(text) if source_is_valid else _log_summary(text)
        (destination / f"log-{log_index:04d}.txt").write_text(summary, encoding="utf-8")
    if run_candidates:
        source_run = max(run_candidates, key=lambda item: int("resource_id" in item))
        retained = _copy_fields(source_run, "run.json")
        if retained:
            _write_json(destination / "run.json", retained)
    if not any(destination.iterdir()):
        raise SanitizationError("private evidence contained no allowlisted diagnostic fields")


def scan_sanitized_tree(root: Path) -> None:
    """Validate the output tree with the structurally independent artifact scanner."""
    try:
        validate_artifact_tree(root)
    except ArtifactValidationError as exc:
        raise SanitizationError(str(exc)) from exc
