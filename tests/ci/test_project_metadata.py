"""Offline tests for the read-only PR metadata contract."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("metadata", ROOT / "scripts/ci/check_project_metadata.py")
metadata = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metadata)


def pr(**changes):
    body = "\n\n".join("## " + heading + "\n\n" + ("Refs #217 — partial implementation." if heading == "Related Issues" else "Recorded details.") for heading in metadata.SECTIONS)
    result = {"title": "ci(verification): add read-only checks", "body": body, "labels": [{"name": "priority:high"}]}
    result.update(changes)
    return result


class MetadataTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(metadata.validate(pr()), [])

    def test_missing_priority(self):
        self.assertTrue(metadata.validate(pr(labels=[])))

    def test_multiple_priorities(self):
        self.assertTrue(metadata.validate(pr(labels=["priority:high", "priority:low"])))

    def test_unknown_priority(self):
        self.assertTrue(metadata.validate(pr(labels=["priority:urgent"])))

    def test_unrelated_label_preserved(self):
        self.assertEqual(metadata.validate(pr(labels=["documentation", "priority:medium"])), [])

    def test_title_prefix(self):
        self.assertTrue(metadata.validate(pr(title="Add some tests")))

    def test_allowed_title_forms(self):
        valid_titles = (
            "feat: add a capability",
            "fix: repair a defect",
            "docs: explain a workflow",
            "test: cover an edge case",
            "perf: reduce query latency",
            "refactor: simplify validation",
            "ci: add a workflow",
            "build: update a package",
            "chore: remove stale output",
            "style: normalize indentation",
            "revert: restore prior behavior",
            "feat(api)!: change a contract",
        )
        for title in valid_titles:
            with self.subTest(title=title):
                self.assertEqual(metadata.validate(pr(title=title)), [])

    def test_invalid_title_forms(self):
        invalid_titles = (
            "Feat: uppercase type",
            "feature: unknown type",
            "fix: trailing period.",
            "fix: trailing space ",
            "fix(scope):",
            "fix(API): uppercase scope",
        )
        for title in invalid_titles:
            with self.subTest(title=title):
                self.assertTrue(metadata.validate(pr(title=title)))

    def test_untrusted_title_text_is_only_validated(self):
        self.assertEqual(metadata.validate(pr(title="fix: shell $(touch /tmp/untrusted)")), [])

    def test_trailing_reference(self):
        self.assertTrue(metadata.validate(pr(title="ci: add checks (#217)")))

    def test_trailing_period(self):
        self.assertTrue(metadata.validate(pr(title="ci: add checks.")))

    def test_breaking_title(self):
        self.assertEqual(metadata.validate(pr(title="feat(api)!: change the contract")), [])

    def test_wrong_section_order(self):
        self.assertTrue(metadata.validate(pr(body="## Changes\n\n## Summary")))

    def test_fenced_heading(self):
        self.assertEqual(metadata.headings("```markdown\n## Fake\n```\n## Real"), ["Real"])

    def test_archived_heading(self):
        self.assertEqual(metadata.headings("<details>\n## Old\n</details>\n## Current"), ["Current"])

    def test_foreign_reference(self):
        value = pr()
        value["body"] = value["body"].replace("Refs #217", "Refs other/repo#217")
        self.assertTrue(metadata.validate(value))

    def test_zero_reference(self):
        value = pr()
        value["body"] = value["body"].replace("Refs #217", "Refs #0")
        self.assertTrue(metadata.validate(value))


if __name__ == "__main__":
    unittest.main()
