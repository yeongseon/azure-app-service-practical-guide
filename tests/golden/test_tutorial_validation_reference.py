from __future__ import annotations

from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import unittest
from unittest.mock import patch


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


# One gate's adversarial fixtures stay in its existing registered suite.
class TutorialValidationReferenceTests(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.tutorial = self.root / "docs/language-guides/python/tutorial/01-test.md"
        self.base = ""

    def setUp(self) -> None:
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

    def method_key(self, method: str) -> str:
        return f"{self.tutorial.relative_to(self.root).as_posix()}#{method}"

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

    def test_new_null_method_is_rejected(self) -> None:
        self.write_validation("  az_cli:\n")

        problems = self.problems()

        self.assertEqual(problems, [f"{self.method_key('az_cli')} must be a mapping"])

    def test_new_null_method_beside_a_base_method_is_rejected(self) -> None:
        self.write_validation("  az_cli:\n    result: not_tested\n    last_tested: null\n")
        base = self.commit_base()
        self.write_validation(
            "  az_cli:\n    result: not_tested\n    last_tested: null\n  bicep:\n"
        )

        problems = self.problems(base)

        self.assertEqual(problems, [f"{self.method_key('bicep')} must be a mapping"])

    def test_unchanged_legacy_null_method_is_accepted(self) -> None:
        self.write_validation("  az_cli:\n")
        base = self.commit_base()

        problems = self.problems(base)

        self.assertEqual(problems, [])

    def base_with(self, yaml_text: str) -> str:
        self.write_validation(yaml_text)
        run_git(self.root, "add", ".")
        run_git(self.root, "commit", "--allow-empty", "-m", "base")
        return run_git(self.root, "rev-parse", "HEAD")

    def legacy_method(self, cli_version: str, result: str = "pass") -> str:
        return (
            f"  az_cli:\n    result: {result}\n    last_tested: 2026-10-18\n"
            f"    cli_version: {cli_version}\n"
        )

    def test_changed_scalar_type_cannot_inherit_the_legacy_exemption(self) -> None:
        for result in ("pass", "fail"):
            for old, new in (("1", "true"), ("0", "false"), ("1", "1.0"), ("1.0", "true")):
                with self.subTest(result=result, old=old, new=new):
                    base = self.base_with(self.legacy_method(old, result))
                    self.write_validation(self.legacy_method(new, result))

                    problems = self.problems(base)

                    self.assertIn(
                        f"{self.method_key('az_cli')}: new or changed {result} requires run_id and evidence",
                        problems,
                    )

    def test_changed_nested_key_and_set_types_cannot_inherit_the_legacy_exemption(self) -> None:
        for label, old, new in (
            ("list element", "[1]", "[true]"),
            ("mapping value", "{a: 1}", "{a: true}"),
            ("mapping key", "{1: a}", "{true: a}"),
            ("set member", "!!set {1}", "!!set {true}"),
            ("ordered pairs", "!!omap [a: 1]", "!!omap [a: true]"),
        ):
            with self.subTest(label=label):
                base = self.base_with(self.legacy_method(old))
                self.write_validation(self.legacy_method(new))

                problems = self.problems(base)

                self.assertIn(
                    f"{self.method_key('az_cli')}: new or changed pass requires run_id and evidence",
                    problems,
                )

    def test_unchanged_typed_legacy_values_stay_accepted(self) -> None:
        for value in ("1", "1.0", "true", "[1]", "{a: 1}", "{1: a}", "!!set {1}", "!!omap [a: 1]"):
            with self.subTest(value=value):
                base = self.base_with(self.legacy_method(value))
                self.write_validation(self.legacy_method(value))

                problems = self.problems(base)

                self.assertEqual(problems, [])

    def test_recursive_alias_is_compared_without_a_traceback(self) -> None:
        recursive = (
            "  az_cli: &method\n    result: pass\n    last_tested: 2026-10-18\n    again: *method\n"
        )
        base = self.base_with(recursive)
        self.write_validation(recursive)

        unchanged = self.problems(base)
        self.write_validation(recursive.replace("2026-10-18", "2026-10-17"))
        changed = self.problems(base)

        self.assertEqual(unchanged, [])
        self.assertIn(
            f"{self.method_key('az_cli')}: new or changed pass requires run_id and evidence", changed
        )

    def test_a_value_too_deep_to_compare_is_treated_as_changed(self) -> None:
        legacy = "  az_cli:\n    result: pass\n    last_tested: 2026-10-18\n"
        base = self.base_with(legacy)
        self.write_validation(legacy)

        with patch.object(tutorial_validation, "_same_yaml_value", side_effect=RecursionError):
            problems = self.problems(base)

        self.assertEqual(
            problems, [f"{self.method_key('az_cli')}: new or changed pass requires run_id and evidence"]
        )

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

    def execution_fixture(self, result: str = "pass", method: str = "az_cli") -> dict[str, Any]:
        self.write_validation(
            f"  {method}:\n    result: {result}\n    last_tested: 2026-10-18\n"
            "    cli_version: '2.83.0'\n    run_id: run-1\n"
            "    evidence: evidence/runs/run-1\n"
        )
        package = self.root / "evidence/runs/run-1"
        package.mkdir(parents=True, exist_ok=True)
        (package / "raw.txt").write_bytes(b"synthetic fixture only\n")
        return {
            "schema_version": 1,
            "run_id": "run-1",
            "tutorial": self.tutorial.relative_to(self.root).as_posix(),
            "method": method,
            "execution_status": "COMPLETE",
            "tutorial_result": result,
            "phases": [{"name": "verify", "completed_at": "2026-10-18T12:00:00Z", "outcome": result}],
            "final_required_phase": "verify",
            "final_required_phase_completed_at": "2026-10-18T12:00:00Z",
            "cli_version": "2.83.0",
            "source_commit": self.base,
            "environment": {"region": "test-region", "sku": "B1", "runtime": "Python 3.11", "hosting_model": "Linux"},
            "raw_evidence": {"raw.txt": hashlib.sha256(b"synthetic fixture only\n").hexdigest()},
        }

    def save_record(self, record: dict[str, Any]) -> Path:
        path = self.root / "evidence/runs/run-1/tutorial-execution.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return path

    def assert_record_rejected(self, record: dict[str, Any], message: str) -> None:
        self.save_record(record)

        problems = self.problems()

        self.assertTrue(any(message in problem for problem in problems), problems)

    def test_valid_pass_record_is_accepted(self) -> None:
        self.save_record(self.execution_fixture())

        problems = self.problems()

        self.assertEqual(problems, [])

    def quoted_date_frontmatter(self, text: str) -> str:
        return (
            f"  az_cli:\n    result: pass\n    last_tested: '{text}'\n"
            "    cli_version: '2.83.0'\n    run_id: run-1\n"
            "    evidence: evidence/runs/run-1\n"
        )

    def test_non_canonical_date_text_is_rejected_even_with_an_agreeing_record(self) -> None:
        self.save_record(self.execution_fixture())
        for text in ("20261018", "2026-W42-7", "2026W427"):
            with self.subTest(last_tested=text):
                self.write_validation(self.quoted_date_frontmatter(text))

                problems = self.problems()

                self.assertTrue(any("invalid last_tested date" in p for p in problems), problems)

    def test_canonical_quoted_date_text_is_accepted_with_an_agreeing_record(self) -> None:
        self.save_record(self.execution_fixture())
        self.write_validation(self.quoted_date_frontmatter("2026-10-18"))

        problems = self.problems()

        self.assertEqual(problems, [])

    def test_valid_fail_record_is_accepted(self) -> None:
        for status in ("COMPLETE", "FAILED"):
            with self.subTest(status=status):
                record = self.execution_fixture(result="fail")
                record["execution_status"] = status
                self.save_record(record)

                problems = self.problems()

                self.assertEqual(problems, [])

    def test_valid_bicep_without_cli_version_is_accepted(self) -> None:
        record = self.execution_fixture(method="bicep")
        self.write_validation(
            "  bicep:\n    result: pass\n    last_tested: '2026-10-18'\n"
            "    run_id: run-1\n    evidence: evidence/runs/run-1\n"
        )
        del record["cli_version"]
        self.save_record(record)

        problems = self.problems()

        self.assertEqual(problems, [])

    def test_empty_package_is_rejected(self) -> None:
        self.execution_fixture()
        (self.root / "evidence/runs/run-1/raw.txt").unlink()

        problems = self.problems()

        self.assertTrue(any("tutorial-execution.json" in p for p in problems), problems)

    def test_missing_record_is_rejected(self) -> None:
        self.execution_fixture()

        problems = self.problems()

        self.assertTrue(any("tutorial-execution.json" in p for p in problems), problems)

    def test_malformed_json_is_rejected(self) -> None:
        self.execution_fixture()
        path = self.root / "evidence/runs/run-1/tutorial-execution.json"
        for content in (b"{", b"\xff", b'{"x": NaN}', b'{"x": 1, "x": 2}', b"[" * 2000):
            with self.subTest(content=content[:20]):
                path.write_bytes(content)

                problems = self.problems()

                self.assertTrue(any("invalid tutorial-execution.json" in p for p in problems), problems)

    def test_unknown_record_field_is_rejected(self) -> None:
        record = self.execution_fixture()
        record["unexpected"] = True

        self.assert_record_rejected(record, "schema")

    def test_wrong_record_run_id_is_rejected(self) -> None:
        record = self.execution_fixture()
        record["run_id"] = "other"

        self.assert_record_rejected(record, "record run_id")

    def test_other_tutorial_record_is_rejected(self) -> None:
        record = self.execution_fixture()
        record["tutorial"] = "docs/language-guides/java/tutorial/01-test.md"

        self.assert_record_rejected(record, "record tutorial must equal")

    def test_wrong_method_record_is_rejected(self) -> None:
        record = self.execution_fixture()
        record["method"] = "bicep"

        self.assert_record_rejected(record, "record method must equal")

    def test_result_mismatch_is_rejected(self) -> None:
        record = self.execution_fixture()
        record["tutorial_result"] = "fail"
        record["phases"][0]["outcome"] = "fail"

        self.assert_record_rejected(record, "record tutorial_result must equal")

    def test_final_phase_date_mismatch_is_rejected(self) -> None:
        record = self.execution_fixture()
        record["final_required_phase_completed_at"] = "2026-10-17T12:00:00Z"
        record["phases"][0]["completed_at"] = "2026-10-17T12:00:00Z"

        self.assert_record_rejected(record, "last_tested must equal the UTC date")

    def test_offset_local_date_cannot_replace_utc_date(self) -> None:
        record = self.execution_fixture()
        record["final_required_phase_completed_at"] = "2026-10-18T00:30:00+02:00"
        record["phases"][0]["completed_at"] = "2026-10-18T00:30:00+02:00"

        self.assert_record_rejected(record, "last_tested must equal the UTC date")

    def test_offset_utc_date_is_accepted(self) -> None:
        record = self.execution_fixture()
        record["final_required_phase_completed_at"] = "2026-10-19T00:30:00+02:00"
        record["phases"][0]["completed_at"] = "2026-10-18T22:30:00Z"
        self.save_record(record)

        problems = self.problems()

        self.assertEqual(problems, [])

    def test_pass_requires_complete_execution(self) -> None:
        for status in ("NOT_RUN", "BLOCKED", "PARTIAL", "FAILED"):
            with self.subTest(status=status):
                record = self.execution_fixture()
                record["execution_status"] = status

                self.assert_record_rejected(record, "incompatible execution_status")

    def test_fail_cannot_claim_unexecuted_status(self) -> None:
        for status in ("NOT_RUN", "BLOCKED", "PARTIAL"):
            with self.subTest(status=status):
                record = self.execution_fixture(result="fail")
                record["execution_status"] = status

                self.assert_record_rejected(record, "incompatible execution_status")

    def test_future_phase_time_is_rejected(self) -> None:
        record = self.execution_fixture()
        record["phases"].append({"name": "future", "completed_at": "2026-10-20T00:00:00Z", "outcome": "pass"})

        self.assert_record_rejected(record, "cannot be in the future")

    def test_final_required_phase_must_exist(self) -> None:
        record = self.execution_fixture()
        record["final_required_phase"] = "absent"

        self.assert_record_rejected(record, "must name a phase")

    def test_final_phase_time_must_agree(self) -> None:
        record = self.execution_fixture()
        record["phases"][0]["completed_at"] = "2026-10-18T11:00:00Z"

        self.assert_record_rejected(record, "completion time must agree")

    def test_phase_cannot_complete_after_final(self) -> None:
        record = self.execution_fixture()
        record["phases"].append({"name": "late", "completed_at": "2026-10-18T13:00:00Z", "outcome": "pass"})

        self.assert_record_rejected(record, "phase cannot complete after")

    def test_duplicate_phase_names_are_rejected(self) -> None:
        record = self.execution_fixture()
        record["phases"].append(record["phases"][0].copy())

        self.assert_record_rejected(record, "phase names must be unique")

    def test_final_phase_outcome_must_agree(self) -> None:
        record = self.execution_fixture()
        record["phases"][0]["outcome"] = "fail"

        self.assert_record_rejected(record, "outcome must agree")

    def test_cli_version_mismatch_is_rejected(self) -> None:
        record = self.execution_fixture()
        record["cli_version"] = "2.82.0"

        self.assert_record_rejected(record, "cli_version must equal")

    def test_symlinked_record_is_rejected(self) -> None:
        record = self.execution_fixture()
        outside = self.root / "outside.json"
        outside.write_text(json.dumps(record), encoding="utf-8")
        (self.root / "evidence/runs/run-1/tutorial-execution.json").symlink_to(outside)

        problems = self.problems()

        self.assertTrue(any("symlink not allowed" in p for p in problems), problems)

    def test_outside_record_is_not_used(self) -> None:
        record = self.execution_fixture()
        (self.root / "evidence/runs/tutorial-execution.json").write_text(json.dumps(record))

        problems = self.problems()

        self.assertTrue(any("invalid tutorial-execution.json" in p for p in problems), problems)

    def test_record_directory_is_rejected(self) -> None:
        self.execution_fixture()
        (self.root / "evidence/runs/run-1/tutorial-execution.json").mkdir()

        problems = self.problems()

        self.assertTrue(any("regular files" in p for p in problems), problems)

    def test_new_fail_without_reference_is_rejected(self) -> None:
        self.write_validation("  az_cli:\n    result: fail\n    last_tested: 2026-10-18\n")

        problems = self.problems()

        self.assertTrue(any("new or changed fail requires" in p for p in problems), problems)

    def test_unchanged_legacy_malformed_method_is_accepted(self) -> None:
        self.write_validation("  az_cli:\n    result: old-value\n    last_tested: old-date\n    old: true\n")
        base = self.commit_base()

        problems = self.problems(base)

        self.assertEqual(problems, [])

    def test_not_tested_unchanged_is_accepted(self) -> None:
        self.write_validation("  az_cli:\n    result: not_tested\n    last_tested: null\n")
        base = self.commit_base()

        problems = self.problems(base)

        self.assertEqual(problems, [])

    def test_missing_required_record_fields_are_rejected(self) -> None:
        for field in self.execution_fixture():
            with self.subTest(field=field):
                record = self.execution_fixture()
                del record[field]

                self.assert_record_rejected(record, "schema")

    def test_malformed_record_shapes_are_rejected(self) -> None:
        for field, value in (
            ("schema_version", True), ("schema_version", 1.0), ("schema_version", 2),
            ("run_id", []), ("method", {}), ("tutorial_result", []),
            ("phases", []), ("phases", [None]), ("phases", [{"name": "verify"}]),
            ("execution_status", "FINISHED"), ("cli_version", " "),
            ("source_commit", "HEAD"), ("environment", {}),
            ("environment", {"region": None}), ("raw_evidence", {}),
            ("raw_evidence", {"raw.txt": "a" * 63}),
        ):
            with self.subTest(field=field, value=value):
                record = self.execution_fixture()
                record[field] = value

                self.assert_record_rejected(record, "schema")

    def test_non_object_record_is_rejected(self) -> None:
        self.execution_fixture()
        path = self.root / "evidence/runs/run-1/tutorial-execution.json"
        for value in (None, [], "pass", True, 1):
            with self.subTest(value=value):
                path.write_text(json.dumps(value))

                problems = self.problems()

                self.assertTrue(any("schema" in p for p in problems), problems)

    def test_nested_unknown_fields_are_rejected(self) -> None:
        for field in ("environment", "phases"):
            with self.subTest(field=field):
                record = self.execution_fixture()
                target = record[field][0] if field == "phases" else record[field]
                target["extra"] = True

                self.assert_record_rejected(record, "schema")

    def test_malformed_completion_times_are_rejected(self) -> None:
        for value in ("2026-10-18", "2026-10-18T12:00:00", "2026-02-30T00:00:00Z",
                      "2026-10-18T12:00:00+25:00", "0001-01-01T00:00:00+01:00"):
            with self.subTest(value=value):
                record = self.execution_fixture()
                record["final_required_phase_completed_at"] = value

                self.save_record(record)
                self.assertTrue(self.problems())

    def test_raw_digest_mismatch_is_rejected(self) -> None:
        record = self.execution_fixture()
        record["raw_evidence"]["raw.txt"] = "a" * 64

        self.assert_record_rejected(record, "SHA-256 mismatch")

    def test_raw_paths_must_stay_inside_package(self) -> None:
        for relative in ("../raw.txt", "/raw.txt", "./raw.txt", "dir/../raw.txt", "a//b", "a\\b", "a\0b"):
            with self.subTest(relative=relative):
                record = self.execution_fixture()
                record["raw_evidence"] = {relative: "a" * 64}

                self.assert_record_rejected(record, "canonical and inside")

    def test_raw_file_must_exist(self) -> None:
        record = self.execution_fixture()
        (self.root / "evidence/runs/run-1/raw.txt").unlink()

        self.assert_record_rejected(record, "invalid raw_evidence path")

    def test_raw_symlink_is_rejected(self) -> None:
        record = self.execution_fixture()
        raw = self.root / "evidence/runs/run-1/raw.txt"
        target = self.root / "outside.txt"
        raw.rename(target)
        raw.symlink_to(target)

        self.assert_record_rejected(record, "symlink not allowed")

    def test_unhashable_frontmatter_values_return_problems(self) -> None:
        for fragment in ("result: []", "result: {}", "? [a, b]\n    : pass"):
            with self.subTest(fragment=fragment):
                self.write_validation(f"  az_cli:\n    {fragment}\n    last_tested: null\n")

                problems = self.problems()

                self.assertTrue(problems)

    def test_mixed_frontmatter_keys_return_problems(self) -> None:
        self.write_validation("  1: {}\n  false: {}\n  az_cli:\n    result: not_tested\n    1: true\n")

        problems = self.problems()

        self.assertTrue(problems)

    def test_yaml_invalid_calendar_date_returns_problems(self) -> None:
        self.write_validation("  az_cli:\n    result: pass\n    last_tested: 2026-02-30\n")

        problems = self.problems()

        self.assertTrue(problems)

    def test_duplicate_frontmatter_keys_are_rejected(self) -> None:
        self.write_validation("  az_cli:\n    result: pass\n    result: not_tested\n    last_tested: null\n")

        problems = self.problems()

        self.assertTrue(any("duplicate YAML key" in p for p in problems), problems)

    def test_not_tested_requires_explicit_null_and_absent_reference(self) -> None:
        for fields in ("", "    last_tested: null\n    run_id: null\n", "    last_tested: null\n    evidence: null\n"):
            with self.subTest(fields=fields):
                self.write_validation("  az_cli:\n    result: not_tested\n" + fields)

                problems = self.problems()

                self.assertTrue(problems)

    def test_schema_discovery_includes_tutorial_record(self) -> None:
        spec = importlib.util.spec_from_file_location("lane176_schemas", ROOT / "scripts/golden/validate_schemas.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        path = self.save_record(self.execution_fixture())

        with patch.object(module, "ROOT", self.root):
            documents = module.documents()

        self.assertIn((path, "tutorial-execution.schema.json"), documents)

    def test_new_tutorial_package_obeys_existing_retention_gate(self) -> None:
        spec = importlib.util.spec_from_file_location("lane176_retained", ROOT / "scripts/golden/check_retained_packages.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.save_record(self.execution_fixture())
        package = self.root / "evidence/runs/run-1"
        files = {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in package.iterdir()}
        registry = {"packages": {"run-1": {"files": files}}}
        (self.root / "evidence/retained-digests.json").write_text(json.dumps(registry))
        self.commit_base()

        problems = module.violations(self.root, self.base)

        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
