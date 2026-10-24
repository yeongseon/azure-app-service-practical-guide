"""Small content regressions for the private endpoint / access restriction playbook.

These tests check selected invariants only. They never contact Azure: the
configuration commands are validated as text against a strict read-only
allowlist, not executed, and no test proves any causal claim in the prose.
"""
from __future__ import annotations

from pathlib import Path
import re
import shlex
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
PE = ROOT / "docs/troubleshooting/playbooks/private-endpoint-access-restrictions.md"
SCM = ROOT / "docs/troubleshooting/playbooks/scm-access-dns-and-http-failures.md"
NETWORKING = ROOT / "docs/operations/networking.md"
SECTIONS = (
    "1. Summary", "2. Common Misreadings", "3. Competing Hypotheses",
    "4. What to Check First", "5. Evidence to Collect",
    "6. Validation and Disproof by Hypothesis", "7. Likely Root Cause Patterns",
    "8. Immediate Mitigations", "9. Prevention", "See Also", "Sources",
)
# The ONLY shell on the page: two read-only reads, compared as exact logical lines.
# Slot variation is described in prose, so the fence itself never needs to change.
APPROVED_COMMANDS = (
    'az resource show --ids "$APP_RESOURCE_ID" --api-version 2024-11-01 --output json',
    'az webapp config access-restriction show --resource-group "$RG" --name "$APP_NAME" --output json',
)
# The retired rule of thumb "a private endpoint never closes default-endpoint access".
NEVER_CLOSES = re.compile(
    r"(?:\*{0,2}not\*{0,2}|n't|never)\s+automatically\s+(?:disabl\w*|block\w*)[^.\n]{0,40}public(?:\s+inbound)?\s+endpoint"
    r"|public(?:\s+inbound)?\s+endpoint\s+(?:is|are)\s+not\s+automatically\s+disabled",
    re.IGNORECASE,
)
FENCE = re.compile(r"```bash\n(.*?)\n```", re.DOTALL)


def first_bash_fence(text: str) -> str:
    match = FENCE.search(text)
    assert match is not None, "no bash fence"
    return match.group(1)


def logical_lines(script: str) -> list[str]:
    """Join backslash continuations and collapse whitespace; drop blank lines."""
    joined = script.replace("\\\n", " ")
    return [" ".join(line.split()) for line in joined.split("\n") if line.strip()]


def unapproved_configuration(page: str) -> list[str]:
    """Explain every way the page's shell differs from the two approved commands.

    Deliberately not a shell parser: any extra fence, line, operator, redirect,
    positional argument or missing flag changes a logical line and is reported.
    """
    fences = FENCE.findall(page)
    if len(fences) != 1:
        return [f"expected exactly one bash fence, found {len(fences)}"]
    actual = tuple(logical_lines(fences[0]))
    if actual == APPROVED_COMMANDS:
        return []
    return [f"unapproved shell line: {line!r}" for line in actual if line not in APPROVED_COMMANDS] or [
        f"approved commands missing or reordered: {actual!r}"
    ]


class PrivateEndpointPlaybookTests(unittest.TestCase):
    def test_numbered_sections_in_order(self) -> None:
        self.assertEqual(re.findall(r"^## (.+)$", PE.read_text(), re.MULTILINE), list(SECTIONS))

    def test_execution_and_causality_boundaries_present(self) -> None:
        text = PE.read_text()
        for token in ("NOT_RUN", "NOT_TESTED", "INCONCLUSIVE", "NOT_MET"):
            self.assertIn(token, text)
        self.assertNotIn("last_tested:", text)
        self.assertNotIn("captured_at:", text)

    def test_page_is_reachable_from_navigation_and_playbook_index(self) -> None:
        nav = (ROOT / "mkdocs.yml").read_text()
        index = (ROOT / "docs/troubleshooting/playbooks/index.md").read_text()
        self.assertIn("troubleshooting/playbooks/" + PE.name, nav)
        self.assertIn(f"]({PE.name})", index)

    def test_fences_balanced_and_one_diagram_with_matching_id(self) -> None:
        text = PE.read_text()
        self.assertEqual(len(re.findall(r"^```", text, re.MULTILINE)) % 2, 0)
        ids = re.findall(r"<!-- diagram-id: ([a-z0-9-]+) -->", text)
        self.assertEqual(len(ids), 1)
        self.assertIn(f"- id: {ids[0]}", text)
        self.assertIn("```mermaid\nflowchart TD\n", text)

    def test_policy_matrix_keeps_distinct_boundaries(self) -> None:
        rows: dict[tuple[str, str, str], str] = {}
        for line in PE.read_text().splitlines():
            cells = [part.strip() for part in line.strip().strip("|").split("|")]
            if len(cells) == 4 and cells[0] in {"Private endpoint", "Default endpoint"}:
                key = (cells[0], cells[1], cells[2])
                self.assertNotIn(key, rows, f"duplicate matrix row {key}")
                rows[key] = cells[3]
        expected = {
            ("Private endpoint", "Any publicNetworkAccess value", "Any main/SCM site rules"): "not evaluated for this traffic",
            ("Default endpoint", "Disabled", "Even a matching Allow"): "BLOCKED at app access",
            ("Default endpoint", "Enabled", "No match; default unset; zero configured rules"): "Implicit ALLOW",
            ("Default endpoint", "Enabled", "No match; default unset; one or more configured rules"): "Implicit DENY",
            ("Default endpoint", "null; no PE exists", "Evaluate applicable site rules"): "default ENABLED",
            ("Default endpoint", "null; PE exists", "Any site rule"): "default DISABLED",
        }
        for key, token in expected.items():
            with self.subTest(row=key):
                self.assertIn(key, rows)
                self.assertIn(token, rows[key])
        self.assertIn("does not guarantee HTTP 200", PE.read_text())

    def test_main_and_scm_controls_are_assessed_separately(self) -> None:
        text = PE.read_text()
        for posture in ("Public-only, main", "Public-only, SCM", "Private-only, main", "Private-only, SCM"):
            self.assertIn(f"| {posture} |", text)
        self.assertIn("Mixed: private deployment, SCM", text)

    def test_missing_property_is_never_projected_into_a_null(self) -> None:
        text = PE.read_text()
        self.assertIn("An absent property is UNKNOWN, not a verified JSON null", text)
        # A --query projection can fabricate a null for a field that was never returned.
        self.assertNotIn("--query", first_bash_fence(text))

    def test_audit_keeps_scope_and_missing_evidence_limits(self) -> None:
        text = PE.read_text()
        for token in (
            "AppServiceIPSecAuditLogs", "_ResourceId =~ TargetResourceId",
            "CsHost =~ TargetHost", "TimeGenerated >= StartUtc and TimeGenerated < EndUtc",
            "project TimeGenerated, CsHost, CIp, Result, Details, ServiceEndpoint",
            "excluding the unmatched rule", "No rows is not proof of no denial",
            "privateEndpointNetworkPolicies", "scmIpSecurityRestrictionsUseMain",
        ):
            self.assertIn(token, text)
        self.assertNotIn("ScSubStatus", text)

    def test_configuration_shell_is_exactly_the_two_approved_read_only_commands(self) -> None:
        self.assertEqual(unapproved_configuration(PE.read_text()), [])

    def test_exact_form_check_rejects_every_known_bypass(self) -> None:
        # Given: the real page and its single fence body.
        page = PE.read_text()
        body = first_bash_fence(page)
        mutations = {
            "semicolon append": body + "; az webapp stop",
            "single newline append": body + "\naz webapp stop",
            "blank-line append": body + "\n\naz webapp stop --name x",
            "adjacent and-and": body + "&&az webapp stop",
            "attached redirect": body.replace("--output json", "--output json>out.txt", 1),
            "pipe": body + " | tee out.txt",
            "command substitution": body.replace("$RG", "$(az account show)", 1),
            "extra positional": body.replace("az resource show", "az resource show extra", 1),
            "missing api-version": body.replace("  --api-version 2024-11-01 \\\n", "", 1),
            "changed verb": body.replace("resource show", "resource delete", 1),
            "dropped command": body.split("\n\n")[0],
        }

        for name, mutated in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(mutated, body)
                # When / Then: the exact-form check reports a difference.
                self.assertTrue(unapproved_configuration(page.replace(body, mutated, 1)), name)

        # And: an extra fence, or a missing fence, is rejected too.
        self.assertTrue(unapproved_configuration(page + "\n```bash\naz webapp stop\n```\n"))
        self.assertTrue(unapproved_configuration(page.replace(body, "", 1).replace("```bash\n\n```", "")))

    @unittest.skipUnless(shutil.which("bash"), "bash required for syntax checks")
    def test_configuration_script_parses(self) -> None:
        subprocess.run(["bash", "-n"], input=first_bash_fence(PE.read_text()), text=True, check=True, capture_output=True)

    def test_pages_link_in_both_directions(self) -> None:
        self.assertIn(f"]({SCM.name})", PE.read_text())
        self.assertIn(f"]({PE.name})", SCM.read_text())

    def test_no_page_says_a_private_endpoint_never_closes_default_access(self) -> None:
        # Given: the sentences that previously shipped on three pages.
        for old in (
            "Creating a Private Endpoint does not automatically block the public endpoint.",
            "The public inbound endpoint is not automatically disabled.",
            "Adding a private endpoint does not automatically disable the public endpoint;",
            "Creating a Private Endpoint assigns a private IP but does **not** automatically disable the public endpoint.",
        ):
            self.assertTrue(NEVER_CLOSES.search(old), old)

        # When: every page under docs/ is scanned.
        offenders = [
            f"{path.relative_to(ROOT)}:{number}"
            for path in sorted((ROOT / "docs").rglob("*.md"))
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if NEVER_CLOSES.search(line)
        ]

        # Then: none remains; raw publicNetworkAccess plus PE existence decides.
        self.assertEqual(offenders, [])

    def test_networking_page_no_longer_treats_configuration_as_reachability(self) -> None:
        text = NETWORKING.read_text()
        self.assertNotIn("proves the app is reachable from the entire internet", text)
        self.assertNotIn("HTTP response is `200` from the in-network client", text)
        self.assertIn("../troubleshooting/playbooks/private-endpoint-access-restrictions.md", text)


if __name__ == "__main__":
    unittest.main()
