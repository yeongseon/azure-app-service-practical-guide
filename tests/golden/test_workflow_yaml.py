#!/usr/bin/env python3
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

from ruamel.yaml import YAML

ROOT = pathlib.Path(__file__).resolve().parents[2]


class WorkflowYamlTests(unittest.TestCase):
    def test_every_workflow_rejects_no_duplicate_keys(self):
        yaml = YAML(typ="safe")
        yaml.allow_duplicate_keys = False
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            with self.subTest(path=path.name), path.open() as stream:
                yaml.load(stream)

    def test_commit_hash_validation_requires_hex_format(self):
        # Given: the Python heredoc embedded in the provenance-fetch workflow step.
        yaml = YAML(typ="safe")
        workflow_path = ROOT / ".github/workflows/validate-content-sources.yml"
        with workflow_path.open(encoding="utf-8") as stream:
            workflow = yaml.load(stream)
        steps = workflow["jobs"]["validate-golden-contracts"]["steps"]
        fetch_step = next(
            step
            for step in steps
            if step.get("name") == "Fetch retained Golden provenance commits"
        )
        script_match = re.search(
            r"python3 - <<'PY'[^\n]*\n(?P<script>.*?)\nPY(?:\n|$)",
            fetch_step["run"],
            re.DOTALL,
        )
        assert script_match is not None
        script = script_match.group("script")

        valid_lowercase = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        invalid_non_hex = "g" * 40
        invalid_uppercase = "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2"
        with tempfile.TemporaryDirectory() as temporary_directory:
            runs_directory = pathlib.Path(temporary_directory) / "evidence/runs"
            valid_directory = runs_directory / "valid"
            valid_directory.mkdir(parents=True)
            (valid_directory / "manifest.json").write_text(
                json.dumps({"source_commit": valid_lowercase}), encoding="utf-8"
            )
            non_hex_directory = runs_directory / "non-hex"
            non_hex_directory.mkdir()
            (non_hex_directory / "provenance.json").write_text(
                json.dumps(
                    {"derivation": {"collector_commit": invalid_non_hex}}
                ),
                encoding="utf-8",
            )
            uppercase_directory = runs_directory / "uppercase"
            uppercase_directory.mkdir()
            (uppercase_directory / "provenance.json").write_text(
                json.dumps(
                    {"derivation": {"collector_commit": invalid_uppercase}}
                ),
                encoding="utf-8",
            )

            # When: the exact extracted workflow code discovers commits to fetch.
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=temporary_directory,
                check=True,
                capture_output=True,
                text=True,
            )

        # Then: only a lowercase hexadecimal SHA is emitted.
        self.assertEqual(completed.stdout.splitlines(), [valid_lowercase])

    def test_content_validation_filters_cover_all_gate_inputs(self):
        yaml = YAML(typ="safe")
        workflow_path = ROOT / ".github/workflows/validate-content-sources.yml"
        with workflow_path.open(encoding="utf-8") as stream:
            workflow = yaml.load(stream)
        required = {"docs/**", "evidence/**", "schemas/**", "tests/**", "scripts/**"}

        for event in ("pull_request", "push"):
            with self.subTest(event=event):
                self.assertTrue(required <= set(workflow["on"][event]["paths"]))
                self.assertNotIn("paths-ignore", workflow["on"][event])

        self.assertIn("main", workflow["on"]["push"]["branches"])
        pull_request_paths = workflow["on"]["pull_request"]["paths"]
        self.assertIn("requirements-docs.txt", pull_request_paths)
        self.assertEqual([path for path in pull_request_paths if path.startswith("!")], [])

    def test_documentation_build_job_installs_and_builds_strictly_without_conditions(self) -> None:
        # Given: the parsed pull-request documentation build job and its two commands.
        yaml = YAML(typ="safe")
        workflow_path = ROOT / ".github/workflows/validate-content-sources.yml"
        with workflow_path.open(encoding="utf-8") as stream:
            workflow = yaml.load(stream)
        job = workflow["jobs"]["build-docs"]
        commands = ("pip install -r requirements-docs.txt", "mkdocs build --strict")
        for defaults in (workflow.get("defaults"), job.get("defaults")):
            run_defaults = (defaults or {}).get("run", {})
            self.assertNotIn("working-directory", run_defaults)
            self.assertEqual(run_defaults.get("shell", "bash"), "bash")

        # When: each command is resolved to the step that runs it exactly.
        for command in commands:
            with self.subTest(command=command):
                steps = [step for step in job["steps"] if step.get("run", "").strip() == command]

                # Then: neither a missing step nor a skip, dependency, fail-open policy or other
                # working directory or shell is allowed.
                self.assertEqual(len(steps), 1, command)
                self.assertNotIn("needs", job, command)
                for scope in (job, steps[0]):
                    self.assertNotIn("continue-on-error", scope, command)
                    self.assertNotIn("if", scope, command)
                self.assertNotIn("working-directory", steps[0], command)
                self.assertEqual(steps[0].get("shell", "bash"), "bash", command)

        # And: the dependencies are installed before the site is built.
        runs = [step.get("run", "").strip() for step in job["steps"]]
        self.assertLess(runs.index(commands[0]), runs.index(commands[1]))

    def test_diagram_gates_are_unconditional_and_blocking_when_workflow_runs(self) -> None:
        # Given: the parsed content-validation job and its required diagram commands.
        yaml = YAML(typ="safe")
        workflow_path = ROOT / ".github/workflows/validate-content-sources.yml"
        with workflow_path.open(encoding="utf-8") as stream:
            workflow = yaml.load(stream)
        job = workflow["jobs"]["validate-content-sources"]
        commands = (
            "python scripts/test_diagram_inventory.py",
            "python scripts/diagram_inventory.py --check",
            "python scripts/diagram_inventory.py --verify-tree --strict",
            "python scripts/test_check_diagram_manifest_coverage.py",
            "python scripts/check_diagram_manifest_coverage.py",
        )

        # When: each command is resolved to the step that executes it exactly.
        for command in commands:
            with self.subTest(command=command):
                steps = [step for step in job["steps"] if step.get("run", "").strip() == command]

                # Then: neither a missing step nor a skip/fail-open policy is allowed.
                self.assertEqual(len(steps), 1, command)
                self.assertNotIn("needs", job, command)
                for scope in (job, steps[0]):
                    self.assertNotIn("continue-on-error", scope, command)
                    self.assertNotIn("if", scope, command)

    def test_refresh_workflow_regenerates_the_manifest_after_the_dashboard(self) -> None:
        # Given: the parsed scheduled refresh job and the commands of its steps.
        yaml = YAML(typ="safe")
        workflow_path = ROOT / ".github/workflows/refresh-golden-status.yml"
        with workflow_path.open(encoding="utf-8") as stream:
            workflow = yaml.load(stream)
        steps = workflow["jobs"]["refresh"]["steps"]
        runs = [step.get("run", "") for step in steps]

        # When: the dashboard, manifest and publication steps are located.
        dashboard = [i for i, run in enumerate(runs) if "python scripts/generate_golden_status.py" in run]
        manifest = [i for i, run in enumerate(runs) if run.strip() == "python scripts/diagram_inventory.py --write"]
        publication = [i for i, run in enumerate(runs) if "git commit" in run]

        # Then: the manifest is regenerated once, between them, unconditionally, and committed with the dashboard.
        self.assertEqual((len(dashboard), len(manifest), len(publication)), (1, 1, 1))
        self.assertLess(dashboard[0], manifest[0])
        self.assertLess(manifest[0], publication[0])
        self.assertNotIn("continue-on-error", steps[manifest[0]])
        self.assertNotIn("if", steps[manifest[0]])
        staged = " ".join(line for line in runs[publication[0]].splitlines() if line.strip().startswith("git add"))
        for path in (
            "docs/meta/golden-status.md",
            "docs/reference/diagram-manifest.json",
            "docs/reference/diagram-inventory.md",
        ):
            self.assertIn(path, staged)

    def test_documentation_deployment_filter_covers_build_inputs(self):
        yaml = YAML(typ="safe")
        workflow_path = ROOT / ".github/workflows/docs.yml"
        with workflow_path.open(encoding="utf-8") as stream:
            workflow = yaml.load(stream)
        push = workflow["on"]["push"]
        required = {
            "docs/**",
            "mkdocs.yml",
            "requirements-docs.txt",
            "scripts/capture/manifest.yaml",
            ".github/workflows/docs.yml",
        }

        self.assertTrue(required <= set(push["paths"]))
        self.assertEqual([path for path in push["paths"] if path.startswith("!")], [])
        self.assertNotIn("paths-ignore", push)
        self.assertIn("main", push["branches"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
