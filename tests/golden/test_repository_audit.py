"""Repository audit tests (#180).

An audit is only trustworthy if its claims can be checked against the
repository. These tests verify that every audited path exists, that the
CI-orphan finding is still true, and that nothing is marked for deletion
without the separate review the policy requires.
"""

import sys

sys.dont_write_bytecode = True

import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest
from collections import Counter
from typing import TypedDict

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


class Membership(TypedDict, total=False):
    members: list[str]


class Disposition(Membership):
    path: str
    decision: str
    reason: str


def tracked_paths(root: pathlib.Path = ROOT) -> list[str]:
    """Preserve Git's NUL-delimited filename bytes without newline translation."""
    output = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout
    return [os.fsdecode(path) for path in output.split(b"\0") if path]


def coverage_problems(tracked: list[str], records: list[Disposition]) -> list[str]:
    """Check exact, disjoint winning membership; directory members are relative paths.

    Only tracked input participates. Longest explicit path wins, but it never
    admits a new member implicitly. Empty parent groups are valid when all
    descendants have more-specific records; empty leaf groups are not.
    """
    actual = set(tracked)
    problems: list[str] = []
    declared: list[str] = []
    keys = [row["path"] for row in records]
    for path, count in Counter(keys).items():
        if count > 1:
            problems.append(f"classification tie: {path}")
    for row in records:
        key = row["path"]
        if row["decision"] not in VALID:
            problems.append(f"illegal disposition: {key}")
        if not row["reason"].strip():
            problems.append(f"missing reason: {key}")
        members = [key + member for member in row.get("members", [])] if key.endswith("/") else [key]
        if not any(path == key or path.startswith(key) and key.endswith("/") for path in actual):
            problems.append(f"orphan classification: {key}")
        for path in members:
            declared.append(path)
            if pathlib.PurePosixPath(path).as_posix() != path or ".." in pathlib.PurePosixPath(path).parts or path.startswith("/"):
                problems.append(f"noncanonical member: {path}")
            candidates = [candidate for candidate in keys
                          if path == candidate or candidate.endswith("/") and path.startswith(candidate)]
            longest = max(map(len, candidates), default=0)
            winners = [candidate for candidate in candidates if len(candidate) == longest]
            if winners != [key]:
                problems.append(f"member not assigned to unique longest classification: {path} ({key})")
            if (path.startswith("evidence/") or "artifacts-sanitized" in path.split("/")
                    or "results" in path.split("/") or path.startswith("docs/assets/")
                    or path.startswith("labs/") and "/golden/" in path) and row["decision"] != "KEEP":
                problems.append(f"protected capture must stay KEEP: {path}")
    for path, count in Counter(declared).items():
        if count > 1:
            problems.append(f"duplicate membership: {path}")
    problems.extend(f"unclassified tracked path: {path}" for path in sorted(actual - set(declared)))
    problems.extend(f"classified path absent from tree: {path}" for path in sorted(set(declared) - actual))
    required = {path for path in actual if "/" not in path}
    required |= {path.split("/")[0] + "/" for path in actual if "/" in path}
    required |= {"/".join(path.split("/")[:2]) + "/" for path in actual if path.count("/") >= 2}
    problems.extend(f"missing explicit root or major group: {path}" for path in sorted(required - set(keys)))
    return sorted(problems)


class CoverageTests(unittest.TestCase):
    maxDiff: int | None = None
    tracked: list[str] = []
    records: list[Disposition] = []

    def setUp(self) -> None:
        self.tracked = ["README.md", "docs/index.md", "docs/topic/page.md"]
        self.records: list[Disposition] = [
            {"path": "README.md", "decision": "KEEP", "reason": "Reader entry point"},
            {"path": "docs/", "decision": "KEEP", "reason": "Navigation", "members": ["index.md"]},
            {"path": "docs/topic/", "decision": "KEEP", "reason": "Topic guidance", "members": ["page.md"]},
        ]

    def test_exact_membership_passes(self) -> None:
        self.assertEqual(coverage_problems(self.tracked, self.records), [])

    def test_additions_are_named_even_below_broad_groups(self) -> None:
        for added in ["NEW.md", "other/file.md", "docs/new.md", "docs/new-section/page.md", "docs/topic/nested/page.md"]:
            with self.subTest(path=added):
                self.assertIn(f"unclassified tracked path: {added}", coverage_problems(self.tracked + [added], self.records))

    def test_new_major_section_requires_its_own_record_even_if_member_is_added(self) -> None:
        self.records[1]["members"] = ["index.md", "new-section/page.md"]
        problems = coverage_problems(self.tracked + ["docs/new-section/page.md"], self.records)
        self.assertIn("missing explicit root or major group: docs/new-section/", problems)

    def test_removal_and_rename_report_both_sides(self) -> None:
        problems = coverage_problems(["README.md", "docs/index.md", "docs/topic/renamed.md"], self.records)
        self.assertIn("classified path absent from tree: docs/topic/page.md", problems)
        self.assertIn("unclassified tracked path: docs/topic/renamed.md", problems)

    def test_empty_members_cannot_fall_back_to_prefix(self) -> None:
        self.records[2]["members"] = []
        self.assertIn("unclassified tracked path: docs/topic/page.md", coverage_problems(self.tracked, self.records))

    def test_longest_override_wins_with_a_distinct_disposition(self) -> None:
        self.records[2]["members"] = []
        self.records.append({"path": "docs/topic/page.md", "decision": "ARCHIVE", "reason": "Historical draft"})
        self.assertEqual(coverage_problems(self.tracked, self.records), [])

    def test_ties_and_duplicate_or_ancestor_membership_fail(self) -> None:
        self.records.append(self.records[2].copy())
        self.records[1]["members"] = ["index.md", "topic/page.md"]
        problems = coverage_problems(self.tracked, self.records)
        self.assertIn("classification tie: docs/topic/", problems)
        self.assertIn("duplicate membership: docs/topic/page.md", problems)
        self.assertTrue(any("unique longest classification: docs/topic/page.md" in p for p in problems))

    def test_orphans_and_illegal_dispositions_fail(self) -> None:
        self.records.append({"path": "gone/", "decision": "DROP", "reason": "Unknown", "members": ["file"]})
        problems = coverage_problems(self.tracked, self.records)
        self.assertIn("orphan classification: gone/", problems)
        self.assertIn("classified path absent from tree: gone/file", problems)
        self.assertIn("illegal disposition: gone/", problems)

    def test_capture_members_cannot_be_archived(self) -> None:
        for path in ["evidence/runs/run/raw.json", "labs/example/results/raw.json",
                     "labs/example/artifacts-sanitized/raw.json", "labs/example/golden/manifest.json",
                     "docs/assets/capture.webp"]:
            with self.subTest(path=path):
                record: Disposition = {"path": path, "decision": "ARCHIVE", "reason": "Historical"}
                self.assertIn(f"protected capture must stay KEEP: {path}", coverage_problems([path], [record]))

    def test_noncanonical_members_fail_by_path_name(self) -> None:
        for member in ["../x", "/abs", "a//b", "./a", "a/./b"]:
            with self.subTest(member=member):
                self.records[1]["members"] = ["index.md", member]
                problems = coverage_problems(self.tracked, self.records)
                self.assertIn(f"noncanonical member: docs/{member}", problems)

    def test_blank_reason_fails_by_path_name(self) -> None:
        self.records[0]["reason"] = " \t\n"
        problems = coverage_problems(self.tracked, self.records)
        self.assertEqual(problems, ["missing reason: README.md"])

    def test_git_preserves_distinct_cr_and_lf_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            _ = subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            (root / "docs").mkdir()
            for name in ["docs/a\nb.md", "docs/a\rb.md"]:
                _ = (root / name).write_bytes(b"")
            _ = subprocess.run(["git", "add", "--", "docs"], cwd=root, check=True)
            records: list[Disposition] = [
                {"path": "docs/", "decision": "KEEP", "reason": "Declared LF path", "members": ["a\nb.md"]},
            ]
            tracked = tracked_paths(root)
            self.assertEqual(tracked, ["docs/a\nb.md", "docs/a\rb.md"])
            self.assertEqual(coverage_problems(tracked, records), ["unclassified tracked path: docs/a\rb.md"])

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
    maxDiff: int | None = None

    def test_every_audited_path_exists(self):
        for row in AUDIT["paths"]:
            self.assertTrue(
                (ROOT / row["path"]).exists(),
                msg=f"audit decides on {row['path']}, which is not in the repository")

    def test_declared_full_coverage_matches_the_tracked_tree(self):
        self.assertEqual(AUDIT["coverage_mode"], "exact-tracked-members")
        self.assertEqual(
            coverage_problems(tracked_paths(), AUDIT["paths"]), [],
            msg="Update docs/reference/golden-repository-audit.json: add the path to the winning record's members or add a more specific record; delete or rename the record of a removed or renamed path.",
        )

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

    def test_description_findings_have_sources_and_scoped_dispositions(self):
        records = AUDIT["baseline_findings"]["description_drift"]
        self.assertEqual({row["id"] for row in records}, {
            "windows-readme", "historical-stage-prerequisites", "historical-stage-layout",
            "startup-entrypoints-resolved", "java-package-resolved", "historical-catalog",
        })
        for row in records:
            self.assertIn(row["decision"], VALID, msg=row["id"])
            self.assertEqual(row["verification"], "Observed by reading")
            fields = ("section", "baseline_description", "disposition", "issues", "current_sources")
            if row["id"] in {"startup-entrypoints-resolved", "java-package-resolved", "historical-catalog"}:
                fields += ("baseline_source",)
            for field in fields:
                self.assertTrue(row[field], msg=f"{row['id']}:{field}")
            if "baseline_source" in row:
                self.assertTrue(isinstance(row["baseline_source"], str), msg=row["id"])
            for path in [row["path"], *row["current_sources"]]:
                self.assertTrue((ROOT / path).is_file(), msg=path)
            self.assertTrue(set(row["issues"]) <= {"#202", "#203", "#176", "#182"})


class ReviewHonestyTests(unittest.TestCase):
    def test_no_comparison_claims_an_unattributed_human_review(self):
        methods = {
            comparison["review_method"]
            for record in AUDIT["paired_runbooks"] for comparison in record["comparisons"].values()
        }
        self.assertEqual(methods, {SEMANTIC_REVIEW_METHOD})
        self.assertIn(SEMANTIC_REVIEW_METHOD, AUDIT["review_methods"])
        self.assertIn("nor attributed to a human reviewer", AUDIT["review_methods"][SEMANTIC_REVIEW_METHOD])

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
