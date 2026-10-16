from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validation_status", ROOT / "scripts/generate_validation_status.py"
)
assert SPEC is not None and SPEC.loader is not None
validation_status = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validation_status)


class MethodStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = date(2026, 10, 14)

    def completed(self, result: str, last_tested: date | str) -> dict[str, date | str]:
        return {
            "result": result,
            "last_tested": last_tested,
            "run_id": "run-1",
            "evidence": "evidence/runs/run-1",
        }

    def test_pass_at_89_days_is_current(self) -> None:
        result = self.completed("pass", self.today - timedelta(days=89))

        status, tested = validation_status.get_method_status(result, self.today)

        self.assertEqual(status, validation_status.ICON_PASS)
        self.assertEqual(tested, "2026-07-17")

    def test_pass_at_90_days_is_current(self) -> None:
        result = self.completed("pass", self.today - timedelta(days=90))

        status, _ = validation_status.get_method_status(result, self.today)

        self.assertEqual(status, validation_status.ICON_PASS)

    def test_pass_at_91_days_is_stale(self) -> None:
        result = self.completed("pass", self.today - timedelta(days=91))

        status, _ = validation_status.get_method_status(result, self.today)

        self.assertEqual(status, validation_status.ICON_STALE)

    def test_future_date_is_invalid_not_pass(self) -> None:
        result = self.completed("pass", self.today + timedelta(days=1))

        status, tested = validation_status.get_method_status(result, self.today)

        self.assertEqual(status, validation_status.ICON_NO_DATA)
        self.assertEqual(tested, "2026-10-15")

    def test_malformed_date_is_invalid_not_pass(self) -> None:
        result = self.completed("pass", "not-a-date")

        status, tested = validation_status.get_method_status(result, self.today)

        self.assertEqual(status, validation_status.ICON_NO_DATA)
        self.assertEqual(tested, "not-a-date")

    def test_unknown_result_is_invalid_not_pass(self) -> None:
        result = self.completed("passed", "2026-10-01")

        status, tested = validation_status.get_method_status(result, self.today)

        self.assertEqual(status, validation_status.ICON_NO_DATA)
        self.assertEqual(tested, "2026-10-01")

    def test_not_tested_with_date_is_invalid(self) -> None:
        result = {"result": "not_tested", "last_tested": "2026-10-01"}

        status, tested = validation_status.get_method_status(result, self.today)

        self.assertEqual(status, validation_status.ICON_NO_DATA)
        self.assertEqual(tested, "2026-10-01")

    def test_fail_preserves_its_own_date(self) -> None:
        result = self.completed("fail", "2026-10-01")

        status, tested = validation_status.get_method_status(result, self.today)

        self.assertEqual(status, validation_status.ICON_FAIL)
        self.assertEqual(tested, "2026-10-01")

    def test_pass_without_run_identity_is_invalid(self) -> None:
        result = {"result": "pass", "last_tested": "2026-10-01"}

        status, tested = validation_status.get_method_status(result, self.today)

        self.assertEqual(status, validation_status.ICON_NO_DATA)
        self.assertEqual(tested, "2026-10-01")

    def test_cli_and_bicep_keep_independent_run_identities(self) -> None:
        cli = self.completed("pass", "2026-10-01")
        bicep = self.completed("fail", "2026-09-30")
        bicep["run_id"] = "run-2"
        bicep["evidence"] = "evidence/runs/run-2"

        cli_status, cli_date = validation_status.get_method_status(cli, self.today)
        bicep_status, bicep_date = validation_status.get_method_status(bicep, self.today)

        self.assertEqual(cli_status, validation_status.ICON_PASS)
        self.assertEqual(cli_date, "2026-10-01")
        self.assertEqual(bicep_status, validation_status.ICON_FAIL)
        self.assertEqual(bicep_date, "2026-09-30")


if __name__ == "__main__":
    unittest.main()
