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
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
AUDIT = json.loads((ROOT / "docs/reference/golden-repository-audit.json").read_text())
WORKFLOWS = ROOT / ".github/workflows"

VALID = {"KEEP", "REWRITE", "MOVE", "DELETE", "ARCHIVE"}
REQUIRED_PAIRED_RUNBOOKS = {
    "deployment-succeeded-startup-failed",
    "windows-java-httpplatformhandler-timeout",
}
REQUIRED_COMPARISONS = {"entrypoint", "package", "build", "prerequisite", "cleanup"}
ALLOWED_LINK_VALIDATORS = {"scripts/validate_documented_paths.py"}
SEMANTIC_REVIEW_METHOD = "static-review"


def invoked_by_ci(basename):
    """True when a workflow runs the script on a pull request.

    Presence in a `paths:` trigger filter is not invocation: a path filter
    makes edits trigger a workflow while nothing in it executes the file.

    Job gating is not invocation either. Review found this function
    reporting a validator as CI-enforced while it sat in a job gated on
    `push` to `main`, so it never ran on a pull request -- enforced
    everywhere except where a change is actually reviewed. A job whose
    condition restricts it to pushes or to a branch ref does not count.
    """
    gate = re.compile(r"github\.event_name\s*==\s*'push'|github\.ref\s*==")
    for workflow in WORKFLOWS.glob("*.yml"):
        current_gated = False
        for line in workflow.read_text().splitlines():
            stripped = line.strip()
            if re.match(r"^[a-z0-9_-]+:$", stripped) and line.startswith("  ") and not line.startswith("    "):
                current_gated = False  # a new job begins
            if stripped.startswith("if:") and gate.search(stripped):
                current_gated = True
            if stripped.startswith("- '") or stripped.startswith('- "'):
                continue  # a path filter entry, not a command
            if basename in stripped and re.search(r"python3?\s|bash\s|run:", stripped):
                if not current_gated:
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

    def test_every_top_level_repository_area_is_audited(self):
        # Tracked files only: local tool or build directories must not change the result.
        audited = {row["path"].split("/", 1)[0] for row in AUDIT["paths"]}
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.splitlines()
        actual = {path.split("/", 1)[0] for path in tracked if "/" in path}
        self.assertEqual(sorted(actual - audited), [], msg="top-level areas missing from the audit")

    def test_historical_drift_and_issue_links_are_recorded(self):
        findings = AUDIT["baseline_findings"]
        self.assertIn("10 labs", findings["catalog_drift"])
        self.assertIn("13", findings["catalog_drift"])
        self.assertEqual(findings["execution_corrections"], ["#202", "#203"])
        self.assertEqual(findings["catalog_corrections"], ["#176", "#182"])

    def test_every_paired_runbook_has_structured_comparisons_and_link_audit(self):
        records = AUDIT["paired_runbooks"]
        self.assertEqual({record["id"] for record in records}, REQUIRED_PAIRED_RUNBOOKS)
        for record in records:
            self.assertEqual(set(record["comparisons"]), REQUIRED_COMPARISONS, msg=record["id"])
            for name, comparison in record["comparisons"].items():
                self.assertEqual(comparison["result"], "MATCH", msg=f"{record['id']}:{name}")
                self.assertEqual(comparison["review_method"], SEMANTIC_REVIEW_METHOD, msg=f"{record['id']}:{name}")
                for evidence_path in comparison["evidence"]:
                    self.assertTrue((ROOT / evidence_path).exists(), msg=evidence_path)
            link_audit = record["link_audit"]
            self.assertEqual(link_audit["repo_local"], "PASS", msg=record["id"])
            self.assertEqual(link_audit["absolute_github"], "PASS", msg=record["id"])
            self.assertIn(link_audit["validator"], ALLOWED_LINK_VALIDATORS, msg=record["id"])
            self.assertTrue((ROOT / link_audit["validator"]).is_file(), msg=record["id"])
            self.assertTrue(invoked_by_ci(pathlib.Path(link_audit["validator"]).name), msg=record["id"])


class ReviewHonestyTests(unittest.TestCase):
    def test_no_comparison_claims_an_unattributed_human_review(self):
        methods = {
            comparison["review_method"]
            for record in AUDIT["paired_runbooks"] for comparison in record["comparisons"].values()
        }
        self.assertEqual(methods, {SEMANTIC_REVIEW_METHOD})
        self.assertIn(SEMANTIC_REVIEW_METHOD, AUDIT["review_methods"])
        self.assertIn("nor attributed to a human reviewer", AUDIT["review_methods"][SEMANTIC_REVIEW_METHOD])

    def test_the_inventory_states_that_it_is_partial_below_the_top_level(self):
        self.assertIn("partial below the top level", AUDIT["coverage_note"])

    def test_the_slot_procedure_pages_are_dispositioned_with_a_canonical_choice(self):
        by_path = {entry["path"]: entry for entry in AUDIT["paths"]}
        canonical = by_path["docs/operations/deployment-slots.md"]
        compact = by_path["docs/operations/deployment/slots-and-swap.md"]
        self.assertIn("authoritative executable procedure", canonical["reason"])
        self.assertIn("links to the canonical", compact["reason"])


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
    """A validator named as an enforcer must actually be invoked by CI.

    This class replaced an earlier pair of tests that pinned the transient
    finding itself: that validate_frontmatter.py was orphaned and therefore
    marked REWRITE. Those tests failed the moment the defect was fixed,
    which is what they were written to do. Pinning the finding is only
    useful until it is resolved; the durable property is that a documented
    enforcement claim is backed by an actual CI invocation.
    """

    def _claimed_enforcers(self):
        """Validators the retained mechanical contract names as enforcers."""
        contract = (ROOT / "DOCUMENTATION_CONTRACT.md").read_text()
        found = set()
        for match in re.finditer(r"`(tools/[\w./-]+\.py|scripts/[\w./-]+\.py)`", contract):
            path = match.group(1)
            window = contract[max(0, match.start() - 220):match.end() + 220].lower()
            if any(w in window for w in ("will fail", "rejects", "fails with", "blocking")):
                found.add(path)
        return found

    def test_contract_still_names_the_frontmatter_validator_as_an_enforcer(self):
        self.assertIn("tools/validate_frontmatter.py", self._claimed_enforcers())

    def test_every_validator_contract_calls_an_enforcer_is_invoked_by_ci(self):
        for path in sorted(self._claimed_enforcers()):
            if not (ROOT / path).is_file():
                continue
            self.assertTrue(
                invoked_by_ci(pathlib.Path(path).name),
                msg=f"DOCUMENTATION_CONTRACT.md says {path} rejects something, but no workflow runs it, "
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
