#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.impact_classifier import Change, Job, classify_changes, parse_name_status_z


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

    def test_expected_output_change_near_command_selects_full_verification(self) -> None:
        old_text = "# Recipe\n\n```bash\naz webapp list\n```\n\nExpected: old\n"
        new_text = "# Recipe\n\n```bash\naz webapp list\n```\n\nExpected: new\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            _ = (root / "docs/recipe.md").write_text(new_text)

            selected = classify_changes(
                (Change.modified("docs/recipe.md"),),
                root=root,
                base_reader=lambda _: old_text,
            )

        self.assertEqual(selected, ALL_JOBS)

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
