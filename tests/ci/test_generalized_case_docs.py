"""Small content regressions and synthetic arithmetic, not Azure/KQL validation.

These tests check selected invariants only. They do not prove the correctness of
natural-language causal claims, parse KQL, or reproduce an Azure incident.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import shlex
import shutil
import statistics
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCM = ROOT / "docs/troubleshooting/playbooks/scm-access-dns-and-http-failures.md"
TAIL = ROOT / "docs/troubleshooting/playbooks/performance/tail-latency-baseline-comparison.md"
PRIVATE = ROOT / "docs/troubleshooting/playbooks/private-endpoint-access-restrictions.md"
PLAYBOOKS = (SCM, TAIL, PRIVATE)
SECTIONS = (
    "1. Summary", "2. Common Misreadings", "3. Competing Hypotheses",
    "4. What to Check First", "5. Evidence to Collect",
    "6. Validation and Disproof by Hypothesis", "7. Likely Root Cause Patterns",
    "8. Immediate Mitigations", "9. Prevention", "See Also", "Sources",
)


def synthetic_rows(text: str) -> dict[str, list[float]]:
    """Read only the two numeric rows from the explicitly synthetic table."""
    rows: dict[str, list[float]] = {}
    for line in text.splitlines():
        cells = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(cells) == 8 and cells[0] in {"Baseline", "Incident"}:
            rows[cells[0]] = [float(cell) for cell in cells[1:]]
    return rows


def expected_row(values: list[float]) -> list[float]:
    ordered = sorted(values)
    n = len(ordered)
    percentiles = [ordered[math.ceil(n * p / 100) - 1] for p in (50, 95, 99)]
    slow = sum(value > 10 for value in ordered)
    return [float(n), statistics.mean(ordered), *percentiles, float(slow), 100 * slow / n]


class GeneralizedCaseDocsTests(unittest.TestCase):
    def test_numbered_sections_in_order(self) -> None:
        for path in PLAYBOOKS:
            with self.subTest(path=path.name):
                headings = re.findall(r"^## (.+)$", path.read_text(), re.MULTILINE)
                self.assertEqual(headings, list(SECTIONS))

    def test_execution_and_causality_boundaries_present(self) -> None:
        for path in PLAYBOOKS:
            text = path.read_text()
            with self.subTest(path=path.name):
                for token in ("NOT_RUN", "NOT_TESTED", "INCONCLUSIVE"):
                    self.assertIn(token, text)
                self.assertNotIn("last_tested:", text)
                self.assertNotIn("captured_at:", text)

    def test_navigation_keeps_all_pages_reachable(self) -> None:
        nav = (ROOT / "mkdocs.yml").read_text()
        index = (ROOT / "docs/troubleshooting/playbooks/index.md").read_text()
        for path in PLAYBOOKS:
            self.assertIn(str(path.relative_to(ROOT / "docs")), nav)
            self.assertIn(str(path.relative_to(SCM.parent)), index)

    def test_kql_keeps_scope_units_and_missing_data(self) -> None:
        text = TAIL.read_text()
        for token in (
            "_ResourceId =~ TargetResourceId", "CsHost =~ TargetHost",
            "TimeGenerated >= BaselineStart and TimeGenerated < BaselineEnd",
            "TimeGenerated >= IncidentStart and TimeGenerated < IncidentEnd",
            "where ValidWindows", "INVALID_WINDOW", "NO_RETAINED_ROWS",
            "NO_VALID_TIMINGS", "kind=leftouter", "real(null)",
            "TimedRows=countif(isnotnull(DurationMs))",
            "100.0 * SlowRows / TimedRows", "100.0 * ErrorRows / RetainedRows",
        ):
            self.assertIn(token, text)
        self.assertNotRegex(text, r"(?:MeanMs|P\d+Ms)\s*=\s*coalesce")

    def test_synthetic_table_matches_declared_distribution(self) -> None:
        actual = synthetic_rows(TAIL.read_text())
        self.assertEqual(set(actual), {"Baseline", "Incident"})
        expected = {
            "Baseline": expected_row([1.0] * 980 + [15.0] * 20),
            "Incident": expected_row([1.0] * 970 + [25.0] * 30),
        }
        self.assertEqual(actual, expected)

    def test_changed_synthetic_number_is_detectable(self) -> None:
        text = TAIL.read_text()
        mutated = text.replace("| Incident | 1000 | 1.72 |", "| Incident | 1000 | 9.99 |")
        self.assertNotEqual(mutated, text)
        self.assertNotEqual(
            synthetic_rows(mutated)["Incident"],
            expected_row([1.0] * 970 + [25.0] * 30),
        )

    def test_fences_and_diagram_ids(self) -> None:
        for path in PLAYBOOKS:
            text = path.read_text()
            with self.subTest(path=path.name):
                self.assertEqual(len(re.findall(r"^```", text, re.MULTILINE)) % 2, 0)
                ids = re.findall(r"<!-- diagram-id: ([a-z0-9-]+) -->", text)
                self.assertEqual(len(ids), 1)
                self.assertIn(f"- id: {ids[0]}", text)
                self.assertIn("```mermaid\nflowchart TD\n", text)

    def test_private_matrix_retains_distinct_policy_boundaries(self) -> None:
        rows: dict[tuple[str, str, str], str] = {}
        for line in PRIVATE.read_text().splitlines():
            cells = [part.strip() for part in line.strip().strip("|").split("|")]
            if len(cells) == 4 and cells[0] in {"Private endpoint", "Default endpoint"}:
                key = (cells[0], cells[1], cells[2])
                self.assertNotIn(key, rows)
                rows[key] = cells[3]
        expected_tokens = {
            ("Private endpoint", "Any publicNetworkAccess value", "Any main/SCM site rules"): "NOT_EVALUATED",
            ("Default endpoint", "Disabled", "Even a matching Allow"): "BLOCKED at app access",
            ("Default endpoint", "Enabled", "No match; default unset; zero configured rules"): "Implicit ALLOW",
            ("Default endpoint", "Enabled", "No match; default unset; one or more configured rules"): "Implicit DENY",
            ("Default endpoint", "null; no PE exists", "Evaluate applicable site rules"): "default ENABLED",
            ("Default endpoint", "null; PE exists", "Any site rule"): "default DISABLED",
        }
        for key, token in expected_tokens.items():
            with self.subTest(row=key):
                self.assertIn(key, rows)
                self.assertIn(token, rows[key])
        self.assertIn("does not guarantee HTTP 200", PRIVATE.read_text())

    def test_private_audit_keeps_scope_and_missing_evidence_limits(self) -> None:
        text = PRIVATE.read_text()
        for token in (
            "AppServiceIPSecAuditLogs", "_ResourceId =~ TargetResourceId",
            "CsHost =~ TargetHost", "TimeGenerated >= StartUtc and TimeGenerated < EndUtc",
            "project TimeGenerated, CsHost, CIp, Result, Details, ServiceEndpoint",
            "excluding the unmatched rule", "No rows is not proof of no denial",
            "NOT_MET", "privateEndpointNetworkPolicies", "scmIpSecurityRestrictionsUseMain",
        ):
            self.assertIn(token, text)
        self.assertNotIn("ScSubStatus", text)

    def test_scm_and_private_policy_pages_cross_link(self) -> None:
        self.assertIn(f"]({PRIVATE.name})", SCM.read_text())
        self.assertIn(f"]({SCM.name})", PRIVATE.read_text())

    @unittest.skipUnless(shutil.which("bash"), "bash required for syntax checks")
    def test_private_configuration_examples_are_read_only(self) -> None:
        scripts = re.findall(r"```bash\n(.*?)\n```", PRIVATE.read_text(), re.DOTALL)
        self.assertEqual(len(scripts), 1)
        script = scripts[0]
        commands = [shlex.split(part) for part in script.replace("\\\n", " ").split("\n\n")]
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0][:3], ["az", "webapp", "show"])
        self.assertEqual(commands[1][:5], ["az", "webapp", "config", "access-restriction", "show"])
        for command in commands:
            self.assertIn("--resource-group", command)
            self.assertIn("--name", command)
            self.assertIn("--output", command)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True, capture_output=True)

    @unittest.skipUnless(shutil.which("bash"), "bash required for syntax and mock checks")
    def test_bash_probe_syntax(self) -> None:
        script = re.search(r"```bash\n(.*?)\n```", SCM.read_text(), re.DOTALL)
        self.assertIsNotNone(script)
        body = script.group(1)  # type: ignore[union-attr]
        self.assertNotIn("--insecure", body)
        self.assertIn("--connect-timeout 10 --max-time 30", body)
        subprocess.run(["bash", "-n"], input=body, text=True, check=True, capture_output=True)

    @unittest.skipUnless(shutil.which("bash"), "bash required for mock checks")
    def test_probe_retains_mock_failures_without_network(self) -> None:
        script = re.search(r"```bash\n(.*?)\n```", SCM.read_text(), re.DOTALL)
        self.assertIsNotNone(script)
        body = script.group(1)  # type: ignore[union-attr]
        mocks = (
            "nslookup() { printf 'mock DNS failure\\n'; return 1; }\n"
            "curl() { printf 'http=000 remote_ip= total_seconds=0\\n'; return 6; }\n"
        )
        result = subprocess.run(
            ["bash", "-c", mocks + body], text=True, capture_output=True, check=True,
        )
        self.assertIn("dns_exit=1", result.stdout)
        self.assertIn("curl_exit=6", result.stdout)
        self.assertIn("http=000", result.stdout)


if __name__ == "__main__":
    unittest.main()
