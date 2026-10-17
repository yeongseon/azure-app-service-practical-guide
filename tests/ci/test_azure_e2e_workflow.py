from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github/workflows/e2e-azure.yml"


class AzureE2EWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    def _job(self, name: str) -> str:
        marker = f"  {name}:\n"
        start = self.workflow_text.index(marker) + len(marker)
        lines = self.workflow_text[start:].splitlines(keepends=True)
        body: list[str] = []
        for line in lines:
            if line.startswith("  ") and not line.startswith("    "):
                break
            body.append(line)
        return "".join(body)

    def _step(self, job_name: str, step_name: str) -> str:
        job = self._job(job_name)
        marker = f"      - name: {step_name}\n"
        start = job.index(marker) + len(marker)
        return job[start:].split("      - name:", maxsplit=1)[0]

    def test_first_job_restricts_ref_and_workflow_ref_to_main(self) -> None:
        jobs = self.workflow_text.split("jobs:\n", maxsplit=1)[1]
        self.assertTrue(jobs.startswith("  validate-context:\n"))
        context = self._job("validate-context")
        self.assertIn("github.ref == 'refs/heads/main'", context)
        self.assertIn("github.workflow_ref", context)
        self.assertIn("@refs/heads/main", context)

    def test_every_oidc_job_depends_on_context_validation(self) -> None:
        privileged = {name for name in ("scenario-a", "cleanup", "ttl-sweep") if "id-token: write" in self._job(name)}
        self.assertTrue(privileged)
        for name in privileged:
            self.assertIn("validate-context", self._job(name), msg=name)

    def test_ttl_is_validated_before_any_oidc_job(self) -> None:
        context = self._job("validate-context")
        self.assertIn("validate-ttl", context)
        self.assertIn("inputs.ttl_hours", context)

    def test_resource_group_name_is_derived_from_run_identity(self) -> None:
        inputs = self.workflow_text.split("    inputs:\n", maxsplit=1)[1].split("\npermissions:", maxsplit=1)[0]
        self.assertNotIn("resource_group:", inputs)
        self.assertIn("rg-golden-e2e-${{ github.run_id }}-${{ github.run_attempt }}", self.workflow_text)

    def test_cleanup_result_is_sanitized_and_uploaded(self) -> None:
        cleanup_text = self._job("cleanup")
        self.assertIn("cleanup-result.json", cleanup_text)
        self.assertIn("scan-sanitized", cleanup_text)
        self.assertIn("actions/upload-artifact", cleanup_text)
        self.assertIn("GITHUB_STEP_SUMMARY", cleanup_text)
        self.assertIn("id: cleanup-sanitize", cleanup_text)
        self.assertIn("id: cleanup-scan", cleanup_text)
        self.assertIn("steps.cleanup-sanitize.outcome == 'success'", cleanup_text)
        self.assertIn("steps.cleanup-scan.outcome == 'success'", cleanup_text)
        self.assertIn("Require sanitized cleanup artifact", cleanup_text)

        upload = self._step("cleanup", "Upload sanitized cleanup result")
        self.assertIn(
            "if: always() && steps.cleanup-sanitize.outcome == 'success' && steps.cleanup-scan.outcome == 'success'",
            upload,
        )
        fallback = self._step("cleanup", "Require sanitized cleanup artifact")
        self.assertIn(
            "if: always() && (steps.cleanup-sanitize.outcome != 'success' || steps.cleanup-scan.outcome != 'success')",
            fallback,
        )

    def test_target_validation_requires_helpers_before_oidc_jobs(self) -> None:
        target = self._job("validate-target")
        for required in (
            "scripts/golden/azure_cleanup.py",
            "scripts/golden/azure_e2e_cli.py",
            "scripts/golden/azure_e2e_guard.py",
            "scripts/golden/azure_e2e_sanitize.py",
            "labs/deployment-succeeded-startup-failed/run.py",
        ):
            self.assertIn(required, target)
        self.assertIn("require-target-paths", target)

    def test_ttl_sweep_fails_closed_and_excludes_all_in_progress_runs(self) -> None:
        sweep = self._job("ttl-sweep")
        self.assertIn("actions: read", sweep)
        self.assertIn("gh api", sweep)
        self.assertIn("status=in_progress", sweep)
        self.assertIn("--active-run-ids-file", sweep)
        self.assertIn("set -euo pipefail", sweep)

        command = self._step("ttl-sweep", "Delete only owner-tagged groups with expired TTL")
        self.assertIn("status=in_progress", command)
        self.assertIn("status=queued", command)
        self.assertIn('test -s "$active_runs"', command)


if __name__ == "__main__":
    unittest.main()
