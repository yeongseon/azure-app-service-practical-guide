#!/usr/bin/env python3
"""Independent structural validator for uploadable Azure E2E artifacts."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Final, TypeAlias

FILE_RE: Final = re.compile(
    r"^(?:run\.json|evaluation\.json|cleanup-result\.json|failure-record\.json|raw-log-[0-9]{4}\.json)$"
)
RAW_LOG_FILE_RE: Final = re.compile(r"raw-log-[0-9]{4}\.json")
RUN_ID_RE: Final = re.compile(r"(?:[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}|[0-9]+-[1-9][0-9]*)")
SHA_RE: Final = re.compile(r"[0-9a-f]{40}")
GROUP_RE: Final = re.compile(r"rg-golden-e2e-[0-9]+-[1-9][0-9]*")
GITHUB_ID_RE: Final = re.compile(r"[0-9]{1,20}")
GITHUB_ATTEMPT_RE: Final = re.compile(r"[1-9][0-9]{0,5}")
RESOURCE: Final = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-golden-e2e/providers/Microsoft.Web/sites/app-golden-e2e"
TIMESTAMP_RE: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})"
)
ENUMS: Final = frozenset({
    "BLOCKED", "COMPLETE", "FAIL", "FAILED", "INCONCLUSIVE", "NOT_RUN", "PASS", "PENDING",
    "SUPPORTED", "CONTRADICTED", "VERIFIED",
})
FAILURE_STATUSES: Final = frozenset({"BLOCKED", "FAILED"})
FAILURE_STAGES: Final = frozenset({
    "target-validation", "oidc-config", "oidc-login", "provisioning", "deployment",
    "runner-start", "runner-crash", "evaluation", "sanitize",
})
SCENARIOS: Final = frozenset({"deployment-succeeded-startup-failed"})
JsonScalar: TypeAlias = None | bool | int | float | str
Validator: TypeAlias = Callable[[JsonScalar], bool]


class ArtifactValidationError(Exception):
    """An upload artifact violates the closed structural contract."""


def _string_matches(value: JsonScalar, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _timestamp(value: JsonScalar) -> bool:
    if not isinstance(value, str) or TIMESTAMP_RE.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and 2000 <= parsed.year <= 2100


def _bounded_int(value: JsonScalar, minimum: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _reject_constant(value: str) -> None:
    raise ArtifactValidationError(f"non-finite JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, JsonScalar]]) -> dict[str, JsonScalar]:
    result: dict[str, JsonScalar] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactValidationError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _status(value: JsonScalar) -> bool:
    return isinstance(value, str) and value in ENUMS


SCHEMAS: Final[dict[str, dict[str, Validator]]] = {
    "run.json": {
        "run_id": lambda value: _string_matches(value, RUN_ID_RE),
        "execution_status": _status, "hypothesis_status": _status, "cleanup_status": _status,
        "started_at": _timestamp, "ended_at": _timestamp, "captured_at": _timestamp,
        "source_commit": lambda value: _string_matches(value, SHA_RE),
        "target_commit": lambda value: _string_matches(value, SHA_RE),
        "scenario": lambda value: isinstance(value, str) and value in SCENARIOS,
        "resource_id": lambda value: value == RESOURCE,
        "exit_code": lambda value: _bounded_int(value, -255, 255),
        "command_exit": lambda value: _bounded_int(value, -255, 255),
        "assertion_count": lambda value: _bounded_int(value, 0, 1_000_000),
        "assertions_passed": lambda value: _bounded_int(value, 0, 1_000_000),
        "assertions_failed": lambda value: _bounded_int(value, 0, 1_000_000),
    },
    "evaluation.json": {
        "run_id": lambda value: _string_matches(value, RUN_ID_RE), "evaluated_at": _timestamp,
        "evidence_validation": _status, "hypothesis_evaluation": _status,
        "independent_reproduction": _status,
        "matching_import_errors": lambda value: _bounded_int(value, 0, 1_000_000),
        "assertion_count": lambda value: _bounded_int(value, 0, 1_000_000),
        "assertions_passed": lambda value: _bounded_int(value, 0, 1_000_000),
        "assertions_failed": lambda value: _bounded_int(value, 0, 1_000_000),
    },
    "cleanup-result.json": {
        "github_run_id": lambda value: _string_matches(value, GITHUB_ID_RE),
        "github_run_attempt": lambda value: _string_matches(value, GITHUB_ATTEMPT_RE),
        "run_id": lambda value: _string_matches(value, RUN_ID_RE),
        "group_name": lambda value: _string_matches(value, GROUP_RE), "cleanup_status": _status,
        "exists": lambda value: isinstance(value, bool), "started_at": _timestamp,
        "ended_at": _timestamp, "verified_at": _timestamp,
        "exit_code": lambda value: _bounded_int(value, -255, 255),
    },
    "raw-log.json": {
        "role": lambda value: isinstance(value, str) and value in {"scenario-runner", "runner-log"},
        "byte_length": lambda value: _bounded_int(value, 0, 10_000_000_000),
        "line_count": lambda value: _bounded_int(value, 0, 100_000_000),
        "sha256": lambda value: _string_matches(value, re.compile(r"[0-9a-f]{64}")),
    },
    "failure-record.json": {
        "status": lambda value: isinstance(value, str) and value in FAILURE_STATUSES,
        "failure_stage": lambda value: isinstance(value, str) and value in FAILURE_STAGES,
        "github_run_id": lambda value: _string_matches(value, GITHUB_ID_RE),
        "github_run_attempt": lambda value: _string_matches(value, GITHUB_ATTEMPT_RE),
        "evidence_run_id": lambda value: _string_matches(value, RUN_ID_RE),
        "exit_code": lambda value: _bounded_int(value, -255, 255),
        "started_at": _timestamp,
        "ended_at": _timestamp,
    },
}


def _validate_json(path: Path) -> None:
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ArtifactValidationError, ValueError) as exc:
        raise ArtifactValidationError(f"invalid JSON artifact: {path.name}") from exc
    schema = SCHEMAS["raw-log.json"] if RAW_LOG_FILE_RE.fullmatch(path.name) else SCHEMAS[path.name]
    if not isinstance(document, dict) or not document or not set(document).issubset(schema):
        raise ArtifactValidationError(f"JSON artifact violates key allowlist: {path.name}")
    if not all(schema[key](value) for key, value in document.items()):
        raise ArtifactValidationError(f"JSON artifact violates value constraints: {path.name}")
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    if path.read_text(encoding="utf-8") != canonical:
        raise ArtifactValidationError(f"JSON artifact is not canonical: {path.name}")


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
        _validate_json(path)
