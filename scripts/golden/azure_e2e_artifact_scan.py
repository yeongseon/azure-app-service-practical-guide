#!/usr/bin/env python3
"""Independent structural validator for uploadable Azure E2E artifacts."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

FILE_RE: Final = re.compile(r"^(?:run\.json|evaluation\.json|cleanup-result\.json|log-[0-9]{4}\.txt)$")
LOG_HEADER_RE: Final = re.compile(r"source_lines: [0-9]+\nexit_code: -?[0-9]+\n")
LOG_LINE_RE: Final = re.compile(r"line [1-9][0-9]*: (?:<line dropped: unsafe>|[A-Za-z0-9._:/ -]{1,240})")
TIMESTAMP_RE: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.+-]+Z?")
RUN_ID_RE: Final = re.compile(r"(?:[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}|[0-9]+-[1-9][0-9]*)")
SHA_RE: Final = re.compile(r"[0-9a-f]{40}")
GROUP_RE: Final = re.compile(r"rg-golden-e2e-[0-9]+-[1-9][0-9]*")
RESOURCE: Final = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-golden-e2e/providers/Microsoft.Web/sites/app-golden-e2e"
SHORT_RE: Final = re.compile(r"[A-Za-z0-9._:/ -]{1,160}")
ENUMS: Final = frozenset({
    "BLOCKED", "COMPLETE", "FAIL", "FAILED", "INCONCLUSIVE", "NOT_RUN", "PASS", "PENDING",
    "SUPPORTED", "CONTRADICTED", "VERIFIED",
})
SCHEMAS: Final = {
    "run.json": frozenset({
        "run_id", "execution_status", "hypothesis_status", "cleanup_status", "started_at", "ended_at",
        "captured_at", "source_commit", "target_commit", "scenario", "resource_id", "exit_code",
        "command_exit", "assertion_count", "assertions_passed", "assertions_failed",
    }),
    "evaluation.json": frozenset({
        "run_id", "evaluated_at", "evidence_validation", "hypothesis_evaluation",
        "independent_reproduction", "matching_import_errors", "assertion_count", "assertions_passed",
        "assertions_failed",
    }),
    "cleanup-result.json": frozenset({
        "github_run_id", "github_run_attempt", "run_id", "group_name", "cleanup_status", "exists",
        "started_at", "ended_at", "verified_at", "exit_code",
    }),
}


class ArtifactValidationError(Exception):
    """An upload artifact violates the closed structural contract."""


def _valid_value(key: str, value: bool | int | float | str | None) -> bool:
    if isinstance(value, bool | int | float) or value is None:
        return True
    if not isinstance(value, str):
        return False
    if key.endswith("_at"):
        return bool(TIMESTAMP_RE.fullmatch(value))
    if key in {"source_commit", "target_commit"}:
        return bool(SHA_RE.fullmatch(value))
    if key == "run_id":
        return bool(RUN_ID_RE.fullmatch(value))
    if key == "group_name":
        return bool(GROUP_RE.fullmatch(value))
    if key == "resource_id":
        return value == RESOURCE
    if key.endswith("_status") or key in {"evidence_validation", "hypothesis_evaluation", "independent_reproduction"}:
        return value in ENUMS
    return bool(SHORT_RE.fullmatch(value))


def _validate_json(path: Path) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"invalid JSON artifact: {path.name}") from exc
    if not isinstance(document, dict) or not document or not set(document).issubset(SCHEMAS[path.name]):
        raise ArtifactValidationError(f"JSON artifact violates key allowlist: {path.name}")
    if not all(_valid_value(key, value) for key, value in document.items()):
        raise ArtifactValidationError(f"JSON artifact violates value constraints: {path.name}")


def _validate_log(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactValidationError(f"log is not UTF-8: {path.name}") from exc
    header = LOG_HEADER_RE.match(text)
    if header is None:
        raise ArtifactValidationError(f"log summary header is invalid: {path.name}")
    lines = text[header.end():].splitlines()
    if not lines or any(LOG_LINE_RE.fullmatch(line) is None for line in lines):
        raise ArtifactValidationError(f"log summary body is invalid: {path.name}")
    numbers = [int(line.split(":", maxsplit=1)[0].split()[1]) for line in lines]
    if numbers != sorted(set(numbers)):
        raise ArtifactValidationError(f"log summary line numbers are invalid: {path.name}")


def validate_artifact_tree(root: Path) -> None:
    """Accept only flat, nonempty trees composed of the documented output forms."""
    if not root.is_dir():
        raise ArtifactValidationError("artifact root is not an existing directory")
    paths = tuple(sorted(root.iterdir()))
    if not paths:
        raise ArtifactValidationError("artifact root is empty")
    for path in paths:
        if not path.is_file() or path.is_symlink() or FILE_RE.fullmatch(path.name) is None:
            raise ArtifactValidationError(f"artifact path is not allowlisted: {path.name}")
        if path.suffix == ".json":
            _validate_json(path)
        else:
            _validate_log(path)
