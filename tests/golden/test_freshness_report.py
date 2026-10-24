from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "freshness_report", ROOT / "scripts/golden/freshness_report.py"
)
assert SPEC is not None and SPEC.loader is not None
freshness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freshness)


class FreshnessReportTests(unittest.TestCase):
    def test_report_is_read_only_and_uses_existing_last_tested(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tutorial = root / "docs/language-guides/python/tutorial/01-test.md"
            tutorial.parent.mkdir(parents=True)
            tutorial.write_text(
                "---\nvalidation:\n  az_cli:\n    last_tested: 2026-07-01\n    result: pass\n---\n# Test\n",
                encoding="utf-8",
            )
            before = tutorial.read_bytes()

            report = freshness.build_report(root, date(2026, 10, 16))

            self.assertEqual(tutorial.read_bytes(), before)
            self.assertIn("2026-07-01", report)
            self.assertIn("Stale", report)

    def test_future_last_tested_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tutorial = root / "docs/language-guides/python/tutorial/01-test.md"
            tutorial.parent.mkdir(parents=True)
            tutorial.write_text(
                "---\nvalidation:\n  az_cli:\n    last_tested: 2026-10-17\n    result: pass\n---\n# Test\n",
                encoding="utf-8",
            )

            report = freshness.build_report(root, date(2026, 10, 16))

        self.assertIn("Invalid", report)


if __name__ == "__main__":
    unittest.main()
