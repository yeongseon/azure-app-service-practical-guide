from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/golden"))
SPEC = importlib.util.spec_from_file_location(
    "azure_e2e_guard", ROOT / "scripts/golden/azure_e2e_guard.py"
)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class AzureE2EGuardTests(unittest.TestCase):
    def _complete_run(self, root: Path, evaluation: dict[str, str] | None = None) -> Path:
        run_dir = root / "20261016T075147Z-fixture"
        run_dir.mkdir()
        artifacts: dict[str, dict[str, int | str]] = {}
        for relative in guard.REQUIRED_EVIDENCE:
            target = run_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}", encoding="utf-8")
            artifacts[relative] = {"size": 2, "sha256": hashlib.sha256(b"{}").hexdigest()}
        (run_dir / "run.json").write_text(
            json.dumps({
                "run_id": run_dir.name,
                "execution_status": "COMPLETE",
                "started_at": "2026-10-16T00:00:00Z",
                "ended_at": "2026-10-16T00:10:00Z",
                "artifacts": artifacts,
            }),
            encoding="utf-8",
        )
        if evaluation is not None:
            (run_dir / "evaluation-fixture.json").write_text(json.dumps(evaluation), encoding="utf-8")
        return run_dir

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

    def test_empty_evaluation_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._complete_run(Path(temporary), {})
            outcome = guard.inspect_run(run_dir)
        self.assertEqual(outcome.execution_status, "FAILED")

    def test_failed_evidence_verdict_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._complete_run(Path(temporary), {
                "run_id": "20261016T075147Z-fixture",
                "evaluated_at": "2026-10-16T00:11:00Z",
                "evidence_validation": "FAIL",
                "hypothesis_evaluation": "SUPPORTED",
            })
            outcome = guard.inspect_run(run_dir)
        self.assertEqual(outcome.execution_status, "FAILED")

    def test_unknown_evaluation_values_are_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._complete_run(Path(temporary), {
                "run_id": "20261016T075147Z-fixture",
                "evaluated_at": "2026-10-16T00:11:00Z",
                "evidence_validation": "MAYBE",
                "hypothesis_evaluation": "PROBABLY",
            })
            outcome = guard.inspect_run(run_dir)
        self.assertEqual(outcome.execution_status, "FAILED")

    def test_evaluation_run_id_must_bind_to_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._complete_run(Path(temporary), {
                "run_id": "different-run",
                "evaluated_at": "2026-10-16T00:11:00Z",
                "evidence_validation": "PASS",
                "hypothesis_evaluation": "SUPPORTED",
            })
            outcome = guard.inspect_run(run_dir)
        self.assertEqual(outcome.execution_status, "FAILED")

    def test_required_evidence_digest_must_bind_to_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._complete_run(Path(temporary), {
                "run_id": "20261016T075147Z-fixture",
                "evaluated_at": "2026-10-16T00:11:00Z",
                "evidence_validation": "PASS",
                "hypothesis_evaluation": "SUPPORTED",
            })
            (run_dir / "console.json").write_text("tampered", encoding="utf-8")
            outcome = guard.inspect_run(run_dir)
        self.assertEqual(outcome.execution_status, "FAILED")

    def test_evaluation_time_must_follow_capture_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._complete_run(Path(temporary), {
                "run_id": "20261016T075147Z-fixture",
                "evaluated_at": "2026-10-15T23:59:00Z",
                "evidence_validation": "PASS",
                "hypothesis_evaluation": "SUPPORTED",
            })
            outcome = guard.inspect_run(run_dir)
        self.assertEqual(outcome.execution_status, "FAILED")

    def test_offline_evaluation_never_claims_azure_verified(self) -> None:
        summary = guard.render_summary(
            guard.RunSummary(
                target_commit="a" * 40,
                run_id="fixture",
                github_run_id="12345",
                github_run_attempt="1",
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

    def test_hostile_secrets_are_sanitized_end_to_end(self) -> None:
        hostile_values = (
            "https://example.invalid/blob?sv=2024-11-04&se=2026-10-17&sig=abc%2Bdef%3D",
            "DefaultEndpointsProtocol=https;AccountName=private;AccountKey=base64secret==;EndpointSuffix=core.windows.net",
            "AccountKey=base64secret==",
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signature",
            "jwt=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.c2lnbmF0dXJl",
            "PASSWORD=super-secret-password",
            "client_secret: confidential-value",
            '{"password":"hunter2"}',
            '"client_secret": "json-confidential-value"',
            "AZURE_CLIENT_SECRET=raw-azure-secret",
            "ARM_CLIENT_SECRET='raw-arm-secret'",
            'export AZURE_CLIENT_SECRET="quoted-azure-secret"',
            '"ARM_CLIENT_SECRET"="quoted-prefixed-secret"',
            'DB_PASSWORD="very secret password with spaces"',
            "{'client_secret': 'secret value;with=punctuation'}",
            "ipv6=2603:1030:20e:3::23 link_local=fe80::1",
            '"session": "QWxhZGRpbjpvcGVuIHNlc2FtZTEyMzQ1Njc4OTA="',
        )
        for index, hostile in enumerate(hostile_values):
            with self.subTest(hostile=hostile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "source"
                source.mkdir()
                (source / f"capture-{index}.txt").write_text(hostile, encoding="utf-8")
                destination = root / "sanitized"
                guard.sanitize_tree(source, destination)
                guard.scan_sanitized_tree(destination)
                self.assertNotIn("super-secret", (destination / f"capture-{index}.txt").read_text())

    def test_sanitizer_preserves_timestamps_and_is_idempotent(self) -> None:
        raw = (
            "at 12:34:56 ipv6 2603:1030:20e:3::23 resource "
            "/subscriptions/12345678-1234-1234-1234-123456789abc/"
            "resourceGroups/private/providers/Microsoft.Web/sites/private-app"
        )

        sanitized = guard.sanitize_text(raw)

        self.assertIn("12:34:56", sanitized)
        self.assertIn("2001:db8::1", sanitized)
        self.assertIn(guard.RESOURCE_ID_PLACEHOLDER, sanitized)
        self.assertEqual(guard.sanitize_text(sanitized), sanitized)

    def test_canonical_resource_placeholder_passes_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "capture.txt").write_text(guard.RESOURCE_ID_PLACEHOLDER, encoding="utf-8")

            guard.scan_sanitized_tree(root)

    def test_scan_rejects_each_non_placeholder_sensitive_value(self) -> None:
        hostile_values = (
            "12345678-1234-1234-1234-123456789abc",
            "employee@microsoft.com",
            "20.30.40.50",
            "/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/private/providers/Microsoft.Web/sites/app",
            "sig=abc%2Bdef%3D",
            "DefaultEndpointsProtocol=https;AccountKey=base64secret==",
            "2603:1030:20e:3::23",
            "fe80::1",
            '{"password":"hunter2"}',
            '"client_secret": "json-confidential-value"',
            "AZURE_CLIENT_SECRET=raw-azure-secret",
            "ARM_CLIENT_SECRET='raw-arm-secret'",
            'export AZURE_CLIENT_SECRET="quoted-azure-secret"',
            '"ARM_CLIENT_SECRET"="quoted-prefixed-secret"',
            'DB_PASSWORD="very secret password with spaces"',
            "{'client_secret': 'secret value;with=punctuation'}",
        )
        for hostile in hostile_values:
            with self.subTest(hostile=hostile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "capture.txt").write_text(hostile, encoding="utf-8")
                with self.assertRaises(guard.GuardError):
                    guard.scan_sanitized_tree(root)

    def test_required_target_paths_reject_historical_commit_missing_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repository, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
            (repository / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=repository, check=True)
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True
            ).stdout.strip()

            with self.assertRaises(guard.GuardError):
                guard.require_target_paths(repository, sha)

    def test_utc_z_timestamps_remain_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = self._complete_run(Path(temporary), {
                "run_id": "20261016T075147Z-fixture",
                "evaluated_at": "2026-10-16T00:11:00Z",
                "evidence_validation": "PASS",
                "hypothesis_evaluation": "SUPPORTED",
            })

            outcome = guard.inspect_run(run_dir)

        self.assertEqual(outcome.execution_status, "COMPLETE")

    def test_success_summary_includes_github_run_identity(self) -> None:
        summary = guard.render_summary(guard.RunSummary(
            target_commit="a" * 40,
            run_id="evidence-run",
            github_run_id="12345",
            github_run_attempt="2",
            environment="azure-e2e",
            execution_status="COMPLETE",
            captured_at="2026-10-16T00:00:00Z",
            evaluated_at="2026-10-16T01:00:00Z",
            mode="azure",
        ))
        self.assertIn("GitHub run ID: `12345` attempt `2`", summary)


if __name__ == "__main__":
    unittest.main()
