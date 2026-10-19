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


class TutorialValidationContractTests(unittest.TestCase):
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
        self.assertTrue(any("canonical retained package" in p for p in self.problems()))

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
