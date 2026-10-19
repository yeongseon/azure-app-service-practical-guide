from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tutorial_validation", ROOT / "scripts/golden/validate_tutorial_validation.py"
)
assert SPEC is not None and SPEC.loader is not None
tutorial_validation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tutorial_validation
SPEC.loader.exec_module(tutorial_validation)


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


class TutorialValidationReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        run_git(self.root, "init")
        run_git(self.root, "config", "user.email", "test@example.com")
        run_git(self.root, "config", "user.name", "Validation Test")
        self.tutorial = (
            self.root / "docs/language-guides/python/tutorial/01-test.md"
        )
        self.tutorial.parent.mkdir(parents=True)
        (self.root / "README.md").write_text("base\n", encoding="utf-8")
        self.base = self.commit_base()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_validation(self, yaml_text: str) -> None:
        self.tutorial.write_text(
            f"---\nvalidation:\n{yaml_text}---\n# Test\n", encoding="utf-8"
        )

    def commit_base(self) -> str:
        run_git(self.root, "add", ".")
        run_git(self.root, "commit", "-m", "base")
        return run_git(self.root, "rev-parse", "HEAD")

    def problems(self, base_ref: str | None = None) -> list[str]:
        return tutorial_validation.validate(
            self.root, base_ref=base_ref or self.base, today=date(2026, 10, 19)
        )

    def test_validation_sequence_is_rejected(self) -> None:
        self.write_validation("  []\n")
        self.assertTrue(any("validation must be a mapping" in p for p in self.problems()))

    def test_malformed_validation_yaml_is_rejected(self) -> None:
        self.write_validation("  az_cli: [\n")
        self.assertTrue(any("malformed YAML frontmatter" in p for p in self.problems()))

    def test_unknown_azure_cli_key_is_rejected(self) -> None:
        self.write_validation("  azure_cli:\n    result: not_tested\n    last_tested: null\n")
        self.assertTrue(any("unknown validation method" in p for p in self.problems()))

    def test_unknown_hyphenated_az_cli_key_is_rejected(self) -> None:
        self.write_validation("  az-cli:\n    result: not_tested\n    last_tested: null\n")
        self.assertTrue(any("unknown validation method" in p for p in self.problems()))

    def test_non_mapping_method_is_rejected(self) -> None:
        self.write_validation("  az_cli: pass\n")
        self.assertTrue(any("az_cli must be a mapping" in p for p in self.problems()))

    def test_unknown_result_is_rejected(self) -> None:
        self.write_validation("  az_cli:\n    result: inconclusive\n    last_tested: null\n")
        self.assertTrue(any("invalid result" in p for p in self.problems()))

    def test_malformed_date_is_rejected(self) -> None:
        self.write_validation("  az_cli:\n    result: fail\n    last_tested: yesterday\n")
        self.assertTrue(any("invalid last_tested" in p for p in self.problems()))

    def test_future_date_is_rejected(self) -> None:
        self.write_validation("  az_cli:\n    result: fail\n    last_tested: 2026-10-20\n")
        self.assertTrue(any("future last_tested" in p for p in self.problems()))

    def test_not_tested_requires_null_date_and_no_reference(self) -> None:
        self.write_validation(
            "  az_cli:\n    result: not_tested\n    last_tested: 2026-10-18\n"
            "    run_id: run-1\n    evidence: evidence/runs/run-1\n"
        )
        problems = self.problems()
        self.assertTrue(any("not_tested requires last_tested: null" in p for p in problems))
        self.assertTrue(any("not_tested cannot reference" in p for p in problems))

    def test_reference_requires_existing_canonical_package_directory(self) -> None:
        self.write_validation(
            "  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
            "    run_id: run-1\n    evidence: evidence/runs/../runs/run-1\n"
        )
        problems = self.problems()
        self.assertTrue(any("evidence field must equal" in p for p in problems))

    def test_directory_traversal_attack_via_parent_directory(self) -> None:
        """Attack: run_id="../runs/run-1" with traversal in evidence field."""
        self.write_validation(
            "  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
            "    run_id: ../runs/run-1\n    evidence: evidence/runs/../runs/run-1\n"
        )
        problems = self.problems()
        self.assertTrue(any("single path component" in p for p in problems))

    def test_directory_traversal_with_parent_in_run_id_is_rejected(self) -> None:
        """Attack: run_id="." or ".." escapes the runs directory."""
        for bad_id in [".", ".."]:
            with self.subTest(run_id=bad_id):
                self.write_validation(
                    f"  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
                    f"    run_id: {bad_id}\n    evidence: evidence/runs/{bad_id}\n"
                )
                problems = self.problems()
                self.assertTrue(
                    any(f"cannot be {bad_id}" in p for p in problems),
                    f"Expected rejection of run_id={bad_id}, got: {problems}"
                )

    def test_symlink_in_package_path_is_rejected(self) -> None:
        """Attack: evidence/runs/run-link symlink -> /var/lib/sensitive escapes via resolved path."""
        (self.root / "evidence" / "runs").mkdir(parents=True)
        target = self.root / "target"
        target.mkdir()
        (self.root / "evidence" / "runs" / "run-link").symlink_to(target)
        
        self.write_validation(
            "  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
            "    run_id: run-link\n    evidence: evidence/runs/run-link\n"
        )
        problems = self.problems()
        self.assertTrue(any("symlink not allowed in package directory" in p for p in problems))

    def test_in_tree_symlink_package_is_rejected_as_symlink(self) -> None:
        runs = self.root / "evidence" / "runs"
        (runs / "actual").mkdir(parents=True)
        (runs / "link").symlink_to(runs / "actual")
        self.write_validation(
            "  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
            "    run_id: link\n    evidence: evidence/runs/link\n"
        )

        problems = self.problems()

        self.assertTrue(any("symlink not allowed in package directory" in p for p in problems))

    def test_symlinked_runs_directory_is_rejected_as_symlink(self) -> None:
        external_runs = self.root / "external-runs"
        (external_runs / "run-1").mkdir(parents=True)
        (self.root / "evidence").mkdir()
        (self.root / "evidence" / "runs").symlink_to(external_runs)
        self.write_validation(
            "  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
            "    run_id: run-1\n    evidence: evidence/runs/run-1\n"
        )

        problems = self.problems()

        self.assertTrue(any("symlink not allowed in path to runs directory" in p for p in problems))

    def test_empty_run_id_is_rejected(self) -> None:
        """Attack: empty run_id bypasses validation."""
        self.write_validation(
            "  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
            '    run_id: ""\n    evidence: evidence/runs/\n'
        )
        problems = self.problems()
        self.assertTrue(any("must be non-empty" in p for p in problems))

    def test_run_id_with_slashes_is_rejected(self) -> None:
        """Attack: run_id with / or \\ allows directory traversal."""
        for sep in ["/", "\\\\"]:
            with self.subTest(separator=sep):
                escaped_sep = sep.replace("\\", "\\\\")
                self.write_validation(
                    f"  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
                    f'    run_id: run-1{escaped_sep}..{escaped_sep}runs{escaped_sep}run-2\n'
                    f'    evidence: evidence/runs/run-1{escaped_sep}..{escaped_sep}runs{escaped_sep}run-2\n'
                )
                problems = self.problems()
                self.assertTrue(any("single path component" in p for p in problems))

    def test_absolute_path_in_run_id_is_rejected(self) -> None:
        """Attack: absolute path in run_id bypasses relative path validation."""
        self.write_validation(
            f"  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
            f'    run_id: /tmp/run-1\n'
            f'    evidence: evidence/runs//tmp/run-1\n'
        )
        problems = self.problems()
        self.assertTrue(any("single path component" in p for p in problems))

    def test_evidence_field_must_match_canonical_format(self) -> None:
        """Attack: evidence field doesn't match evidence/runs/<run_id> format."""
        (self.root / "evidence" / "runs" / "run-1").mkdir(parents=True)
        
        self.write_validation(
            "  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
            "    run_id: run-1\n    evidence: evidence/runs/run-2\n"
        )
        problems = self.problems()
        self.assertTrue(any("evidence field must equal" in p for p in problems))

    def test_invalid_run_id_characters_are_rejected(self) -> None:
        """Attack: run_id with special characters bypasses allowlist."""
        (self.root / "evidence" / "runs").mkdir(parents=True)
        
        for bad_id in ["run@1", "run&2", "run#3", "run!4"]:
            with self.subTest(run_id=bad_id):
                self.write_validation(
                    f"  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n"
                    f"    run_id: {bad_id}\n    evidence: evidence/runs/{bad_id}\n"
                )
                problems = self.problems()
                self.assertTrue(
                    any("invalid characters" in p for p in problems),
                    f"Expected rejection of run_id={bad_id}, got: {problems}"
                )

    def test_new_pass_without_run_reference_is_rejected(self) -> None:
        self.write_validation("  az_cli:\n    result: pass\n    last_tested: 2026-10-18\n")
        self.assertTrue(any("new or changed pass" in p for p in self.problems()))

    def test_changed_legacy_pass_date_without_run_reference_is_rejected(self) -> None:
        self.write_validation("  az_cli:\n    result: pass\n    last_tested: 2026-10-17\n")
        base = self.commit_base()
        self.write_validation("  az_cli:\n    result: pass\n    last_tested: 2026-10-18\n")
        self.assertTrue(any("new or changed pass" in p for p in self.problems(base)))

    def test_unchanged_legacy_pass_without_reference_is_accepted(self) -> None:
        self.write_validation("  az_cli:\n    result: pass\n    last_tested: 2026-10-17\n")
        base = self.commit_base()
        self.assertEqual(self.problems(base), [])

    def test_file_absent_in_valid_base_is_not_base_unavailable(self) -> None:
        self.write_validation("  az_cli:\n    result: pass\n    last_tested: 2026-10-18\n")
        problems = self.problems()
        self.assertTrue(any("new or changed pass" in p for p in problems))
        self.assertFalse(any("base commit is unavailable" in p for p in problems))

    def test_unavailable_base_fails_closed(self) -> None:
        self.write_validation("  az_cli:\n    result: not_tested\n    last_tested: null\n")
        self.assertTrue(
            any("base commit is unavailable" in p for p in self.problems("f" * 40))
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
