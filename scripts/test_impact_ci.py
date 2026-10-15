#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import final


SCRIPT = Path(__file__).with_name("impact_ci.py")
ALL_OUTPUTS = {
    "scripts",
    "nodejs",
    "nodejs_container",
    "python",
    "dotnet",
    "java",
    "bicep",
    "golden",
}


@final
class ImpactCiIntegrationTests(unittest.TestCase):
    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    root = Path()

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        _ = self._git("init", "--initial-branch=main")
        _ = self._git("config", "user.name", "CI Test")
        _ = self._git("config", "user.email", "ci@example.com")
        self._write("README.md", "initial\n")
        self._commit("initial")

    def tearDown(self) -> None:
        if self.temporary_directory is not None:
            self.temporary_directory.cleanup()

    def test_normal_multi_commit_push_uses_push_base(self) -> None:
        base = self._git("rev-parse", "HEAD").stdout.strip()
        self._write("docs/note.md", "prose only\n")
        self._commit("docs")
        self._write("apps/python-flask/src/app.py", "print('changed')\n")
        self._commit("app")

        result, outputs = self._select(push_base=base)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs["python"], "true")
        self.assertEqual(outputs["java"], "false")

    def test_pull_request_uses_base_sha_and_writes_exact_output_map(self) -> None:
        base = self._git("rev-parse", "HEAD").stdout.strip()
        self._write("apps/python-flask/src/app.py", "print('changed')\n")
        self._commit("app")

        result, outputs = self._select(event_name="pull_request", pr_base=base)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            outputs,
            {
                "scripts": "false",
                "nodejs": "false",
                "nodejs_container": "false",
                "python": "true",
                "dotnet": "false",
                "java": "false",
                "bicep": "false",
                "golden": "false",
            },
        )

    def test_all_zero_push_base_fails_safe_to_full_regression(self) -> None:
        result, outputs = self._select(push_base="0" * 40)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({key for key, value in outputs.items() if value == "true"}, ALL_OUTPUTS)

    def test_empty_push_base_fails_safe_to_full_regression(self) -> None:
        result, outputs = self._select(push_base="")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({key for key, value in outputs.items() if value == "true"}, ALL_OUTPUTS)

    def test_unreachable_push_base_fails_safe_to_full_regression(self) -> None:
        _ = self._git("checkout", "--orphan", "detached-history")
        _ = self._git("rm", "--force", "README.md")
        self._write("orphan.txt", "orphan\n")
        self._commit("orphan")
        unreachable = self._git("rev-parse", "HEAD").stdout.strip()
        _ = self._git("checkout", "main")

        result, outputs = self._select(push_base=unreachable)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({key for key, value in outputs.items() if value == "true"}, ALL_OUTPUTS)

    def test_merge_commit_push_classifies_entire_push_range(self) -> None:
        base = self._git("rev-parse", "HEAD").stdout.strip()
        _ = self._git("checkout", "-b", "feature")
        self._write("apps/java-springboot/src/App.java", "class App {}\n")
        self._commit("feature")
        _ = self._git("checkout", "main")
        self._write("docs/note.md", "prose only\n")
        self._commit("main docs")
        _ = self._git("merge", "--no-ff", "feature", "--message", "merge feature")

        result, outputs = self._select(push_base=base)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs["java"], "true")
        self.assertEqual(outputs["python"], "false")

    def test_malformed_selection_is_rejected_before_job_results_are_read(self) -> None:
        environment = os.environ.copy()
        environment.update({f"SELECTED_{name}": "false" for name in self._job_names()})
        environment["SELECTED_PYTHON"] = "yes"
        environment["RESULT_CLASSIFY"] = "success"

        result = subprocess.run(
            (sys.executable, str(SCRIPT), "aggregate"),
            cwd=self.root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SELECTED_PYTHON", result.stderr)
        self.assertNotIn("RESULT_PYTHON", result.stderr)

    def test_selected_and_unselected_job_results_are_enforced(self) -> None:
        environment = os.environ.copy()
        environment["RESULT_CLASSIFY"] = "success"
        for name in self._job_names():
            environment[f"SELECTED_{name}"] = "true" if name == "PYTHON" else "false"
            environment[f"RESULT_{name}"] = "success" if name == "PYTHON" else "skipped"

        result = subprocess.run(
            (sys.executable, str(SCRIPT), "aggregate"),
            cwd=self.root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def _select(
        self,
        *,
        event_name: str = "push",
        pr_base: str = "",
        push_base: str = "",
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
        output = self.root / "github-output.txt"
        result = subprocess.run(
            (
                sys.executable,
                str(SCRIPT),
                "select",
                "--event-name",
                event_name,
                "--pr-base",
                pr_base,
                "--push-base",
                push_base,
                "--github-output",
                str(output),
            ),
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        values = dict(line.split("=", 1) for line in output.read_text().splitlines()) if output.exists() else {}
        return result, values

    @staticmethod
    def _job_names() -> tuple[str, ...]:
        return ("SCRIPTS", "NODEJS", "NODEJS_CONTAINER", "PYTHON", "DOTNET", "JAVA", "BICEP", "GOLDEN")

    def _write(self, relative_path: str, content: str) -> None:
        path = self.root / relative_path
        _ = path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(content, encoding="utf-8")

    def _commit(self, message: str) -> None:
        _ = self._git("add", ".")
        _ = self._git("commit", "--message", message)

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ("git", *args),
            cwd=self.root,
            text=True,
            capture_output=True,
            check=True,
        )


if __name__ == "__main__":
    _ = unittest.main()
