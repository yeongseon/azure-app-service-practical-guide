"""Content regressions and synthetic arithmetic for the tail-latency playbook.

Not Azure/KQL validation: these check selected invariants only.
"""
from __future__ import annotations

import math
import re
import statistics
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAIL = ROOT / "docs/troubleshooting/playbooks/performance/tail-latency-baseline-comparison.md"
SECTIONS = (
    "1. Summary", "2. Common Misreadings", "3. Competing Hypotheses",
    "4. What to Check First", "5. Evidence to Collect",
    "6. Validation and Disproof by Hypothesis", "7. Likely Root Cause Patterns",
    "8. Immediate Mitigations", "9. Prevention", "See Also", "Sources",
)


def synthetic_rows(text: str) -> dict[str, list[float]]:
    rows: dict[str, list[float]] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 8 and cells[0] in {"Baseline", "Incident"}:
            rows[cells[0]] = [float(c) for c in cells[1:]]
    return rows


def expected_row(values: list[float]) -> list[float]:
    o = sorted(values)
    n = len(o)
    pct = [o[math.ceil(n * p / 100) - 1] for p in (50, 95, 99)]
    slow = sum(v > 10 for v in o)
    return [float(n), statistics.mean(o), *pct, float(slow), 100 * slow / n]


class TailLatencyPlaybookTests(unittest.TestCase):
    def test_numbered_sections_in_order(self) -> None:
        self.assertEqual(re.findall(r"^## (.+)$", TAIL.read_text(), re.MULTILINE), list(SECTIONS))

    def test_execution_boundaries_present(self) -> None:
        text = TAIL.read_text()
        for token in ("NOT_RUN", "NOT_TESTED", "INCONCLUSIVE"):
            self.assertIn(token, text)
        self.assertNotIn("last_tested:", text)
        self.assertNotIn("captured_at:", text)

    def test_navigation_reachable(self) -> None:
        rel = str(TAIL.relative_to(ROOT / "docs"))
        self.assertIn(rel, (ROOT / "mkdocs.yml").read_text())
        self.assertIn("performance/tail-latency-baseline-comparison.md",
                      (ROOT / "docs/troubleshooting/playbooks/index.md").read_text())
        self.assertIn("playbooks/performance/tail-latency-baseline-comparison.md",
                      (ROOT / "docs/troubleshooting/index.md").read_text())

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
        self.assertEqual(synthetic_rows(TAIL.read_text()), {
            "Baseline": expected_row([1.0] * 980 + [15.0] * 20),
            "Incident": expected_row([1.0] * 970 + [25.0] * 30),
        })

    def test_changed_synthetic_number_is_detectable(self) -> None:
        text = TAIL.read_text()
        mutated = text.replace("| Incident | 1000 | 1.72 |", "| Incident | 1000 | 9.99 |")
        self.assertNotEqual(mutated, text)
        self.assertNotEqual(synthetic_rows(mutated)["Incident"], expected_row([1.0] * 970 + [25.0] * 30))

    def test_causality_and_percentile_guards(self) -> None:
        text = TAIL.read_text()
        self.assertIn("is **not** the dependency's contribution", text)
        self.assertIn("Do not average per-minute P99 values", text)
        self.assertIn("AppRequests", text)

    def test_overstrong_shorthand_removed_from_existing_page(self) -> None:
        page = (ROOT / "docs/troubleshooting/playbooks/performance-degradation.md").read_text()
        self.assertNotIn("Tail latency helps isolate queueing", page)

    def test_fences_and_diagram_id(self) -> None:
        text = TAIL.read_text()
        self.assertEqual(len(re.findall(r"^```", text, re.MULTILINE)) % 2, 0)
        ids = re.findall(r"<!-- diagram-id: ([a-z0-9-]+) -->", text)
        self.assertEqual(len(ids), 1)
        self.assertIn(f"- id: {ids[0]}", text)


if __name__ == "__main__":
    unittest.main()
