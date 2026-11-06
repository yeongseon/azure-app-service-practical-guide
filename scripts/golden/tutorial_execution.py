"""Check retained tutorial execution agreement, not execution authenticity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
from typing import Final, TypedDict

import jsonschema


SCHEMA: Final = Path(__file__).resolve().parents[2] / "schemas/golden/tutorial-execution.schema.json"


class Phase(TypedDict):
    name: str
    completed_at: str
    outcome: str


class OptionalCLI(TypedDict, total=False):
    cli_version: str


class ExecutionRecord(OptionalCLI):
    schema_version: int
    run_id: str
    tutorial: str
    method: str
    execution_status: str
    tutorial_result: str
    phases: list[Phase]
    final_required_phase: str
    final_required_phase_completed_at: str
    source_commit: str
    environment: dict[str, str]
    raw_evidence: dict[str, str]


@dataclass(frozen=True, slots=True)
class TutorialBinding:
    tutorial: str
    method: str
    result: str
    tested: date | None
    cli_version: str | None


class RecordError(ValueError):
    """Malformed JSON record, including duplicate fields and non-JSON numbers."""


def _unique_fields(pairs: list[tuple[str, ExecutionRecord]]) -> dict[str, ExecutionRecord]:
    fields: dict[str, ExecutionRecord] = {}
    for key, value in pairs:
        if key in fields:
            raise RecordError(f"duplicate JSON field: {key}")
        fields[key] = value
    return fields


def _invalid_constant(value: str) -> None:
    raise RecordError(f"invalid JSON constant: {value}")


def _regular_file(package: Path, relative: str) -> Path:
    """Resolve only canonical package-local regular files without symlinks."""
    path = PurePosixPath(relative)
    if (path.is_absolute() or path.as_posix() != relative
            or ".." in path.parts or "\\" in relative or "\0" in relative):
        raise RecordError("file path must be canonical and inside the package")
    current = package
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise RecordError("symlink not allowed in record or raw evidence path")
    if not stat.S_ISREG(current.stat().st_mode):
        raise RecordError("record and raw evidence must be regular files")
    if not current.resolve().is_relative_to(package.resolve()):
        raise RecordError("file must remain inside the package")
    return current


def _load_record(package: Path) -> tuple[ExecutionRecord | None, list[str]]:
    try:
        path = _regular_file(package, "tutorial-execution.json")
        record: ExecutionRecord = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields,
            parse_constant=_invalid_constant,
        )
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        return None, [f"invalid tutorial-execution.json: {exc}"]
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    checker = jsonschema.Draft202012Validator(schema)
    errors = list(checker.iter_errors(record))
    if errors:
        return None, [f"tutorial-execution.json schema: {error.message}" for error in errors]
    if type(record["schema_version"]) is not int:
        return None, ["schema_version must be integer 1"]
    return record, []


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RecordError("completion time requires a timezone")
    return parsed.astimezone(timezone.utc)


def _phase_problems(record: ExecutionRecord, now: datetime) -> list[str]:
    try:
        final = _utc(record["final_required_phase_completed_at"])
        times = [_utc(phase["completed_at"]) for phase in record["phases"]]
    except (ValueError, OverflowError) as exc:
        return [f"invalid phase completion time: {exc}"]
    problems: list[str] = []
    names = [phase["name"] for phase in record["phases"]]
    if len(set(names)) != len(names):
        problems.append("phase names must be unique")
    final_name = record["final_required_phase"]
    if final_name not in names:
        problems.append("final_required_phase must name a phase in phases")
    else:
        index = names.index(final_name)
        if times[index] != final:
            problems.append("final required phase completion time must agree with phases")
        if record["phases"][index]["outcome"] != record["tutorial_result"]:
            problems.append("final required phase outcome must agree with tutorial_result")
    if final > now or any(completed > now for completed in times):
        problems.append("phase completion time cannot be in the future")
    if any(completed > final for name, completed in zip(names, times) if name != final_name):
        problems.append("phase cannot complete after final_required_phase_completed_at")
    return problems


def _binding_problems(record: ExecutionRecord, binding: TutorialBinding) -> list[str]:
    problems: list[str] = []
    if record["tutorial"] != binding.tutorial:
        problems.append("record tutorial must equal the referencing tutorial metadata")
    if record["method"] != binding.method:
        problems.append("record method must equal the referencing tutorial metadata")
    if record["tutorial_result"] != binding.result:
        problems.append("record tutorial_result must equal the referencing tutorial metadata")
    allowed = {"COMPLETE"} if binding.result == "pass" else {"COMPLETE", "FAILED"}
    if record["execution_status"] not in allowed:
        problems.append(f"{binding.result} has incompatible execution_status")
    if (binding.cli_version is not None and "cli_version" in record
            and record["cli_version"] != binding.cli_version):
        problems.append("record cli_version must equal frontmatter cli_version")
    try:
        if binding.tested != _utc(record["final_required_phase_completed_at"]).date():
            problems.append("last_tested must equal the UTC date of the final required phase")
    except (ValueError, OverflowError):
        problems.append("invalid final required phase completion time")
    return problems


def _raw_problems(package: Path, digests: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for relative, expected in digests.items():
        try:
            path = _regular_file(package, relative)
            if relative == "tutorial-execution.json":
                problems.append("raw_evidence cannot reference the execution record itself")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                problems.append(f"raw_evidence SHA-256 mismatch: {relative}")
        except (OSError, ValueError, RuntimeError) as exc:
            problems.append(f"invalid raw_evidence path {relative!r}: {exc}")
    return problems


def execution_problems(package: Path, binding: TutorialBinding, now: datetime) -> list[str]:
    record, problems = _load_record(package)
    if record is None:
        return problems
    if record["run_id"] != package.name:
        problems.append("record run_id must equal the package directory and frontmatter run_id")
    problems.extend(_binding_problems(record, binding))
    problems.extend(_phase_problems(record, now))
    problems.extend(_raw_problems(package, record["raw_evidence"]))
    return problems
