"""Selected wording regressions, not GitHub enforcement or review approval.

These offline checks pin the requested review procedure and template structure.
They cannot certify a remote reviewer, protection setting, Oracle score or merge.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[2]
REVIEW_LINK: Final = "DOCUMENTATION_CONTRACT.md#current-head-github-review-loop"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class ReviewAndTriageContractTests(unittest.TestCase):
    def test_template_keeps_ordered_sections_and_third_checkbox(self) -> None:
        template = read(".github/pull_request_template.md")
        headings = re.findall(r"^## (.+)$", template, flags=re.MULTILINE)
        checkboxes = re.findall(r"^- \[ \] (.+)$", template, flags=re.MULTILINE)
        self.assertEqual(headings, [
            "Summary", "Changes", "Type of Change", "Validation", "Checklist", "Related Issues",
        ])
        self.assertEqual(checkboxes[2],
                         "Scope and mandatory review gates were checked; no failing gate was bypassed.")

    def test_template_validation_contains_review_evidence_fields(self) -> None:
        template = read(".github/pull_request_template.md")
        validation = template.split("## Validation\n", 1)[1].split("## Checklist\n", 1)[0]
        self.assertIn("### GitHub review evidence", validation)
        for field in (
            "Current head SHA:", "Reviewer identity and review URL/ID:",
            "Reviewed head SHA:", "Review outcome:", "Findings and thread dispositions:",
            "Required CI results for this head:", "Oracle and applicable image-review evidence:",
            "Remaining merge blockers:",
        ):
            with self.subTest(field=field):
                self.assertIn(f"- {field}", validation)
        self.assertIn(REVIEW_LINK, validation)

    def test_short_agent_entrypoint_links_to_canonical_procedure(self) -> None:
        agents = read("AGENTS.md")
        boundary = agents.split("## Review and Merge Boundary\n", 1)[1]
        self.assertIn(f"]({REVIEW_LINK})", boundary)
        self.assertNotIn("### Current-head GitHub review loop", agents)

    def test_review_states_do_not_claim_success_or_provider_enforcement(self) -> None:
        contract = read("DOCUMENTATION_CONTRACT.md")
        review = " ".join(contract.split("### Current-head GitHub review loop\n", 1)[1]
                          .split("## Merge Policy", 1)[0].split())
        for phrase in (
            "local review states, not CI results or GitHub review API states",
            "`REQUESTED`", "`COMPLETE`", "`FINDINGS_OPEN`", "`BLOCKED`",
            "A bot review is evidence, not an approval or a substitute for Oracle review",
            "GitHub does not enforce these procedural gates in that record",
            "No response, an acknowledgement reaction, quota failure or an empty comment list is not review success",
            "names no push trigger; do not assume a push runs a fresh review",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, review)

    def test_each_head_requires_request_dispositions_and_premerge_guard(self) -> None:
        contract = read("DOCUMENTATION_CONTRACT.md")
        review = " ".join(contract.split("### Current-head GitHub review loop\n", 1)[1]
                          .split("## Merge Policy", 1)[0].split())
        for phrase in (
            "request the configured reviewer explicitly", "@codex review",
            "fixed with evidence and relevant tests", "not applicable with a reason and evidence",
            "deferred with a linked issue",
            "Deferral is not a disposition for a must-fix finding",
            "a resolved-thread flag alone is not proof of a fix",
            "A head SHA change makes every earlier review history",
            "never reuse an earlier result as coverage of changed code",
            "Merge conditions are unchanged",
            "A missing required check is `BLOCKED`",
            "expected-head guard immediately before the squash merge",
            "head SHA from the GitHub API and compare it with the reviewed SHA",
            "gh api repos/{owner}/{repo}/pulls/{n} --jq .head.sha",
            "stop the merge and restart this review and validation loop for the new head",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, review)

    def test_loop_adds_no_merge_gate_and_makes_no_bot_review_a_precondition(self) -> None:
        contract = read("DOCUMENTATION_CONTRACT.md")
        review = " ".join(contract.split("### Current-head GitHub review loop\n", 1)[1]
                          .split("## Merge Policy", 1)[0].split())
        for phrase in (
            "it adds no merge gate",
            "the Oracle review, CI on the exact head and the image gates of Merge Policy "
            "remain the only conditions for an autonomous squash merge",
            "a missing review, or a `REQUESTED`, `FINDINGS_OPEN` or `BLOCKED` state, "
            "does not by itself stop a merge that satisfies those gates",
            "a review that was never requested is recorded as none, not as a failing gate",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, review)
        for phrase in ("a `COMPLETE` current-head review", "active changes-requested review"):
            with self.subTest(forbidden=phrase):
                self.assertNotIn(phrase, review)
        self.assertNotIn("GitHub review completed for the current head SHA",
                         read(".github/pull_request_template.md"))
        self.assertIn("it adds no merge gate to the retained gates below", read("AGENTS.md"))

    def test_existing_oracle_autonomous_merge_and_image_gates_remain(self) -> None:
        contract = " ".join(read("DOCUMENTATION_CONTRACT.md").split())
        for phrase in (
            "**ALL work performed by AI agents MUST undergo Oracle quality review before completion.**",
            "**NO WORK IS CONSIDERED COMPLETE WITHOUT ORACLE APPROVAL.**",
            "There is no separate human approval step — passing every gate IS the approval.",
            "**Oracle review ≥ 90/100**", "Any must-fix item is a blocker even at ≥ 90.",
            "Every required GitHub Actions check on the PR head SHA passes.",
            "**Caption ↔ image match**", "**Final-image PII verification**",
            "on the **final committed bytes**", "gh pr merge <pr> --squash --delete-branch",
            "Never bypass a failing or pending gate. Never merge with `--admin` to skip checks.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract)


if __name__ == "__main__":
    unittest.main()
