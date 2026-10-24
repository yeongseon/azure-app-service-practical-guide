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
    def _target_repository(self, root: Path, hostile_path: str, hostile_kind: str) -> tuple[Path, str]:
        repository = root / "repository"
        repository.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
        for relative in guard.REQUIRED_TARGET_PATHS:
            target = repository / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative == hostile_path and hostile_kind == "directory":
                target.mkdir()
                (target / "nested.py").write_text("fixture\n", encoding="utf-8")
            elif relative == hostile_path and hostile_kind == "symlink":
                target.symlink_to("/tmp/not-a-helper")
            elif relative == hostile_path and hostile_kind == "gitlink":
                target.write_text("fixture\n", encoding="utf-8")
            else:
                target.write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        if hostile_kind == "gitlink":
            subprocess.run(
                ["git", "update-index", "--add", "--cacheinfo", "160000," + "a" * 40 + "," + hostile_path],
                cwd=repository,
                check=True,
            )
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=repository, check=True)
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True
        ).stdout.strip()
        return repository, sha

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

    def test_required_target_paths_reject_directory_instead_of_helper_blob(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hostile_path = guard.REQUIRED_TARGET_PATHS[0]
            repository, sha = self._target_repository(Path(temporary), hostile_path, "directory")

            with self.assertRaises(guard.GuardError):
                guard.require_target_paths(repository, sha)

    def test_required_target_paths_reject_symlink_instead_of_helper_blob(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hostile_path = guard.REQUIRED_TARGET_PATHS[0]
            repository, sha = self._target_repository(Path(temporary), hostile_path, "symlink")

            with self.assertRaises(guard.GuardError):
                guard.require_target_paths(repository, sha)

    def test_required_target_paths_reject_gitlink_instead_of_helper_blob(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hostile_path = guard.REQUIRED_TARGET_PATHS[0]
            repository, sha = self._target_repository(Path(temporary), hostile_path, "gitlink")

            with self.assertRaises(guard.GuardError):
                guard.require_target_paths(repository, sha)

    def test_required_target_paths_accept_regular_and_executable_blobs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, _ = self._target_repository(Path(temporary), "", "")
            executable = repository / guard.REQUIRED_TARGET_PATHS[0]
            executable.chmod(0o755)
            subprocess.run(["git", "add", str(executable)], cwd=repository, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "executable fixture"], cwd=repository, check=True)
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True
            ).stdout.strip()

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
