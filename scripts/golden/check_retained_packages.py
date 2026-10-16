#!/usr/bin/env python3
"""Verify immutable retained Golden packages and their append-only digest registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIGESTS = pathlib.Path("evidence/retained-digests.json")
DECLARATIONS = pathlib.Path("evidence/run-declarations.json")
DECLARATION_FIELDS = {"scenario", "retained_package"}
FROZEN_HISTORICAL_RUN_IDS = {
    "20260927T104304Z-aba0d3a9daa7",
    "20260927T114621Z-04c6c02c9ae1",
}


def _base_ref(explicit: str | None) -> str:
    if explicit:
        return explicit
    base = os.environ.get("GITHUB_BASE_REF")
    return f"origin/{base}" if base else "origin/main"


def _git(repo: pathlib.Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True
    ).stdout


def _document(repo: pathlib.Path, revision: str | None = None) -> dict:
    if revision is None:
        text = (repo / DIGESTS).read_text()
    else:
        text = _git(repo, "show", f"{revision}:{DIGESTS.as_posix()}")
    return json.loads(text)


def _declarations(repo: pathlib.Path, revision: str | None = None) -> dict:
    if revision is None:
        path = repo / DECLARATIONS
        if not path.is_file():
            return {"version": 1, "runs": {}}
        text = path.read_text()
    else:
        try:
            text = _git(repo, "show", f"{revision}:{DECLARATIONS.as_posix()}")
        except subprocess.CalledProcessError:
            return {"version": 1, "runs": {}}
    return json.loads(text)


def _declaration_problems(current: dict, base: dict) -> list[str]:
    problems: list[str] = []
    if set(current) != {"version", "runs"} or current.get("version") != 1:
        problems.append("run declaration registry has an invalid top-level schema")
        return problems
    runs = current.get("runs")
    if not isinstance(runs, dict):
        return ["run declaration registry runs must be an object"]
    base_runs = base.get("runs") if isinstance(base.get("runs"), dict) else {}
    for run_id, declaration in runs.items():
        if (not isinstance(declaration, dict)
                or set(declaration) != DECLARATION_FIELDS
                or not isinstance(declaration.get("scenario"), str)
                or not declaration["scenario"].strip()):
            problems.append(f"invalid run declaration schema: {run_id}")
            continue
        expected = f"evidence/runs/{run_id}"
        if declaration.get("retained_package") != expected:
            problems.append(f"run declaration has non-canonical retained_package: {run_id}")
    for run_id, declaration in base_runs.items():
        if runs.get(run_id) != declaration:
            problems.append(f"existing run declaration changed or removed: {run_id}")
    return problems


def _package_root(path: str) -> str | None:
    parts = pathlib.PurePosixPath(path).parts
    if len(parts) >= 4 and parts[:2] == ("evidence", "runs"):
        return "/".join(parts[:3])
    if len(parts) >= 4 and parts[0] == "labs" and parts[2] == "golden":
        return "/".join(parts[:3])
    return None


def violations(repo: pathlib.Path, base_ref: str) -> list[str]:
    """Return digest, immutability, and append-only registry violations."""
    current = _document(repo)
    current_declarations = _declarations(repo)
    packages = current.get("packages") or {}
    problems: list[str] = []
    registered: set[str] = set()
    for package_id, package in packages.items():
        files = package.get("files") if isinstance(package, dict) else None
        if not isinstance(files, dict) or not files:
            problems.append(f"digest entry has no files: {package_id}")
            continue
        for relative, expected in files.items():
            registered.add(relative)
            path = repo / relative
            if not path.is_file():
                problems.append(f"registered retained file missing: {relative}")
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                problems.append(f"retained digest mismatch: {relative}")

    tracked = _git(repo, "ls-files", "evidence/runs", "labs/*/golden").splitlines()
    for relative in tracked:
        if _package_root(relative) and relative not in registered:
            problems.append(f"retained file is not digest-registered: {relative}")

    try:
        base = _document(repo, base_ref)
    except subprocess.CalledProcessError:
        base = {"packages": {}}
    base_packages = base.get("packages") or {}
    problems.extend(_declaration_problems(
        current_declarations, _declarations(repo, base_ref)))
    for package_id, entry in base_packages.items():
        if packages.get(package_id) != entry:
            problems.append(f"existing digest entry changed or removed: {package_id}")
    for package_id, entry in packages.items():
        frozen_historical = package_id in FROZEN_HISTORICAL_RUN_IDS
        if (package_id not in base_packages and entry.get("historical") is True
                and not frozen_historical):
            problems.append(f"new digest entry cannot be historical: {package_id}")
        files = entry.get("files") or {}
        manifests = [path for path in files if path.startswith("evidence/runs/")
                     and path.endswith("/manifest.json")]
        for relative in manifests:
            manifest = json.loads((repo / relative).read_text())
            if manifest.get("execution_status") == "COMPLETE" and not frozen_historical:
                source_commit = manifest.get("source_commit")
                environment = manifest.get("environment")
                required_env = ("subscription_kind", "region", "runtime", "sku")
                if (not isinstance(source_commit, str) or len(source_commit) != 40
                        or not isinstance(environment, dict)
                        or any(not environment.get(field) for field in required_env)
                        or not manifest.get("recipe_digest")
                        or not manifest.get("collector_digest")
                        or not manifest.get("hypothesis_claim_level")):
                    problems.append(f"new COMPLETE run lacks full provenance: {package_id}")

    base_files = set(_git(repo, "ls-tree", "-r", "--name-only", base_ref).splitlines())
    base_roots = {_package_root(path) for path in base_files if _package_root(path)}
    changes = _git(repo, "diff", "--name-status", "--find-renames", f"{base_ref}...HEAD").splitlines()
    for line in changes:
        columns = line.split("\t")
        status, paths = columns[0], columns[1:]
        for relative in paths:
            root = _package_root(relative)
            if root is None:
                continue
            whole_new_package = root not in base_roots
            if status != "A" or not whole_new_package:
                problems.append(f"existing retained package changed: {relative}")
    return sorted(set(problems))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref")
    args = parser.parse_args()
    try:
        problems = violations(ROOT, _base_ref(args.base_ref))
    except (OSError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"retained package check error: {exc}", file=sys.stderr)
        return 2
    if problems:
        print("Retained Golden package integrity failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("Retained Golden package immutability: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
