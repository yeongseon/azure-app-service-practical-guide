#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.impact_classifier import (
    Change,
    Job,
    classify_changes,
    executable_markdown_changed,
    parse_name_status_z,
)


ALL_JOBS = frozenset(Job)


class ImpactClassifierTests(unittest.TestCase):
    def test_ordinary_documentation_prose_stays_lightweight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            _ = (root / "docs/overview.md").write_text("# Overview\n\nNew prose.\n")

            selected = classify_changes(
                (Change.modified("docs/overview.md"),), root=root, base_reader=lambda _: "# Overview\n\nOld prose.\n"
            )

        self.assertEqual(selected, frozenset())

    def test_executable_documentation_change_selects_full_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            _ = (root / "docs/recipe.md").write_text(
                "# Recipe\n\n```bash\naz webapp show --name \"$APP_NAME\"\n```\n"
            )

            selected = classify_changes(
                (Change.modified("docs/recipe.md"),),
                root=root,
                base_reader=lambda _: "# Recipe\n\n```bash\naz webapp list\n```\n",
            )

        self.assertEqual(selected, ALL_JOBS)

    def test_docker_recipe_change_selects_full_verification(self) -> None:
        old_text = "## Build\n\n```bash\ndocker build --tag demo .\n```\n"
        new_text = "## Build\n\n```bash\ndocker build --tag app-demo .\n```\n"

        changed = executable_markdown_changed(old_text, new_text)

        self.assertTrue(changed)

    def test_repository_command_families_select_full_verification(self) -> None:
        for command in (
            "gradle bootRun",
            "uvicorn app:app",
            "flask run",
            "mkdocs serve",
            "pip install flask",
            "nslookup example.com",
        ):
            with self.subTest(command=command):
                old_text = f"## Run\n\n```bash\n{command}\n```\n"
                new_text = old_text.replace(command, f"{command} --help")

                changed = executable_markdown_changed(old_text, new_text)

                self.assertTrue(changed)

    def test_typed_shell_fences_accept_any_command_family(self) -> None:
        recipes = (
            ("```bash", "```", "make test"),
            ("~~~sh", "~~~", "pytest -q"),
            ("```shell title=\"Install\"", "```", "pnpm install"),
            ("```bash", "```", "yarn test"),
            ("```sh", "```", "java -jar app.jar"),
            ("~~~shell", "~~~", "go test ./..."),
            ("```bash title=\"Check\"", "```", "npx prettier --check ."),
            ("```shell", "```", "Get-ChildItem Env:"),
            ("```Bash", "```", "make test"),
            ("~~~SH", "~~~", "pytest -q"),
        )
        for opening, closing, command in recipes:
            with self.subTest(opening=opening, command=command):
                old_text = f"## Run\n\n{opening}\n{command}\n{closing}\n"
                new_text = old_text.replace(command, f"{command} --verbose")

                changed = executable_markdown_changed(old_text, new_text)

                self.assertTrue(changed)

    def test_untyped_fence_keeps_command_family_heuristic(self) -> None:
        for command, expected in (("docker build .", True), ("make test", False)):
            with self.subTest(command=command):
                old_text = f"## Run\n\n```\n{command}\n```\n"
                new_text = old_text.replace(command, f"{command} --verbose")

                changed = executable_markdown_changed(old_text, new_text)

                self.assertEqual(changed, expected)

    def test_prose_only_change_outside_command_recipe_stays_lightweight(self) -> None:
        old_text = (
            "# Container\n\nOld introduction.\n\n"
            "## Build\n\n```bash\ndocker build --tag demo .\n```\n"
        )
        new_text = old_text.replace("Old introduction.", "New introduction.")

        changed = executable_markdown_changed(old_text, new_text)

        self.assertFalse(changed)

    def test_same_section_prose_change_stays_lightweight(self) -> None:
        old_text = (
            "## Run\n\n```bash\nflask run\n```\n\n"
            "Expected output:\n\n```text\nServing Flask app\n```\n\n"
            "This prose explains what to do next.\n"
        )
        new_text = old_text.replace("what to do next", "the next step")

        changed = executable_markdown_changed(old_text, new_text)

        self.assertFalse(changed)

    def test_expected_output_fence_change_selects_full_verification(self) -> None:
        old_text = (
            "## Run\n\n```bash\ncurl --fail http://localhost:3000/health\n```\n\n"
            "Expected output:\n\n```text\nhealthy\n```\n"
        )
        new_text = old_text.replace("healthy", "ok")

        changed = executable_markdown_changed(old_text, new_text)

        self.assertTrue(changed)

    def test_immediately_following_output_fence_selects_full_verification(self) -> None:
        old_text = (
            "## Run\n\n```bash\nflask run\n```\n\n"
            "```text\nServing Flask app\n```\n"
        )
        new_text = old_text.replace("Serving Flask app", "Debug mode: off")

        changed = executable_markdown_changed(old_text, new_text)

        self.assertTrue(changed)

    def test_output_labeled_fence_selects_full_verification(self) -> None:
        old_text = (
            "## Run\n\n```bash\nflask run\n```\n\nDetails.\n\n"
            "Output:\n\n```text\nServing Flask app\n```\n"
        )
        new_text = old_text.replace("Serving Flask app", "Debug mode: off")

        changed = executable_markdown_changed(old_text, new_text)

        self.assertTrue(changed)

    def test_output_under_later_heading_stays_lightweight(self) -> None:
        old_text = (
            "## Run\n\n```bash\nflask run\n```\n\n"
            "## Troubleshooting\n\nOutput:\n\n```text\nNo issues found\n```\n"
        )
        new_text = old_text.replace("No issues found", "No failures found")

        changed = executable_markdown_changed(old_text, new_text)

        self.assertFalse(changed)

    def test_output_after_unrelated_fence_stays_lightweight(self) -> None:
        old_text = (
            "## Run\n\n```bash\nflask run\n```\n\n"
            "```text\nConfiguration note\n```\n\n"
            "Output:\n\n```text\nNo issues found\n```\n"
        )
        new_text = old_text.replace("No issues found", "No failures found")

        changed = executable_markdown_changed(old_text, new_text)

        self.assertFalse(changed)

    def test_annotated_command_fence_selects_full_verification(self) -> None:
        old_text = "## Start\n\n```bash title=\"Start the app\"\ngunicorn app:app\n```\n"
        new_text = old_text.replace("app:app", "src.app:app")

        changed = executable_markdown_changed(old_text, new_text)

        self.assertTrue(changed)

    def test_tilde_command_fence_selects_full_verification(self) -> None:
        old_text = "## Deploy\n\n~~~bash\nkubectl apply --filename app.yaml\n~~~\n"
        new_text = old_text.replace("app.yaml", "deployment.yaml")

        changed = executable_markdown_changed(old_text, new_text)

        self.assertTrue(changed)

    def test_one_language_change_selects_only_its_app_job(self) -> None:
        selected = classify_changes((Change.modified("apps/python-flask/src/app.py"),))

        self.assertEqual(selected, frozenset({Job.PYTHON}))

    def test_node_docker_context_selects_app_and_container_checks(self) -> None:
        selected = classify_changes((Change.modified("apps/nodejs/src/server.js"),))

        self.assertEqual(selected, frozenset({Job.NODEJS, Job.NODEJS_CONTAINER}))

    def test_one_lab_change_selects_shell_and_full_bicep(self) -> None:
        selected = classify_changes((Change.modified("labs/snat-exhaustion/trigger.sh"),))

        self.assertEqual(selected, frozenset({Job.SCRIPTS, Job.BICEP}))

    def test_shared_lab_helper_expands_all_jobs(self) -> None:
        selected = classify_changes(
            (Change.modified("labs/_shared/scripts/deploy-lab.sh"),)
        )

        self.assertEqual(selected, ALL_JOBS)

    def test_shared_validator_expands_all_jobs(self) -> None:
        selected = classify_changes((Change.modified("scripts/scan_lab_pii.py"),))

        self.assertEqual(selected, ALL_JOBS)

    def test_workflow_change_expands_all_jobs(self) -> None:
        selected = classify_changes(
            (Change.modified(".github/workflows/app-infra-ci.yml"),)
        )

        self.assertEqual(selected, ALL_JOBS)

    def test_rename_classifies_both_old_and_new_paths(self) -> None:
        selected = classify_changes(
            (
                Change.renamed(
                    "apps/python-flask/src/old.py", "apps/java-springboot/src/New.java"
                ),
            )
        )

        self.assertEqual(selected, frozenset({Job.PYTHON, Job.JAVA}))

    def test_deletion_classifies_the_removed_path(self) -> None:
        selected = classify_changes(
            (Change.deleted("apps/dotnet-aspnetcore/GuideApi/Program.cs"),)
        )

        self.assertEqual(selected, frozenset({Job.DOTNET}))

    def test_manual_or_scheduled_full_regression_selects_every_job(self) -> None:
        selected = classify_changes((), full_regression=True)

        self.assertEqual(selected, ALL_JOBS)

    def test_name_status_parser_preserves_renames_and_deletions(self) -> None:
        raw = (
            b"R100\0apps/nodejs/old.js\0apps/python-flask/new.py\0"
            b"D\0labs/old/trigger.sh\0"
        )

        changes = parse_name_status_z(raw)

        self.assertEqual(
            changes,
            (
                Change("R100", "apps/nodejs/old.js", "apps/python-flask/new.py"),
                Change.deleted("labs/old/trigger.sh"),
            ),
        )


if __name__ == "__main__":
    _ = unittest.main()
