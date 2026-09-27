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


class EnforcementInvariantTests(unittest.TestCase):
    """A rule AGENTS.md says a validator enforces must actually be invoked.

    This class replaced an earlier pair of tests that pinned the transient
    finding itself: that validate_frontmatter.py was orphaned and therefore
    marked REWRITE. Those tests failed the moment the defect was fixed,
    which is what they were written to do. Pinning the finding is only
    useful until it is resolved; the durable property is that a documented
    enforcement claim is backed by an actual CI invocation.
    """

    def _claimed_enforcers(self):
        """Validators AGENTS.md names as rejecting something."""
        agents = (ROOT / "AGENTS.md").read_text()
        found = set()
        for match in re.finditer(r"`(tools/[\w./-]+\.py|scripts/[\w./-]+\.py)`", agents):
            path = match.group(1)
            window = agents[max(0, match.start() - 220):match.end() + 220].lower()
            if any(w in window for w in ("will fail", "rejects", "fails with", "blocking")):
                found.add(path)
        return found

    def test_agents_md_still_names_the_frontmatter_validator_as_an_enforcer(self):
        self.assertIn("tools/validate_frontmatter.py", self._claimed_enforcers())

    def test_every_validator_agents_md_calls_an_enforcer_is_invoked_by_ci(self):
        for path in sorted(self._claimed_enforcers()):
            if not (ROOT / path).is_file():
                continue
            self.assertTrue(
                invoked_by_ci(pathlib.Path(path).name),
                msg=f"AGENTS.md says {path} rejects something, but no workflow runs it, "
                    "so the rule is documented and unenforced")

    def test_a_ci_wired_validator_is_correctly_detected(self):
        """Guards the detector itself against always returning False."""
        self.assertTrue(invoked_by_ci("validate_pii.py"))

    def test_an_uninvoked_script_is_correctly_detected_as_such(self):
        """Guards the detector against always returning True."""
        self.assertFalse(invoked_by_ci("build_doc_graph.py"))

    def test_audit_decision_matches_the_measured_ci_state(self):
        for row in AUDIT["paths"]:
            if not row["path"].endswith(".py"):
                continue
            if invoked_by_ci(pathlib.Path(row["path"]).name):
                self.assertNotEqual(
                    row["decision"], "REWRITE",
                    msg=f"{row['path']} is invoked by CI, so a REWRITE-for-orphaning "
                        "decision is stale")


if __name__ == "__main__":
    unittest.main(verbosity=1)
