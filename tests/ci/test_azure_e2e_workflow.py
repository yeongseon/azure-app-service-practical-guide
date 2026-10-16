from __future__ import annotations

from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
