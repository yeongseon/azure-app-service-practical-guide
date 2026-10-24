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
SHELL_CONTROL = {";", "&&", "||", "|", "&", ">", ">>", "<", "<<", "<<<"}
ALLOWED = {
    ("az", "resource", "show"): {"--ids", "--api-version", "--output"},
    ("az", "webapp", "config", "access-restriction", "show"): {
        "--resource-group", "--name", "--slot", "--output",
    },
}


def first_bash_fence(text: str) -> str:
    match = re.search(r"```bash\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "no bash fence"
    return match.group(1)


def disallowed_in(script: str) -> list[str]:
    """Return reasons a configuration script is not on the read-only allowlist."""
    problems: list[str] = []
    commands = [part for part in script.replace("\\\n", " ").split("\n\n") if part.strip()]
    for command in commands:
        if "$(" in command or "`" in command:
            problems.append(f"command substitution: {command[:50]}")
        tokens = shlex.split(command, comments=False, posix=True)
        for key, flags in ALLOWED.items():
            if tuple(tokens[: len(key)]) == key:
                used = {token for token in tokens[len(key):] if token.startswith("--")}
                if not used <= flags:
                    problems.append(f"unexpected flags {sorted(used - flags)} for {' '.join(key)}")
                break
        else:
            problems.append(f"command not allowlisted: {' '.join(tokens[:4])}")
        if any(token in SHELL_CONTROL for token in tokens):
            problems.append(f"shell control operator in: {' '.join(tokens[:4])}")
    return problems


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
            ("Private endpoint", "Any publicNetworkAccess value", "Any main/SCM site rules"): "NOT_EVALUATED",
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

    def test_configuration_commands_are_on_the_read_only_allowlist(self) -> None:
        script = first_bash_fence(PE.read_text())
        self.assertEqual(disallowed_in(script), [])
        commands = [p for p in script.replace("\\\n", " ").split("\n\n") if p.strip()]
        self.assertEqual(len(commands), 2)

    def test_allowlist_rejects_the_mutations_the_old_check_missed(self) -> None:
        # Given: the real script with an appended mutating command, and a changed verb.
        script = first_bash_fence(PE.read_text())

        # When / Then: both are rejected.
        self.assertTrue(disallowed_in(script + "\n\naz webapp stop --name x --resource-group y"))
        self.assertTrue(disallowed_in(script.replace(" show", " update", 1)))
        self.assertTrue(disallowed_in(script.replace("--output json", "--output json > out.txt", 1)))

    @unittest.skipUnless(shutil.which("bash"), "bash required for syntax checks")
    def test_configuration_script_parses(self) -> None:
        subprocess.run(["bash", "-n"], input=first_bash_fence(PE.read_text()), text=True, check=True, capture_output=True)

    def test_pages_link_in_both_directions(self) -> None:
        self.assertIn(f"]({SCM.name})", PE.read_text())
        self.assertIn(f"]({PE.name})", SCM.read_text())

    def test_networking_page_no_longer_treats_configuration_as_reachability(self) -> None:
        text = NETWORKING.read_text()
        self.assertNotIn("proves the app is reachable from the entire internet", text)
        self.assertNotIn("HTTP response is `200` from the in-network client", text)
        self.assertIn("../troubleshooting/playbooks/private-endpoint-access-restrictions.md", text)


if __name__ == "__main__":
    unittest.main()
