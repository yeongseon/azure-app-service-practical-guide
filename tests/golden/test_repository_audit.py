"""Repository audit tests (#180).

An audit is only trustworthy if its claims can be checked against the
repository. These tests verify that every audited path exists, that the
CI-orphan finding is still true, and that nothing is marked for deletion
without the separate review the policy requires.
"""

import sys

sys.dont_write_bytecode = True

import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
AUDIT = json.loads((ROOT / "docs/reference/golden-repository-audit.json").read_text())
WORKFLOWS = ROOT / ".github/workflows"

VALID = {"KEEP", "REWRITE", "MOVE", "DELETE", "ARCHIVE"}


def invoked_by_ci(basename):
    """True when a workflow actually RUNS the script.

    Presence in a `paths:` trigger filter is not invocation. A path filter
    makes edits trigger a workflow while nothing in it executes the file,
    which is how an unenforced validator can look covered.
    """
    for workflow in WORKFLOWS.glob("*.yml"):
        for line in workflow.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("- '") or stripped.startswith('- "'):
                continue  # a path filter entry, not a command
            if basename in stripped and re.search(r"python3?\s|bash\s|run:", stripped):
                return True
    return False


class ShapeTests(unittest.TestCase):
    def test_every_decision_uses_the_declared_vocabulary(self):
        for row in AUDIT["paths"]:
            self.assertIn(row["decision"], VALID, msg=row["path"])

    def test_every_path_carries_a_substantive_reason(self):
        for row in AUDIT["paths"]:
            self.assertGreater(
                len(row["reason"].strip()), 40,
                msg=f"{row['path']} needs a reason that states why, not a label")

    def test_paths_are_unique(self):
        paths = [row["path"] for row in AUDIT["paths"]]
        self.assertEqual(len(paths), len(set(paths)))


class ExistenceTests(unittest.TestCase):
    def test_every_audited_path_exists(self):
        for row in AUDIT["paths"]:
            self.assertTrue(
                (ROOT / row["path"]).exists(),
                msg=f"audit decides on {row['path']}, which is not in the repository")


class DeletionPolicyTests(unittest.TestCase):
    def test_nothing_is_marked_delete_without_separate_review(self):
        deletions = [r["path"] for r in AUDIT["paths"] if r["decision"] == "DELETE"]
        self.assertEqual(
            deletions, [],
            msg="DELETE requires a separate review; this audit may not authorise it")

    def test_no_evidence_path_is_archived_or_deleted(self):
        for row in AUDIT["paths"]:
            if row["path"].startswith("evidence/") or "artifacts-sanitized" in row["path"]:
                self.assertEqual(row["decision"], "KEEP", msg=row["path"])


class RewriteFindingTests(unittest.TestCase):
    """The REWRITE finding must still be true, or the audit is stale."""

    def test_validate_frontmatter_is_marked_rewrite(self):
        row = [r for r in AUDIT["paths"] if r["path"] == "tools/validate_frontmatter.py"][0]
        self.assertEqual(row["decision"], "REWRITE")

    def test_validate_frontmatter_is_genuinely_not_invoked_by_ci(self):
        self.assertFalse(
            invoked_by_ci("validate_frontmatter.py"),
            msg="the audit claims this validator is never invoked; if CI now runs it, "
                "the REWRITE finding is stale and must be re-decided")

    def test_a_ci_wired_validator_is_correctly_detected(self):
        """Guards the detector itself against always returning False."""
        self.assertTrue(invoked_by_ci("validate_pii.py"))

    def test_every_rewrite_reason_names_the_defect(self):
        for row in AUDIT["paths"]:
            if row["decision"] == "REWRITE":
                self.assertIn("invoke", row["reason"].lower(), msg=row["path"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
