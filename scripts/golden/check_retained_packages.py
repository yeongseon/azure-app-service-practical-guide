#!/usr/bin/env python3
"""Verify immutable retained Golden packages and their append-only digest registry."""

from __future__ import annotations

import argparse
import datetime
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
SCENARIO_A_RECIPE = pathlib.Path("scripts/golden/scenario-a-recipe.json")
SCENARIO_B_RECIPE = pathlib.Path("scripts/golden/scenario-b-recipe.json")


def recipe_definition(repo: pathlib.Path, scenario: str) -> dict:
    path = SCENARIO_B_RECIPE if scenario == "snat-exhaustion" else SCENARIO_A_RECIPE
    return json.loads((repo / path).read_text())


FROZEN_HISTORICAL_RUN_IDS = {
    "20260927T104304Z-aba0d3a9daa7",
    "20260927T114621Z-04c6c02c9ae1",
}


def _git_bytes(repo: pathlib.Path, commit: str, path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=repo, capture_output=True, check=False)
    if completed.returncode != 0:
        subprocess.run(
            ["git", "fetch", "--no-tags", "origin", commit], cwd=repo,
            capture_output=True, check=False)
        completed = subprocess.run(
            ["git", "show", f"{commit}:{path}"], cwd=repo,
            capture_output=True, check=False)
    if completed.returncode != 0:
        raise ValueError(f"source_commit does not contain provenance input: {path}")
    return completed.stdout


def _provenance_digest_problems(
        repo: pathlib.Path, manifest: dict, scenario: str) -> list[str]:
    source_commit = manifest.get("source_commit")
    recipe_paths = manifest.get("recipe_paths")
    definition = recipe_definition(repo, scenario)
    if recipe_paths != definition.get("recipe_paths"):
        return ["provenance inputs do not match the versioned recipe definition"]
    if (not isinstance(source_commit, str)
            or not isinstance(recipe_paths, list) or not recipe_paths):
        return ["new COMPLETE run lacks reproducible provenance inputs"]
    try:
        common = pathlib.PurePosixPath(os.path.commonpath(recipe_paths)).as_posix()
        prefix = common.rstrip("/") + "/"
        fingerprints = {
            path.removeprefix(prefix): hashlib.sha256(
                _git_bytes(repo, source_commit, path)).hexdigest()
            for path in sorted(recipe_paths)
        }
    except ValueError as exc:
        return [str(exc)]
    canonical = json.dumps(fingerprints, sort_keys=True, separators=(",", ":")).encode()
    recipe = hashlib.sha256(canonical).hexdigest()
    problems = []
    if manifest.get("recipe_digest") != f"sha256:{recipe}":
        problems.append("recipe_digest does not match canonical source fingerprints")
    return problems


def _derivation_problems(repo: pathlib.Path, run_dir: pathlib.Path, manifest: dict) -> list[str]:
    provenance_path = run_dir / "provenance.json"
    evidence_path = run_dir / "evidence.json"
    if not provenance_path.is_file() or not evidence_path.is_file():
        return ["new COMPLETE run lacks derivation provenance"]
    provenance = json.loads(provenance_path.read_text())
    evidence = json.loads(evidence_path.read_text())
    derivation = provenance.get("derivation")
    if not isinstance(derivation, dict) or derivation.get("derived_offline") is not True:
        return ["new COMPLETE run lacks offline derivation metadata"]
    definition = recipe_definition(repo, provenance.get("scenario", ""))
    declaration = json.loads((repo / DECLARATIONS).read_text())["runs"].get(
        manifest.get("run_id"), {})
    collector_commit = derivation.get("collector_commit")
    current_collector = collector_commit == definition.get("derivation_collector_commit")
    declared_collector = collector_commit == declaration.get("collector_commit")
    if (derivation.get("collector_path") != definition.get("collector_path")
            or not (current_collector or declared_collector)):
        return ["derivation collector does not match the versioned recipe definition"]
    expected_digest = definition.get("derivation_collector_digest")
    collector_digest = derivation.get("collector_digest")
    if current_collector and collector_digest != expected_digest:
        return ["derivation collector digest does not match the versioned recipe definition"]
    try:
        collector_bytes = _git_bytes(
            repo, derivation["collector_commit"], derivation["collector_path"])
    except ValueError:
        collector_path = repo / derivation["collector_path"]
        if not collector_path.is_file():
            return ["derivation collector is unavailable from both Git and the checkout"]
        collector_bytes = collector_path.read_bytes()
    actual = hashlib.sha256(collector_bytes).hexdigest()
    problems = []
    if collector_digest != f"sha256:{actual}":
        problems.append("derivation collector digest mismatch")
    try:
        derived_at = datetime.datetime.fromisoformat(
            derivation["derived_at"].replace("Z", "+00:00"))
        captured_at = datetime.datetime.fromisoformat(
            manifest["captured_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError) as exc:
        return [f"invalid derivation timestamp: {exc}"]
    if derived_at < captured_at:
        problems.append("derivation predates capture")
    if derived_at > datetime.datetime.now(datetime.timezone.utc):
        problems.append("derivation is in the future")
    required_shape = ({"phase_windows", "phase_probes", "destination_health",
                       "destination_binding", "snat_port_pressure"}
                      if provenance.get("scenario") == "snat-exhaustion"
                      else {"fault_status", "fault_console_rows", "phase_windows",
                            "baseline_probes", "fault_probes", "recovery_probes"})
    observations = evidence.get("observations") or {}
    if not required_shape <= set(observations):
        problems.append("derivation evidence shape is incomplete")
    return problems


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
                or not DECLARATION_FIELDS <= set(declaration)
                or set(declaration) - DECLARATION_FIELDS - {"collector_commit"}
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
            root = _package_root(relative)
            if root and root.startswith("evidence/runs/"):
                directory_id = pathlib.PurePosixPath(root).name
                if package_id != directory_id:
                    problems.append(f"retained package key does not match directory identity: {relative}")

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
            directory_id = pathlib.PurePosixPath(relative).parent.name
            if manifest.get("run_id") != directory_id or package_id != directory_id:
                problems.append(f"retained run identity mismatch: {relative}")
            for name in ("evidence.json", "result.json"):
                sibling = repo / pathlib.PurePosixPath(relative).parent / name
                if sibling.is_file() and json.loads(sibling.read_text()).get("run_id") != directory_id:
                    problems.append(f"retained run identity mismatch: {sibling.relative_to(repo)}")
            new_package = package_id not in base_packages
            if (manifest.get("execution_status") == "COMPLETE"
                    and not frozen_historical and new_package):
                source_commit = manifest.get("source_commit")
                environment = manifest.get("environment")
                required_env = ("subscription_kind", "region", "runtime", "sku")
                if (not isinstance(source_commit, str) or len(source_commit) != 40
                        or not isinstance(environment, dict)
                        or any(not environment.get(field) for field in required_env)
                        or not manifest.get("recipe_digest")
                        or not manifest.get("hypothesis_claim_level")):
                    problems.append(f"new COMPLETE run lacks full provenance: {package_id}")
                problems.extend(
                    f"{package_id}: {problem}"
                    for problem in _provenance_digest_problems(
                        repo, manifest,
                        current_declarations["runs"][package_id]["scenario"])
                )
                problems.extend(
                    f"{package_id}: {problem}"
                    for problem in _derivation_problems(
                        repo, (repo / relative).parent, manifest)
                )

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
