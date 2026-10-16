from __future__ import annotations

from pathlib import Path
import unittest

from ruamel.yaml import YAML


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github/workflows/e2e-azure.yml"


class AzureE2EWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        parser = YAML(typ="base")
        parser.allow_duplicate_keys = False
        self.workflow = parser.load(WORKFLOW_PATH.read_text(encoding="utf-8"))
        self.jobs = self.workflow["jobs"]

    def test_first_job_restricts_ref_and_workflow_ref_to_main(self) -> None:
        first_name, first_job = next(iter(self.jobs.items()))
        self.assertEqual(first_name, "validate-context")
        guard = first_job.get("if", "")
        self.assertIn("github.ref == 'refs/heads/main'", guard)
        self.assertIn("github.workflow_ref", guard)
        self.assertIn("@refs/heads/main", guard)

    def test_every_oidc_job_depends_on_context_validation(self) -> None:
        privileged = {
            name for name, job in self.jobs.items()
            if job.get("permissions", {}).get("id-token") == "write"
        }
        self.assertTrue(privileged)
        for name in privileged:
            needs = self.jobs[name].get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
            self.assertIn("validate-context", needs, msg=name)

    def test_ttl_is_validated_before_any_oidc_job(self) -> None:
        validate_steps = self.jobs["validate-context"]["steps"]
        commands = "\n".join(step.get("run", "") for step in validate_steps)
        self.assertIn("validate-ttl", commands)
        self.assertIn("inputs.ttl_hours", str(self.jobs["validate-context"]))

    def test_resource_group_name_is_derived_from_run_identity(self) -> None:
        self.assertNotIn("resource_group", self.workflow["on"]["workflow_dispatch"]["inputs"])
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("rg-golden-e2e-${{ github.run_id }}-${{ github.run_attempt }}", workflow_text)

    def test_cleanup_result_is_sanitized_and_uploaded(self) -> None:
        cleanup_text = str(self.jobs["cleanup"])
        self.assertIn("cleanup-result.json", cleanup_text)
        self.assertIn("scan-sanitized", cleanup_text)
        self.assertIn("actions/upload-artifact", cleanup_text)
        self.assertIn("GITHUB_STEP_SUMMARY", cleanup_text)


if __name__ == "__main__":
    unittest.main()
