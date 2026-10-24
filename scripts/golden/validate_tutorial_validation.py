#!/usr/bin/env python3
"""Validate tutorial frontmatter and retained-package references."""

from __future__ import annotations

import argparse
from datetime import date
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Final

import yaml


ROOT: Final = Path(__file__).resolve().parents[2]
TUTORIAL_GLOB: Final = "docs/language-guides/*/tutorial/*.md"
METHODS: Final = frozenset({"az_cli", "bicep"})
METHOD_FIELDS: Final = frozenset(
    {"last_tested", "cli_version", "result", "run_id", "evidence"}
)
RESULTS: Final = frozenset({"pass", "fail", "not_tested"})
FRONTMATTER: Final = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _load_frontmatter(text: str) -> tuple[dict[str, Any] | None, str | None]:
    match = FRONTMATTER.match(text)
    if match is None:
        return None, "missing YAML frontmatter"
    try:
        document = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return None, f"malformed YAML frontmatter: {exc.problem or 'parse error'}"
    if not isinstance(document, dict):
        return None, "frontmatter must be a mapping"
    return document, None


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )


def _base_documents(
    root: Path, base_ref: str, tutorials: list[Path]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    commit = _git(root, "cat-file", "-e", f"{base_ref}^{{commit}}")
    if commit.returncode != 0:
        return {}, [f"base commit is unavailable: {base_ref}"]
    documents: dict[str, dict[str, Any]] = {}
    for path in tutorials:
        relative = path.relative_to(root).as_posix()
        shown = _git(root, "show", f"{base_ref}:{relative}")
        if shown.returncode != 0:
            continue
        document, problem = _load_frontmatter(shown.stdout)
        if problem is not None:
            return {}, [f"{relative}: base {problem}"]
        assert document is not None
        documents[relative] = document
    return documents, []


def _validate_run_id(run_id: str) -> str | None:
    """Validate run_id is safe and canonical. Return error message or None."""
    if not run_id:
        return "run_id must be non-empty"
    if "/" in run_id or "\\" in run_id:
        return "run_id must be a single path component (no separators)"
    if run_id in (".", ".."):
        return f"run_id cannot be {run_id}"
    if not re.match(r"^[a-zA-Z0-9._-]+$", run_id):
        return "run_id contains invalid characters"
    return None


def _validate_retained_package(root: Path, run_id: str, evidence: str) -> str | None:
    """Validate retained package reference is safe and points to canonical location.
    
    Returns error message or None if valid.
    """
    expected_evidence = f"evidence/runs/{run_id}"
    if evidence != expected_evidence:
        return f"evidence field must equal '{expected_evidence}' (got '{evidence}')"
    
    evidence_path = root / "evidence"
    runs_path = evidence_path / "runs"
    package_path = runs_path / run_id
    try:
        if package_path.is_symlink():
            return "symlink not allowed in package directory"
        for component in (evidence_path, runs_path):
            if component.is_symlink():
                return "symlink not allowed in path to runs directory"
    except (OSError, ValueError):
        return "cannot check symlink status of package path"

    try:
        package_resolved = package_path.resolve()
        root_resolved = root.resolve()
        evidence_runs_resolved = (root_resolved / "evidence" / "runs").resolve()
    except (OSError, RuntimeError) as exc:
        return f"cannot resolve package path: {exc}"
    
    if package_resolved.parent != evidence_runs_resolved:
        return "resolved package parent must exactly equal <repo>/evidence/runs"
    
    if not package_resolved.is_dir():
        return "retained package directory does not exist or is not a directory"
    
    return None


def _method_problems(
    root: Path,
    key: str,
    method_data: Any,
    base_method: Any,
    today: date,
) -> list[str]:
    if not isinstance(method_data, dict):
        return [f"{key} must be a mapping"]
    problems: list[str] = []
    unknown = sorted(set(method_data) - METHOD_FIELDS)
    if unknown:
        problems.append(f"{key}: unknown fields: {', '.join(unknown)}")
    result = method_data.get("result")
    if result not in RESULTS:
        problems.append(f"{key}: invalid result")
        return problems
    tested = method_data.get("last_tested")
    run_id = method_data.get("run_id")
    evidence = method_data.get("evidence")
    if result == "not_tested":
        if tested is not None:
            problems.append(f"{key}: not_tested requires last_tested: null")
        if run_id is not None or evidence is not None:
            problems.append(f"{key}: not_tested cannot reference retained evidence")
        return problems
    try:
        tested_date = tested if type(tested) is date else date.fromisoformat(tested)
    except (TypeError, ValueError):
        tested_date = None
    if tested_date is None:
        problems.append(f"{key}: invalid last_tested date")
    elif tested_date > today:
        problems.append(f"{key}: future last_tested date")
    references_complete = isinstance(run_id, str) and isinstance(evidence, str)
    if run_id is not None or evidence is not None:
        if not isinstance(run_id, str):
            problems.append(f"{key}: run_id must be a string")
        if not isinstance(evidence, str):
            problems.append(f"{key}: evidence must be a string")
        if isinstance(run_id, str):
            run_id_error = _validate_run_id(run_id)
            if run_id_error:
                problems.append(f"{key}: {run_id_error}")
            elif isinstance(evidence, str):
                package_error = _validate_retained_package(root, run_id, evidence)
                if package_error:
                    problems.append(f"{key}: {package_error}")
    changed_pass = result == "pass" and method_data != base_method
    if changed_pass and not references_complete:
        problems.append(f"{key}: new or changed pass requires run_id and evidence")
    return problems


def validate(root: Path, *, base_ref: str, today: date | None = None) -> list[str]:
    tutorials = sorted(root.glob(TUTORIAL_GLOB))
    base_documents, problems = _base_documents(root, base_ref, tutorials)
    if problems:
        return problems
    check_date = today or date.today()
    for path in tutorials:
        relative = path.relative_to(root).as_posix()
        document, problem = _load_frontmatter(path.read_text(encoding="utf-8"))
        if problem is not None:
            problems.append(f"{relative}: {problem}")
            continue
        assert document is not None
        validation = document.get("validation")
        if validation is None:
            continue
        if not isinstance(validation, dict):
            problems.append(f"{relative}: validation must be a mapping")
            continue
        unknown_methods = sorted(set(validation) - METHODS)
        if unknown_methods:
            problems.append(
                f"{relative}: unknown validation method: {', '.join(unknown_methods)}"
            )
        base_validation = base_documents.get(relative, {}).get("validation")
        base_mapping = base_validation if isinstance(base_validation, dict) else {}
        for method in sorted(METHODS & set(validation)):
            problems.extend(
                _method_problems(
                    root,
                    f"{relative}#{method}",
                    validation[method],
                    base_mapping.get(method),
                    check_date,
                )
            )
    return sorted(set(problems))


def _base_ref(explicit: str | None) -> str:
    if explicit:
        return explicit
    base = os.environ.get("GITHUB_BASE_REF")
    return f"origin/{base}" if base else "origin/main"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--base-ref")
    args = parser.parse_args()
    problems = validate(
        args.root.resolve(), base_ref=_base_ref(args.base_ref), today=date.today()
    )
    if problems:
        print("Tutorial validation contract failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("Tutorial validation contract: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
