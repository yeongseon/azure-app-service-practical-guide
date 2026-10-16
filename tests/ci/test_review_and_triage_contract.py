"""Narrow documentation regressions, not remote review or protection validation.

These tests preserve selected operating instructions and navigation. They do
not query GitHub, approve a PR, prove Azure behavior, or enable auto-merge.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class ReviewAndTriageContractTests(unittest.TestCase):
    def test_pr_template_preserves_canonical_sections_and_review_fields(self) -> None:
        template = read(".github/pull_request_template.md")
        self.assertEqual(
            re.findall(r"^## (.+)$", template, flags=re.MULTILINE),
            ["Summary", "Changes", "Type of Change", "Validation", "Checklist", "Related Issues"],
        )
        for field in (
            "Current head SHA:", "Reviewer identity and review URL/ID:",
            "Reviewed head SHA:", "Review outcome:",
            "Findings and thread dispositions:", "Required CI results for this head:",
            "Oracle and applicable image-review evidence:", "Remaining merge blockers:",
        ):
            with self.subTest(field=field):
                self.assertIn(field, template)
        self.assertIn("AGENTS.md#github-review-before-merge", template)

    def test_agent_rule_keeps_current_head_and_no_false_success_boundaries(self) -> None:
        agents = " ".join(read("AGENTS.md").split())
        for phrase in (
            "### GitHub review before merge", "@codex review",
            "REQUESTED", "COMPLETE is not merge approval", "FINDINGS_OPEN", "BLOCKED",
            "A new head SHA requires a fresh review",
            "All existing mandatory merge gates in DOCUMENTATION_CONTRACT.md remain in force",
            "AI review comments are not human approvals",
            "expected-head guard", "Merge by squash only",
            "No response, an acknowledgement reaction, quota failure or an empty comment list is not review success",
            "Do not enable native auto-merge until repository-level requirements are verified",
            "UNKNOWN protection state",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, agents)

    def test_main_index_directly_routes_to_all_generalized_playbooks(self) -> None:
        index = read("docs/troubleshooting/index.md")
        start = index.index("### Inbound Access and Slow-Request Symptom Routes")
        end = index.index("## Quick Decision Tree", start)
        routes = index[start:end]
        targets = (
            "playbooks/scm-access-dns-and-http-failures.md",
            "playbooks/private-endpoint-access-restrictions.md",
            "playbooks/performance/tail-latency-baseline-comparison.md",
        )
        for target in targets:
            with self.subTest(target=target):
                self.assertIn(f"]({target})", routes)
                self.assertTrue((ROOT / "docs/troubleshooting" / target).is_file())
        self.assertIn("not customer RCA records or new lab execution results", routes)

    def test_quick_start_keeps_client_ingress_separate_from_app_egress(self) -> None:
        index = read("docs/troubleshooting/index.md")
        start = index.index("## Quick Start")
        end = index.index("## Hands-on Labs", start)
        quick_start = index[start:end]
        self.assertIn(
            "| Browser or deployment-agent inbound access issue | [Inbound symptom routes](#inbound-access-and-slow-request-symptom-routes) |",
            quick_start,
        )
        self.assertIn(
            "| First 10 minutes of an app-to-dependency outbound issue | [Network Checklist](first-10-minutes/outbound-network.md) |",
            quick_start,
        )
        self.assertNotIn("| First 10 minutes of a network issue |", quick_start)


if __name__ == "__main__":
    unittest.main()
