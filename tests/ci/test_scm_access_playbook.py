"""Small content regressions for the SCM client-access playbook.

These tests check selected invariants only. They do not prove the correctness of
natural-language causal claims, and they never contact Azure or the network: the
bash probe is syntax-checked and run against mocked ``nslookup``/``curl``.
"""
from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCM = ROOT / "docs/troubleshooting/playbooks/scm-access-dns-and-http-failures.md"
SECTIONS = (
    "1. Summary", "2. Common Misreadings", "3. Competing Hypotheses",
    "4. What to Check First", "5. Evidence to Collect",
    "6. Validation and Disproof by Hypothesis", "7. Likely Root Cause Patterns",
    "8. Immediate Mitigations", "9. Prevention", "See Also", "Sources",
)


def probe_script() -> str:
    match = re.search(r"```bash\n(.*?)\n```", SCM.read_text(), re.DOTALL)
    assert match is not None, "playbook has no bash probe"
    return match.group(1)


class ScmAccessPlaybookTests(unittest.TestCase):
    def test_numbered_sections_in_order(self) -> None:
        headings = re.findall(r"^## (.+)$", SCM.read_text(), re.MULTILINE)
        self.assertEqual(headings, list(SECTIONS))

    def test_execution_and_causality_boundaries_present(self) -> None:
        text = SCM.read_text()
        for token in ("NOT_RUN", "NOT_TESTED", "INCONCLUSIVE"):
            self.assertIn(token, text)
        # Source review must not masquerade as a retained Azure execution.
        self.assertNotIn("last_tested:", text)
        self.assertNotIn("captured_at:", text)

    def test_page_is_reachable_from_navigation_and_playbook_index(self) -> None:
        nav = (ROOT / "mkdocs.yml").read_text()
        index = (ROOT / "docs/troubleshooting/playbooks/index.md").read_text()
        self.assertIn("troubleshooting/playbooks/" + SCM.name, nav)
        self.assertIn(f"]({SCM.name})", index)

    def test_fences_balanced_and_one_diagram_with_matching_id(self) -> None:
        text = SCM.read_text()
        self.assertEqual(len(re.findall(r"^```", text, re.MULTILINE)) % 2, 0)
        ids = re.findall(r"<!-- diagram-id: ([a-z0-9-]+) -->", text)
        self.assertEqual(len(ids), 1)
        self.assertIn(f"- id: {ids[0]}", text)
        self.assertIn("```mermaid\nflowchart TD\n", text)

    @unittest.skipUnless(shutil.which("bash"), "bash required for syntax checks")
    def test_probe_is_bounded_never_disables_tls_and_parses(self) -> None:
        body = probe_script()
        self.assertNotIn("--insecure", body)
        self.assertNotRegex(body, r"\bcurl\b[^\n]*\s-k\b")
        # --disable must be curl's first argument or .curlrc can still alter the probe.
        self.assertRegex(body, r"(?m)^curl --disable ")
        self.assertIn("--connect-timeout 10 --max-time 30", body)
        self.assertIn("nslookup -timeout=5 -retry=1", body)
        subprocess.run(["bash", "-n"], input=body, text=True, check=True, capture_output=True)

    def _run_probe(self, dns_rc: int, curl_rc: int, http: str, errexit: bool = False):
        mocks = (
            f"nslookup() {{ printf 'mock dns args=%s\\n' \"$*\"; return {dns_rc}; }}\n"
            f"curl() {{ printf 'mock curl first=%s\\n' \"$1\" >&2; "
            f"printf 'http={http} remote_ip= total_seconds=0\\n'; return {curl_rc}; }}\n"
        )
        prefix = "set -e\n" if errexit else ""
        return subprocess.run(
            ["bash", "-c", prefix + mocks + probe_script()],
            text=True, capture_output=True, check=True, timeout=10,
        )

    @unittest.skipUnless(shutil.which("bash"), "bash required for mock checks")
    def test_dns_failure_is_retained_even_under_errexit(self) -> None:
        # Given: a failing lookup and a shell running with set -e.
        result = self._run_probe(dns_rc=1, curl_rc=0, http="200", errexit=True)

        # Then: the probe still reports the DNS exit and continues to curl.
        self.assertIn("dns_exit=1", result.stdout)
        self.assertIn("curl_exit=0", result.stdout)
        self.assertIn("args=-timeout=5 -retry=1", result.stdout)

    @unittest.skipUnless(shutil.which("bash"), "bash required for mock checks")
    def test_transport_failure_is_not_reported_as_http_success(self) -> None:
        result = self._run_probe(dns_rc=0, curl_rc=6, http="000", errexit=True)
        self.assertIn("dns_exit=0", result.stdout)
        self.assertIn("curl_exit=6", result.stdout)
        self.assertIn("http=000", result.stdout)

    @unittest.skipUnless(shutil.which("bash"), "bash required for mock checks")
    def test_success_and_auth_status_both_exit_zero_and_curl_gets_disable_first(self) -> None:
        # A 403 completes the transfer: curl exits 0 without --fail (documented in the page).
        result = self._run_probe(dns_rc=0, curl_rc=0, http="403")
        self.assertIn("curl_exit=0", result.stdout)
        self.assertIn("http=403", result.stdout)
        self.assertIn("first=--disable", result.stderr)


if __name__ == "__main__":
    unittest.main()
