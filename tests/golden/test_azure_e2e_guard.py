from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "azure_e2e_guard", ROOT / "scripts/golden/azure_e2e_guard.py"
)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class AzureE2EGuardTests(unittest.TestCase):
    def test_workflow_upload_requires_successful_sanitize_and_scan(self) -> None:
        workflow = (ROOT / ".github/workflows/e2e-azure.yml").read_text(encoding="utf-8")

        self.assertIn("steps.sanitize.outcome == 'success'", workflow)
        self.assertIn("steps.sanitized-scan.outcome == 'success'", workflow)

    def test_target_requires_full_commit_sha(self) -> None:
        with self.assertRaises(guard.GuardError):
            guard.parse_target_sha("main")

    def test_missing_run_result_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outcome = guard.inspect_run(Path(temporary))

        self.assertEqual(outcome.execution_status, "BLOCKED")
        self.assertNotEqual(outcome.exit_code, 0)

    def test_missing_required_evidence_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            (run_dir / "run.json").write_text(
                json.dumps({"execution_status": "COMPLETE"}), encoding="utf-8"
            )

            outcome = guard.inspect_run(run_dir)

        self.assertEqual(outcome.execution_status, "FAILED")
        self.assertNotEqual(outcome.exit_code, 0)

    def test_missing_evaluation_result_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            (run_dir / "run.json").write_text(
                json.dumps({"execution_status": "COMPLETE"}), encoding="utf-8"
            )
            for relative in guard.REQUIRED_EVIDENCE:
                target = run_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("{}", encoding="utf-8")

            outcome = guard.inspect_run(run_dir)

        self.assertEqual(outcome.execution_status, "FAILED")
        self.assertIn("evaluation result", outcome.message)

    def test_offline_evaluation_never_claims_azure_verified(self) -> None:
        summary = guard.render_summary(
            guard.RunSummary(
                target_commit="a" * 40,
                run_id="fixture",
                environment="azure-e2e",
                execution_status="COMPLETE",
                captured_at="2026-10-16T00:00:00Z",
                evaluated_at="2026-10-16T01:00:00Z",
                mode="offline",
            )
        )

        self.assertNotIn("Azure Verified", summary)
        self.assertIn("Offline replay", summary)

    def test_sanitizer_replaces_identifiers_and_addresses(self) -> None:
        raw = (
            "subscription 12345678-1234-1234-1234-123456789abc "
            "user@microsoft.com 10.4.5.6 20.30.40.50 "
            "https://app-private-name.azurewebsites.net "
            "/subscriptions/12345678-1234-1234-1234-123456789abc/"
            "resourceGroups/private-group/providers/Microsoft.Web/sites/private-app "
            "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.fixture.signature "
            "PASSWORD=super-secret-password "
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        )

        sanitized = guard.sanitize_text(raw)

        self.assertNotIn("12345678-1234-1234-1234-123456789abc", sanitized)
        self.assertNotIn("user@microsoft.com", sanitized)
        self.assertNotIn("10.4.5.6", sanitized)
        self.assertNotIn("20.30.40.50", sanitized)
        self.assertNotIn("app-private-name", sanitized)
        self.assertNotIn("private-group", sanitized)
        self.assertNotIn("private-app", sanitized)
        self.assertNotIn("eyJhbGciOiJSUzI1NiJ9", sanitized)
        self.assertNotIn("super-secret-password", sanitized)
        self.assertNotIn("0123456789abcdef", sanitized)

    def test_sanitizer_rejects_binary_and_secret_named_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "client-secret.json").write_text("{}", encoding="utf-8")

            with self.assertRaises(guard.GuardError):
                guard.sanitize_tree(source, root / "destination")

    def test_sanitized_scan_fails_closed_on_secret_like_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "capture.txt").write_text(
                "Authorization: Bearer token-value", encoding="utf-8"
            )

            with self.assertRaises(guard.GuardError):
                guard.scan_sanitized_tree(root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "capture.bin").write_bytes(b"\x00\x01secret")

            with self.assertRaises(guard.GuardError):
                guard.sanitize_tree(source, root / "destination")


if __name__ == "__main__":
    unittest.main()
